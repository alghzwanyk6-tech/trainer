"""OpenCV colour detection of the red target inside the captured play area.

The pipeline is deliberately small, fast and explainable:

    BGR frame → HSV → ``inRange`` (hue range around the target colour)
             → morphological open/close → largest circular contour
             → centroid + radius

Everything here is a pure function of its inputs (apart from the detector's
small memo cache and last-frame diagnostics), so the whole vision stage can be
tested with synthetic ``numpy`` pictures and no screen.

Detection stays pluggable: :class:`Detector` is the interface the bot loop
consumes, and :class:`ColorDetector` is today's colour implementation. A YOLO
or ONNX detector can be added later without touching the game or the control
panel.

Typical usage::

    detector = ColorDetector()
    detector.configure(cfg)                  # hue tolerance + debug flag
    detection = detector.detect(frame.image)  # play-area pixel coordinates
    if detection is not None:
        print(detection.x, detection.y, detection.radius)
"""

from __future__ import annotations

import colorsys
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np

import config

__all__ = [
    "ColorDetector",
    "Detection",
    "Detector",
    "HSV",
    "HSVRange",
    "HUD_COLOR_CYAN_HEX",
    "HUD_COLOR_CYAN_RGB",
    "HUD_COLOR_MAGENTA_HEX",
    "HUD_COLOR_MAGENTA_RGB",
    "apply_circular_fov_mask",
    "build_hsv_ranges",
    "build_hud_color_ranges",
    "build_mask",
    "clean_mask",
    "find_largest_blob",
    "get_circular_stencil",
    "mask_to_rgb",
    "rgb_to_hsv",
]

HSV = tuple[int, int, int]
"""An OpenCV 8-bit HSV triple: hue ``0-179``, saturation/value ``0-255``."""

HSVRange = tuple[HSV, HSV]
"""Inclusive ``(lower, upper)`` pair accepted by ``cv2.inRange``."""

HUD_COLOR_CYAN_HEX: Final[str] = "#00F0FF"
HUD_COLOR_MAGENTA_HEX: Final[str] = "#FF00FF"
HUD_COLOR_CYAN_RGB: Final[config.RGB] = (0, 240, 255)
HUD_COLOR_MAGENTA_RGB: Final[config.RGB] = (255, 0, 255)


def build_hud_color_ranges(
    profile: str = "MAGENTA",
    tolerance_h: float = 12.0,
) -> tuple[HSVRange, ...]:
    """Build HSV thresholds for standard competitive HUD color profiles (Cyan #00F0FF or Magenta #FF00FF)."""
    p = profile.strip().upper()
    rgb = HUD_COLOR_CYAN_RGB if "CYAN" in p else HUD_COLOR_MAGENTA_RGB
    return build_hsv_ranges(rgb, tolerance_h)

MAX_BLOB_ASPECT: Final[float] = 2.5
"""Widest bounding-box ratio still accepted as a round target."""


# ---------------------------------------------------------------------------
# Colour maths (pure)
# ---------------------------------------------------------------------------


def rgb_to_hsv(color: config.RGB) -> HSV:
    """Convert an RGB colour to OpenCV's 8-bit HSV scale.

    Args:
        color: ``(r, g, b)`` with channels in ``0-255``.

    Returns:
        ``(hue, saturation, value)`` where hue is ``0-179`` and the other two
        channels are ``0-255``, matching ``cv2.COLOR_BGR2HSV`` output.
    """
    red, green, blue = (channel / 255.0 for channel in color)
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    return (
        int(round(hue * 179.0)),
        int(round(saturation * 255.0)),
        int(round(value * 255.0)),
    )


def build_hsv_ranges(
    color: config.RGB,
    tolerance_h: float,
    min_saturation: int = config.HSV_MIN_SATURATION,
    min_value: int = config.HSV_MIN_VALUE,
) -> tuple[HSVRange, ...]:
    """Build the HSV limits that isolate ``color`` with a hue tolerance.

    Red sits on the wrap-around point of the hue wheel, so a tolerance around
    it usually needs two ranges (``0-10`` and ``170-179``). The helper returns
    one range when no wrap is needed and two when it is.

    Args:
        color: Target RGB colour.
        tolerance_h: Half-width of the hue window, in OpenCV hue units.
        min_saturation: Floor applied to the saturation channel.
        min_value: Floor applied to the value channel.

    Returns:
        One or two inclusive ``(lower, upper)`` HSV ranges.
    """
    hue, saturation, value = rgb_to_hsv(color)
    tolerance = max(0, int(round(tolerance_h)))

    # Never require more saturation/brightness than the colour itself has, so
    # muted target colours still produce a usable range.
    lower_s = max(0, min(int(min_saturation), saturation))
    lower_v = max(0, min(int(min_value), value))
    lower_hue = hue - tolerance
    upper_hue = hue + tolerance

    if lower_hue < 0:
        return (
            ((0, lower_s, lower_v), (upper_hue, 255, 255)),
            ((180 + lower_hue, lower_s, lower_v), (179, 255, 255)),
        )
    if upper_hue > 179:
        return (
            ((lower_hue, lower_s, lower_v), (179, 255, 255)),
            ((0, lower_s, lower_v), (upper_hue - 180, 255, 255)),
        )
    return (((lower_hue, lower_s, lower_v), (upper_hue, 255, 255)),)


def mask_to_rgb(mask: np.ndarray) -> np.ndarray:
    """Convert a single-channel mask into an RGB picture for the debug overlay.

    Args:
        mask: ``uint8`` array of shape ``(height, width)``.

    Returns:
        An RGB ``uint8`` array of shape ``(height, width, 3)``.
    """
    return cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)


# ---------------------------------------------------------------------------
# Masking and blob search
# ---------------------------------------------------------------------------


def build_mask(frame_bgr: np.ndarray, ranges: tuple[HSVRange, ...]) -> np.ndarray:
    """Return the binary mask of every pixel inside one of ``ranges``.

    Args:
        frame_bgr: BGR picture from :class:`~bot.capture.Frame`.
        ranges: HSV ranges from :func:`build_hsv_ranges`.

    Returns:
        A ``uint8`` mask with ``255`` where the target colour matches.

    Raises:
        ValueError: If ``frame_bgr`` is not an ``H x W x 3`` picture.
    """
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        raise ValueError(f"expected an HxWx3 BGR frame, got {frame_bgr.shape}")

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask: np.ndarray | None = None
    for lower, upper in ranges:
        part = cv2.inRange(hsv, np.array(lower, dtype=np.uint8), np.array(upper, dtype=np.uint8))
        mask = part if mask is None else cv2.bitwise_or(mask, part)
    if mask is None:  # pragma: no cover - callers always pass >= 1 range
        raise ValueError("at least one HSV range is required")
    return mask


def clean_mask(mask: np.ndarray, kernel_size: int = config.MASK_KERNEL_SIZE) -> np.ndarray:
    """Remove speckle noise and fill small holes in a mask.

    An opening pass deletes isolated pixels (anti-aliased edges, red text
    fragments) and a closing pass reconnects the target circle.

    Args:
        mask: Single-channel binary mask.
        kernel_size: Side of the square structuring element, in pixels.

    Returns:
        A cleaned mask of the same size.
    """
    size = max(1, int(kernel_size))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=2)


_CIRCULAR_STENCIL_CACHE: dict[tuple[int, int, int, int, int], np.ndarray] = {}


def get_circular_stencil(w: int, h: int, cx: int, cy: int, radius: int) -> np.ndarray:
    """Return a cached binary circular mask with 255 inside the circle and 0 outside.

    Args:
        w: Frame width.
        h: Frame height.
        cx: Center X coordinate.
        cy: Center Y coordinate.
        radius: Circle radius in pixels.

    Returns:
        A uint8 array of shape (h, w) with 255 inside the circle and 0 outside.
    """
    key = (int(w), int(h), int(cx), int(cy), int(radius))
    stencil = _CIRCULAR_STENCIL_CACHE.get(key)
    if stencil is None:
        if len(_CIRCULAR_STENCIL_CACHE) >= 32:
            _CIRCULAR_STENCIL_CACHE.clear()
        stencil = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(stencil, (int(cx), int(cy)), int(radius), 255, -1)
        _CIRCULAR_STENCIL_CACHE[key] = stencil
    return stencil


def apply_circular_fov_mask(
    mask: np.ndarray,
    center: tuple[int, int] | None = None,
    fov_radius: float | None = None,
) -> np.ndarray:
    """Zero out all mask pixels falling outside the FOV targeting circle.

    Guarantees that nothing outside the reticle circle can ever be detected or tracked.

    Args:
        mask: Single-channel uint8 binary mask of shape (h, w).
        center: Optional (cx, cy) center coordinates. Defaults to (w // 2, h // 2).
        fov_radius: Radius of the active FOV circle in pixels.

    Returns:
        The mask with all pixels outside the FOV circle set to 0.
    """
    if fov_radius is None or fov_radius <= 0:
        return mask
    h, w = mask.shape[:2]
    cx = w // 2 if center is None else int(center[0])
    cy = h // 2 if center is None else int(center[1])
    radius = int(fov_radius)
    if radius >= math.hypot(w, h):
        return mask
    stencil = get_circular_stencil(w, h, cx, cy, radius)
    return cv2.bitwise_and(mask, stencil)


@dataclass(frozen=True, slots=True)
class Detection:
    """One detected target, in play-area pixel coordinates.

    Attributes:
        x: Centroid X measured from the left edge of the captured frame.
        y: Centroid Y measured from the top edge of the captured frame.
        radius: Equivalent radius in pixels, derived from the blob area.
        area: Contour area in square pixels.
        bbox: Bounding box ``(x, y, width, height)`` of the blob.
    """

    x: float
    y: float
    radius: float
    area: float
    bbox: tuple[int, int, int, int]

    @property
    def diameter(self) -> float:
        """Diameter of the detected target in pixels."""
        return self.radius * 2.0

    def distance_to(self, x: float, y: float) -> float:
        """Return the distance from the centroid to a point.

        Args:
            x: Point X in play-area pixels.
            y: Point Y in play-area pixels.

        Returns:
            Euclidean distance in pixels.
        """
        return math.hypot(x - self.x, y - self.y)


def find_largest_blob(
    mask: np.ndarray,
    min_area: float,
    max_area: float | None = None,
    center: tuple[float, float] | None = None,
    fov_radius: float | None = None,
) -> Detection | None:
    """Locate the best target blob in a binary mask, rejecting large decoys and out-of-FOV blobs.

    Args:
        mask: Single-channel binary mask.
        min_area: Minimum contour area, in square pixels, below which a blob is
            treated as noise.
        max_area: Optional maximum contour area; blobs larger than this (windows,
            banners, taskbars) are rejected.
        center: Optional ``(cx, cy)`` crosshair coordinate to prioritize closest targets.
        fov_radius: Optional maximum distance from ``center``; blobs outside this
            radius are rejected.

    Returns:
        The winning :class:`Detection`, or ``None`` when nothing qualifies.
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best: Detection | None = None
    best_score = -1.0

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        if max_area is not None and area > max_area:
            continue

        moments = cv2.moments(contour)
        if moments["m00"] <= 0.0:
            continue

        bx, by, bw, bh = cv2.boundingRect(contour)
        long_side, short_side = max(bw, bh), min(bw, bh)
        if short_side <= 0 or long_side / short_side > MAX_BLOB_ASPECT:
            continue

        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]

        if center is not None and fov_radius is not None and fov_radius > 0:
            dist = math.hypot(cx - center[0], cy - center[1])
            if dist > fov_radius:
                continue
            # Score: heavily prioritize proximity to crosshair / reticle center.
            # Close enemy markers must always take priority over distant large background blobs.
            score = 10000.0 / (1.0 + dist) + min(area, 200.0) * 0.1
        else:
            score = area

        if score > best_score:
            best = Detection(
                x=cx,
                y=cy,
                radius=max(1.0, math.sqrt(area / math.pi)),
                area=area,
                bbox=(int(bx), int(by), int(bw), int(bh)),
            )
            best_score = score

    return best


# ---------------------------------------------------------------------------
# Detector interface
# ---------------------------------------------------------------------------


class Detector(ABC):
    """Interface every target detector must implement.

    The bot loop only knows this interface, so swapping the colour detector for
    a learned model later is a one-line change in ``main.py``.
    """

    @abstractmethod
    def detect(self, frame_bgr: np.ndarray) -> Detection | None:
        """Return the target found in ``frame_bgr``, or ``None``.

        Args:
            frame_bgr: BGR picture of the play area.

        Returns:
            The best detection in play-area pixel coordinates.
        """

    def configure(self, cfg: config.Config) -> None:
        """Apply live settings from the control panel.

        Args:
            cfg: Current configuration. The default implementation does
                nothing; detectors that have tunables override it.
        """


class ColorDetector(Detector):
    """Hue-based detector tuned for the solid red training target.

    The minimum blob area adapts to the configured target size: a 20 px target
    is roughly a third of the area of the default 56 px one, so a fixed
    threshold would silently stop detecting the smallest targets.

    Attributes:
        color: RGB colour of the target (defaults to ``config.TARGET_RED``).
        tolerance_h: Current hue tolerance in OpenCV units.
        min_area: Current minimum blob area in square pixels.
        kernel_size: Morphology kernel side in pixels.
        keep_mask: When ``True`` the cleaned mask is retained for the debug
            overlay (``Config.debug_view``).
        last_mask: Mask from the most recent :meth:`detect`, or ``None``.
        last_elapsed_ms: Duration of the most recent :meth:`detect` call.
    """

    def __init__(
        self,
        color: config.RGB = config.TARGET_RED,
        tolerance_h: float | None = None,
        min_area: float = float(config.MIN_BLOB_AREA_PX),
        kernel_size: int = config.MASK_KERNEL_SIZE,
        keep_mask: bool = False,
    ) -> None:
        """Create the detector.

        Args:
            color: RGB target colour.
            tolerance_h: Hue tolerance; defaults to the control's default.
            min_area: Minimum blob area in square pixels.
            kernel_size: Morphology kernel side in pixels.
            keep_mask: Retain the mask after every :meth:`detect` call.
        """
        default_tolerance = float(config.CONTROLS_BY_KEY["color_tolerance_h"].default)
        self.color = color
        self.tolerance_h = default_tolerance if tolerance_h is None else float(tolerance_h)
        self.min_area = max(1.0, float(min_area))
        self.max_area: float | None = 6000.0
        self.fov_radius: float | None = 250.0
        self.kernel_size = max(1, int(kernel_size))
        self.keep_mask = keep_mask
        self.last_mask: np.ndarray | None = None
        self.last_elapsed_ms = 0.0

        self._ranges_cache: tuple[HSVRange, ...] | None = None
        self._ranges_key: tuple[config.RGB, int] | None = None

    # -- configuration -----------------------------------------------------

    def configure(self, cfg: config.Config) -> None:
        """Apply hue tolerance, target size, target colour and the debug flag from ``cfg``."""
        self.tolerance_h = float(cfg.color_tolerance_h)
        self.keep_mask = bool(cfg.debug_view)

        nominal_area = math.pi * cfg.target_radius_px**2
        self.min_area = max(
            float(config.MIN_BLOB_AREA_FLOOR_PX),
            min(float(config.MIN_BLOB_AREA_PX), nominal_area * 0.20),
        )
        self.max_area = float(getattr(cfg, "max_target_area_px", 5000.0))
        self.fov_radius = float(getattr(cfg, "fov_radius_px", 250.0))
        # Live colour update — clears the HSV range cache when changed
        live_color = getattr(cfg, "target_color", None)
        if live_color is not None and live_color != self.color:
            self.color = live_color
            self._ranges_cache = None

    def hsv_ranges(self) -> tuple[HSVRange, ...]:
        """Return the HSV ranges for the current colour and tolerance.

        The result is memoised, so changing the slider recomputes it once.

        Returns:
            One or two HSV ranges ready for :func:`build_mask`.
        """
        key = (self.color, int(round(self.tolerance_h)))
        if self._ranges_cache is None or self._ranges_key != key:
            self._ranges_cache = build_hsv_ranges(self.color, self.tolerance_h)
            self._ranges_key = key
        return self._ranges_cache

    # -- detection ---------------------------------------------------------

    def detect(self, frame_bgr: np.ndarray) -> Detection | None:
        """Detect the red target in one play-area frame.

        Args:
            frame_bgr: BGR picture from :class:`~bot.capture.Frame`.

        Returns:
            The largest qualifying blob, or ``None`` when the target is hidden.

        Raises:
            ValueError: If ``frame_bgr`` is not an ``H x W x 3`` picture.
        """
        started = time.perf_counter()
        raw_mask = build_mask(frame_bgr, self.hsv_ranges())
        h, w = frame_bgr.shape[:2]
        center = (w / 2.0, h / 2.0)
        if self.fov_radius is not None and self.fov_radius > 0:
            raw_mask = apply_circular_fov_mask(raw_mask, (int(center[0]), int(center[1])), self.fov_radius)
        mask = clean_mask(raw_mask, self.kernel_size)
        detection = find_largest_blob(
            mask,
            self.min_area,
            max_area=self.max_area,
            center=center,
            fov_radius=self.fov_radius,
        )
        self.last_mask = mask if self.keep_mask else None
        self.last_elapsed_ms = (time.perf_counter() - started) * 1000.0
        return detection

    @property
    def mask_rgb(self) -> np.ndarray | None:
        """Return the last mask as an RGB picture for the debug overlay."""
        return None if self.last_mask is None else mask_to_rgb(self.last_mask)
