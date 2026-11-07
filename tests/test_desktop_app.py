"""Unit tests for Desktop App components and helpers."""

import tkinter as tk
import config
from desktop_app import hex_to_rgb, rgb_to_hex, AimBotDesktopApp


def test_hex_to_rgb_valid() -> None:
    assert hex_to_rgb("ff0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)
    assert hex_to_rgb("123456") == (0x12, 0x34, 0x56)


def test_hex_to_rgb_invalid() -> None:
    assert hex_to_rgb("invalid") is None
    assert hex_to_rgb("#123") is None
    assert hex_to_rgb("") is None


def test_rgb_to_hex() -> None:
    assert rgb_to_hex((255, 0, 0)) == "#ff0000"
    assert rgb_to_hex((0, 255, 0)) == "#00ff00"
    assert rgb_to_hex((0, 0, 255)) == "#0000ff"


def test_desktop_app_full() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        app = AimBotDesktopApp(root)
        assert app is not None
        assert app.worker is not None
        # Test tab switching across all 6 VORTX panels
        for t_idx in range(6):
            app._switch_tab(t_idx)
            assert app._active_tab == t_idx
        # Clean shutdown
        # Test Mini HUD and mouse protection
        app.disable_mouse_var.set(True)
        app._on_disable_mouse_toggle()
        assert app.cfg.disable_mouse_movement is True

        app.open_mini_hud()
        assert app._mini_hud is not None
        assert app._mini_hud.win.winfo_exists()
        app._mini_hud.update_status(True)
        app._mini_hud.update_status(False)
        app._mini_hud.close()
        assert app._mini_hud is None

        # Test Chiaki auto-detect function
        app.auto_detect_chiaki()
        assert app._active_src_mode == app.SRC_WINDOW

        # Default should be controller mode
        assert app.input_mode_var.get() == "controller"
        assert app.cfg.controller_mode is True

        # Toggle to mouse mode
        app.input_mode_var.set("mouse")
        app._on_input_mode_change()
        assert app.cfg.controller_mode is False

        # Toggle back to controller mode
        app.input_mode_var.set("controller")
        app._on_input_mode_change()
        assert app.cfg.controller_mode is True

        # Test FOV radius change
        app._on_fov_radius_change("320")
        assert app.cfg.fov_radius_px == 320.0
        assert app.worker._smart_detector.fov_radius == 320.0

        # Test Max area change
        app._on_max_area_change("7500")
        assert app.cfg.max_target_area_px == 7500.0
        assert app.worker._smart_detector.max_area == 7500.0

        # Test Intensity Presets
        app._select_intensity("SUPER")
        assert app.cfg.intensity_profile == "SUPER"
        assert app.cfg.aim_speed == 0.85
        assert app.cfg.smoothing == 0.15
        assert app.cfg.fov_radius_px == 450.0

        app._select_intensity("SOFT")
        assert app.cfg.intensity_profile == "SOFT"
        assert app.cfg.aim_speed == 0.20
        assert app.cfg.smoothing == 0.70
        assert app.cfg.fov_radius_px == 160.0

        # Test Target Priority Selection
        app._select_target_priority("MARKER")
        assert app.cfg.target_priority == "MARKER"
        assert app.cfg.vertical_offset_px == 0.0
        app._select_target_priority("HEAD")
        assert app.cfg.target_priority == "HEAD"
        app._select_target_priority("RANDOM")
        assert app.cfg.target_priority == "RANDOM"
        app._select_target_priority("CHEST")
        assert app.cfg.target_priority == "CHEST"

        # Test Controller Remapping & Presets
        app._on_binding_change("AIM_TRIGGER", "LT")
        assert app.cfg.controller_bindings["AIM_TRIGGER"] == "LT"
        assert app.cfg.aim_trigger == "LT"

        app._on_binding_change("FIRE_TRIGGER", "RT")
        assert app.cfg.controller_bindings["FIRE_TRIGGER"] == "RT"
        assert app.cfg.fire_trigger == "RT"

        # Test Stick Tuning Sliders & Real-Time Persistence
        app._on_stick_sens_drag(2.45)
        assert app.cfg.stick_sensitivity == 2.45
        assert app.cfg.controller_bindings["STICK_SENSITIVITY"] == 2.45

        app._on_stick_smoothing_drag(0.25)
        assert app.cfg.stick_smoothing == 0.25
        assert app.cfg.controller_bindings["STICK_SMOOTHING"] == 0.25

        app._apply_controller_preset({
            "AIM_TRIGGER": "LB",
            "FIRE_TRIGGER": "RB",
            "TACTICAL_JUMP": "L2",
            "SLIDE_CANCEL_PRONE": "R3",
            "MELEE_ACTION": "R2",
        })
        assert app.cfg.controller_bindings["AIM_TRIGGER"] == "LB"
        assert app.cfg.aim_trigger == "LB"
        assert app.cfg.controller_bindings["FIRE_TRIGGER"] == "RB"
        assert app.cfg.fire_trigger == "RB"
        assert app.cfg.controller_bindings["TACTICAL_JUMP"] == "L2"
        assert app.cfg.controller_bindings["SLIDE_CANCEL_PRONE"] == "R3"
        assert app.cfg.controller_bindings["MELEE_ACTION"] == "R2"

        # Test Vertical Offset
        app._on_vertical_offset_drag(-15.0)
        assert app.cfg.vertical_offset_px == -15.0

        # Test VORTX Advanced Controller & Kinematics Settings
        app._on_power_exponent_drag(1.25)
        assert app.cfg.power_exponent == 1.25

        app._on_reversal_damp_drag(0.40)
        assert app.cfg.reversal_damping == 0.40

        app._on_stick_breakaway_drag(0.12)
        assert app.cfg.stick_min_breakaway == 0.12

        app._on_trigger_thresh_drag(0.10)
        assert app.cfg.trigger_threshold == 0.10

        app._on_head_bias_drag(0.65)
        assert app.cfg.head_bias_percent == 0.65

        app._on_recoil_v_drag(12.5)
        assert app.cfg.recoil_vertical_px == 12.5

        app._on_recoil_h_drag(-2.0)
        assert app.cfg.recoil_horizontal_px == -2.0

        app._on_recoil_delay_drag(45.0)
        assert app.cfg.recoil_delay_ms == 45.0

        app.static_rejection_var.set(True)
        app._toggle_static_rejection()
        assert app.cfg.static_prop_rejection is True

        app.triggerbot_var.set(True)
        app._toggle_triggerbot()
        assert app.cfg.triggerbot_enabled is True

        app._on_close()
    finally:
        try:
            root.destroy()
        except Exception:
            pass


