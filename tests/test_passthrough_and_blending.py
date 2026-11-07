"""Unit tests for Full Controller Pass-Through & Input Blending."""

from unittest.mock import MagicMock
import config
from bot.controller import BotController
from bot.gamepad import (
    GamepadState,
    HidHideManager,
    XINPUT_GAMEPAD_A,
    XINPUT_GAMEPAD_B,
    XINPUT_GAMEPAD_DPAD_UP,
    XINPUT_GAMEPAD_LEFT_SHOULDER,
)


class MockVPad:
    """Mock Virtual Gamepad to track pass-through and blending actuation."""

    def __init__(self) -> None:
        self.lx = 0.0
        self.ly = 0.0
        self.rx = 0.0
        self.ry = 0.0
        self.lt = 0.0
        self.rt = 0.0
        self.pressed_buttons: set[int] = set()
        self.dpad_direction = None
        self.update_count = 0

    def left_joystick_float(self, x_value_float: float, y_value_float: float) -> None:
        self.lx = x_value_float
        self.ly = y_value_float

    def right_joystick_float(self, x_value_float: float, y_value_float: float) -> None:
        self.rx = x_value_float
        self.ry = y_value_float

    def left_trigger_float(self, value_float: float) -> None:
        self.lt = value_float

    def right_trigger_float(self, value_float: float) -> None:
        self.rt = value_float

    def press_button(self, button: int) -> None:
        self.pressed_buttons.add(button)

    def release_button(self, button: int) -> None:
        self.pressed_buttons.discard(button)

    def directional_pad(self, direction: int) -> None:
        self.dpad_direction = direction

    def update(self) -> None:
        self.update_count += 1


def test_passthrough_gamepad_axes_and_triggers() -> None:
    mock_vpad = MockVPad()
    cfg = config.Config()
    controller = BotController(cfg, vpad=mock_vpad)

    state = GamepadState(
        connected=True,
        left_stick=(-0.75, 0.50),
        right_stick=(0.20, -0.10),
        left_trigger=0.65,
        right_trigger=0.30,
        buttons=XINPUT_GAMEPAD_A,
    )

    # 1. Pass-through with zero aim deflection
    rx, ry = controller.pass_through_gamepad(state, aim_rx=0.0, aim_ry=0.0)
    assert rx == 0.20
    assert ry == -0.10
    assert mock_vpad.lx == -0.75
    assert mock_vpad.ly == 0.50
    assert mock_vpad.lt == 0.65
    assert mock_vpad.rt == 0.30
    assert mock_vpad.update_count == 1
    # Idle pass-through should not increment aim move count
    assert controller.move_count == 0

    # 2. Pass-through with active aim-assist blending (R_final = R_user + R_bot)
    rx_blended, ry_blended = controller.pass_through_gamepad(state, aim_rx=0.45, aim_ry=0.25)
    assert round(rx_blended, 2) == 0.65
    assert round(ry_blended, 2) == 0.15
    assert round(mock_vpad.rx, 2) == 0.65
    assert round(mock_vpad.ry, 2) == 0.15
    assert controller.move_count == 1

    # 3. Triggerbot auto-fire override
    controller.pass_through_gamepad(state, triggerbot_active=True)
    assert mock_vpad.rt == 1.0


def test_passthrough_clamping_and_disconnected() -> None:
    mock_vpad = MockVPad()
    cfg = config.Config()
    controller = BotController(cfg, vpad=mock_vpad)

    # Disconnected controller returns (0.0, 0.0)
    disc_state = GamepadState(connected=False)
    rx, ry = controller.pass_through_gamepad(disc_state, aim_rx=0.5, aim_ry=0.5)
    assert (rx, ry) == (0.0, 0.0)

    # Clamping past [-1.0, 1.0]
    sat_state = GamepadState(
        connected=True,
        right_stick=(0.80, -0.90),
    )
    rx_sat, ry_sat = controller.pass_through_gamepad(sat_state, aim_rx=0.50, aim_ry=-0.40)
    assert rx_sat == 1.0
    assert ry_sat == -1.0


def test_apply_stick_deflection_blends_user_stick() -> None:
    mock_vpad = MockVPad()
    cfg = config.Config(fov_radius_px=200.0)
    controller = BotController(cfg, vpad=mock_vpad)

    # dx = 100 -> bot deflection 0.50 (linear)
    # user right stick = 0.30 -> final rx = 0.80
    rx, ry = controller.apply_stick_deflection(
        dx=100.0, dy=0.0, sens=1.0, smoothing=0.0, power_exponent=1.0,
        user_stick=(0.30, 0.0)
    )
    assert round(rx, 2) == 0.80
    assert mock_vpad.rx == 0.80


def test_hidhide_manager_elevated_helpers(monkeypatch) -> None:
    mgr = HidHideManager()
    # Mock ShellExecuteW
    called = []

    def mock_shell_execute(hwnd, op, path, params, dir, show):
        called.append((op, path, params, show))
        return 42  # Success code > 32

    import ctypes
    monkeypatch.setattr(ctypes.windll.shell32, "ShellExecuteW", mock_shell_execute)

    # Test run_elevated_cli
    if mgr.cli_path is not None:
        ok = mgr.run_elevated_cli("--cloak-state")
        assert ok is True
        assert len(called) >= 1
        assert called[-1][0] == "runas"

        # Test whitelist and cloaking
        assert mgr.whitelist_current_process_elevated() is True
        assert mgr.set_cloaking_elevated(True) is True
        assert mgr.set_cloaking_elevated(False) is True
