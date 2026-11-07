"""Fast screen capture of the play area for the vision bot.

The bot is only ever allowed to see the left-hand play area of its own window —
never the control panel and never another application. This module turns the
window's client rectangle into a screen-space :class:`ScreenRegion` and grabs
that region with ``mss``, returning a BGR ``numpy`` array that OpenCV can use
directly.

Only this module (and ``bot/controller.py``) talks to the operating system.
``main.py`` passes the window handle that pygame reports; everything else works
with the returned frames.

Typical usage::

    enable_dpi_awareness()                      # call BEFORE pygame.init()
    handle = pygame.display.get_wm_info()["window"]
    region = play_area_region(handle)
    with ScreenCapture(region) as capture:
        frame = capture.grab()
        frame.image.shape                       # (820, 1000, 3), BGR
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from dataclasses import dataclass
from typing import Final

import numpy as np

try:  # ``mss`` is a hard dependency, but a clear error beats an import crash.
    import mss
except ImportError:  # pragma: no cover - exercised only in broken installs
    mss = None  # type: ignore[assignment]

try:
    import dxcam
except ImportError:
    dxcam = None  # type: ignore[assignment]

import config

__all__ = [
    "CaptureError",
    "DXGIScreenCapture",
    "Frame",
    "MJPEGStreamCapture",
    "ScreenCapture",
    "ScreenRegion",
    "capture_frame",
    "client_origin",
    "enable_dpi_awareness",
    "find_window_info",
    "find_window_region",
    "play_area_region",
    "screen_fov_region",
    "virtual_screen_rect",
]

# ---------------------------------------------------------------------------
# DPI awareness
# ---------------------------------------------------------------------------

_dpi_aware: bool | None = None
"""Cached result of :func:`enable_dpi_awareness` so it only runs once."""

_DPI_PER_MONITOR_V2: Final[int] = -4
"""``DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2`` (Windows 10 1703+)."""


def _query_dpi_awareness() -> int | None:
    """Return the process DPI-awareness level on Windows, or ``None``.

    Returns:
        ``0`` unaware, ``1`` system aware, ``2`` per-monitor aware, or ``None``
        when the query is unavailable (non-Windows host).
    """
    if sys.platform != "win32":
        return None
    try:
        level = ctypes.c_int(0)
        result = ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(level))
        return int(level.value) if result == 0 else None
    except (AttributeError, OSError, ValueError):
        return None


def enable_dpi_awareness() -> bool:
    """Opt the current process into per-monitor DPI awareness (best effort).

    Screen coordinates reported by WinAPI and by ``mss`` are only guaranteed to
    match pygame's logical coordinates when the process is DPI aware. Call this
    once, **before** ``pygame.init()``.

    The function tries the modern API first and falls back to older ones, so it
    works on Windows 7 through 11. It is idempotent and never raises.

    Returns:
        ``True`` when the process is DPI aware after the call, ``False`` when
        the host cannot be configured (non-Windows or locked-down process).
    """
    global _dpi_aware
    if _dpi_aware is not None:
        return _dpi_aware

    if sys.platform != "win32":
        _dpi_aware = False
        return _dpi_aware

    attempts = (
        lambda: ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(_DPI_PER_MONITOR_V2)
        ),
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0,
        lambda: bool(ctypes.windll.user32.SetProcessDPIAware()),
    )
    for attempt in attempts:
        try:
            if attempt():
                _dpi_aware = True
                return _dpi_aware
        except (AttributeError, OSError, ValueError):
            continue

    # A host that already set awareness earlier (SDL does) reports failure for
    # every call; trust the actual process state in that case.
    level = _query_dpi_awareness()
    _dpi_aware = level is not None and level > 0
    return _dpi_aware


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScreenRegion:
    """A rectangle in physical screen pixels.

    Attributes:
        left: Left edge in virtual-screen coordinates.
        top: Top edge in virtual-screen coordinates.
        width: Width in pixels (must be positive).
        height: Height in pixels (must be positive).
    """

    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject degenerate rectangles early.

        Raises:
            ValueError: If ``width`` or ``height`` is not positive.
        """
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"region must have a positive size, got {self.width}x{self.height}"
            )

    @property
    def right(self) -> int:
        """X coordinate just past the right edge."""
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """Y coordinate just past the bottom edge."""
        return self.top + self.height

    @property
    def center(self) -> tuple[float, float]:
        """Centre of the region in screen coordinates."""
        return self.left + self.width / 2.0, self.top + self.height / 2.0

    def to_mss(self) -> dict[str, int]:
        """Return the mapping ``mss.grab`` expects for this region."""
        return {
            "left": int(self.left),
            "top": int(self.top),
            "width": int(self.width),
            "height": int(self.height),
        }

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        """Translate local ``(x, y)`` pixels into screen coordinates.

        Args:
            x: Horizontal offset inside the region.
            y: Vertical offset inside the region.

        Returns:
            The matching point on the physical screen.
        """
        return self.left + x, self.top + y

    def contains(self, x: float, y: float) -> bool:
        """Return ``True`` when the screen point lies inside the region."""
        return self.left <= x < self.right and self.top <= y < self.bottom


@dataclass(frozen=True, slots=True)
class Frame:
    """One captured picture of the play area.

    Attributes:
        image: BGR ``uint8`` array of shape ``(height, width, 3)``.
        region: Screen region the picture was taken from.
        captured_at: ``time.perf_counter()`` value taken right after capture.
    """

    image: np.ndarray
    region: ScreenRegion
    captured_at: float

    def __post_init__(self) -> None:
        """Validate the array shape.

        Raises:
            ValueError: If the image is not an ``H x W x 3`` BGR array.
        """
        if self.image.ndim != 3 or self.image.shape[2] != 3:
            raise ValueError(
                f"frame image must be HxWx3 BGR, got shape {self.image.shape}"
            )

    @property
    def width(self) -> int:
        """Frame width in pixels."""
        return int(self.image.shape[1])

    @property
    def height(self) -> int:
        """Frame height in pixels."""
        return int(self.image.shape[0])


def client_origin(window_handle: int) -> tuple[int, int] | None:
    """Return the screen position of a window's client area.

    Args:
        window_handle: Native window handle (HWND) as reported by pygame in
            ``pygame.display.get_wm_info()["window"]``.

    Returns:
        ``(x, y)`` of the client area's top-left corner in physical screen
        pixels, or ``None`` when the handle is invalid or the host is not
        Windows.
    """
    if sys.platform != "win32" or not window_handle:
        return None
    try:
        import ctypes.wintypes as wintypes

        user32 = ctypes.windll.user32
        client = wintypes.RECT()
        if not user32.GetClientRect(ctypes.c_void_p(int(window_handle)), ctypes.byref(client)):
            return None
        if client.right <= 0 or client.bottom <= 0:
            return None
        point = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(ctypes.c_void_p(int(window_handle)), ctypes.byref(point)):
            return None
        return int(point.x), int(point.y)
    except (AttributeError, OSError, ValueError, TypeError):
        return None


def play_area_region(
    window_handle: int,
    width: int = config.GAME_ZONE_WIDTH,
    height: int = config.WINDOW_HEIGHT,
) -> ScreenRegion | None:
    """Resolve the screen region occupied by the play area.

    The play area is the left ``width`` pixels of the window's client area, so
    the region starts at the client origin and never includes the panel.

    Args:
        window_handle: Native window handle (HWND) of the pygame window.
        width: Play-area width in pixels.
        height: Play-area height in pixels.

    Returns:
        A :class:`ScreenRegion`, or ``None`` when the window geometry cannot be
        resolved (minimised, invalid handle, non-Windows host).
    """
    origin = client_origin(window_handle)
    if origin is None:
        return None
    return ScreenRegion(origin[0], origin[1], int(width), int(height))


def screen_fov_region(
    width: int = 600,
    height: int = 600,
    around_cursor: bool = False,
) -> ScreenRegion:
    """Return a ScreenRegion centered on the primary display or around the cursor.

    Args:
        width: FOV width in pixels.
        height: FOV height in pixels.
        around_cursor: If True, centers the FOV box around the current mouse cursor.

    Returns:
        A :class:`ScreenRegion` bounding the requested screen area.
    """
    if sys.platform == "win32":
        try:
            metrics = ctypes.windll.user32.GetSystemMetrics
            sw = int(metrics(0))  # SM_CXSCREEN
            sh = int(metrics(1))  # SM_CYSCREEN
            if sw > 0 and sh > 0:
                w = min(sw, max(50, int(width)))
                h = min(sh, max(50, int(height)))

                if around_cursor:
                    import ctypes.wintypes as wintypes
                    pt = wintypes.POINT()
                    if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                        cx, cy = int(pt.x), int(pt.y)
                    else:
                        cx, cy = sw // 2, sh // 2
                else:
                    cx, cy = sw // 2, sh // 2

                left = max(0, min(sw - w, cx - w // 2))
                top = max(0, min(sh - h, cy - h // 2))
                return ScreenRegion(left, top, w, h)
        except Exception:
            pass

    v = virtual_screen_rect()
    if v is not None:
        w = min(v.width, max(50, int(width)))
        h = min(v.height, max(50, int(height)))
        cx = v.left + v.width // 2
        cy = v.top + v.height // 2
        return ScreenRegion(cx - w // 2, cy - h // 2, w, h)

    return ScreenRegion(0, 0, width, height)


def find_window_region(
    title_substring: str | list[str] | tuple[str, ...] = "Remote Play"
) -> ScreenRegion | None:
    """Find the client area of a window whose title matches title_substring.

    Args:
        title_substring: Substring or sequence of substrings to search for (case-insensitive).
            Automatically matches Chiaki variants ('chiaki', 'chiaki-ng').

    Returns:
        ScreenRegion of the window or None if not found.
    """
    res = find_window_info(title_substring)
    return res[1] if res is not None else None


def find_window_info(
    title_substring: str | list[str] | tuple[str, ...] = "Remote Play"
) -> tuple[str, ScreenRegion] | None:
    """Find a window matching title_substring, returning (matched_title, ScreenRegion).

    Args:
        title_substring: Substring or collection of candidate substrings to match.

    Returns:
        Tuple of (matched_window_title, ScreenRegion) or None if no matching window is open.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes.wintypes as wintypes

        user32 = ctypes.windll.user32
        found_hwnd = None
        found_title = ""

        if isinstance(title_substring, (list, tuple)):
            raw_keywords = list(title_substring)
        else:
            raw_keywords = [title_substring]

        keywords: list[str] = []
        for kw in raw_keywords:
            k = kw.strip().lower()
            if k:
                keywords.append(k)
                if "chiaki" in k:
                    keywords.extend(["chiaki-ng", "chiaki"])
                if "remote play" in k or "playstation" in k:
                    keywords.extend(["ps remote play", "remote play", "playstation"])
        keywords = list(dict.fromkeys(keywords))

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_cb(hwnd: int, lparam: int) -> bool:
            nonlocal found_hwnd, found_title
            if user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
                length = user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, length + 1)
                    title = buf.value.strip()
                    title_lower = title.lower()
                    if any(kw in title_lower for kw in keywords):
                        found_hwnd = hwnd
                        found_title = title
                        return False  # stop enumeration
            return True

        cb = WNDENUMPROC(enum_cb)
        user32.EnumWindows(cb, 0)

        if found_hwnd:
            origin = client_origin(found_hwnd)
            client = wintypes.RECT()
            if (
                user32.GetClientRect(ctypes.c_void_p(int(found_hwnd)), ctypes.byref(client))
                and origin
            ):
                w = client.right - client.left
                h = client.bottom - client.top
                if w > 0 and h > 0:
                    return found_title, ScreenRegion(origin[0], origin[1], int(w), int(h))
    except Exception:
        pass
    return None


_SM_XVIRTUALSCREEN: Final[int] = 76
"""``GetSystemMetrics`` index for the virtual desktop's left edge."""

_SM_YVIRTUALSCREEN: Final[int] = 77
"""``GetSystemMetrics`` index for the virtual desktop's top edge."""

_SM_CXVIRTUALSCREEN: Final[int] = 78
"""``GetSystemMetrics`` index for the virtual desktop's width."""

_SM_CYVIRTUALSCREEN: Final[int] = 79
"""``GetSystemMetrics`` index for the virtual desktop's height."""


def virtual_screen_rect() -> ScreenRegion | None:
    """Return the bounding box of every monitor, in virtual-screen pixels.

    The rectangle can start at negative coordinates when a monitor is placed
    left of or above the primary one, which is exactly why the emergency
    corner stop cannot assume the desktop starts at ``(0, 0)``.

    The Windows metric API is tried first because it is a pure, cheap query.
    On other hosts, or when that call is unavailable, the first monitor
    reported by ``mss`` is used instead.

    Returns:
        The union of all monitor rectangles, or ``None`` when the desktop
        geometry cannot be read.
    """
    if sys.platform == "win32":
        try:
            metrics = ctypes.windll.user32.GetSystemMetrics
            left = int(metrics(_SM_XVIRTUALSCREEN))
            top = int(metrics(_SM_YVIRTUALSCREEN))
            width = int(metrics(_SM_CXVIRTUALSCREEN))
            height = int(metrics(_SM_CYVIRTUALSCREEN))
            if width > 0 and height > 0:
                return ScreenRegion(left, top, width, height)
        except (AttributeError, OSError, ValueError, TypeError):
            pass

    if mss is None:  # pragma: no cover - broken install only
        return None
    grabber = None
    try:
        grabber = mss.MSS()
        monitor = grabber.monitors[0]
        width = int(monitor["width"])
        height = int(monitor["height"])
        if width <= 0 or height <= 0:
            return None
        return ScreenRegion(int(monitor["left"]), int(monitor["top"]), width, height)
    except Exception:  # mss raises platform-specific errors
        return None
    finally:
        if grabber is not None:
            try:
                grabber.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


class CaptureError(RuntimeError):
    """Raised when a screenshot cannot be taken.

    The bot catches this, stops itself and reports the message instead of
    crashing the game loop.
    """


class DXGIScreenCapture:
    """Ultra-fast DirectX 11 Desktop Duplication capture backend (up to 240 FPS)."""

    def __init__(self, region: ScreenRegion) -> None:
        self._region = region
        self._camera = None
        self._closed = False
        self._init_camera()

    def _init_camera(self) -> None:
        if dxcam is None:
            raise CaptureError("dxcam is not installed")
        try:
            self._camera = dxcam.create(output_color="BGR")
        except Exception as exc:
            raise CaptureError(f"DXGI Desktop Duplication unavailable: {exc}") from exc

    @property
    def region(self) -> ScreenRegion:
        return self._region

    def set_region(self, region: ScreenRegion) -> None:
        self._region = region

    def grab(self) -> Frame:
        if self._closed or self._camera is None:
            raise CaptureError("DXGI capture is closed or uninitialized")
        try:
            box = (
                int(self._region.left),
                int(self._region.top),
                int(self._region.left + self._region.width),
                int(self._region.top + self._region.height),
            )
            raw = self._camera.grab(region=box)
            if raw is None:
                # dxcam returns None if screen hasn't changed; get latest frame
                raw = getattr(self._camera, "_latest_frame", None)
            if raw is None:
                raise CaptureError("DXGI grab returned empty buffer")
            image = np.ascontiguousarray(raw)
            return Frame(image=image, region=self._region, captured_at=time.perf_counter())
        except Exception as exc:
            raise CaptureError(f"DXGI grab failure: {exc}") from exc

    def close(self) -> None:
        self._closed = True
        if self._camera is not None:
            try:
                del self._camera
            except Exception:
                pass
            self._camera = None


class MJPEGStreamCapture:
    """Non-blocking high-throughput localhost MJPEG stream consumer for console streaming.

    Connects to local streaming daemons:
    - Port 9003 for PlayStation Chiaki-ng
    - Port 5218 for Xbox Greenlight Desktop
    Maintains a dedicated reader thread with minimal internal buffering (CAP_PROP_BUFFERSIZE=1)
    to eliminate frame queue latency, with automatic fallback to DXGI/ScreenCapture.
    """

    def __init__(
        self,
        stream_url: str = "http://127.0.0.1:9003/stream",
        fallback_capture: Any = None,
        region: ScreenRegion | None = None,
    ) -> None:
        self.stream_url = stream_url
        self.fallback = fallback_capture
        self._region = region or (fallback_capture.region if fallback_capture else ScreenRegion(0, 0, 1920, 1080))
        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._connected = False
        self._start_consumer()

    def _start_consumer(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._consumer_loop, daemon=True)
        self._thread.start()

    def _consumer_loop(self) -> None:
        try:
            import cv2
        except ImportError:
            return

        while self._running:
            try:
                cap = cv2.VideoCapture(self.stream_url)
                if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not cap.isOpened():
                    self._connected = False
                    cap.release()
                    time.sleep(1.0)
                    continue

                self._connected = True
                while self._running and cap.isOpened():
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        break
                    with self._lock:
                        self._latest_frame = frame
                cap.release()
                self._connected = False
            except Exception:
                self._connected = False
                time.sleep(1.0)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def region(self) -> ScreenRegion:
        return self._region

    def set_region(self, region: ScreenRegion) -> None:
        self._region = region
        if self.fallback is not None and hasattr(self.fallback, "set_region"):
            self.fallback.set_region(region)

    def grab(self) -> Frame:
        with self._lock:
            frame_img = self._latest_frame

        if self._connected and frame_img is not None:
            h, w = frame_img.shape[:2]
            reg = self._region
            rx = max(0, min(w - 1, int(reg.left)))
            ry = max(0, min(h - 1, int(reg.top)))
            rw = min(w - rx, int(reg.width))
            rh = min(h - ry, int(reg.height))
            if rw > 0 and rh > 0 and (rw != w or rh != h):
                frame_img = frame_img[ry : ry + rh, rx : rx + rw]
            return Frame(image=frame_img, region=self._region, captured_at=time.perf_counter())

        if self.fallback is not None:
            return self.fallback.grab()

        raise CaptureError(f"MJPEG stream disconnected ({self.stream_url}) and no fallback available")

    def close(self) -> None:
        self._running = False
        if self.fallback is not None and hasattr(self.fallback, "close"):
            self.fallback.close()


_GLOBAL_DXGI_FAILED: bool = False


class ScreenCapture:
    """Reusable high-performance screen grabber with DXGI and mss backends.

    Supports ultra-low-latency DirectX 11 Desktop Duplication (120-240 FPS) with
    seamless automatic fallback to ``mss``. The underlying handles are created
    lazily, on the thread that first calls :meth:`grab`.

    Attributes:
        region: Region grabbed by :meth:`grab`; change it with
            :meth:`set_region` when the window moves.
    """

    def __init__(
        self,
        region: ScreenRegion,
        *,
        with_cursor: bool = False,
        backend: str = "auto",
    ) -> None:
        """Create the grabber (no capture happens yet).

        Args:
            region: Screen region to grab.
            with_cursor: Include the mouse cursor in the picture. Off by
                default so the cursor cannot be mistaken for a target.
            backend: Capture backend ("auto", "dxgi", "mss").
        """
        self._region = region
        self._with_cursor = with_cursor
        self._backend = backend
        self._dxgi_capture: DXGIScreenCapture | None = None
        self._dxgi_failed = False
        self._grabber: object | None = None
        self._closed = False

    @property
    def region(self) -> ScreenRegion:
        """Region currently grabbed."""
        return self._region

    def set_region(self, region: ScreenRegion) -> None:
        """Point the grabber at a new region.

        Args:
            region: New screen region (for example after the window moved).
        """
        self._region = region
        if self._dxgi_capture is not None:
            self._dxgi_capture.set_region(region)

    def _ensure_grabber(self) -> object:
        """Create the ``mss`` handle if needed.

        Returns:
            The live ``mss`` handle.

        Raises:
            CaptureError: If ``mss`` is missing, the capture is closed, or the
                handle cannot be created.
        """
        if self._closed:
            raise CaptureError("screen capture has been closed")
        if self._grabber is not None:
            return self._grabber
        if mss is None:  # pragma: no cover - broken install only
            raise CaptureError("mss is not installed: run pip install -r requirements.txt")
        try:
            if sys.platform.startswith("linux"):
                self._grabber = mss.MSS(with_cursor=self._with_cursor)
            else:
                self._grabber = mss.MSS()
        except Exception as exc:  # mss raises platform-specific errors
            raise CaptureError(f"cannot open a screen capture device: {exc}") from exc
        return self._grabber

    def _drop_grabber(self) -> None:
        """Close and forget the mss handle; safe to call repeatedly."""
        grabber, self._grabber = self._grabber, None
        if grabber is not None:
            try:
                grabber.close()  # type: ignore[attr-defined]
            except Exception:
                pass

    def grab(self) -> Frame:
        """Capture one frame of the configured region.

        Returns:
            A :class:`Frame` whose ``image`` is a new, contiguous BGR array.

        Raises:
            CaptureError: If the screen cannot be read (locked session, monitor
                disconnected, invalid region, ...).
        """
        if self._closed:
            raise CaptureError("screen capture has been closed")

        # 1. Attempt ultra-fast DXGI capture if requested
        global _GLOBAL_DXGI_FAILED
        if self._backend in ("auto", "dxgi") and not self._dxgi_failed and not _GLOBAL_DXGI_FAILED:
            if self._dxgi_capture is None:
                try:
                    self._dxgi_capture = DXGIScreenCapture(self._region)
                except Exception:
                    self._dxgi_failed = True
                    _GLOBAL_DXGI_FAILED = True
                    self._dxgi_capture = None
                    if self._backend == "dxgi":
                        raise

            if self._dxgi_capture is not None:
                try:
                    return self._dxgi_capture.grab()
                except Exception:
                    if self._backend == "dxgi":
                        raise
                    self._dxgi_failed = True
                    _GLOBAL_DXGI_FAILED = True
                    self._dxgi_capture = None

        # 2. Standard robust mss capture fallback
        grabber = self._ensure_grabber()
        region = self._region
        try:
            shot = grabber.grab(region.to_mss())  # type: ignore[attr-defined]
            pixels = np.asarray(shot, dtype=np.uint8)
            if pixels.ndim != 3 or pixels.shape[2] < 3:
                raise CaptureError(
                    f"unexpected screenshot shape {pixels.shape}; expected HxWx4 BGRA"
                )
            image = np.ascontiguousarray(pixels[:, :, :3])
        except CaptureError:
            raise
        except Exception as exc:
            self._drop_grabber()
            raise CaptureError(
                f"could not capture {region.width}x{region.height} "
                f"at ({region.left}, {region.top}): {exc}"
            ) from exc

        return Frame(image=image, region=region, captured_at=time.perf_counter())

    def close(self) -> None:
        """Release capture handles."""
        if not self._closed:
            self._closed = True
            if self._dxgi_capture is not None:
                try:
                    self._dxgi_capture.close()
                except Exception:
                    pass
                self._dxgi_capture = None
            self._drop_grabber()

    def __enter__(self) -> "ScreenCapture":
        """Return ``self`` for use in a ``with`` block."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close the grabber when leaving a ``with`` block."""
        self.close()


def capture_frame(region: ScreenRegion, *, with_cursor: bool = False) -> Frame:
    """Take a single frame and release the grabber immediately.

    Convenience wrapper for calibration scripts and tests; the bot loop should
    keep a :class:`ScreenCapture` alive instead so it does not reconnect every
    frame.

    Args:
        region: Screen region to grab.
        with_cursor: Include the mouse cursor in the picture.

    Returns:
        The captured :class:`Frame`.

    Raises:
        CaptureError: If the screen cannot be read.
    """
    with ScreenCapture(region, with_cursor=with_cursor) as capture:
        return capture.grab()
