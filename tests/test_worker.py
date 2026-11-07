"""Unit tests for BotWorker lifecycle and operations."""

import config
import numpy as np
from bot.capture import Frame, ScreenRegion
from bot.controller import CursorFns
from bot.worker import BotWorker
from bot.vision import Detection


def test_bot_worker_instantiation() -> None:
    cfg = config.Config(bot_enabled=False, debug_view=True)
    worker = BotWorker(
        cfg=cfg,
        window_handle_getter=lambda: 0,  # Mock invalid HWND
    )

    assert worker._running is False
    # Single step with invalid HWND shouldn't crash
    res = worker.step()
    assert res is None

    # Debug view should return a valid object
    debug = worker.get_debug_view()
    assert debug is not None


def test_bot_worker_start_stop() -> None:
    cfg = config.Config(bot_enabled=False)
    worker = BotWorker(
        cfg=cfg,
        window_handle_getter=lambda: 0,
    )

    worker.start()
    assert worker._running is True
    assert worker._thread is not None and worker._thread.is_alive()

    worker.stop()
    assert worker._running is False
    assert worker._thread is None


def test_preview_only_detects_without_controller_actions() -> None:
    cfg = config.Config(bot_enabled=True)
    region = ScreenRegion(10, 20, 100, 80)
    frame = Frame(
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        region=region,
        captured_at=1.0,
    )

    class FakeCapture:
        def grab(self) -> Frame:
            return frame

    worker = BotWorker(cfg=cfg, region_getter=lambda: region)
    worker.refresh_region = lambda: region  # type: ignore[method-assign]
    worker._capture = FakeCapture()  # type: ignore[assignment]
    detection = Detection(30.0, 40.0, 10.0, 300.0, (20, 30, 20, 20))
    worker._smart_detector.detect = lambda image: detection  # type: ignore[method-assign]
    worker._update_debug_view = lambda *args: None  # type: ignore[method-assign]
    worker._controller.step = lambda *args: (_ for _ in ()).throw(  # type: ignore[method-assign]
        AssertionError("preview must not invoke the controller")
    )

    worker.set_preview_only(True)
    result = worker.preview_step()

    assert result is detection
    assert cfg.bot_enabled is False
    assert "مكتشف عند (30, 40)" in worker.get_preview_status()
    assert worker._controller.move_count == 0
    assert worker._controller.click_count == 0


def test_worker_preview_png_generation() -> None:
    cfg = config.Config(bot_enabled=False)
    region = ScreenRegion(0, 0, 100, 100)
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[40:60, 40:60] = [0, 0, 255]
    frame = Frame(image=img, region=region, captured_at=1.0)

    class FakeCapture:
        def grab(self) -> Frame:
            return frame

    worker = BotWorker(cfg=cfg, region_getter=lambda: region)
    worker.refresh_region = lambda: region  # type: ignore[method-assign]
    worker._capture = FakeCapture()  # type: ignore[assignment]
    worker.set_preview_only(True)
    worker.preview_step()

    png_bytes = worker.get_latest_preview_png(max_width=80, max_height=80)
    assert png_bytes is not None
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_controller_mode_gates_aim_assist() -> None:
    from bot.gamepad import GamepadState

    cfg = config.Config(bot_enabled=True, controller_mode=True, controller_lt_aim=True)
    region = ScreenRegion(0, 0, 200, 200)
    frame = Frame(image=np.zeros((200, 200, 3), dtype=np.uint8), region=region, captured_at=1.0)

    class FakeCapture:
        def grab(self) -> Frame:
            return frame

    worker = BotWorker(cfg=cfg, region_getter=lambda: region)
    worker.refresh_region = lambda: region  # type: ignore[method-assign]
    worker._capture = FakeCapture()  # type: ignore[assignment]
    worker._is_cursor_in_virtual_corner = lambda: False  # type: ignore[method-assign]
    cursor_pos = [50, 50]
    worker._controller._position = lambda: (cursor_pos[0], cursor_pos[1])  # type: ignore[method-assign]
    worker._controller._move = lambda x, y: cursor_pos.__setitem__(0, x)  # type: ignore[method-assign]

    detection = Detection(100.0, 100.0, 15.0, 700.0, (85, 85, 30, 30))
    worker._smart_detector.detect = lambda image: detection  # type: ignore[method-assign]

    # 1. Controller is idle (LT not pressed: is_aiming = False)
    worker._gamepad.poll = lambda: GamepadState(connected=True, left_trigger=0.0, is_aiming=False)  # type: ignore[method-assign]
    result_idle = worker.step()
    # Must NOT move mouse or click when LT is not held!
    assert result_idle is None
    assert worker._controller.move_count == 0

    # 2. Controller is aiming (LT pressed: is_aiming = True)
    worker._gamepad.poll = lambda: GamepadState(connected=True, left_trigger=0.85, is_aiming=True)  # type: ignore[method-assign]
    result_aiming = worker.step()
    assert result_aiming is not None
    assert result_aiming.moved is True


def test_vgamepad_updates_with_disable_mouse_movement() -> None:
    from bot.gamepad import GamepadState

    cfg = config.Config(
        bot_enabled=True,
        input_mode="vgamepad",
        aim_trigger="LT",
        controller_lt_aim=True,
        disable_mouse_movement=True,  # Physical mouse frozen!
    )
    region = ScreenRegion(0, 0, 200, 200)
    frame = Frame(image=np.zeros((200, 200, 3), dtype=np.uint8), region=region, captured_at=1.0)

    class FakeCapture:
        def grab(self) -> Frame:
            return frame

    class MockVPad:
        def __init__(self) -> None:
            self.last_rx = 0.0
            self.last_ry = 0.0
            self.updates = 0

        def right_joystick_float(self, x_value_float: float, y_value_float: float) -> None:
            self.last_rx = x_value_float
            self.last_ry = y_value_float

        def update(self) -> None:
            self.updates += 1

    worker = BotWorker(cfg=cfg, region_getter=lambda: region)
    mock_vpad = MockVPad()
    worker._controller.vpad = mock_vpad
    worker.refresh_region = lambda: region  # type: ignore[method-assign]
    worker._capture = FakeCapture()  # type: ignore[assignment]
    worker._is_cursor_in_virtual_corner = lambda: False  # type: ignore[method-assign]

    # Target placed away from center (center is 100, 100)
    detection = Detection(160.0, 140.0, 15.0, 700.0, (145, 125, 30, 30))
    worker._smart_detector.detect = lambda image: detection  # type: ignore[method-assign]

    # Holding LT (is_aiming = True)
    worker._gamepad.poll = lambda **kwargs: GamepadState(connected=True, left_trigger=1.0, is_aiming=True)  # type: ignore[method-assign]
    res = worker.step()

    assert res is not None
    assert res.moved is True
    # Virtual gamepad updated despite disable_mouse_movement=True
    assert mock_vpad.updates > 0
    assert mock_vpad.last_rx > 0.0

    # When aim trigger released, stick is reset immediately
    worker._gamepad.poll = lambda **kwargs: GamepadState(connected=True, left_trigger=0.0, is_aiming=False)  # type: ignore[method-assign]
    res_released = worker.step()
    assert res_released is None
    assert mock_vpad.last_rx == 0.0
    assert mock_vpad.last_ry == 0.0



