"""Unit tests for config module."""

import json
from pathlib import Path

import pytest

import config


def test_default_config() -> None:
    cfg = config.Config()
    assert cfg.bot_enabled is False
    assert cfg.ai_assistant is True
    assert cfg.aim_speed == 0.35
    assert cfg.smoothing == 0.50
    assert cfg.deadzone_px == 3.0
    assert cfg.click_cooldown_ms == 120.0
    assert cfg.target_size_px == 56.0
    assert cfg.target_radius_px == 28.0
    assert cfg.click_cooldown_s == 0.12


def test_control_spec_clamp() -> None:
    slider = config.CONTROLS_BY_KEY["aim_speed"]
    assert slider.clamp(0.0) == slider.minimum
    assert slider.clamp(2.0) == slider.maximum
    assert slider.clamp(0.351) == 0.35

    toggle = config.CONTROLS_BY_KEY["bot_enabled"]
    with pytest.raises(TypeError):
        toggle.clamp(1.0)


def test_config_set_and_value() -> None:
    cfg = config.Config()
    cfg.set_value("aim_speed", 0.75)
    assert cfg.value("aim_speed") == 0.75
    cfg.set_value("bot_enabled", True)
    assert cfg.value("bot_enabled") is True

    with pytest.raises(KeyError):
        cfg.value("unknown_key")

    with pytest.raises(KeyError):
        cfg.set_value("unknown_key", 123)


def test_config_save_and_load(tmp_path: Path) -> None:
    cfg_file = tmp_path / "user_config.json"
    cfg = config.Config(aim_speed=0.88, bot_enabled=True, ai_assistant=False)
    cfg.save(cfg_file)

    loaded = config.Config.load(cfg_file)
    assert loaded.aim_speed == 0.88
    assert loaded.bot_enabled is True
    assert loaded.ai_assistant is False


def test_config_reset() -> None:
    cfg = config.Config(aim_speed=0.99, bot_enabled=True)
    cfg.reset()
    assert cfg.aim_speed == 0.35
    assert cfg.bot_enabled is False


def test_telemetry_and_binding_config(tmp_path: Path) -> None:
    cfg = config.Config(
        input_mode="vgamepad",
        aim_trigger="LT",
        fire_trigger="RT",
        stick_sensitivity=1.25,
        stick_smoothing=0.35,
        vertical_offset=15,
    )
    assert cfg.INPUT_MODE == "vgamepad"
    assert cfg.AIM_TRIGGER == "LT"
    assert cfg.FIRE_TRIGGER == "RT"
    assert cfg.STICK_SENSITIVITY == 1.25
    assert cfg.STICK_SMOOTHING == 0.35
    assert cfg.VERTICAL_OFFSET == 15

    # Test JSON persistence
    test_file = tmp_path / "user_config.json"
    cfg.save(test_file)

    loaded = config.Config.load(test_file)
    assert loaded.INPUT_MODE == "vgamepad"
    assert loaded.AIM_TRIGGER == "LT"
    assert loaded.FIRE_TRIGGER == "RT"
    assert loaded.STICK_SENSITIVITY == 1.25
    assert loaded.STICK_SMOOTHING == 0.35
    assert loaded.VERTICAL_OFFSET == 15
