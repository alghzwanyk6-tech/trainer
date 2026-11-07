"""Windows Gamepad integration for Controller aim assist.

Supports:
- Xbox 360, Xbox One, Xbox Series via Windows XInput
- DualShock 4 & DualSense (PS4 / PS5) via DirectInput / SDL2 / DS4Windows
- Any PC-compatible controller (HID / USB / Bluetooth)
"""

from __future__ import annotations

import ctypes
import math
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import config

__all__ = [
    "BUTTON_MASKS",
    "GamepadManager",
    "GamepadState",
    "HidHideManager",
    "is_action_button_pressed",
]

# ---------------------------------------------------------------------------
# XInput Constants & Structures
# ---------------------------------------------------------------------------

XINPUT_GAMEPAD_DPAD_UP: Final[int] = 0x0001
XINPUT_GAMEPAD_DPAD_DOWN: Final[int] = 0x0002
XINPUT_GAMEPAD_DPAD_LEFT: Final[int] = 0x0004
XINPUT_GAMEPAD_DPAD_RIGHT: Final[int] = 0x0008
XINPUT_GAMEPAD_START: Final[int] = 0x0010
XINPUT_GAMEPAD_BACK: Final[int] = 0x0020
XINPUT_GAMEPAD_LEFT_THUMB: Final[int] = 0x0040
XINPUT_GAMEPAD_RIGHT_THUMB: Final[int] = 0x0080
XINPUT_GAMEPAD_LEFT_SHOULDER: Final[int] = 0x0100
XINPUT_GAMEPAD_RIGHT_SHOULDER: Final[int] = 0x0200
XINPUT_GAMEPAD_A: Final[int] = 0x1000
XINPUT_GAMEPAD_B: Final[int] = 0x2000
XINPUT_GAMEPAD_X: Final[int] = 0x4000
XINPUT_GAMEPAD_Y: Final[int] = 0x8000

ERROR_SUCCESS: Final[int] = 0
ERROR_DEVICE_NOT_CONNECTED: Final[int] = 1167

XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE: Final[int] = 7849
XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE: Final[int] = 8689


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [
        ("wLeftMotorSpeed", ctypes.c_ushort),
        ("wRightMotorSpeed", ctypes.c_ushort),
    ]


_xinput_lib = None
for _dll in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
    try:
        _xinput_lib = ctypes.windll.LoadLibrary(_dll)
        break
    except Exception:
        continue


BUTTON_MASKS: Final[dict[str, int]] = {
    "A": XINPUT_GAMEPAD_A,
    "CROSS": XINPUT_GAMEPAD_A,
    "B": XINPUT_GAMEPAD_B,
    "CIRCLE": XINPUT_GAMEPAD_B,
    "X": XINPUT_GAMEPAD_X,
    "SQUARE": XINPUT_GAMEPAD_X,
    "Y": XINPUT_GAMEPAD_Y,
    "TRIANGLE": XINPUT_GAMEPAD_Y,
    "LB": XINPUT_GAMEPAD_LEFT_SHOULDER,
    "L1": XINPUT_GAMEPAD_LEFT_SHOULDER,
    "RB": XINPUT_GAMEPAD_RIGHT_SHOULDER,
    "R1": XINPUT_GAMEPAD_RIGHT_SHOULDER,
    "L3": XINPUT_GAMEPAD_LEFT_THUMB,
    "R3": XINPUT_GAMEPAD_RIGHT_THUMB,
    "START": XINPUT_GAMEPAD_START,
    "OPTIONS": XINPUT_GAMEPAD_START,
    "BACK": XINPUT_GAMEPAD_BACK,
    "SHARE": XINPUT_GAMEPAD_BACK,
    "DPAD_UP": XINPUT_GAMEPAD_DPAD_UP,
    "DPAD_DOWN": XINPUT_GAMEPAD_DPAD_DOWN,
    "DPAD_LEFT": XINPUT_GAMEPAD_DPAD_LEFT,
    "DPAD_RIGHT": XINPUT_GAMEPAD_DPAD_RIGHT,
}


def is_action_button_pressed(
    binding_key: str,
    buttons: int,
    lt: float,
    rt: float,
    trigger_threshold: float = 0.15,
) -> bool:
    """Evaluate whether the mapped physical button or trigger is actively engaged."""
    key = binding_key.strip().upper()
    if key in ("ALWAYS", "ON", "AUTO"):
        return True
    if "L1" in key and "L2" in key:
        return (lt >= trigger_threshold) or bool(buttons & XINPUT_GAMEPAD_LEFT_SHOULDER)
    if "R1" in key and "R2" in key:
        return (rt >= trigger_threshold) or bool(buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER)
    if key in ("L2", "LT"):
        return lt >= trigger_threshold
    if key in ("R2", "RT"):
        return rt >= trigger_threshold
    if key in ("L1", "LB"):
        return bool(buttons & XINPUT_GAMEPAD_LEFT_SHOULDER)
    if key in ("R1", "RB"):
        return bool(buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER)
    if key in BUTTON_MASKS:
        return bool(buttons & BUTTON_MASKS[key])
    for name, mask in BUTTON_MASKS.items():
        if name == key:
            return bool(buttons & mask)
    return False


@dataclass(frozen=True, slots=True)
class GamepadState:
    """Snapshot of a controller's input state with full action mapping."""

    connected: bool = False
    device_name: str = "غير متصل"
    user_index: int = 0
    left_trigger: float = 0.0      # 0.0 .. 1.0 (LT / L2)
    right_trigger: float = 0.0     # 0.0 .. 1.0 (RT / R2)
    left_stick: tuple[float, float] = (0.0, 0.0)   # (lx, ly) in [-1.0, 1.0]
    right_stick: tuple[float, float] = (0.0, 0.0)  # (rx, ry) in [-1.0, 1.0]
    buttons: int = 0
    is_aiming: bool = False        # Mapped to AIM_TRIGGER (e.g. L1 / LT)
    is_firing: bool = False        # Mapped to FIRE_TRIGGER (e.g. R1 / RT)
    is_jumping: bool = False       # Mapped to TACTICAL_JUMP (e.g. L2 / A)
    is_sliding: bool = False       # Mapped to SLIDE_CANCEL_PRONE (e.g. R3)
    is_melee: bool = False         # Mapped to MELEE_ACTION (e.g. R2)
    dpad: tuple[int, int] = (0, 0) # (dx: -1, 0, 1, dy: -1, 0, 1)

    @property
    def left_bumper(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_LEFT_SHOULDER)

    @property
    def right_bumper(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER)

    @property
    def a_button(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_A)

    @property
    def b_button(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_B)

    @property
    def x_button(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_X)

    @property
    def y_button(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_Y)

    @property
    def l3_button(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_LEFT_THUMB)

    @property
    def r3_button(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_RIGHT_THUMB)

    @property
    def dpad_up(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_DPAD_UP)

    @property
    def dpad_down(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_DPAD_DOWN)

    @property
    def dpad_left(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_DPAD_LEFT)

    @property
    def dpad_right(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_DPAD_RIGHT)

    @property
    def start_button(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_START)

    @property
    def back_button(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_BACK)


class GamepadManager:
    """Manages Gamepad polling via XInput and DirectInput/SDL2 fallback."""

    def __init__(self, trigger_threshold: float = 0.15) -> None:
        self.trigger_threshold = max(0.01, min(0.99, float(trigger_threshold)))
        self._last_connected_index: int = 0
        self._pygame_initialized: bool = False

    @property
    def is_available(self) -> bool:
        """True if any gamepad subsystem is available."""
        return _xinput_lib is not None

    def poll(
        self,
        preferred_index: int | None = None,
        bindings: dict[str, Any] | None = None,
    ) -> GamepadState:
        """Poll the controller state with tactical button remapping support.
        
        Checks XInput first, then falls back to DirectInput/SDL2 (PlayStation controllers).
        """
        b = bindings if bindings is not None else getattr(config, "CONTROLLER_BINDINGS", {})
        aim_trigger = str(b.get("AIM_TRIGGER", "L1"))
        fire_trigger = str(b.get("FIRE_TRIGGER", "R1"))
        jump_trigger = str(b.get("TACTICAL_JUMP", "L2"))
        slide_trigger = str(b.get("SLIDE_CANCEL_PRONE", "R3"))
        melee_trigger = str(b.get("MELEE_ACTION", "R2"))
        stick_sens = float(b.get("STICK_SENSITIVITY", 1.25))
        effective_threshold = float(b.get("TRIGGER_THRESHOLD", self.trigger_threshold))

        # 1. Try XInput
        if _xinput_lib is not None:
            state = XINPUT_STATE()
            indices_to_try = (
                [preferred_index] if preferred_index is not None
                else [self._last_connected_index] + [i for i in range(4) if i != self._last_connected_index]
            )

            for idx in indices_to_try:
                try:
                    res = _xinput_lib.XInputGetState(idx, ctypes.byref(state))
                    if res == ERROR_SUCCESS:
                        self._last_connected_index = idx
                        gp = state.Gamepad

                        lt = gp.bLeftTrigger / 255.0
                        rt = gp.bRightTrigger / 255.0

                        lx = self._normalize_axis(gp.sThumbLX, XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE)
                        ly = self._normalize_axis(gp.sThumbLY, XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE)
                        rx = self._normalize_axis(gp.sThumbRX, XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE)
                        ry = self._normalize_axis(gp.sThumbRY, XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE)

                        is_aiming = is_action_button_pressed(aim_trigger, gp.wButtons, lt, rt, effective_threshold)
                        is_firing = is_action_button_pressed(fire_trigger, gp.wButtons, lt, rt, effective_threshold)
                        is_jumping = is_action_button_pressed(jump_trigger, gp.wButtons, lt, rt, effective_threshold)
                        is_sliding = is_action_button_pressed(slide_trigger, gp.wButtons, lt, rt, effective_threshold)
                        is_melee = is_action_button_pressed(melee_trigger, gp.wButtons, lt, rt, effective_threshold)

                        dpad_x, dpad_y = 0, 0
                        if gp.wButtons & XINPUT_GAMEPAD_DPAD_UP: dpad_y = 1
                        elif gp.wButtons & XINPUT_GAMEPAD_DPAD_DOWN: dpad_y = -1
                        if gp.wButtons & XINPUT_GAMEPAD_DPAD_LEFT: dpad_x = -1
                        elif gp.wButtons & XINPUT_GAMEPAD_DPAD_RIGHT: dpad_x = 1

                        scaled_rx = max(-1.0, min(1.0, rx * stick_sens))
                        scaled_ry = max(-1.0, min(1.0, ry * stick_sens))

                        return GamepadState(
                            connected=True,
                            device_name=f"Xbox/XInput #{idx}",
                            user_index=idx,
                            left_trigger=lt,
                            right_trigger=rt,
                            left_stick=(lx, ly),
                            right_stick=(scaled_rx, scaled_ry),
                            buttons=gp.wButtons,
                            is_aiming=is_aiming,
                            is_firing=is_firing,
                            is_jumping=is_jumping,
                            is_sliding=is_sliding,
                            is_melee=is_melee,
                            dpad=(dpad_x, dpad_y),
                        )
                except Exception:
                    continue

        # 2. Try Pygame Joystick (DirectInput / PS4 / PS5 DualSense)
        try:
            import pygame
            if not self._pygame_initialized:
                if not pygame.get_init():
                    pygame.init()
                if not pygame.joystick.get_init():
                    pygame.joystick.init()
                self._pygame_initialized = True

            pygame.event.pump()
            if pygame.joystick.get_count() > 0:
                js = pygame.joystick.Joystick(0)
                if not js.get_init():
                    js.init()

                name = js.get_name()
                display_name = name
                name_lower = name.lower()
                if any(k in name_lower for k in ("dualsense", "wireless controller", "ps5", "playstation", "sony")):
                    display_name = "Sony PS5 DualSense"
                elif "xbox" in name_lower:
                    display_name = f"Xbox Controller ({name[:12]})"

                num_axes = js.get_numaxes()
                num_btns = js.get_numbuttons()

                # Read sticks & triggers for DualSense / DualShock
                lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0
                lt, rt = 0.0, 0.0

                if num_axes >= 6:
                    lx = js.get_axis(0)
                    ly = js.get_axis(1)
                    rx = js.get_axis(2)
                    ry = js.get_axis(3)
                    raw_lt = js.get_axis(4)
                    raw_rt = js.get_axis(5)
                    lt = max(0.0, min(1.0, (raw_lt + 1.0) / 2.0)) if raw_lt != 0.0 else 0.0
                    rt = max(0.0, min(1.0, (raw_rt + 1.0) / 2.0)) if raw_rt != 0.0 else 0.0
                elif num_axes >= 4:
                    lx = js.get_axis(0)
                    ly = js.get_axis(1)
                    rx = js.get_axis(2)
                    ry = js.get_axis(3)

                scaled_rx = max(-1.0, min(1.0, rx * stick_sens))
                scaled_ry = max(-1.0, min(1.0, ry * stick_sens))

                py_buttons = 0
                if num_btns > 0 and js.get_button(0): py_buttons |= XINPUT_GAMEPAD_A
                if num_btns > 1 and js.get_button(1): py_buttons |= XINPUT_GAMEPAD_B
                if num_btns > 2 and js.get_button(2): py_buttons |= XINPUT_GAMEPAD_X
                if num_btns > 3 and js.get_button(3): py_buttons |= XINPUT_GAMEPAD_Y
                if num_btns > 4 and js.get_button(4): py_buttons |= XINPUT_GAMEPAD_LEFT_SHOULDER
                if num_btns > 5 and js.get_button(5): py_buttons |= XINPUT_GAMEPAD_RIGHT_SHOULDER
                if num_btns > 6 and js.get_button(6):
                    lt = max(lt, 1.0)
                if num_btns > 7 and js.get_button(7):
                    rt = max(rt, 1.0)
                if num_btns > 8 and js.get_button(8): py_buttons |= XINPUT_GAMEPAD_BACK   # Share
                if num_btns > 9 and js.get_button(9): py_buttons |= XINPUT_GAMEPAD_START  # Options
                if num_btns > 10 and js.get_button(10): py_buttons |= XINPUT_GAMEPAD_LEFT_THUMB   # L3
                if num_btns > 11 and js.get_button(11): py_buttons |= XINPUT_GAMEPAD_RIGHT_THUMB  # R3
                if num_btns > 12 and js.get_button(12): py_buttons |= XINPUT_GAMEPAD_START  # PS Button

                dpad_x, dpad_y = 0, 0
                if js.get_numhats() > 0:
                    hx, hy = js.get_hat(0)
                    dpad_x, dpad_y = hx, hy
                    if hy == 1: py_buttons |= XINPUT_GAMEPAD_DPAD_UP
                    elif hy == -1: py_buttons |= XINPUT_GAMEPAD_DPAD_DOWN
                    if hx == -1: py_buttons |= XINPUT_GAMEPAD_DPAD_LEFT
                    elif hx == 1: py_buttons |= XINPUT_GAMEPAD_DPAD_RIGHT

                is_aiming = is_action_button_pressed(aim_trigger, py_buttons, lt, rt, effective_threshold)
                is_firing = is_action_button_pressed(fire_trigger, py_buttons, lt, rt, effective_threshold)
                is_jumping = is_action_button_pressed(jump_trigger, py_buttons, lt, rt, effective_threshold)
                is_sliding = is_action_button_pressed(slide_trigger, py_buttons, lt, rt, effective_threshold)
                is_melee = is_action_button_pressed(melee_trigger, py_buttons, lt, rt, effective_threshold)

                return GamepadState(
                    connected=True,
                    device_name=display_name,
                    user_index=0,
                    left_trigger=lt,
                    right_trigger=rt,
                    left_stick=(lx, ly),
                    right_stick=(scaled_rx, scaled_ry),
                    buttons=py_buttons,
                    is_aiming=is_aiming,
                    is_firing=is_firing,
                    is_jumping=is_jumping,
                    is_sliding=is_sliding,
                    is_melee=is_melee,
                    dpad=(dpad_x, dpad_y),
                )
        except Exception:
            pass

        return GamepadState(connected=False, user_index=self._last_connected_index)

    def set_vibration(self, user_index: int, left_speed: float, right_speed: float) -> bool:
        """Send haptic rumble to the gamepad motors (0.0 to 1.0)."""
        if _xinput_lib is None:
            return False
        vib = XINPUT_VIBRATION()
        vib.wLeftMotorSpeed = int(max(0.0, min(1.0, left_speed)) * 65535)
        vib.wRightMotorSpeed = int(max(0.0, min(1.0, right_speed)) * 65535)
        try:
            return _xinput_lib.XInputSetState(user_index, ctypes.byref(vib)) == ERROR_SUCCESS
        except Exception:
            return False

    @staticmethod
    def _normalize_axis(raw_val: int, deadzone: int) -> float:
        """Filter stick deadzone and scale into [-1.0, 1.0]."""
        if abs(raw_val) < deadzone:
            return 0.0
        if raw_val > 0:
            norm = (raw_val - deadzone) / (32767.0 - deadzone)
        else:
            norm = (raw_val + deadzone) / (32768.0 - deadzone)
        return max(-1.0, min(1.0, norm))


# ---------------------------------------------------------------------------
# HidHide Kernel Gamepad Cloaking Integration
# ---------------------------------------------------------------------------


class HidHideManager:
    """Manages Nefarius HidHide kernel-level gamepad cloaking.

    Hides physical gaming controllers from game processes to eliminate
    double-input collisions while allowing the bot process exclusive read access.
    """

    KNOWN_CLI_PATHS: Final[tuple[str, ...]] = (
        r"C:\Program Files\Nefarius Software Solutions\HidHide\x64\HidHideCLI.exe",
        r"C:\Program Files\Nefarius Software Solutions\HidHideCLI\x64\HidHideCLI.exe",
    )
    KNOWN_GUI_PATHS: Final[tuple[str, ...]] = (
        r"C:\Program Files\Nefarius Software Solutions\HidHide\x64\HidHideClient.exe",
        r"C:\Program Files\Nefarius Software Solutions\HidHide\HidHideClient.exe",
        r"C:\Program Files\Nefarius Software Solutions\HidHideClient\x64\HidHideClient.exe",
    )

    def __init__(self, cli_path: str | Path | None = None) -> None:
        self.cli_path: Path | None = None
        self.gui_path: Path | None = None

        if cli_path is not None:
            p = Path(cli_path)
            if p.is_file():
                self.cli_path = p
            return

        for candidate in self.KNOWN_CLI_PATHS:
            p = Path(candidate)
            if p.is_file():
                self.cli_path = p
                break
        if self.cli_path is None:
            found = shutil.which("HidHideCLI.exe")
            if found:
                self.cli_path = Path(found)

        for candidate in self.KNOWN_GUI_PATHS:
            p = Path(candidate)
            if p.is_file():
                self.gui_path = p
                break
        if self.gui_path is None:
            found_gui = shutil.which("HidHideClient.exe")
            if found_gui:
                self.gui_path = Path(found_gui)

    @property
    def is_installed(self) -> bool:
        """True if HidHide CLI or driver is present on the system."""
        return self.cli_path is not None and self.cli_path.is_file()

    @property
    def is_gui_installed(self) -> bool:
        """True if HidHide Client GUI is available."""
        return self.gui_path is not None and self.gui_path.is_file()

    def get_status(self) -> dict[str, Any]:
        """Query driver status, cloaking state, and whitelist."""
        if not self.is_installed or self.cli_path is None:
            return {
                "installed": False,
                "service_running": False,
                "cloaked": False,
                "accessible": False,
                "message": "HidHide غير مثبت على النظام",
            }

        # Check if service is running
        try:
            res = subprocess.run(
                ["sc.exe", "query", "HidHide"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            service_running = "RUNNING" in res.stdout
        except Exception:
            service_running = False

        # Attempt to read cloaking state
        try:
            res = subprocess.run(
                [str(self.cli_path), "--cloak-state"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                is_cloaked = "Active" in res.stdout
                return {
                    "installed": True,
                    "service_running": service_running,
                    "cloaked": is_cloaked,
                    "accessible": True,
                    "message": "نشط ومفعل (محمي)" if is_cloaked else "مثبت (غير محجوب)",
                }
            elif "Access is denied" in res.stderr or "0x0005" in res.stderr:
                return {
                    "installed": True,
                    "service_running": service_running,
                    "cloaked": False,
                    "accessible": False,
                    "message": "مثبت (يتطلب صلاحية مسؤول للتحكم)",
                }
        except Exception:
            pass

        return {
            "installed": True,
            "service_running": service_running,
            "cloaked": False,
            "accessible": False,
            "message": "مثبت على النظام",
        }

    def whitelist_current_process(self, app_path: str | None = None) -> bool:
        """Register the current process with HidHide so it can read hidden gamepads."""
        if not self.is_installed or self.cli_path is None:
            return False
        target = app_path if app_path else sys.executable
        try:
            res = subprocess.run(
                [str(self.cli_path), "--app-reg", target],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.returncode == 0
        except Exception:
            return False

    def set_cloaking(self, enable: bool) -> bool:
        """Enable or disable global HID cloaking."""
        if not self.is_installed or self.cli_path is None:
            return False
        flag = "--cloak-on" if enable else "--cloak-off"
        try:
            res = subprocess.run(
                [str(self.cli_path), flag],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.returncode == 0
        except Exception:
            return False

    def launch_gui(self) -> bool:
        """Launch the official Nefarius HidHide configuration GUI with elevated privileges."""
        if not self.is_gui_installed or self.gui_path is None:
            return False
        try:
            res = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", str(self.gui_path), "", None, 1
            )
            return int(res) > 32
        except Exception:
            return False

    def run_elevated_cli(self, arguments: str) -> bool:
        """Execute HidHideCLI with elevated administrative privileges."""
        if not self.is_installed or self.cli_path is None:
            return False
        try:
            res = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", str(self.cli_path), arguments, None, 0
            )
            return int(res) > 32
        except Exception:
            return False

    def whitelist_current_process_elevated(self, app_path: str | None = None) -> bool:
        """Register the current process with HidHide using UAC elevation."""
        target = app_path if app_path else sys.executable
        return self.run_elevated_cli(f'--app-reg "{target}"')

    def set_cloaking_elevated(self, enable: bool) -> bool:
        """Toggle kernel cloaking using UAC elevation."""
        flag = "--cloak-on" if enable else "--cloak-off"
        return self.run_elevated_cli(flag)

