"""Unit tests for Windows XInput Gamepad Manager."""

import config
from bot.gamepad import (
    GamepadManager,
    GamepadState,
    XINPUT_GAMEPAD,
    XINPUT_GAMEPAD_A,
    XINPUT_GAMEPAD_B,
    XINPUT_GAMEPAD_LEFT_SHOULDER,
    XINPUT_GAMEPAD_RIGHT_SHOULDER,
)


def test_gamepad_manager_initialization() -> None:
    mgr = GamepadManager(trigger_threshold=0.20)
    assert mgr.trigger_threshold == 0.20
    # On Windows 10/11 xinput dll should be available
    assert mgr.is_available is True


def test_gamepad_state_defaults() -> None:
    state = GamepadState()
    assert state.connected is False
    assert state.left_trigger == 0.0
    assert state.right_trigger == 0.0
    assert state.is_aiming is False
    assert state.is_firing is False
    assert state.left_bumper is False
    assert state.right_bumper is False
    assert state.a_button is False
    assert state.b_button is False


def test_gamepad_state_aiming_and_firing() -> None:
    state_aim = GamepadState(connected=True, left_trigger=0.5, is_aiming=True)
    assert state_aim.is_aiming is True

    state_fire = GamepadState(connected=True, right_trigger=0.8, is_firing=True)
    assert state_fire.is_firing is True

    state_buttons = GamepadState(
        connected=True,
        buttons=XINPUT_GAMEPAD_LEFT_SHOULDER | XINPUT_GAMEPAD_A
    )
    assert state_buttons.left_bumper is True
    assert state_buttons.right_bumper is False
    assert state_buttons.a_button is True


def test_gamepad_axis_normalization() -> None:
    # Deadzone filtering
    deadzone = 7849
    # Below deadzone -> 0.0
    assert GamepadManager._normalize_axis(5000, deadzone) == 0.0
    assert GamepadManager._normalize_axis(-5000, deadzone) == 0.0

    # Max deflection
    assert GamepadManager._normalize_axis(32767, deadzone) == 1.0
    assert GamepadManager._normalize_axis(-32768, deadzone) == -1.0


def test_hidhide_manager_queries() -> None:
    from bot.gamepad import HidHideManager

    # Test non-existent path
    mgr_dummy = HidHideManager(cli_path="C:/non_existent_hidhide_cli.exe")
    assert mgr_dummy.is_installed is False
    st = mgr_dummy.get_status()
    assert st["installed"] is False
    assert mgr_dummy.whitelist_current_process() is False
    assert mgr_dummy.set_cloaking(True) is False

    # Test default detection
    mgr = HidHideManager()
    status = mgr.get_status()
    assert "installed" in status
    assert "message" in status
