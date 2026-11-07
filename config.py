"""Central configuration for the Aim Trainer & Vision Bot.

This module is the single source of truth for every constant, layout value,
colour, tuning default and slider range used by the project. Nothing here
imports pygame, OpenCV or any other runtime dependency: it must stay pure so
that the game loop, the vision pipeline and the unit tests can all import it
without a display or a GUI context.

Modules are expected to import this file as ``config``::

    import config
    config.WINDOW_WIDTH            # 1400
    cfg = config.Config()          # defaults used by the sliders

Typical usage for the UI layer::

    for spec in config.CONTROLS:
        value = getattr(cfg, spec.key)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent
"""Absolute path of the project root (the folder containing ``config.py``)."""

DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
"""Directory for runtime artefacts (session logs, screenshots, exports)."""

SESSIONS_DIR: Final[Path] = DATA_DIR / "sessions"
"""Per-session JSON/CSV records written by ``core.game.GameSession``."""

USER_CONFIG_PATH: Final[Path] = PROJECT_ROOT / "user_config.json"
"""Where the user's slider choices are persisted between runs."""

# ---------------------------------------------------------------------------
# Window and layout
# ---------------------------------------------------------------------------

WINDOW_WIDTH: Final[int] = 1400
WINDOW_HEIGHT: Final[int] = 820
WINDOW_TITLE: Final[str] = "Aim Trainer & Vision Bot"
TARGET_FPS: Final[int] = 60
"""Target frame rate of the pygame main loop."""

GAME_ZONE_WIDTH: Final[int] = 1000
"""Width of the play area on the left of the window."""

PANEL_WIDTH: Final[int] = WINDOW_WIDTH - GAME_ZONE_WIDTH
"""Width of the control panel on the right of the window."""

GAME_ZONE_BOUNDS: Final[tuple[int, int, int, int]] = (
    0,
    0,
    GAME_ZONE_WIDTH,
    WINDOW_HEIGHT,
)
"""``(x, y, width, height)`` of the play area inside the window."""

PANEL_BOUNDS: Final[tuple[int, int, int, int]] = (
    GAME_ZONE_WIDTH,
    0,
    PANEL_WIDTH,
    WINDOW_HEIGHT,
)
"""``(x, y, width, height)`` of the control panel inside the window."""

PANEL_PADDING: Final[int] = 18
"""Inner padding used by ``core.ui`` when laying out the panel."""

CONTROL_ROW_HEIGHT: Final[int] = 54
"""Vertical space reserved for one slider/toggle row."""

# ---------------------------------------------------------------------------
# Colours (RGB, pygame-friendly)
# ---------------------------------------------------------------------------

RGB = tuple[int, int, int]

BACKGROUND: Final[RGB] = (16, 18, 24)
GAME_BACKGROUND: Final[RGB] = (22, 25, 33)
PANEL_BACKGROUND: Final[RGB] = (28, 32, 42)
PANEL_SECTION: Final[RGB] = (36, 41, 54)
TEXT_PRIMARY: Final[RGB] = (236, 239, 246)
TEXT_MUTED: Final[RGB] = (148, 158, 178)
ACCENT: Final[RGB] = (86, 156, 255)
ACCENT_ACTIVE: Final[RGB] = (120, 200, 140)
DANGER: Final[RGB] = (255, 92, 92)
TARGET_RED: Final[RGB] = (255, 45, 45)
CROSSHAIR: Final[RGB] = (240, 244, 255)
DEBUG_OUTLINE: Final[RGB] = (0, 255, 180)
"""Colour used for the debug overlay geometry."""

# ---------------------------------------------------------------------------
# Game defaults
# ---------------------------------------------------------------------------

TARGET_MARGIN_PX: Final[int] = 40
"""Minimum distance between a target edge and the play-area border."""

MIN_TARGET_DISTANCE_PX: Final[float] = 150.0
"""Minimum distance between two consecutive target centres."""

HIT_PADDING_PX: Final[float] = 0.0
"""Extra tolerance added to the target radius when judging a hit."""

COUNTDOWN_SECONDS: Final[float] = 3.0
"""Grace period shown before the session timer starts."""

HUD_HEIGHT: Final[int] = 56
"""Height of the heads-up strip drawn across the top of the play area."""

HUD_GAP_PX: Final[int] = 12
"""Clearance kept between the HUD strip and the top of a target."""

# ---------------------------------------------------------------------------
# Bot defaults (non-slider tunables)
# ---------------------------------------------------------------------------

MAX_STEP_PX: Final[float] = 120.0
"""Maximum cursor travel per bot loop iteration, in screen pixels."""

MIN_BLOB_AREA_PX: Final[int] = 300
"""Blobs smaller than this are treated as noise and ignored."""

JUMP_RESET_PX: Final[float] = 250.0
"""A large centroid jump that resets tracking in the desktop app."""

TRAINER_JUMP_RESET_PX: Final[float] = 120.0
"""Respawn threshold for the built-in trainer's targets."""

BOT_TARGET_HZ: Final[int] = 60
"""Target frequency of the capture → detect → act loop."""

HSV_MIN_SATURATION: Final[int] = 45
"""Lower saturation bound (0-255) shared by every generated HSV range.

Allows detecting washed-out/desaturated markers over Remote Play streams."""

HSV_MIN_VALUE: Final[int] = 60
"""Lower value bound (0-255) shared by every generated red HSV range.

Excluding near-black pixels prevents shadows from matching the target hue.
"""

MASK_KERNEL_SIZE: Final[int] = 3
"""Side length of the square kernel used to open/close the mask, in pixels."""

MIN_BLOB_AREA_FLOOR_PX: Final[int] = 8
"""Hard floor for the blob-area filter so tiny targets are still detected."""

HUMANIZE_JITTER_PX: Final[float] = 1.5
"""Random offset applied to the click position when Humanize is on."""

HUMANIZE_WOBBLE: Final[float] = 0.15
"""Per-iteration random variation applied to the aim gain."""

CLICK_INSIDE_RATIO: Final[float] = 0.75
"""Fraction of the detected radius the cursor must reach before clicking.

Clicking at 75% of the radius leaves a safety margin for detection error and
for the OS rounding the cursor to whole pixels, so the game's own hit test
(``distance <= radius``) still succeeds.
"""

DEADZONE_RADIUS_RATIO: Final[float] = 0.25
"""Upper bound on the deadzone, as a fraction of the detected radius.

The deadzone rejects detector jitter; capping it at a quarter of the radius
means it can never hide a real target from the click band, even for the
smallest 20 px target the panel allows.
"""

BOT_CORNER_STOP_PX: Final[int] = 4
"""Distance from a virtual-screen corner that counts as the emergency stop.

pyautogui's own fail-safe is disabled so the bot can start and run on any
screen; the bot loop reproduces the gesture itself: if the cursor sits within
this many pixels of a screen corner, the bot stops gracefully. The bot never
aims at a corner, so a corner position can only come from the user.
"""

BOT_MAX_CAPTURE_FAILURES: Final[int] = 60
"""Consecutive capture errors tolerated before the bot stops itself (1 second at 60 Hz)."""

BOT_PATH_POINTS: Final[int] = 32
"""Number of recent cursor positions kept for the debug trail."""

BOT_PREVIEW_SIZE: Final[tuple[int, int]] = (150, 104)
"""Size of the downscaled mask preview published to the debug overlay."""

TOAST_SECONDS: Final[float] = 4.0
"""How long a bot status/error message stays on screen."""

# ---------------------------------------------------------------------------
# Controller Remapping & Tactical Shooter Presets
# ---------------------------------------------------------------------------

INPUT_MODE: Final[str] = "vgamepad"
AIM_TRIGGER: Final[str] = "LT"
FIRE_TRIGGER: Final[str] = "RT"
STICK_SENSITIVITY: Final[float] = 1.25
STICK_SMOOTHING: Final[float] = 0.35
VERTICAL_OFFSET: Final[int] = 15

CONTROLLER_BINDINGS: Final[dict[str, Any]] = {
    "INPUT_MODE": "vgamepad",     # Options: ["vgamepad", "sendinput", "overlay_only"]
    "AIM_TRIGGER": "LT",          # Options: ["LT", "LB", "RMB", "Always"]
    "FIRE_TRIGGER": "RT",         # Options: ["RT", "RB", "LMB"]
    "TACTICAL_JUMP": "L2",        # Map jump to L2/LT for bumper jumper tactical
    "SLIDE_CANCEL_PRONE": "R3",   # Right stick click or customizable paddle
    "MELEE_ACTION": "R2",
    "STICK_SENSITIVITY": 1.25,
    "STICK_SMOOTHING": 0.35,
    "VERTICAL_OFFSET": 15,
    "DEADZONE_PX": 3.0,
}

INTENSITY_PROFILES: Final[dict[str, dict[str, Any]]] = {
    "SOFT": {
        "aim_speed": 0.20,
        "smoothing": 0.70,
        "fov_radius_px": 160.0,
        "label": "SOFT",
        "description": "Stealth / Natural human smoothing",
    },
    "NORMAL": {
        "aim_speed": 0.35,
        "smoothing": 0.50,
        "fov_radius_px": 220.0,
        "label": "NORMAL",
        "description": "Tactical shooter balanced tracking",
    },
    "MEDIUM": {
        "aim_speed": 0.55,
        "smoothing": 0.35,
        "fov_radius_px": 300.0,
        "label": "MEDIUM",
        "description": "Fast acquisition & target switching",
    },
    "SUPER": {
        "aim_speed": 0.85,
        "smoothing": 0.15,
        "fov_radius_px": 450.0,
        "label": "SUPER",
        "description": "Instant snap lock & max response",
    },
}

TARGET_PRIORITIES: Final[tuple[str, ...]] = ("MARKER", "HEAD", "RANDOM", "CHEST")

GAME_PRESETS: Final[dict[str, dict[str, Any]]] = {
    "COD_BO6_PS5": {
        "name": "Call of Duty: BO6 / BO7 (PS5 Remote Play)",
        "target_priority": "MARKER",
        "power_exponent": 1.10,
        "reversal_damping": 0.30,
        "aim_speed": 0.65,
        "smoothing": 0.25,
        "stick_sens": 2.10,
        "stick_sensitivity": 2.10,
        "stick_smooth": 0.18,
        "stick_smoothing": 0.18,
        "recoil_v": 10.0,
        "recoil_vertical_px": 10.0,
        "recoil_h": 0.0,
        "recoil_horizontal_px": 0.0,
        "target_color": (255, 0, 255),  # Magenta / Color Filter 2
        "vertical_offset": 12,
        "bindings": {
            "AIM_TRIGGER": "L2",
            "FIRE_TRIGGER": "R2",
            "TACTICAL_JUMP": "L1",
            "SLIDE_CANCEL_PRONE": "R3",
            "MELEE_ACTION": "R1",
        },
    },
    "WARZONE_TACTICAL": {
        "name": "Warzone / MW3 Long Range",
        "target_priority": "HEAD",
        "power_exponent": 1.15,
        "reversal_damping": 0.35,
        "aim_speed": 0.50,
        "smoothing": 0.35,
        "stick_sens": 1.75,
        "stick_sensitivity": 1.75,
        "stick_smooth": 0.22,
        "stick_smoothing": 0.22,
        "recoil_v": 13.0,
        "recoil_vertical_px": 13.0,
        "recoil_h": 0.0,
        "recoil_horizontal_px": 0.0,
        "target_color": (255, 0, 255),
        "vertical_offset": 15,
        "bindings": {
            "AIM_TRIGGER": "L2",
            "FIRE_TRIGGER": "R2",
            "TACTICAL_JUMP": "L1",
            "SLIDE_CANCEL_PRONE": "R3",
            "MELEE_ACTION": "R1",
        },
    },
    "FLICK_BEAST": {
        "name": "Flick Beast / Instant Snap Lock",
        "target_priority": "HEAD",
        "power_exponent": 1.05,
        "reversal_damping": 0.20,
        "aim_speed": 0.85,
        "smoothing": 0.12,
        "stick_sens": 2.60,
        "stick_sensitivity": 2.60,
        "stick_smooth": 0.10,
        "stick_smoothing": 0.10,
        "recoil_v": 8.0,
        "recoil_vertical_px": 8.0,
        "recoil_h": 0.0,
        "recoil_horizontal_px": 0.0,
        "target_color": (255, 45, 45),
        "vertical_offset": 10,
        "bindings": {
            "AIM_TRIGGER": "L2",
            "FIRE_TRIGGER": "R2",
            "TACTICAL_JUMP": "L1",
            "SLIDE_CANCEL_PRONE": "R3",
            "MELEE_ACTION": "R1",
        },
    },
}

DEFAULT_POWER_EXPONENT: Final[float] = 1.40
"""Exponent gamma for non-linear thumbstick power curve. 1.0 is linear, 1.4-1.8 gives micro-precision near center and aggressive snap on edges."""

DEFAULT_REVERSAL_DAMPING: Final[float] = 0.40
"""Damping factor (0.0 - 1.0) applied to stick deflection when reversing direction to prevent overshoot oscillation."""

STATIC_PROP_MIN_FRAMES: Final[int] = 15
"""Number of consecutive frames a detected target must stay motionless before being classified as a static prop/corpse."""

STATIC_PROP_MAX_EMA: Final[float] = 0.50
"""Maximum motion EMA (pixels per frame) below which an object is considered stationary."""

# ---------------------------------------------------------------------------
# Controls (the control panel is generated from this table)
# ---------------------------------------------------------------------------

ControlKind = Literal["slider", "toggle"]


@dataclass(frozen=True, slots=True)
class ControlSpec:
    """Declarative description of one interactive control in the panel.

    Attributes:
        key: Attribute name on :class:`Config` that stores the value.
        label: Human readable label rendered by ``core.ui``.
        kind: ``"slider"`` for a numeric range, ``"toggle"`` for a boolean.
        minimum: Lowest accepted value (sliders only).
        maximum: Highest accepted value (sliders only).
        step: Increment applied by drag/keyboard adjustments (sliders only).
        default: Value used by a fresh :class:`Config`.
        unit: Suffix shown next to the numeric readout (e.g. ``"ms"``).
        decimals: Digits shown in the readout (sliders only).
        help: Short tooltip/description line shown under the label.
    """

    key: str
    label: str
    kind: ControlKind
    minimum: float = 0.0
    maximum: float = 1.0
    step: float = 0.01
    default: Any = 0.0
    unit: str = ""
    decimals: int = 2
    help: str = ""

    def is_toggle(self) -> bool:
        """Return ``True`` when this control is a boolean toggle."""
        return self.kind == "toggle"

    @property
    def step_precision(self) -> int:
        """Number of decimal places implied by :attr:`step` (``0.01`` -> 2)."""
        text = f"{float(self.step):.10f}".rstrip("0")
        return len(text.split(".", 1)[1]) if "." in text else 0

    def clamp(self, value: float) -> float:
        """Clamp ``value`` into ``[minimum, maximum]`` and snap it to ``step``.

        Args:
            value: Raw numeric value coming from the UI or a config file.

        Returns:
            The closest legal value on the slider's step grid, rounded to the
            step's precision so ``0.35`` stays ``0.35`` instead of
            ``0.35000000000000003``.
        """
        if self.is_toggle():
            raise TypeError(f"control {self.key!r} is a toggle, not a slider")
        bounded = min(max(float(value), self.minimum), self.maximum)
        steps = round((bounded - self.minimum) / self.step)
        snapped = self.minimum + steps * self.step
        return round(min(max(snapped, self.minimum), self.maximum), self.step_precision)


CONTROLS: Final[tuple[ControlSpec, ...]] = (
    ControlSpec(
        key="bot_enabled",
        label="Bot",
        kind="toggle",
        default=False,
        help="Start/stop the vision bot (also bound to the B key).",
    ),
    ControlSpec(
        key="ai_assistant",
        label="AI Assistant",
        kind="toggle",
        default=True,
        help="Enable AI predictive model & smart trajectory for high efficiency (M key).",
    ),
    ControlSpec(
        key="aim_speed",
        label="Aim speed",
        kind="slider",
        minimum=0.05,
        maximum=1.00,
        step=0.01,
        default=0.35,
        decimals=2,
        help="Portion of the remaining distance covered per bot iteration.",
    ),
    ControlSpec(
        key="smoothing",
        label="Smoothing",
        kind="slider",
        minimum=0.10,
        maximum=1.00,
        step=0.01,
        default=0.50,
        decimals=2,
        help="Exponential smoothing factor applied to the detected centre.",
    ),
    ControlSpec(
        key="deadzone_px",
        label="Deadzone",
        kind="slider",
        minimum=0.0,
        maximum=20.0,
        step=1.0,
        default=3.0,
        unit="px",
        decimals=0,
        help="Ignore detected target movement smaller than this distance.",
    ),
    ControlSpec(
        key="click_cooldown_ms",
        label="Click cooldown",
        kind="slider",
        minimum=50.0,
        maximum=500.0,
        step=5.0,
        default=120.0,
        unit="ms",
        decimals=0,
        help="Minimum delay between two automatic clicks.",
    ),
    ControlSpec(
        key="humanize",
        label="Humanize",
        kind="toggle",
        default=True,
        help="Add slight jitter so the movement does not look robotic.",
    ),
    ControlSpec(
        key="color_tolerance_h",
        label="Color tolerance",
        kind="slider",
        minimum=1.0,
        maximum=30.0,
        step=1.0,
        default=10.0,
        decimals=0,
        help="Hue tolerance used to build the red HSV range.",
    ),
    ControlSpec(
        key="target_size_px",
        label="Target size",
        kind="slider",
        minimum=20.0,
        maximum=100.0,
        step=1.0,
        default=56.0,
        unit="px",
        decimals=0,
        help="Diameter of the target circle.",
    ),
    ControlSpec(
        key="session_length_s",
        label="Session length",
        kind="slider",
        minimum=10.0,
        maximum=120.0,
        step=5.0,
        default=30.0,
        unit="s",
        decimals=0,
        help="Duration of one scored session.",
    ),
    ControlSpec(
        key="debug_view",
        label="Debug view",
        kind="toggle",
        default=False,
        help="Draw the vision mask, centroid and loop timing.",
    ),
    ControlSpec(
        key="fov_radius_px",
        label="FOV Radius",
        kind="slider",
        minimum=50.0,
        maximum=600.0,
        step=10.0,
        default=250.0,
        unit="px",
        decimals=0,
        help="Target acquisition FOV radius around crosshair; rejects decoys outside this circle.",
    ),
    ControlSpec(
        key="max_target_area_px",
        label="Max Target Area",
        kind="slider",
        minimum=500.0,
        maximum=20000.0,
        step=100.0,
        default=5000.0,
        unit="px²",
        decimals=0,
        help="Ceiling for target blob area; large UI elements, banners and windows are rejected.",
    ),
    ControlSpec(
        key="controller_mode",
        label="Controller Mode",
        kind="toggle",
        default=True,
        help="Direct aim assist via gamepad (XInput), preventing mouse desktop hijacking.",
    ),
    ControlSpec(
        key="controller_lt_aim",
        label="Aim on LT",
        kind="toggle",
        default=True,
        help="Only engage aim assist when holding Left Trigger (LT / L2).",
    ),
    ControlSpec(
        key="disable_mouse_movement",
        label="Disable Mouse Movement",
        kind="toggle",
        default=False,
        help="Disables physical mouse movement so your laptop desktop is never hijacked.",
    ),
    ControlSpec(
        key="use_roboflow_ai",
        label="Roboflow Workflow AI",
        kind="toggle",
        default=False,
        help="Enable Roboflow MW2 Player Detection & ByteTrack tracking workflow.",
    ),
    ControlSpec(
        key="stick_sensitivity",
        label="Stick Sensitivity",
        kind="slider",
        minimum=0.10,
        maximum=5.00,
        step=0.05,
        default=1.25,
        decimals=2,
        help="Multiplier for virtual gamepad right-stick deflection.",
    ),
    ControlSpec(
        key="stick_smoothing",
        label="Stick Smoothing",
        kind="slider",
        minimum=0.00,
        maximum=1.00,
        step=0.01,
        default=0.35,
        decimals=2,
        help="Exponential smoothing applied to virtual joystick coordinates.",
    ),
    ControlSpec(
        key="vertical_offset",
        label="Vertical Offset",
        kind="slider",
        minimum=-50.0,
        maximum=50.0,
        step=1.0,
        default=15.0,
        unit="px",
        decimals=0,
        help="Vertical offset applied to target centroid.",
    ),
    ControlSpec(
        key="power_exponent",
        label="Power Curve Exponent",
        kind="slider",
        minimum=1.00,
        maximum=2.50,
        step=0.05,
        default=1.40,
        decimals=2,
        help="Non-linear thumbstick power curve: fine control near crosshair, fast flick on perimeter.",
    ),
    ControlSpec(
        key="reversal_damping",
        label="Reversal Damping",
        kind="slider",
        minimum=0.10,
        maximum=1.00,
        step=0.05,
        default=0.40,
        decimals=2,
        help="Dampens stick deflection when direction flips to eliminate aim oscillation.",
    ),
    ControlSpec(
        key="static_prop_rejection",
        label="Reject Static Props",
        kind="toggle",
        default=True,
        help="Rejects stationary objects, corpses, and decoys using EMA velocity filtering.",
    ),
    ControlSpec(
        key="use_local_ai",
        label="Local DirectML AI",
        kind="toggle",
        default=False,
        help="Local GPU neural network detection via DirectML (DirectX 12).",
    ),
    ControlSpec(
        key="recoil_vertical_px",
        label="Vertical Anti-Recoil",
        kind="slider",
        minimum=0.0,
        maximum=30.0,
        step=1.0,
        default=0.0,
        unit="px",
        decimals=0,
        help="Vertical pull-down recoil compensation while firing.",
    ),
    ControlSpec(
        key="recoil_horizontal_px",
        label="Horizontal Anti-Recoil",
        kind="slider",
        minimum=-15.0,
        maximum=15.0,
        step=1.0,
        default=0.0,
        unit="px",
        decimals=0,
        help="Horizontal drift recoil compensation while firing.",
    ),
    ControlSpec(
        key="stick_min_breakaway",
        label="Stick Breakaway Boost",
        kind="slider",
        minimum=0.00,
        maximum=0.25,
        step=0.01,
        default=0.08,
        decimals=2,
        help="Minimum stick deflection boost to overcome in-game console deadzones (typically 0.05-0.10).",
    ),
    ControlSpec(
        key="trigger_threshold",
        label="Trigger Threshold",
        kind="slider",
        minimum=0.02,
        maximum=0.50,
        step=0.01,
        default=0.15,
        decimals=2,
        help="Trigger depression required to activate aim/fire (Hair-Trigger vs Deep Press).",
    ),
    ControlSpec(
        key="recoil_delay_ms",
        label="Recoil Start Delay",
        kind="slider",
        minimum=0.0,
        maximum=300.0,
        step=10.0,
        default=0.0,
        unit="ms",
        decimals=0,
        help="Delay in milliseconds before anti-recoil pull begins after firing starts.",
    ),
    ControlSpec(
        key="triggerbot_enabled",
        label="Triggerbot Auto-Fire",
        kind="toggle",
        default=False,
        help="Automatically trigger weapon discharge when an enemy enters crosshair center.",
    ),
)

CONTROLS_BY_KEY: Final[dict[str, ControlSpec]] = {spec.key: spec for spec in CONTROLS}
"""Lookup table used by the UI and by validation code."""


# ---------------------------------------------------------------------------
# Runtime configuration object
# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Mutable runtime configuration shared by the game loop, UI and bot.

    Every attribute corresponds to one entry in :data:`CONTROLS`, so the panel
    can bind to it generically (``setattr(cfg, spec.key, value)``). Values are
    always normalised through :meth:`clamped` before being used by the engine,
    which keeps a corrupt ``user_config.json`` from breaking the run.
    """

    bot_enabled: bool = False
    ai_assistant: bool = True
    aim_speed: float = 0.35
    smoothing: float = 0.50
    deadzone_px: float = 3.0
    click_cooldown_ms: float = 120.0
    humanize: bool = True
    color_tolerance_h: float = 10.0
    target_size_px: float = 56.0
    session_length_s: float = 30.0
    debug_view: bool = False
    fov_radius_px: float = 250.0
    max_target_area_px: float = 5000.0
    controller_mode: bool = True
    controller_lt_aim: bool = True
    disable_mouse_movement: bool = False
    use_roboflow_ai: bool = False
    target_color: RGB = TARGET_RED
    """Live-adjustable target colour tracked by both detectors (default: game red)."""
    controller_bindings: dict[str, Any] = field(default_factory=lambda: dict(CONTROLLER_BINDINGS))
    intensity_profile: str = "NORMAL"
    target_priority: str = "CHEST"
    vertical_offset_px: float = 0.0
    auto_track_enabled: bool = True
    input_mode: str = "vgamepad"
    aim_trigger: str = "LT"
    fire_trigger: str = "RT"
    stick_sensitivity: float = 1.25
    stick_smoothing: float = 0.35
    vertical_offset: int = 15
    power_exponent: float = 1.40
    reversal_damping: float = 0.40
    static_prop_rejection: bool = True
    capture_backend: str = "auto"
    use_local_ai: bool = False
    local_ai_model_path: str = ""
    local_ai_confidence: float = 0.45
    head_bias_percent: float = 0.70
    recoil_vertical_px: float = 0.0
    recoil_horizontal_px: float = 0.0
    controller_type: str = "PS5"
    trigger_threshold: float = 0.15
    stick_min_breakaway: float = 0.0
    recoil_delay_ms: float = 0.0
    triggerbot_enabled: bool = False

    # -- property aliases for uppercase telemetry & binding keys ----------

    @property
    def INPUT_MODE(self) -> str:
        return self.input_mode

    @INPUT_MODE.setter
    def INPUT_MODE(self, val: str) -> None:
        self.input_mode = str(val)

    @property
    def AIM_TRIGGER(self) -> str:
        return self.aim_trigger

    @AIM_TRIGGER.setter
    def AIM_TRIGGER(self, val: str) -> None:
        self.aim_trigger = str(val)

    @property
    def FIRE_TRIGGER(self) -> str:
        return self.fire_trigger

    @FIRE_TRIGGER.setter
    def FIRE_TRIGGER(self, val: str) -> None:
        self.fire_trigger = str(val)

    @property
    def STICK_SENSITIVITY(self) -> float:
        return self.stick_sensitivity

    @STICK_SENSITIVITY.setter
    def STICK_SENSITIVITY(self, val: float) -> None:
        self.stick_sensitivity = float(val)

    @property
    def STICK_SMOOTHING(self) -> float:
        return self.stick_smoothing

    @STICK_SMOOTHING.setter
    def STICK_SMOOTHING(self, val: float) -> None:
        self.stick_smoothing = float(val)

    @property
    def VERTICAL_OFFSET(self) -> int:
        return self.vertical_offset

    @VERTICAL_OFFSET.setter
    def VERTICAL_OFFSET(self, val: int) -> None:
        self.vertical_offset = int(val)

    # -- derived helpers ---------------------------------------------------

    @property
    def target_radius_px(self) -> float:
        """Radius of the target in pixels, derived from ``target_size_px``."""
        return self.target_size_px / 2.0

    @property
    def click_cooldown_s(self) -> float:
        """Click cooldown expressed in seconds."""
        return self.click_cooldown_ms / 1000.0

    def value(self, key: str) -> Any:
        """Return the current value of the control named ``key``.

        Args:
            key: A key present in :data:`CONTROLS_BY_KEY`.

        Returns:
            The stored value (``bool`` for toggles, ``float`` for sliders).

        Raises:
            KeyError: If ``key`` is not a known control.
        """
        if key not in CONTROLS_BY_KEY:
            raise KeyError(f"unknown control: {key!r}")
        return getattr(self, key)

    def set_value(self, key: str, value: Any) -> Any:
        """Normalise and store ``value`` for the control named ``key``.

        Args:
            key: A key present in :data:`CONTROLS_BY_KEY`.
            value: Desired value; booleans are coerced for toggles and numeric
                values are clamped into the slider range.

        Returns:
            The value that was actually stored.

        Raises:
            KeyError: If ``key`` is not a known control.
        """
        spec = CONTROLS_BY_KEY[key]
        stored: Any
        if spec.is_toggle():
            stored = bool(value)
        else:
            stored = spec.clamp(float(value))
        setattr(self, key, stored)
        return stored

    def clamped(self) -> "Config":
        """Return a copy where every control holds a legal, normalised value."""
        clean = Config()
        for spec in CONTROLS:
            clean.set_value(spec.key, getattr(self, spec.key, spec.default))
        clean.input_mode = self.input_mode
        clean.aim_trigger = self.aim_trigger
        clean.fire_trigger = self.fire_trigger
        clean.stick_sensitivity = self.stick_sensitivity
        clean.stick_smoothing = self.stick_smoothing
        clean.vertical_offset = self.vertical_offset
        clean.power_exponent = self.power_exponent
        clean.reversal_damping = self.reversal_damping
        clean.static_prop_rejection = self.static_prop_rejection
        clean.capture_backend = self.capture_backend
        clean.use_local_ai = self.use_local_ai
        clean.local_ai_model_path = self.local_ai_model_path
        clean.local_ai_confidence = self.local_ai_confidence
        clean.head_bias_percent = self.head_bias_percent
        clean.recoil_vertical_px = self.recoil_vertical_px
        clean.recoil_horizontal_px = self.recoil_horizontal_px
        clean.controller_type = self.controller_type
        return clean

    # -- serialisation -----------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping of the current values."""
        d = asdict(self)
        d["INPUT_MODE"] = self.input_mode
        d["AIM_TRIGGER"] = self.aim_trigger
        d["FIRE_TRIGGER"] = self.fire_trigger
        d["STICK_SENSITIVITY"] = self.stick_sensitivity
        d["STICK_SMOOTHING"] = self.stick_smoothing
        d["VERTICAL_OFFSET"] = self.vertical_offset
        return d

    @classmethod
    def from_dict(cls, data: Any) -> "Config":
        """Build a :class:`Config` from a decoded JSON mapping.

        Unknown keys are ignored and missing keys fall back to their default,
        so old config files keep working after new controls are added.

        Args:
            data: Mapping decoded from ``user_config.json`` (anything else is
                treated as an empty mapping).

        Returns:
            A normalised :class:`Config` instance.
        """
        cfg = cls()
        if not isinstance(data, dict):
            return cfg
        for spec in CONTROLS:
            if spec.key in data:
                cfg.set_value(spec.key, data[spec.key])
        if "controller_bindings" in data and isinstance(data["controller_bindings"], dict):
            merged = dict(CONTROLLER_BINDINGS)
            merged.update(data["controller_bindings"])
            cfg.controller_bindings = merged
        if "intensity_profile" in data:
            cfg.intensity_profile = str(data["intensity_profile"])
        if "target_priority" in data:
            cfg.target_priority = str(data["target_priority"])
        if "vertical_offset_px" in data:
            try:
                cfg.vertical_offset_px = float(data["vertical_offset_px"])
            except (ValueError, TypeError):
                pass
        if "auto_track_enabled" in data:
            cfg.auto_track_enabled = bool(data["auto_track_enabled"])
        if "target_color" in data and isinstance(data["target_color"], (list, tuple)) and len(data["target_color"]) == 3:
            cfg.target_color = tuple(int(c) for c in data["target_color"])

        # Telemetry & Trigger Binding persistence
        if "INPUT_MODE" in data:
            cfg.input_mode = str(data["INPUT_MODE"])
        elif "input_mode" in data:
            cfg.input_mode = str(data["input_mode"])

        if "AIM_TRIGGER" in data:
            cfg.aim_trigger = str(data["AIM_TRIGGER"])
        elif "aim_trigger" in data:
            cfg.aim_trigger = str(data["aim_trigger"])

        if "FIRE_TRIGGER" in data:
            cfg.fire_trigger = str(data["FIRE_TRIGGER"])
        elif "fire_trigger" in data:
            cfg.fire_trigger = str(data["fire_trigger"])

        if "STICK_SENSITIVITY" in data:
            try:
                cfg.stick_sensitivity = float(data["STICK_SENSITIVITY"])
            except (ValueError, TypeError):
                pass
        elif "stick_sensitivity" in data:
            try:
                cfg.stick_sensitivity = float(data["stick_sensitivity"])
            except (ValueError, TypeError):
                pass

        if "STICK_SMOOTHING" in data:
            try:
                cfg.stick_smoothing = float(data["STICK_SMOOTHING"])
            except (ValueError, TypeError):
                pass
        elif "stick_smoothing" in data:
            try:
                cfg.stick_smoothing = float(data["stick_smoothing"])
            except (ValueError, TypeError):
                pass

        if "VERTICAL_OFFSET" in data:
            try:
                cfg.vertical_offset = int(data["VERTICAL_OFFSET"])
            except (ValueError, TypeError):
                pass
        elif "vertical_offset" in data:
            try:
                cfg.vertical_offset = int(data["vertical_offset"])
            except (ValueError, TypeError):
                pass

        if "capture_backend" in data:
            cfg.capture_backend = str(data["capture_backend"])
        if "local_ai_model_path" in data:
            cfg.local_ai_model_path = str(data["local_ai_model_path"])
        if "local_ai_confidence" in data:
            try:
                cfg.local_ai_confidence = float(data["local_ai_confidence"])
            except (ValueError, TypeError):
                pass
        if "head_bias_percent" in data:
            try:
                cfg.head_bias_percent = float(data["head_bias_percent"])
            except (ValueError, TypeError):
                pass
        if "recoil_vertical_px" in data:
            try:
                cfg.recoil_vertical_px = float(data["recoil_vertical_px"])
            except (ValueError, TypeError):
                pass
        if "recoil_horizontal_px" in data:
            try:
                cfg.recoil_horizontal_px = float(data["recoil_horizontal_px"])
            except (ValueError, TypeError):
                pass
        if "controller_type" in data:
            cfg.controller_type = str(data["controller_type"])

        cfg.controller_bindings["INPUT_MODE"] = cfg.input_mode
        cfg.controller_bindings["AIM_TRIGGER"] = cfg.aim_trigger
        cfg.controller_bindings["FIRE_TRIGGER"] = cfg.fire_trigger
        cfg.controller_bindings["STICK_SENSITIVITY"] = cfg.stick_sensitivity
        cfg.controller_bindings["STICK_SMOOTHING"] = cfg.stick_smoothing
        cfg.controller_bindings["VERTICAL_OFFSET"] = cfg.vertical_offset

        return cfg

    def save(self, path: Path | None = None) -> Path:
        """Persist the current values as JSON.

        Args:
            path: Destination file; defaults to :data:`USER_CONFIG_PATH`.

        Returns:
            The path that was written.
        """
        target = Path(path) if path is not None else USER_CONFIG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.as_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load values from JSON, falling back to defaults on any problem.

        Args:
            path: Source file; defaults to :data:`USER_CONFIG_PATH`.

        Returns:
            A normalised :class:`Config`. A missing or unreadable file yields
            the defaults instead of raising, so the app always starts.
        """
        source = Path(path) if path is not None else USER_CONFIG_PATH
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls.from_dict(raw)

    def reset(self) -> "Config":
        """Restore every control to its documented default and return ``self``."""
        for spec in CONTROLS:
            self.set_value(spec.key, spec.default)
        self.input_mode = "vgamepad"
        self.aim_trigger = "LT"
        self.fire_trigger = "RT"
        self.stick_sensitivity = 1.25
        self.stick_smoothing = 0.35
        self.vertical_offset = 15
        self.controller_bindings = dict(CONTROLLER_BINDINGS)
        return self


def default_config() -> Config:
    """Return a fresh :class:`Config` holding the documented defaults."""
    return Config()


def control_defaults() -> dict[str, Any]:
    """Return ``{control key: default value}`` for every panel control."""
    return {spec.key: spec.default for spec in CONTROLS}
