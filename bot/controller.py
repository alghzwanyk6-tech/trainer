"""Closed-loop mouse control for the vision bot.

The bot never "knows" where the cursor is: after every move it asks Windows for
the real cursor position and aims from there. That feedback loop is what makes
the controller self-correcting when the OS clamps a coordinate, when another
process nudges the mouse, or when the window has moved since the last frame.

One :meth:`BotController.step` call is one control tick:

    1. read the real cursor position                    (closed loop input)
    2. smooth the detected target centre                (noise rejection)
    3. decide: click / hold / step towards the target   (policy)
    4. move the real cursor                             (act)
    5. read the real cursor position again              (closed loop output)

The module is deliberately free of pygame, OpenCV and screen-capture calls: it
consumes a :class:`~bot.vision.Detection` plus a
:class:`~bot.capture.ScreenRegion` and talks to the OS only through three
injectable functions (``mouse_position``, ``mouse_move``, ``mouse_click``), so
the whole policy can be unit-tested headlessly with a fake cursor.

Typical usage from the bot loop::

    controller = BotController(cfg)
    result = controller.step(detection, region)
    if result.clicked:
        game.register_click(result.cursor_after)
"""

from __future__ import annotations

import ctypes
import math
import time
from dataclasses import dataclass
from enum import Enum
from random import Random
from typing import Any, Callable, Final

try:
    import vgamepad as vg
except ImportError:
    vg = None  # type: ignore[assignment]

import config
from bot.capture import ScreenRegion
from bot.gamepad import (
    XINPUT_GAMEPAD_A,
    XINPUT_GAMEPAD_B,
    XINPUT_GAMEPAD_BACK,
    XINPUT_GAMEPAD_DPAD_DOWN,
    XINPUT_GAMEPAD_DPAD_LEFT,
    XINPUT_GAMEPAD_DPAD_RIGHT,
    XINPUT_GAMEPAD_DPAD_UP,
    XINPUT_GAMEPAD_LEFT_SHOULDER,
    XINPUT_GAMEPAD_LEFT_THUMB,
    XINPUT_GAMEPAD_RIGHT_SHOULDER,
    XINPUT_GAMEPAD_RIGHT_THUMB,
    XINPUT_GAMEPAD_START,
    XINPUT_GAMEPAD_X,
    XINPUT_GAMEPAD_Y,
)
from bot.vision import Detection

__all__ = [
    "BotController",
    "ControllerError",
    "CursorFns",
    "StepResult",
    "StepStatus",
    "send_mouse_relative",
]

Position = tuple[int, int]
"""A whole-pixel screen coordinate."""

PositionFn = Callable[[], Position]
"""Returns the real cursor position in screen pixels."""

MoveFn = Callable[[int, int], None]
"""Moves the real cursor to a screen coordinate."""

ClickFn = Callable[[int, int], None]
"""Clicks the left mouse button at a screen coordinate."""

ClockFn = Callable[[], float]
"""Monotonic clock used for the click cooldown."""

MIN_GAIN: Final[float] = 0.01
"""Smallest aim gain, so a near-zero slider value still makes progress."""

MAX_GAIN: Final[float] = 1.0
"""Largest aim gain: never travel past the target in one step."""


class ControllerError(RuntimeError):
    """Raised when the operating system refuses a cursor operation.

    The bot loop catches this, disables itself and shows the message, so a
    locked desktop or a fail-safe hit never crashes the game.
    """


class StepStatus(str, Enum):
    """Outcome of a single control tick.

    Attributes:
        NO_TARGET: Nothing was detected; the smoothing filter was reset.
        MOVING: The cursor was moved towards the target.
        COOLDOWN: The cursor is on target but the click cooldown is running.
        CLICKED: The cursor is on target and a click was sent.
    """

    NO_TARGET = "no_target"
    MOVING = "moving"
    COOLDOWN = "cooldown"
    CLICKED = "clicked"


@dataclass(frozen=True, slots=True)
class StepResult:
    """Everything the UI and the diagnostics need about one control tick.

    Distances are measured from the cursor to the *smoothed* target centre in
    screen pixels. ``cursor_after`` is the position Windows reported after the
    move, not the position that was requested, which is what makes the loop
    closed.

    Attributes:
        status: What the controller decided to do.
        detection: The detection that was consumed, if any.
        target: Smoothed target centre in screen coordinates (floats), or
            ``None`` when nothing was detected.
        cursor_before: Cursor position read before any action.
        cursor_after: Cursor position read after the action.
        distance_before: Distance from ``cursor_before`` to ``target``.
        distance_after: Distance from ``cursor_after`` to ``target``.
        moved: ``True`` when a move request was sent to the OS.
        clicked: ``True`` when a click request was sent to the OS.
        elapsed_ms: Wall time spent inside the whole ``step`` call.
    """

    status: StepStatus
    detection: Detection | None
    target: tuple[float, float] | None
    cursor_before: Position
    cursor_after: Position
    distance_before: float
    distance_after: float
    moved: bool
    clicked: bool
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class CursorFns:
    """The three OS operations the controller needs, bundled for injection.

    Attributes:
        position: Reads the real cursor position.
        move: Moves the real cursor to a coordinate.
        click: Clicks the left button at a coordinate.
    """

    position: PositionFn
    move: MoveFn
    click: ClickFn


# ---------------------------------------------------------------------------
# OS adapters (SendInput fallback with MOUSEEVENTF_MOVE)
# ---------------------------------------------------------------------------

MOUSEEVENTF_MOVE: Final[int] = 0x0001
MOUSEEVENTF_LEFTDOWN: Final[int] = 0x0002
MOUSEEVENTF_LEFTUP: Final[int] = 0x0004


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT),
    ]


def read_cursor_position() -> Position:
    """Return the real cursor position in physical screen pixels."""
    pt = POINT()
    try:
        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                return int(pt.x), int(pt.y)
    except Exception as exc:
        raise ControllerError(f"cannot read the cursor position: {exc}") from exc
    return 0, 0


def send_mouse_relative(dx: int, dy: int) -> None:
    """Send relative mouse displacement via Windows SendInput with MOUSEEVENTF_MOVE."""
    try:
        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
            extra = ctypes.c_ulong(0)
            inp = INPUT()
            inp.type = 0  # INPUT_MOUSE
            inp.mi = MOUSEINPUT(int(dx), int(dy), 0, MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    except Exception as exc:
        raise ControllerError(f"SendInput MOUSEEVENTF_MOVE failed ({dx}, {dy}): {exc}") from exc


def move_cursor(x: int, y: int) -> None:
    """Move cursor using SendInput with MOUSEEVENTF_MOVE."""
    try:
        cur_x, cur_y = read_cursor_position()
        dx = int(x - cur_x)
        dy = int(y - cur_y)
        if dx != 0 or dy != 0:
            send_mouse_relative(dx, dy)
    except Exception as exc:
        raise ControllerError(f"cannot move the cursor to ({x}, {y}): {exc}") from exc


def click_cursor(x: int, y: int) -> None:
    """Click the left mouse button once using SendInput."""
    try:
        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
            extra = ctypes.c_ulong(0)
            down = INPUT()
            down.type = 0
            down.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
            ctypes.windll.user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))

            up = INPUT()
            up.type = 0
            up.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
            ctypes.windll.user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
    except Exception as exc:
        raise ControllerError(f"cannot click at ({x}, {y}): {exc}") from exc


def default_cursor_fns() -> CursorFns:
    """Return the real SendInput-backed cursor operations."""
    return CursorFns(
        position=read_cursor_position,
        move=move_cursor,
        click=click_cursor,
    )


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class BotController:
    """Turns detections into smooth, human-looking cursor movement and clicks.

    The controller reads its tunables from the shared :class:`config.Config`
    on every tick, so moving a slider takes effect on the next frame without
    any reconfiguration call. It owns no thread: drive it from exactly one
    thread (the main loop or a single bot worker) to keep the filter and the
    cooldown consistent.

    Attributes:
        config: The live configuration object owned by the control panel.
        move_count: Number of move requests sent since the last reset.
        click_count: Number of click requests sent since the last reset.
    """

    def __init__(
        self,
        cfg: config.Config,
        *,
        cursor: CursorFns | None = None,
        clock: ClockFn = time.perf_counter,
        rng: Random | None = None,
        jump_reset_px: float = config.JUMP_RESET_PX,
        vpad: Any = None,
    ) -> None:
        """Create the controller.

        Args:
            cfg: Live configuration shared with the control panel.
            cursor: OS operations to use; defaults to SendInput. Inject a fake
                bundle (or pass ``CursorFns`` with stub callables) in tests.
            clock: Monotonic clock used for the click cooldown.
            rng: Random source for humanisation; seed it in tests.
            vpad: Optional virtual controller instance.
        """
        self.config = cfg
        fns = cursor or default_cursor_fns()
        self._position = fns.position
        self._move = fns.move
        self._click = fns.click
        self._clock = clock
        self._rng = rng if rng is not None else Random()
        self._jump_reset_px = max(0.0, float(jump_reset_px))

        # Virtual Gamepad (vgamepad)
        if vpad is not None:
            self.vpad = vpad
        elif vg is not None:
            try:
                self.vpad = vg.VDS4Gamepad()
            except Exception:
                self.vpad = None
        else:
            self.vpad = None

        self._current_stick_x: float = 0.0
        self._current_stick_y: float = 0.0
        self._last_deflection_x: float = 0.0
        self._last_deflection_y: float = 0.0

        self._smoothed: tuple[float, float] | None = None
        self._last_click_at = float("-inf")
        self.move_count = 0
        self.click_count = 0

    # -- virtual joystick --------------------------------------------------

    def apply_stick_deflection(
        self,
        dx: float,
        dy: float,
        sens: float = 1.25,
        smoothing: float = 0.35,
        power_exponent: float | None = None,
        reversal_damping: float | None = None,
        is_firing: bool = False,
        recoil_v: float = 0.0,
        recoil_h: float = 0.0,
        user_stick: tuple[float, float] = (0.0, 0.0),
    ) -> tuple[float, float]:
        """Convert delta offsets into normalized right-stick coordinates and deflect stick.

        - Converts (dx, dy) into normalized right-stick float coordinates [-1.0, 1.0].
        - Applies a deadzone cutoff (abs(val) < 3px returns 0).
        - Injects Dual-Axis anti-recoil pull-down when is_firing is True.
        - Applies non-linear power curve: Sign(delta) * (|delta| / FOV)^gamma * sens.
        - Applies directional reversal damping to eliminate aim overshoot oscillations.
        - Applies exponential smoothing (LERP) to prevent abrupt jitter.
        - Blends with user physical right-stick input (user_stick).
        - Updates right stick via self.vpad.right_joystick_float(x_value_float=rx, y_value_float=ry)
          followed by self.vpad.update().

        Returns:
            (rx, ry) tuple of applied normalized stick values.
        """
        # Deadzone cutoff: abs(val) < 3px returns 0
        val_x = 0.0 if abs(dx) < 3.0 else float(dx)
        val_y = 0.0 if abs(dy) < 3.0 else float(dy)

        # Apply Dual-Axis Anti-Recoil compensation when weapon is firing
        if is_firing:
            effective_recoil_v = recoil_v if recoil_v != 0.0 else float(getattr(self.config, "recoil_vertical_px", 0.0))
            effective_recoil_h = recoil_h if recoil_h != 0.0 else float(getattr(self.config, "recoil_horizontal_px", 0.0))
            val_y += effective_recoil_v
            val_x += effective_recoil_h

        # Convert delta offsets (dx, dy) into normalized coordinates [-1.0, 1.0]
        fov = float(getattr(self.config, "fov_radius_px", 250.0))
        scale = max(50.0, fov)

        # Non-linear Power Curve: Deflection = Sign(Delta) * (|Delta| / FOV)^gamma * Sens
        gamma = (
            float(power_exponent)
            if power_exponent is not None
            else float(getattr(self.config, "power_exponent", 1.40))
        )
        damp = (
            float(reversal_damping)
            if reversal_damping is not None
            else float(getattr(self.config, "reversal_damping", 0.40))
        )

        norm_x = min(1.0, abs(val_x) / scale)
        norm_y = min(1.0, abs(val_y) / scale)

        min_breakaway = float(getattr(self.config, "stick_min_breakaway", 0.0))
        if min_breakaway > 0.0:
            if val_x != 0.0:
                mag_x = math.pow(norm_x, gamma) * float(sens)
                mag_x = min_breakaway + (1.0 - min_breakaway) * min(1.0, mag_x)
                curved_x = math.copysign(mag_x, val_x)
            else:
                curved_x = 0.0

            if val_y != 0.0:
                mag_y = math.pow(norm_y, gamma) * float(sens)
                mag_y = min_breakaway + (1.0 - min_breakaway) * min(1.0, mag_y)
                curved_y = math.copysign(mag_y, val_y)
            else:
                curved_y = 0.0
        else:
            curved_x = (math.copysign(math.pow(norm_x, gamma), val_x) * float(sens)) if val_x != 0.0 else 0.0
            curved_y = (math.copysign(math.pow(norm_y, gamma), val_y) * float(sens)) if val_y != 0.0 else 0.0

        # Directional Reversal Damping: suppress overshoot oscillations when direction flips
        if self._last_deflection_x * curved_x < 0.0:
            curved_x *= damp
        if self._last_deflection_y * curved_y < 0.0:
            curved_y *= damp

        self._last_deflection_x = curved_x
        self._last_deflection_y = curved_y

        target_rx = max(-1.0, min(1.0, curved_x))
        target_ry = max(-1.0, min(1.0, curved_y))

        # Exponential smoothing (LERP) to prevent abrupt jitter
        alpha = 1.0 - min(max(float(smoothing), 0.0), 0.99)
        self._current_stick_x += (target_rx - self._current_stick_x) * alpha
        self._current_stick_y += (target_ry - self._current_stick_y) * alpha

        rx = max(-1.0, min(1.0, self._current_stick_x))
        ry = max(-1.0, min(1.0, self._current_stick_y))

        # Deadzone snap when target is 0
        if target_rx == 0.0 and abs(rx) < 0.01:
            rx = 0.0
            self._current_stick_x = 0.0
        if target_ry == 0.0 and abs(ry) < 0.01:
            ry = 0.0
            self._current_stick_y = 0.0

        # Blend user physical stick input with bot deflection
        final_rx = max(-1.0, min(1.0, user_stick[0] + rx))
        final_ry = max(-1.0, min(1.0, user_stick[1] + ry))

        if self.vpad is not None:
            try:
                self.vpad.right_joystick_float(x_value_float=final_rx, y_value_float=final_ry)
                self.vpad.update()
            except Exception as exc:
                raise ControllerError(f"Virtual gamepad update error: {exc}") from exc

        self.move_count += 1
        return final_rx, final_ry

    def reset_stick(self) -> None:
        """Centers right stick axes to (0.0, 0.0) and calls self.vpad.update()."""
        self._current_stick_x = 0.0
        self._current_stick_y = 0.0
        if self.vpad is not None:
            try:
                self.vpad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
                self.vpad.update()
            except Exception:
                pass

    def pass_through_gamepad(
        self,
        gp_state: Any,
        aim_rx: float = 0.0,
        aim_ry: float = 0.0,
        triggerbot_active: bool = False,
    ) -> tuple[float, float]:
        """Pass through physical controller inputs to the virtual gamepad with blended aim deflection.

        Args:
            gp_state: GamepadState from GamepadManager.poll().
            aim_rx: Aim-assist horizontal deflection offset [-1.0, 1.0].
            aim_ry: Aim-assist vertical deflection offset [-1.0, 1.0].
            triggerbot_active: Whether automated triggerbot should fire right trigger.

        Returns:
            (final_rx, final_ry): Effective right stick deflection applied to virtual gamepad.
        """
        if self.vpad is None or not getattr(gp_state, "connected", False):
            return 0.0, 0.0

        try:
            # 1. Left Stick (movement)
            lx, ly = getattr(gp_state, "left_stick", (0.0, 0.0))
            if hasattr(self.vpad, "left_joystick_float"):
                self.vpad.left_joystick_float(x_value_float=float(lx), y_value_float=float(ly))

            # 2. Right Stick (blended aim: user stick + bot deflection)
            user_rx, user_ry = getattr(gp_state, "right_stick", (0.0, 0.0))
            final_rx = max(-1.0, min(1.0, float(user_rx) + float(aim_rx)))
            final_ry = max(-1.0, min(1.0, float(user_ry) + float(aim_ry)))
            if hasattr(self.vpad, "right_joystick_float"):
                self.vpad.right_joystick_float(x_value_float=final_rx, y_value_float=final_ry)

            # 3. Triggers & Triggerbot
            lt = float(getattr(gp_state, "left_trigger", 0.0))
            rt = float(getattr(gp_state, "right_trigger", 0.0))
            buttons = int(getattr(gp_state, "buttons", 0))

            fire_btn = str(getattr(self.config, "fire_trigger", "R2")).strip().upper()
            if triggerbot_active:
                if fire_btn in ("R1", "RB"):
                    buttons |= XINPUT_GAMEPAD_RIGHT_SHOULDER
                elif fire_btn in ("L1", "LB"):
                    buttons |= XINPUT_GAMEPAD_LEFT_SHOULDER
                elif fire_btn in ("R3",):
                    buttons |= XINPUT_GAMEPAD_RIGHT_THUMB
                elif fire_btn in ("CROSS", "A"):
                    buttons |= XINPUT_GAMEPAD_A
                else:
                    rt = max(rt, 1.0)

            if hasattr(self.vpad, "left_trigger_float"):
                self.vpad.left_trigger_float(value_float=lt)
            if hasattr(self.vpad, "right_trigger_float"):
                self.vpad.right_trigger_float(value_float=rt)

            # 4. Buttons
            self._sync_vpad_buttons(buttons)

            # 5. Commit state to driver
            if hasattr(self.vpad, "update"):
                self.vpad.update()

            if abs(aim_rx) > 0.0 or abs(aim_ry) > 0.0:
                self.move_count += 1
            return final_rx, final_ry
        except Exception as exc:
            raise ControllerError(f"Gamepad pass-through error: {exc}") from exc

    def _sync_vpad_buttons(self, buttons: int) -> None:
        """Map and dispatch digital buttons to the virtual gamepad."""
        if self.vpad is None or vg is None:
            return

        is_ds4 = isinstance(self.vpad, getattr(vg, "VDS4Gamepad", ())) or hasattr(self.vpad, "directional_pad")
        has_press = hasattr(self.vpad, "press_button") and hasattr(self.vpad, "release_button")

        if is_ds4 and hasattr(vg, "DS4_BUTTONS") and has_press:
            ds4_map = (
                (XINPUT_GAMEPAD_A, vg.DS4_BUTTONS.DS4_BUTTON_CROSS),
                (XINPUT_GAMEPAD_B, vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE),
                (XINPUT_GAMEPAD_X, vg.DS4_BUTTONS.DS4_BUTTON_SQUARE),
                (XINPUT_GAMEPAD_Y, vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE),
                (XINPUT_GAMEPAD_LEFT_SHOULDER, vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT),
                (XINPUT_GAMEPAD_RIGHT_SHOULDER, vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT),
                (XINPUT_GAMEPAD_LEFT_THUMB, vg.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT),
                (XINPUT_GAMEPAD_RIGHT_THUMB, vg.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT),
                (XINPUT_GAMEPAD_START, vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS),
                (XINPUT_GAMEPAD_BACK, vg.DS4_BUTTONS.DS4_BUTTON_SHARE),
            )
            for mask, btn in ds4_map:
                if buttons & mask:
                    self.vpad.press_button(btn)
                else:
                    self.vpad.release_button(btn)

            if hasattr(self.vpad, "directional_pad") and hasattr(vg, "DS4_DPAD_DIRECTIONS"):
                up = bool(buttons & XINPUT_GAMEPAD_DPAD_UP)
                down = bool(buttons & XINPUT_GAMEPAD_DPAD_DOWN)
                left = bool(buttons & XINPUT_GAMEPAD_DPAD_LEFT)
                right = bool(buttons & XINPUT_GAMEPAD_DPAD_RIGHT)

                if up and right:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST
                elif up and left:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST
                elif down and right:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST
                elif down and left:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST
                elif up:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH
                elif down:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH
                elif left:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST
                elif right:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST
                else:
                    dpad_dir = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE

                self.vpad.directional_pad(dpad_dir)
        elif hasattr(vg, "XUSB_BUTTON") and has_press:
            x360_map = (
                (XINPUT_GAMEPAD_A, vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
                (XINPUT_GAMEPAD_B, vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
                (XINPUT_GAMEPAD_X, vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
                (XINPUT_GAMEPAD_Y, vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
                (XINPUT_GAMEPAD_LEFT_SHOULDER, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
                (XINPUT_GAMEPAD_RIGHT_SHOULDER, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
                (XINPUT_GAMEPAD_LEFT_THUMB, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB),
                (XINPUT_GAMEPAD_RIGHT_THUMB, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),
                (XINPUT_GAMEPAD_START, vg.XUSB_BUTTON.XUSB_GAMEPAD_START),
                (XINPUT_GAMEPAD_BACK, vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK),
                (XINPUT_GAMEPAD_DPAD_UP, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP),
                (XINPUT_GAMEPAD_DPAD_DOWN, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN),
                (XINPUT_GAMEPAD_DPAD_LEFT, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT),
                (XINPUT_GAMEPAD_DPAD_RIGHT, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT),
            )
            for mask, btn in x360_map:
                if buttons & mask:
                    self.vpad.press_button(btn)
                else:
                    self.vpad.release_button(btn)

    def apply_mouse_move(self, dx: int, dy: int) -> None:
        """Fallback mode using ctypes SendInput with MOUSEEVENTF_MOVE."""
        send_mouse_relative(dx, dy)
        self.move_count += 1

    # -- state -------------------------------------------------------------

    def reset(self) -> None:
        """Forget the smoothing filter, the cooldown, stick deflection, and counters.

        Call this when the bot is switched off or when a new session starts, so
        a stale target centre never drags the cursor on the first tick.
        """
        self._smoothed = None
        self._last_click_at = float("-inf")
        self.move_count = 0
        self.click_count = 0
        self._last_deflection_x = 0.0
        self._last_deflection_y = 0.0
        self.reset_stick()

    @property
    def smoothed_target(self) -> tuple[float, float] | None:
        """Current filtered target centre in screen pixels, if any."""
        return self._smoothed

    @property
    def seconds_since_click(self) -> float:
        """Seconds since the last click, or infinity when none was sent."""
        if self._last_click_at == float("-inf"):
            return math.inf
        return self._clock() - self._last_click_at

    # -- policy ------------------------------------------------------------

    def _smooth_target(
        self,
        raw_x: float,
        raw_y: float,
        radius: float,
    ) -> tuple[float, float]:
        """Filter the detected centre to reject per-frame jitter.

        Two guards keep the filter honest:

        * A jump larger than :data:`config.JUMP_RESET_PX` is treated as a new
          target and snaps the filter, so the cursor does not glide across the
          play area after a respawn.
        * A movement smaller than the deadzone is ignored entirely, so pixel
          noise cannot make the cursor tremble. The applied deadzone is capped
          at a quarter of the detected radius, which guarantees the filtered
          centre always stays inside the click band even for the smallest
          target the panel allows.

        Args:
            raw_x: Detected centre X in screen pixels.
            raw_y: Detected centre Y in screen pixels.
            radius: Detected target radius in pixels.

        Returns:
            The filtered centre in screen pixels.
        """
        previous = self._smoothed
        if previous is None:
            self._smoothed = (raw_x, raw_y)
            return self._smoothed

        gap = math.hypot(raw_x - previous[0], raw_y - previous[1])
        if gap > self._jump_reset_px:
            self._smoothed = (raw_x, raw_y)
            return self._smoothed

        deadzone = min(
            max(float(self.config.deadzone_px), 0.0),
            max(0.0, radius * config.DEADZONE_RADIUS_RATIO),
        )
        if gap <= deadzone:
            return previous

        factor = min(max(float(self.config.smoothing), 0.0), 1.0)
        self._smoothed = (
            previous[0] + (raw_x - previous[0]) * factor,
            previous[1] + (raw_y - previous[1]) * factor,
        )
        return self._smoothed

    def _next_point(
        self,
        cursor: Position,
        target: tuple[float, float],
    ) -> Position:
        """Compute the next cursor position for one tick.

        The step covers :attr:`config.Config.aim_speed` of the remaining
        distance, capped at :data:`config.MAX_STEP_PX` so a huge detection jump
        cannot teleport the cursor. Humanisation perturbs both the gain and the
        destination by a small bounded amount.

        Args:
            cursor: Current real cursor position.
            target: Smoothed target centre in screen pixels.

        Returns:
            The requested cursor position, always at least one pixel away from
            ``cursor`` when the target is further than that.
        """
        cfg = self.config
        dx = target[0] - cursor[0]
        dy = target[1] - cursor[1]

        gain = min(max(float(cfg.aim_speed), MIN_GAIN), MAX_GAIN)
        offset_x = 0.0
        offset_y = 0.0
        if cfg.humanize:
            gain *= 1.0 + self._rng.uniform(-config.HUMANIZE_WOBBLE, config.HUMANIZE_WOBBLE)
            gain = min(max(gain, MIN_GAIN), MAX_GAIN)
            offset_x = self._rng.uniform(-1.0, 1.0) * config.HUMANIZE_JITTER_PX
            offset_y = self._rng.uniform(-1.0, 1.0) * config.HUMANIZE_JITTER_PX

        step_x = dx * gain + offset_x
        step_y = dy * gain + offset_y
        length = math.hypot(step_x, step_y)
        if length > config.MAX_STEP_PX:
            scale = config.MAX_STEP_PX / length
            step_x *= scale
            step_y *= scale

        next_x = int(round(cursor[0] + step_x))
        next_y = int(round(cursor[1] + step_y))
        if (next_x, next_y) == cursor:
            # Sub-pixel gain or jitter cancelled the step; nudge one pixel
            # along the dominant axis so progress never stalls.
            if abs(dx) >= abs(dy):
                next_x += 1 if dx > 0 else -1
            else:
                next_y += 1 if dy > 0 else -1

        # Rounding to whole pixels can push the step a fraction past the cap;
        # walk it back so the documented limit holds exactly.
        while math.hypot(next_x - cursor[0], next_y - cursor[1]) > config.MAX_STEP_PX:
            step_dx = next_x - cursor[0]
            step_dy = next_y - cursor[1]
            if abs(step_dx) >= abs(step_dy) and step_dx != 0:
                next_x += -1 if step_dx > 0 else 1
            elif step_dy != 0:
                next_y += -1 if step_dy > 0 else 1
            else:  # pragma: no cover - only reachable if the cap were 0
                break
        return next_x, next_y

    # -- loop --------------------------------------------------------------

    def step(
        self,
        detection: Detection | None,
        region: ScreenRegion,
    ) -> StepResult:
        """Run one closed-loop control tick.

        Args:
            detection: Target detected in the current frame (play-area pixel
                coordinates), or ``None`` when the frame had no target.
            region: Screen region the frame was captured from; used to map
                play-area pixels onto the physical desktop.

        Returns:
            A :class:`StepResult` describing the decision and the measured
            cursor positions.

        Raises:
            ControllerError: If the OS refuses to read, move or click.
        """
        started = self._clock()
        cfg = self.config

        if detection is None:
            self._smoothed = None
            cursor = self._read_position()
            return StepResult(
                status=StepStatus.NO_TARGET,
                detection=None,
                target=None,
                cursor_before=cursor,
                cursor_after=cursor,
                distance_before=0.0,
                distance_after=0.0,
                moved=False,
                clicked=False,
                elapsed_ms=(self._clock() - started) * 1000.0,
            )

        cursor = self._read_position()
        raw_x, raw_y = region.to_screen(detection.x, detection.y)
        target = self._smooth_target(raw_x, raw_y, detection.radius)
        dx = target[0] - cursor[0]
        dy = target[1] - cursor[1]
        distance = math.hypot(dx, dy)

        click_radius = max(1.0, detection.radius * config.CLICK_INSIDE_RATIO)

        moved = False
        clicked = False
        if distance <= click_radius:
            if started - self._last_click_at >= cfg.click_cooldown_s:
                self._send_click(*cursor)
                self._last_click_at = started
                self.click_count += 1
                clicked = True
                status = StepStatus.CLICKED
            else:
                status = StepStatus.COOLDOWN
        else:
            destination = self._next_point(cursor, target)
            self._send_move(*destination)
            self.move_count += 1
            moved = True
            status = StepStatus.MOVING

        after = self._read_position()
        return StepResult(
            status=status,
            detection=detection,
            target=target,
            cursor_before=cursor,
            cursor_after=after,
            distance_before=distance,
            distance_after=math.hypot(target[0] - after[0], target[1] - after[1]),
            moved=moved,
            clicked=clicked,
            elapsed_ms=(self._clock() - started) * 1000.0,
        )

    def _read_position(self) -> Position:
        """Read the cursor position, translating OS failures.

        Returns:
            ``(x, y)`` in screen pixels.

        Raises:
            ControllerError: If the position cannot be read.
        """
        try:
            x, y = self._position()
        except ControllerError:
            raise
        except Exception as exc:
            raise ControllerError(f"cannot read the cursor position: {exc}") from exc
        return int(x), int(y)

    def _send_move(self, x: int, y: int) -> None:
        """Move the cursor, translating OS failures.

        Args:
            x: Destination screen X in pixels.
            y: Destination screen Y in pixels.

        Raises:
            ControllerError: If the OS refuses the movement.
        """
        try:
            self._move(x, y)
        except ControllerError:
            raise
        except Exception as exc:
            raise ControllerError(f"cannot move the cursor to ({x}, {y}): {exc}") from exc

    def _send_click(self, x: int, y: int) -> None:
        """Click the left button, translating OS failures.

        Args:
            x: Screen X in pixels.
            y: Screen Y in pixels.

        Raises:
            ControllerError: If the OS refuses the click.
        """
        try:
            self._click(x, y)
        except ControllerError:
            raise
        except Exception as exc:
            raise ControllerError(f"cannot click at ({x}, {y}): {exc}") from exc
