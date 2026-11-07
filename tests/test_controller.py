"""Unit tests for bot controller."""

from random import Random

import config
from bot.capture import ScreenRegion
from bot.controller import BotController, CursorFns, StepStatus
from bot.vision import Detection


def test_controller_step_lifecycle() -> None:
    cursor_pos = [100, 100]
    click_log: list[tuple[int, int]] = []

    def mock_pos() -> tuple[int, int]:
        return cursor_pos[0], cursor_pos[1]

    def mock_move(x: int, y: int) -> None:
        cursor_pos[0] = x
        cursor_pos[1] = y

    def mock_click(x: int, y: int) -> None:
        click_log.append((x, y))

    fns = CursorFns(position=mock_pos, move=mock_move, click=mock_click)
    current_time = [10.0]

    cfg = config.Config(
        aim_speed=0.5,
        smoothing=1.0,
        humanize=False,
        click_cooldown_ms=100.0,
    )
    controller = BotController(
        cfg,
        cursor=fns,
        clock=lambda: current_time[0],
        rng=Random(42),
    )

    region = ScreenRegion(0, 0, 1000, 800)

    # 1. No target
    res_none = controller.step(None, region)
    assert res_none.status == StepStatus.NO_TARGET

    # 2. Distant target -> MOVING
    detection = Detection(x=500.0, y=500.0, radius=28.0, area=2400.0, bbox=(472, 472, 56, 56))
    res_moving = controller.step(detection, region)
    assert res_moving.status == StepStatus.MOVING
    assert res_moving.moved is True
    assert cursor_pos[0] > 100

    # 3. Target close -> CLICKED
    cursor_pos[0] = 500
    cursor_pos[1] = 500
    res_click = controller.step(detection, region)
    assert res_click.status == StepStatus.CLICKED
    assert res_click.clicked is True
    assert len(click_log) == 1

    # 4. Immediate next step -> COOLDOWN
    res_cooldown = controller.step(detection, region)
    assert res_cooldown.status == StepStatus.COOLDOWN
    assert len(click_log) == 1


def test_controller_resets_smoothing_on_trainer_respawn() -> None:
    cursor = CursorFns(
        position=lambda: (0, 0),
        move=lambda x, y: None,
        click=lambda x, y: None,
    )
    controller = BotController(
        config.Config(),
        cursor=cursor,
        jump_reset_px=config.TRAINER_JUMP_RESET_PX,
    )
    controller._smooth_target(100.0, 100.0, 28.0)

    respawn = controller._smooth_target(280.0, 100.0, 28.0)

    assert respawn == (280.0, 100.0)


def test_apply_stick_deflection_and_deadzone() -> None:
    class MockVPad:
        def __init__(self) -> None:
            self.last_rx = None
            self.last_ry = None
            self.update_count = 0

        def right_joystick_float(self, x_value_float: float, y_value_float: float) -> None:
            self.last_rx = x_value_float
            self.last_ry = y_value_float

        def update(self) -> None:
            self.update_count += 1

    mock_vpad = MockVPad()
    cfg = config.Config(fov_radius_px=200.0)
    controller = BotController(cfg, vpad=mock_vpad)

    # 1. Deadzone: abs(val) < 3px returns 0
    rx, ry = controller.apply_stick_deflection(dx=2.5, dy=-2.0, sens=1.0, smoothing=0.0)
    assert rx == 0.0
    assert ry == 0.0
    assert mock_vpad.last_rx == 0.0
    assert mock_vpad.last_ry == 0.0
    assert mock_vpad.update_count == 1

    # 2. Deflection past deadzone with smoothing=0.0 and linear power_exponent=1.0
    rx, ry = controller.apply_stick_deflection(dx=100.0, dy=50.0, sens=1.0, smoothing=0.0, power_exponent=1.0)
    assert rx == 0.5  # 100 / 200 = 0.5
    assert ry == 0.25 # 50 / 200 = 0.25
    assert mock_vpad.last_rx == 0.5
    assert mock_vpad.last_ry == 0.25

    # 3. Non-linear power curve: 0.5^1.4 ≈ 0.3789
    rx_curved, ry_curved = controller.apply_stick_deflection(dx=100.0, dy=50.0, sens=1.0, smoothing=0.0, power_exponent=1.4)
    assert round(rx_curved, 3) == 0.379
    assert round(ry_curved, 3) == 0.144

    # 4. Directional reversal damping: flipping sign dampens deflection by 0.40
    # Current x deflection is positive (0.379); now flip to dx = -100.0
    rx_rev, _ = controller.apply_stick_deflection(dx=-100.0, dy=0.0, sens=1.0, smoothing=0.0, power_exponent=1.0, reversal_damping=0.40)
    assert round(rx_rev, 2) == -0.20  # -0.5 * 0.40 = -0.20

    # 5. Clamped to [-1.0, 1.0] (fresh direction)
    controller.reset()
    rx_clamped, ry_clamped = controller.apply_stick_deflection(dx=500.0, dy=-600.0, sens=2.0, smoothing=0.0, power_exponent=1.0)
    assert rx_clamped == 1.0
    assert ry_clamped == -1.0


def test_apply_stick_deflection_smoothing_and_reset() -> None:
    class MockVPad:
        def __init__(self) -> None:
            self.last_rx = 0.0
            self.last_ry = 0.0
            self.update_count = 0

        def right_joystick_float(self, x_value_float: float, y_value_float: float) -> None:
            self.last_rx = x_value_float
            self.last_ry = y_value_float

        def update(self) -> None:
            self.update_count += 1

    mock_vpad = MockVPad()
    cfg = config.Config(fov_radius_px=200.0)
    controller = BotController(cfg, vpad=mock_vpad)

    # Apply with heavy smoothing (e.g. 0.5)
    rx1, ry1 = controller.apply_stick_deflection(dx=200.0, dy=0.0, sens=1.0, smoothing=0.5)
    # Target is 1.0, alpha is 0.5, so rx1 is 0.5
    assert 0.49 < rx1 < 0.51

    rx2, ry2 = controller.apply_stick_deflection(dx=200.0, dy=0.0, sens=1.0, smoothing=0.5)
    # LERP approaches 1.0 (0.5 + (1.0 - 0.5)*0.5 = 0.75)
    assert 0.74 < rx2 < 0.76

    # Test reset_stick
    controller.reset_stick()
    assert mock_vpad.last_rx == 0.0
    assert mock_vpad.last_ry == 0.0
    assert controller._current_stick_x == 0.0
    assert controller._current_stick_y == 0.0
