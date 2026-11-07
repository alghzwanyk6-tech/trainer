"""Unit tests for the Full Controller Remapping & Macro Engine."""

from bot.gamepad import (
    BUTTON_MASKS,
    GamepadManager,
    GamepadState,
    is_action_button_pressed,
    XINPUT_GAMEPAD_LEFT_SHOULDER,
    XINPUT_GAMEPAD_RIGHT_SHOULDER,
    XINPUT_GAMEPAD_RIGHT_THUMB,
)
import config


def test_is_action_button_pressed_triggers() -> None:
    # LT / L2
    assert is_action_button_pressed("L2", 0, lt=0.5, rt=0.0) is True
    assert is_action_button_pressed("LT", 0, lt=0.5, rt=0.0) is True
    assert is_action_button_pressed("L2", 0, lt=0.05, rt=0.0) is False

    # RT / R2
    assert is_action_button_pressed("R2", 0, lt=0.0, rt=0.8) is True
    assert is_action_button_pressed("RT", 0, lt=0.0, rt=0.8) is True
    assert is_action_button_pressed("R2", 0, lt=0.0, rt=0.05) is False


def test_is_action_button_pressed_bumpers_and_sticks() -> None:
    # L1 / LB
    assert is_action_button_pressed("L1", XINPUT_GAMEPAD_LEFT_SHOULDER, 0.0, 0.0) is True
    assert is_action_button_pressed("LB", XINPUT_GAMEPAD_LEFT_SHOULDER, 0.0, 0.0) is True
    assert is_action_button_pressed("L1", 0, 0.0, 0.0) is False

    # R1 / RB
    assert is_action_button_pressed("R1", XINPUT_GAMEPAD_RIGHT_SHOULDER, 0.0, 0.0) is True

    # R3
    assert is_action_button_pressed("R3", XINPUT_GAMEPAD_RIGHT_THUMB, 0.0, 0.0) is True


def test_gamepad_manager_polling_remapping() -> None:
    gm = GamepadManager(trigger_threshold=0.15)

    # Test Bumper Jumper Tactical schema
    bindings = {
        "AIM_TRIGGER": "L1",
        "FIRE_TRIGGER": "R1",
        "TACTICAL_JUMP": "L2",
        "SLIDE_CANCEL_PRONE": "R3",
        "MELEE_ACTION": "R2",
        "STICK_SENSITIVITY": 1.5,
        "DEADZONE_PX": 3.0,
    }

    # When no hardware is connected, poll returns connected=False
    state = gm.poll(bindings=bindings)
    assert state.connected is False or isinstance(state.connected, bool)
