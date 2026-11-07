"""Background worker managing the vision capture, detection, and mouse control loop.

This module decouples the bot's capture-detect-act loop from the pygame rendering
thread. It runs at :data:`config.BOT_TARGET_HZ` (30 Hz) by default, ensuring
ultra-fast responsiveness while maintaining a rock-solid 60 FPS interface.
"""

from __future__ import annotations

import collections
import ctypes
import math
import threading
import time
from typing import Callable, Final

import cv2
import numpy as np
import pygame

import config
from bot.assistant import AIAssistant, PredictiveAimModel, SmartTargetDetector
from bot.capture import (
    CaptureError,
    ScreenCapture,
    ScreenRegion,
    play_area_region,
    virtual_screen_rect,
)
from bot.controller import BotController, ControllerError, StepResult, StepStatus
from bot.gamepad import GamepadManager, GamepadState
from bot.local_ai_detector import LocalAIDetector
from bot.roboflow_detector import RoboflowDetection, RoboflowDetector
from bot.vision import ColorDetector, Detection, Detector, get_circular_stencil
from core.ui import DebugView

__all__ = ["BotWorker"]


class BotWorker:
    """Threaded manager running the real-time screen capture and aim bot loop."""

    def __init__(
        self,
        cfg: config.Config,
        window_handle_getter: Callable[[], int] | None = None,
        *,
        on_stop: Callable[[str], None] | None = None,
        region_getter: Callable[[], ScreenRegion | None] | None = None,
        jump_reset_px: float = config.JUMP_RESET_PX,
    ) -> None:
        """Create the bot worker.

        Args:
            cfg: Live configuration shared with the control panel.
            window_handle_getter: Callable returning the current native window HWND.
            on_stop: Callback invoked when the bot self-terminates (e.g. corner stop).
            region_getter: Optional callable returning custom ScreenRegion (for desktop/screen mode).
        """
        self.cfg = cfg
        self._get_hwnd = window_handle_getter
        self._on_stop = on_stop
        self._region_getter = region_getter

        # Detectors
        self._color_detector = ColorDetector()
        self._color_detector.configure(cfg)
        self._smart_detector = SmartTargetDetector()
        self._smart_detector.configure(cfg)
        self._local_ai_detector = LocalAIDetector()
        self._local_ai_detector.configure(cfg)
        self._roboflow_detector = RoboflowDetector()

        # AI Assistant Models
        self._assistant = AIAssistant(cfg)
        self._predictor = self._assistant.predictor
        self._predictor.jump_reset_px = max(0.0, float(jump_reset_px))

        # Controller & Gamepad
        self._controller = BotController(cfg, jump_reset_px=jump_reset_px)
        self._gamepad = GamepadManager()
        self._latest_gamepad_state = GamepadState()

        # Screen capture instance
        self._capture: ScreenCapture | None = None
        self._active_region: ScreenRegion | None = None

        # Threading state
        self._thread: threading.Thread | None = None
        self._running = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._mode_lock = threading.Lock()
        self._preview_only = False
        self._preview_status = "المعاينة متوقفة"
        self._latest_annotated_frame: np.ndarray | None = None
        self._latest_detection: Detection | None = None

        # Diagnostics & Debug overlay
        self._debug_snapshot = DebugView()
        self._path_history: collections.deque[tuple[float, float]] = collections.deque(
            maxlen=config.BOT_PATH_POINTS
        )
        self._consecutive_capture_failures = 0
        self._last_tick_time = 0.0
        self._loop_hz = 0.0
        self._last_latency_ms = 0.0
        self._firing_start_time: float | None = None
        self._local_ai_tick_counter = 0
        self._cached_local_ai_detection: Detection | None = None
        self._last_local_ai_time: float = 0.0

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Start the background worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="AimBotWorkerThread",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the background worker thread to terminate and join."""
        self._running = False
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._close_capture()

    def set_preview_only(self, enabled: bool) -> None:
        """Enable screen analysis without allowing cursor movement or clicks."""
        with self._mode_lock:
            self._preview_only = bool(enabled)
            if self._preview_only:
                self.cfg.bot_enabled = False
                self._controller.reset()
                self._predictor.reset()
            with self._lock:
                self._preview_status = (
                    "المعاينة تعمل بدون تحريك أو نقر"
                    if self._preview_only
                    else "المعاينة متوقفة"
                )

    def get_preview_status(self) -> str:
        """Return the latest read-only detection and tracking summary."""
        with self._lock:
            return self._preview_status

    def _close_capture(self) -> None:
        """Release screen grabber resource."""
        if self._capture is not None:
            self._capture.close()
            self._capture = None

    # -- region management -------------------------------------------------

    def refresh_region(self) -> ScreenRegion | None:
        """Re-query window geometry or screen FOV and ensure grabber is up-to-date."""
        if self._region_getter is not None:
            region = self._region_getter()
        elif self._get_hwnd is not None:
            hwnd = self._get_hwnd()
            if not hwnd:
                return None
            region = play_area_region(hwnd)
        else:
            region = None

        if region is None:
            return None

        if self._active_region != region:
            self._active_region = region
            backend = str(getattr(self.cfg, "capture_backend", "auto"))
            if self._capture is not None:
                self._capture.set_region(region)
            else:
                self._capture = ScreenCapture(region, backend=backend)
        return self._active_region

    # -- execution step ----------------------------------------------------

    def step(self) -> StepResult | None:
        """Execute one complete capture -> detect -> aim -> act iteration."""
        tick_start = time.perf_counter()

        # Check emergency corner fail-safe gesture
        if self._is_cursor_in_virtual_corner():
            self._handle_emergency_stop(
                "Emergency stop triggered (cursor moved to screen corner)."
            )
            return None

        # 1. ALWAYS poll Gamepad state immediately at the start of tick
        b = dict(getattr(self.cfg, "controller_bindings", {}))
        is_controller_mode = bool(getattr(self.cfg, "controller_mode", True))
        if is_controller_mode:
            try:
                gp_state = self._gamepad.poll(bindings=b)
            except TypeError:
                gp_state = self._gamepad.poll()
            except Exception:
                gp_state = GamepadState()
        else:
            gp_state = GamepadState()
        with self._lock:
            self._latest_gamepad_state = gp_state

        region = self.refresh_region()
        if region is None or self._capture is None:
            self._consecutive_capture_failures += 1
            if self._consecutive_capture_failures >= config.BOT_MAX_CAPTURE_FAILURES:
                self._handle_emergency_stop("Lost track of game window bounds.")
            return None

        # Capture play area frame
        try:
            frame = self._capture.grab()
            self._consecutive_capture_failures = 0
        except CaptureError as exc:
            self._consecutive_capture_failures += 1
            if self._consecutive_capture_failures >= config.BOT_MAX_CAPTURE_FAILURES:
                self._handle_emergency_stop(f"Screen capture failure: {exc}")
            return None

        # Apply live configuration
        use_ai = bool(getattr(self.cfg, "ai_assistant", True))
        active_detector: Detector
        if use_ai:
            self._smart_detector.configure(self.cfg)
            active_detector = self._smart_detector
        else:
            self._color_detector.configure(self.cfg)
            active_detector = self._color_detector

        # Localise target (Hybrid: Priority 1 = Fast Marker/Color, Priority 2 = DirectML Local Neural AI, Priority 3 = Cloud)
        detection = active_detector.detect(frame.image)

        if detection is None and bool(getattr(self.cfg, "use_local_ai", False)):
            self._local_ai_tick_counter += 1
            # Run local neural inference on cadence (every 2nd frame) to maintain smooth 45-60 FPS
            if self._local_ai_tick_counter % 2 == 0 or self._cached_local_ai_detection is None:
                self._local_ai_detector.configure(self.cfg)
                new_det = self._local_ai_detector.detect(frame.image)
                if new_det is not None:
                    self._cached_local_ai_detection = new_det
                    self._last_local_ai_time = time.perf_counter()
                else:
                    self._cached_local_ai_detection = None
                detection = new_det
            else:
                if self._cached_local_ai_detection is not None and (time.perf_counter() - self._last_local_ai_time < 0.20):
                    detection = self._cached_local_ai_detection

        if detection is None and bool(getattr(self.cfg, "use_roboflow_ai", False)):
            self._roboflow_detector.submit_frame_async(frame.image)
            cx, cy = frame.image.shape[1] // 2, frame.image.shape[0] // 2
            fov_r = float(getattr(self.cfg, "fov_radius_px", 250.0))
            max_a = float(getattr(self.cfg, "max_target_area_px", 5000.0))
            detection = self._roboflow_detector.select_best_target(cx, cy, fov_r, max_a)

        # AI Predictive target position & Priority offset
        target_pri = getattr(self.cfg, "target_priority", "CHEST")
        vert_offset = float(
            getattr(self.cfg, "vertical_offset", getattr(self.cfg, "vertical_offset_px", 0.0))
        )
        if detection is not None:
            tx = detection.x
            ty = detection.y
            if target_pri == "HEAD":
                body_h = float(detection.bbox[3]) if (detection.bbox and len(detection.bbox) >= 4) else (detection.radius * 2.0)
                body_cy = float(detection.y)
                aim_bias = float(getattr(self.cfg, "head_bias_percent", 0.70))
                ty = body_cy - (body_h * 0.35 * aim_bias)
            elif target_pri == "RANDOM":
                import random
                ty = detection.y + random.uniform(-0.25, 0.15) * detection.radius
            elif target_pri == "CHEST":
                ty = detection.bbox[1] + detection.bbox[3] * 0.50
            # If target_pri == "MARKER", ty remains detection.y (aim directly at marker)

            if vert_offset != 0.0:
                ty -= vert_offset

            pred_x, pred_y = (tx, ty)
            if use_ai:
                pred_x, pred_y = self._predictor.update_and_predict(
                    tx,
                    ty,
                    frame.captured_at,
                    custom_latency_s=min(0.040, self._last_latency_ms / 1000.0),
                )
            # Use predicted coordinates for aiming
            aim_detection = Detection(
                x=pred_x,
                y=pred_y,
                radius=detection.radius,
                area=detection.area,
                bbox=detection.bbox,
            )
        else:
            pred_x, pred_y = (0.0, 0.0)
            aim_detection = None
            self._predictor.reset()

        # Telemetry & Gamepad Binding Configuration
        b = dict(getattr(self.cfg, "controller_bindings", {}))
        input_mode = str(getattr(self.cfg, "input_mode", getattr(self.cfg, "INPUT_MODE", "vgamepad"))).lower()
        aim_trigger = str(getattr(self.cfg, "aim_trigger", getattr(self.cfg, "AIM_TRIGGER", b.get("AIM_TRIGGER", "LT")))).strip()
        fire_trigger = str(getattr(self.cfg, "fire_trigger", getattr(self.cfg, "FIRE_TRIGGER", b.get("FIRE_TRIGGER", "RT")))).strip()
        stick_sens = float(getattr(self.cfg, "stick_sensitivity", getattr(self.cfg, "STICK_SENSITIVITY", b.get("STICK_SENSITIVITY", 1.25))))
        stick_smoothing = float(getattr(self.cfg, "stick_smoothing", getattr(self.cfg, "STICK_SMOOTHING", b.get("STICK_SMOOTHING", 0.35))))

        b["INPUT_MODE"] = input_mode
        b["AIM_TRIGGER"] = aim_trigger
        b["FIRE_TRIGGER"] = fire_trigger
        b["STICK_SENSITIVITY"] = stick_sens
        b["STICK_SMOOTHING"] = stick_smoothing
        b["TRIGGER_THRESHOLD"] = float(getattr(self.cfg, "trigger_threshold", 0.15))

        gp_state = self._latest_gamepad_state

        # Check active aim-trigger binding
        is_aim_active = False
        aim_upper = aim_trigger.upper()
        if aim_upper in ("ALWAYS", "AUTO"):
            is_aim_active = True
        elif aim_upper == "RMB":
            try:
                if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
                    is_aim_active = bool(ctypes.windll.user32.GetAsyncKeyState(0x02) & 0x8000)
            except Exception:
                is_aim_active = False
        else:
            if gp_state.connected:
                is_aim_active = gp_state.is_aiming
            else:
                # Fallback when physical gamepad is not plugged in: check RMB or allow aim
                try:
                    if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
                        is_aim_active = bool(ctypes.windll.user32.GetAsyncKeyState(0x02) & 0x8000)
                except Exception:
                    is_aim_active = False
                if not is_aim_active and not bool(getattr(self.cfg, "controller_lt_aim", True)):
                    is_aim_active = True

        # If no target is present or trigger is released, immediately call controller.reset_stick()
        if not is_aim_active or detection is None:
            if input_mode == "vgamepad" and gp_state.connected:
                self._controller.pass_through_gamepad(gp_state, aim_rx=0.0, aim_ry=0.0, triggerbot_active=False)
            else:
                self._controller.reset_stick()
            if detection is None:
                self._predictor.reset()
            now = time.perf_counter()
            elapsed_ms = (now - tick_start) * 1000.0
            self._last_latency_ms = elapsed_ms
            self._update_debug_view(active_detector, detection, (pred_x, pred_y), elapsed_ms)
            self._annotate_and_store_preview(frame.image, detection, (pred_x, pred_y), gp_state)
            with self._lock:
                self._latest_detection = detection
                if gp_state.connected and not is_aim_active:
                    self._preview_status = (
                        f"🎮 يد متصلة ({gp_state.device_name}) — اضغط {aim_trigger} للتصويب | {aim_trigger}: غير مضغوط"
                    )
                elif detection is None:
                    self._preview_status = "👁️ بانتظار ظهور هدف داخل مجال الرؤية"
            return None

        # Mode lock check for preview mode
        with self._mode_lock:
            if self._preview_only:
                self._controller.reset_stick()
                return None

        # Compute (dx, dy) from screen center
        h, w = frame.image.shape[:2]
        cx, cy = w / 2.0, h / 2.0
        dx = float(pred_x - cx)
        dy = float(pred_y - cy)

        result: StepResult | None = None
        disable_mouse = bool(getattr(self.cfg, "disable_mouse_movement", False))

        # Telemetry & Actuation
        if input_mode == "vgamepad":
            # Virtual joystick updates seamlessly regardless of disable_mouse_movement
            is_firing_raw = bool(self._latest_gamepad_state.is_firing)
            now_sec = time.perf_counter()
            if is_firing_raw:
                if self._firing_start_time is None:
                    self._firing_start_time = now_sec
                recoil_delay_s = float(getattr(self.cfg, "recoil_delay_ms", 0.0)) / 1000.0
                is_firing = (now_sec - self._firing_start_time) >= recoil_delay_s
            else:
                self._firing_start_time = None
                is_firing = False

            # Check triggerbot (Automatic weapon discharge on target alignment)
            triggerbot_fire = False
            if bool(getattr(self.cfg, "triggerbot_enabled", False)) and detection is not None:
                dist = math.hypot(dx, dy)
                if dist <= max(14.0, detection.radius * 0.45):
                    triggerbot_fire = True

            rx, ry = self._controller.apply_stick_deflection(
                dx, dy, sens=stick_sens, smoothing=stick_smoothing, is_firing=is_firing
            )

            if gp_state.connected:
                rx, ry = self._controller.pass_through_gamepad(
                    gp_state, aim_rx=rx, aim_ry=ry, triggerbot_active=triggerbot_fire
                )
            else:
                if triggerbot_fire and hasattr(self._controller, "vpad") and self._controller.vpad is not None:
                    try:
                        self._controller.vpad.right_trigger_float(value_float=1.0)
                        self._controller.vpad.update()
                    except Exception:
                        pass
            pos = self._controller._read_position()
            result = StepResult(
                status=StepStatus.MOVING if (abs(rx) > 0.0 or abs(ry) > 0.0) else StepStatus.NO_TARGET,
                detection=aim_detection,
                target=(pred_x, pred_y),
                cursor_before=pos,
                cursor_after=pos,
                distance_before=math.hypot(dx, dy),
                distance_after=math.hypot(dx, dy),
                moved=True,
                clicked=False,
                elapsed_ms=(time.perf_counter() - tick_start) * 1000.0,
            )
        elif input_mode == "sendinput":
            self._controller.reset_stick()
            # disable_mouse_movement only freezes physical mouse input
            if not disable_mouse:
                try:
                    result = self._controller.step(aim_detection, region)
                except ControllerError as exc:
                    self._handle_emergency_stop(str(exc))
                    return None
            else:
                result = None
        else:  # overlay_only
            self._controller.reset_stick()
            result = None

        now = time.perf_counter()
        elapsed_ms = (now - tick_start) * 1000.0
        self._last_latency_ms = elapsed_ms

        # Record debug diagnostics
        if detection is not None and result is not None:
            # Play-area local cursor position for path overlay
            local_cursor = (
                float(result.cursor_after[0] - region.left),
                float(result.cursor_after[1] - region.top),
            )
            self._path_history.append(local_cursor)

        self._update_debug_view(active_detector, detection, (pred_x, pred_y), elapsed_ms)
        self._annotate_and_store_preview(frame.image, detection, (pred_x, pred_y), gp_state)
        with self._lock:
            self._latest_detection = detection
            if input_mode == "vgamepad":
                self._preview_status = (
                    f"🎯 تصويب يد افتراضية (vgamepad) نشط | دقة: Δ({dx:+.1f}, {dy:+.1f}) | {aim_trigger}: نشط"
                )
            elif disable_mouse:
                self._preview_status = (
                    f"🎯 قفل بصري نشط عند ({detection.x:.0f}, {detection.y:.0f}) — ماوس اللاب محمي"
                )
        return result

    def preview_step(self) -> Detection | None:
        """Capture and analyze one frame without invoking the controller."""
        tick_start = time.perf_counter()
        region = self.refresh_region()
        if region is None or self._capture is None:
            with self._lock:
                self._preview_status = "النافذة المختارة غير متاحة"
            self._predictor.reset()
            return None

        try:
            frame = self._capture.grab()
            self._consecutive_capture_failures = 0
        except CaptureError as exc:
            with self._lock:
                self._preview_status = f"تعذر التقاط النافذة: {exc}"
            self._predictor.reset()
            return None

        use_ai = bool(getattr(self.cfg, "ai_assistant", True))
        active_detector: Detector
        if use_ai:
            self._smart_detector.configure(self.cfg)
            active_detector = self._smart_detector
        else:
            self._color_detector.configure(self.cfg)
            active_detector = self._color_detector

        # Localise target (Hybrid: Priority 1 = Fast Marker/Color, Priority 2 = DirectML Local Neural AI, Priority 3 = Cloud)
        detection = active_detector.detect(frame.image)

        if detection is None and bool(getattr(self.cfg, "use_local_ai", False)):
            self._local_ai_tick_counter += 1
            # Run local neural inference on cadence (every 2nd frame) to maintain smooth 45-60 FPS
            if self._local_ai_tick_counter % 2 == 0 or self._cached_local_ai_detection is None:
                self._local_ai_detector.configure(self.cfg)
                new_det = self._local_ai_detector.detect(frame.image)
                if new_det is not None:
                    self._cached_local_ai_detection = new_det
                    self._last_local_ai_time = time.perf_counter()
                else:
                    self._cached_local_ai_detection = None
                detection = new_det
            else:
                if self._cached_local_ai_detection is not None and (time.perf_counter() - self._last_local_ai_time < 0.20):
                    detection = self._cached_local_ai_detection

        if detection is None and bool(getattr(self.cfg, "use_roboflow_ai", False)):
            self._roboflow_detector.submit_frame_async(frame.image)
            cx, cy = frame.image.shape[1] // 2, frame.image.shape[0] // 2
            fov_r = float(getattr(self.cfg, "fov_radius_px", 250.0))
            max_a = float(getattr(self.cfg, "max_target_area_px", 5000.0))
            detection = self._roboflow_detector.select_best_target(cx, cy, fov_r, max_a)

        # AI Predictive target position & Priority offset
        target_pri = getattr(self.cfg, "target_priority", "CHEST")
        vert_offset = float(
            getattr(self.cfg, "vertical_offset", getattr(self.cfg, "vertical_offset_px", 15.0))
        )
        if detection is not None:
            tx = detection.x
            ty = detection.y
            if target_pri == "HEAD":
                body_h = float(detection.bbox[3]) if (detection.bbox and len(detection.bbox) >= 4) else (detection.radius * 2.0)
                body_cy = float(detection.y)
                aim_bias = float(getattr(self.cfg, "head_bias_percent", 0.70))
                ty = body_cy - (body_h * 0.35 * aim_bias)
            elif target_pri == "RANDOM":
                import random
                ty = detection.y + random.uniform(-0.25, 0.15) * detection.radius

            if vert_offset > 0:
                ty -= vert_offset
            elif vert_offset < 0:
                ty += vert_offset

            pred_x, pred_y = (tx, ty)
            if use_ai:
                pred_x, pred_y = self._predictor.update_and_predict(
                    tx,
                    ty,
                    frame.captured_at,
                    custom_latency_s=self._last_latency_ms / 1000.0,
                )
        else:
            pred_x, pred_y = (0.0, 0.0)
            self._predictor.reset()

        elapsed_ms = (time.perf_counter() - tick_start) * 1000.0
        self._last_latency_ms = elapsed_ms
        self._update_debug_view(active_detector, detection, (pred_x, pred_y), elapsed_ms)

        if detection is None:
            summary = f"لم يُكتشف هدف باللون المحدد | {elapsed_ms:.1f} ms"
        else:
            confidence = getattr(detection, "confidence", None)
            confidence_text = f" | ثقة {confidence:.2f}" if confidence is not None else ""
            summary = (
                f"مكتشف عند ({detection.x:.0f}, {detection.y:.0f})"
                f" | توقع ({pred_x:.0f}, {pred_y:.0f})"
                f" | نصف القطر {detection.radius:.0f}px"
                f"{confidence_text} | {elapsed_ms:.1f} ms"
            )
        self._annotate_and_store_preview(frame.image, detection, (pred_x, pred_y))
        with self._lock:
            self._latest_detection = detection
            self._preview_status = summary
        return detection

    def _annotate_and_store_preview(
        self,
        frame_img: np.ndarray,
        detection: Detection | None,
        pred_point: tuple[float, float] | None = None,
        gp_state: GamepadState | None = None,
    ) -> None:
        """Annotate frame copy with target overlays, FOV circle, and cache for UI preview."""
        annotated = frame_img.copy()
        h, w = annotated.shape[:2]

        cx, cy = w // 2, h // 2

        # Draw FOV boundary circle & spotlight effect
        fov_r = int(getattr(self.cfg, "fov_radius_px", 250.0))
        if 0 < fov_r < max(w, h):
            stencil = get_circular_stencil(w, h, cx, cy, fov_r)
            outside = (stencil == 0)
            annotated[outside] = (annotated[outside] * 0.55).astype(np.uint8)
            cv2.circle(annotated, (cx, cy), fov_r, color=(0, 230, 255), thickness=2, lineType=cv2.LINE_AA)
            cv2.putText(
                annotated,
                f"Active FOV ({fov_r}px)",
                (max(10, cx - 65), max(20, cy - fov_r - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (0, 230, 255),
                1,
                cv2.LINE_AA,
            )

        # Draw subtle center reference cross
        cv2.drawMarker(
            annotated,
            (cx, cy),
            color=(0, 220, 255),
            markerType=cv2.MARKER_CROSS,
            markerSize=16,
            thickness=1,
        )

        # Draw Controller HUD status tag if connected
        state = gp_state if gp_state is not None else self._latest_gamepad_state
        if state is not None and state.connected:
            b = getattr(self.cfg, "controller_bindings", {})
            aim_btn = b.get("AIM_TRIGGER", "L1")
            aim_tag = f" [{aim_btn} ACTIVE]" if state.is_aiming else ""
            hud_str = f"PAD #{state.user_index} [{state.device_name[:12]}] | {aim_btn}: {'ON' if state.is_aiming else 'OFF'} | LT:{int(state.left_trigger*100)}% RT:{int(state.right_trigger*100)}%{aim_tag}"
            col = (0, 255, 140) if state.is_aiming else (200, 200, 200)
            cv2.putText(annotated, hud_str, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)

        if detection is not None:
            bx, by, bw, bh = detection.bbox
            cv2.rectangle(
                annotated,
                (bx, by),
                (bx + bw, by + bh),
                color=(0, 255, 140),
                thickness=1,
            )
            # Unified reticle on target: draw ONE clean lock on the aim point
            target_x = int(pred_point[0]) if (pred_point is not None and pred_point != (0.0, 0.0)) else int(detection.x)
            target_y = int(pred_point[1]) if (pred_point is not None and pred_point != (0.0, 0.0)) else int(detection.y)

            cv2.drawMarker(
                annotated,
                (target_x, target_y),
                color=(0, 255, 255),
                markerType=cv2.MARKER_CROSS,
                markerSize=14,
                thickness=2,
                line_type=cv2.LINE_AA,
            )
            cv2.circle(
                annotated,
                (target_x, target_y),
                radius=max(4, int(detection.radius)),
                color=(0, 255, 255),
                thickness=1,
                lineType=cv2.LINE_AA,
            )
            if isinstance(detection, RoboflowDetection):
                tag_txt = f"ROBOFLOW: {detection.class_name}"
                if detection.tracker_id is not None:
                    tag_txt += f" #{detection.tracker_id}"
                cv2.putText(
                    annotated, tag_txt, (bx, max(15, by - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 80, 255), 1, cv2.LINE_AA
                )

        with self._lock:
            self._latest_annotated_frame = annotated

    def get_latest_preview_png(
        self, max_width: int = 360, max_height: int = 240
    ) -> bytes | None:
        """Return the latest annotated frame encoded as PNG bytes for GUI display (ultra-fast 60 FPS)."""
        with self._lock:
            if self._latest_annotated_frame is None:
                return None
            img = self._latest_annotated_frame
            if hasattr(self, "_cached_preview_frame") and self._cached_preview_frame is img:
                return getattr(self, "_cached_preview_bytes", None)

        h, w = img.shape[:2]
        if w <= 0 or h <= 0:
            return None

        scale = min(max_width / w, max_height / h, 1.0)
        target_w = max(1, int(w * scale))
        target_h = max(1, int(h * scale))

        if target_w != w or target_h != h:
            resized = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)
        else:
            resized = img

        success, encoded = cv2.imencode(
            ".png",
            resized,
            [int(cv2.IMWRITE_PNG_COMPRESSION), 1],
        )
        if not success:
            return None
        res_bytes = encoded.tobytes()
        with self._lock:
            self._cached_preview_frame = img
            self._cached_preview_bytes = res_bytes
        return res_bytes

    def get_gamepad_state(self) -> GamepadState:
        """Return the latest polled gamepad state."""
        with self._lock:
            return self._latest_gamepad_state

    def get_latest_detection(self) -> Detection | None:
        """Return the most recently computed target detection."""
        with self._lock:
            return self._latest_detection

    # -- safety & emergency stop -------------------------------------------

    def _is_cursor_in_virtual_corner(self) -> bool:
        """Check if the cursor is currently resting inside any screen corner."""
        desktop = virtual_screen_rect()
        if desktop is None:
            return False

        try:
            pos = self._controller._read_position()
        except Exception:
            return False

        margin = config.BOT_CORNER_STOP_PX
        in_left = pos[0] <= desktop.left + margin
        in_right = pos[0] >= desktop.right - margin - 1
        in_top = pos[1] <= desktop.top + margin
        in_bottom = pos[1] >= desktop.bottom - margin - 1

        return (in_left or in_right) and (in_top or in_bottom)

    def _handle_emergency_stop(self, reason: str) -> None:
        """Safely disable the bot and notify listeners."""
        self.cfg.bot_enabled = False
        self._controller.reset()
        self._predictor.reset()
        if self._on_stop is not None:
            self._on_stop(reason)

    # -- debug diagnostics -------------------------------------------------

    def _update_debug_view(
        self,
        detector: Detector,
        detection: Detection | None,
        aim_point: tuple[float, float],
        latency_ms: float,
    ) -> None:
        """Update snapshot for pygame UI rendering."""
        if not self.cfg.debug_view:
            with self._lock:
                self._debug_snapshot.enabled = False
            return

        mask_surf: pygame.Surface | None = None
        if hasattr(detector, "mask_rgb") and detector.mask_rgb is not None:
            mask_rgb = detector.mask_rgb
            # Downscale mask for preview
            preview_w, preview_h = config.BOT_PREVIEW_SIZE
            resized = cv2.resize(
                mask_rgb,
                (preview_w, preview_h),
                interpolation=cv2.INTER_NEAREST,
            )
            mask_surf = pygame.image.frombuffer(
                resized.tobytes(),
                (preview_w, preview_h),
                "RGB",
            )

        with self._lock:
            self._debug_snapshot.enabled = True
            self._debug_snapshot.mask = mask_surf
            self._debug_snapshot.centroid = (
                (detection.x, detection.y) if detection is not None else None
            )
            self._debug_snapshot.radius = detection.radius if detection is not None else 0.0
            self._debug_snapshot.aim_point = (
                aim_point if detection is not None else None
            )
            self._debug_snapshot.path = list(self._path_history)
            self._debug_snapshot.latency_ms = latency_ms
            self._debug_snapshot.loop_hz = self._loop_hz
            self._debug_snapshot.note = "AI Model Active" if getattr(self.cfg, "ai_assistant", False) else "Color Detector"

    def get_debug_view(self) -> DebugView:
        """Return a copy of the current debug snapshot."""
        with self._lock:
            return DebugView(
                enabled=self._debug_snapshot.enabled,
                mask=self._debug_snapshot.mask,
                centroid=self._debug_snapshot.centroid,
                radius=self._debug_snapshot.radius,
                aim_point=self._debug_snapshot.aim_point,
                path=list(self._debug_snapshot.path),
                latency_ms=self._debug_snapshot.latency_ms,
                loop_hz=self._debug_snapshot.loop_hz,
                note=self._debug_snapshot.note,
            )

    # -- thread loop -------------------------------------------------------

    def _run_loop(self) -> None:
        """Continuous execution loop on the background thread."""
        target_period = 1.0 / max(1, config.BOT_TARGET_HZ)
        last_time = time.perf_counter()

        while not self._stop_event.is_set():
            now = time.perf_counter()
            dt = now - last_time
            if dt > 0:
                self._loop_hz = 0.9 * self._loop_hz + 0.1 * (1.0 / dt)
            last_time = now

            if self._preview_only:
                self.preview_step()
            elif self.cfg.bot_enabled:
                self.step()
            else:
                self._controller.reset()
                self._predictor.reset()
                # Maintain physical controller pass-through to virtual gamepad even when bot is idle
                is_controller_mode = bool(getattr(self.cfg, "controller_mode", True))
                input_mode = str(getattr(self.cfg, "input_mode", getattr(self.cfg, "INPUT_MODE", "vgamepad"))).lower()
                if is_controller_mode and input_mode == "vgamepad":
                    try:
                        gp = self._gamepad.poll()
                        if gp.connected:
                            self._controller.pass_through_gamepad(gp, aim_rx=0.0, aim_ry=0.0, triggerbot_active=False)
                    except Exception:
                        pass
                time.sleep(0.015)

            # Sleep to maintain target frequency
            elapsed = time.perf_counter() - now
            sleep_time = max(0.001, target_period - elapsed)
            time.sleep(sleep_time)

        self._close_capture()
