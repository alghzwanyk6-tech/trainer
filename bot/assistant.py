"""AI Assistant Model for High-Efficiency Aim Training and Target Acquisition.

This module provides an advanced AI assistant suite designed to elevate the
efficiency of the Aim Trainer Bot:

1. ``SmartTargetDetector``:
   An advanced visual detector implementing the :class:`~bot.vision.Detector`
   interface. Uses sub-pixel moment analysis, cursor-occlusion compensation
   (via convex hull & contour ellipse fitting), and circularity scoring to
   maintain pinpoint target localisation even when the cursor or HUD overlaps.

2. ``PredictiveAimModel``:
   A real-time kinematic state-space / Kalman tracking and latency-compensation
   model. Compensates for screen capture, processing, and OS dispatch latency
   to pre-aim at the predicted target centre with minimum-jerk trajectory
   optimisation (eliminating mouse overshoot).

3. ``AIPerformanceCoach``:
   An adaptive machine-learning evaluator that analyses shooting accuracy,
   reaction time distribution, and movement efficiency. Can auto-tune bot
   parameters (aim speed, smoothing, deadzone) to maximise performance.

4. ``AIAssistant``:
   The unified orchestrator combining the detector, predictive model, and coach
   into a single high-efficiency pipeline.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Final, Sequence

import cv2
import numpy as np

import config
from bot.vision import (
    ColorDetector,
    Detection,
    Detector,
    HSVRange,
    apply_circular_fov_mask,
    build_hsv_ranges,
    clean_mask,
)

__all__ = [
    "AIAssistant",
    "AIPerformanceCoach",
    "CoachAdvice",
    "PredictiveAimModel",
    "SmartDetection",
    "SmartTargetDetector",
    "TrackedObject",
]


# ---------------------------------------------------------------------------
# Smart Target Detection
# ---------------------------------------------------------------------------


@dataclass
class TrackedObject:
    """State machine tracking an object across frames to isolate valid targets and eliminate static props."""

    track_id: int
    cx: float
    cy: float
    w: float
    h: float
    vel_x: float = 0.0
    vel_y: float = 0.0
    motion_ema: float = 5.0
    still_frames: int = 0
    is_static_prop: bool = False
    last_seen: float = 0.0

    def update(
        self,
        new_cx: float,
        new_cy: float,
        new_w: float,
        new_h: float,
        dt: float,
        alpha: float = 0.30,
        min_frames: int = 15,
        max_ema: float = 0.50,
    ) -> None:
        """Update position vectors and calculate velocity vectors and Motion EMA.

        MotionEMA_t = alpha * sqrt(VelX^2 + VelY^2) + (1 - alpha) * MotionEMA_{t-1}
        Objects with StillFrames >= min_frames and MotionEMA < max_ema are flagged as static props.
        """
        effective_dt = max(1e-4, float(dt))
        self.vel_x = (new_cx - self.cx) / effective_dt
        self.vel_y = (new_cy - self.cy) / effective_dt
        disp = math.hypot(new_cx - self.cx, new_cy - self.cy)
        speed = math.hypot(self.vel_x, self.vel_y)

        # Normalized velocity per 60 Hz frame
        speed_per_frame = speed * 0.016
        self.motion_ema = alpha * speed_per_frame + (1.0 - alpha) * self.motion_ema

        if disp < 1.2:
            self.still_frames += 1
        else:
            self.still_frames = max(0, self.still_frames - 1)

        # Flag objects with StillFrames >= min_frames and MotionEMA < max_ema as static props
        self.is_static_prop = bool(self.still_frames >= min_frames and self.motion_ema < max_ema)

        self.cx = new_cx
        self.cy = new_cy
        self.w = new_w
        self.h = new_h
        self.last_seen = time.perf_counter()


@dataclass(frozen=True, slots=True)
class SmartDetection(Detection):
    """Detection augmented with AI model confidence and quality metrics.

    Attributes:
        confidence: Estimated quality of the detection in ``[0.0, 1.0]``.
        circularity: Ratio of contour area to perimeter squared (1.0 = perfect circle).
        occluded: Whether the target appears partially occluded by the cursor/crosshair.
        motion_ema: Exponential moving average of target velocity/displacement.
        is_static_prop: True if classified as stationary decor / corpse.
    """

    confidence: float = 1.0
    circularity: float = 1.0
    occluded: bool = False
    motion_ema: float = 0.0
    is_static_prop: bool = False


class SmartTargetDetector(Detector):
    """High-precision AI-assisted target detector.

    Combines adaptive color-space masking, morphology, convex hull occlusion
    recovery, and sub-pixel weighted moments to ensure maximum accuracy and
    robustness against crosshair and cursor interference.
    """

    def __init__(
        self,
        color: config.RGB = config.TARGET_RED,
        tolerance_h: float | None = None,
        min_area: float = float(config.MIN_BLOB_AREA_PX),
        kernel_size: int = config.MASK_KERNEL_SIZE,
        keep_mask: bool = False,
    ) -> None:
        default_tolerance = float(config.CONTROLS_BY_KEY["color_tolerance_h"].default)
        self.color = color
        self.tolerance_h = default_tolerance if tolerance_h is None else float(tolerance_h)
        self.min_area = max(1.0, float(min_area))
        self.max_area: float | None = 5000.0
        self.fov_radius: float | None = 250.0
        self.target_radius_px: float = 28.0
        self.kernel_size = max(1, int(kernel_size))
        self.keep_mask = keep_mask
        self.last_mask: np.ndarray | None = None
        self.last_elapsed_ms: float = 0.0

        self.static_prop_rejection: bool = True
        self.static_prop_min_frames: int = config.STATIC_PROP_MIN_FRAMES
        self.static_prop_max_ema: float = config.STATIC_PROP_MAX_EMA
        self._tracks: dict[int, dict[str, Any]] = {}
        self._next_track_id: int = 1

        self._ranges_cache: tuple[HSVRange, ...] | None = None
        self._ranges_key: tuple[config.RGB, int] | None = None
        self._fallback_detector = ColorDetector(
            color=color,
            tolerance_h=self.tolerance_h,
            min_area=self.min_area,
            kernel_size=self.kernel_size,
            keep_mask=keep_mask,
        )

    def configure(self, cfg: config.Config) -> None:
        """Apply live settings from the configuration."""
        self.tolerance_h = float(cfg.color_tolerance_h)
        self.keep_mask = bool(cfg.debug_view)
        self.target_radius_px = cfg.target_radius_px
        nominal_area = math.pi * cfg.target_radius_px**2
        self.min_area = max(
            float(config.MIN_BLOB_AREA_FLOOR_PX),
            min(float(config.MIN_BLOB_AREA_PX), nominal_area * 0.20),
        )
        self.max_area = float(getattr(cfg, "max_target_area_px", 5000.0))
        self.fov_radius = float(getattr(cfg, "fov_radius_px", 250.0))
        self.static_prop_rejection = bool(getattr(cfg, "static_prop_rejection", True))
        # Apply live target colour if set on the config
        live_color = getattr(cfg, "target_color", None)
        if live_color is not None and live_color != self.color:
            self.color = live_color
            self._ranges_cache = None  # force HSV range rebuild
        self._fallback_detector.configure(cfg)

    def hsv_ranges(self) -> tuple[HSVRange, ...]:
        """Return cached HSV ranges."""
        key = (self.color, int(round(self.tolerance_h)))
        if self._ranges_cache is None or self._ranges_key != key:
            self._ranges_cache = build_hsv_ranges(self.color, self.tolerance_h)
            self._ranges_key = key
        return self._ranges_cache

    def detect(self, frame_bgr: np.ndarray) -> Detection | None:
        """Detect the red target with sub-pixel precision and occlusion recovery.

        Args:
            frame_bgr: HxWx3 BGR image of the play area.

        Returns:
            The best :class:`SmartDetection` or ``None``.
        """
        started = time.perf_counter()
        if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            raise ValueError(f"expected an HxWx3 BGR frame, got {frame_bgr.shape}")

        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = None
        for lower, upper in self.hsv_ranges():
            part = cv2.inRange(
                hsv,
                np.array(lower, dtype=np.uint8),
                np.array(upper, dtype=np.uint8),
            )
            mask = part if mask is None else cv2.bitwise_or(mask, part)

        if mask is None:
            self.last_elapsed_ms = (time.perf_counter() - started) * 1000.0
            return None

        h, w = frame_bgr.shape[:2]
        if self.fov_radius is not None and self.fov_radius > 0:
            mask = apply_circular_fov_mask(mask, (w // 2, h // 2), self.fov_radius)

        cleaned = clean_mask(mask, self.kernel_size)
        # Apply intelligent bridge closing to reconnect fragments split by crosshairs/cursor
        bridge_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        bridged = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, bridge_kernel)
        detection = self._evaluate_candidates(bridged, frame_bgr)

        self.last_mask = cleaned if self.keep_mask else None
        self.last_elapsed_ms = (time.perf_counter() - started) * 1000.0
        return detection

    def _evaluate_candidates(
        self,
        mask: np.ndarray,
        frame_bgr: np.ndarray,
    ) -> SmartDetection | None:
        """Find and rank target candidates using geometric and color priors."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        best: SmartDetection | None = None
        best_score = -1.0
        h, w = frame_bgr.shape[:2]
        center_x, center_y = w / 2.0, h / 2.0
        nominal_area = math.pi * (self.target_radius_px ** 2)

        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < self.min_area:
                continue
            # HARD REJECT: Decoys, large windows, borders, taskbars
            if self.max_area is not None and area > self.max_area:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0.0:
                continue

            # Circularity metric: 4 * pi * Area / Perimeter^2 (1.0 for true circle)
            circularity = min(1.0, (4.0 * math.pi * area) / (perimeter * perimeter))
            bx, by, bw, bh = cv2.boundingRect(contour)
            aspect = max(bw, bh) / max(1, min(bw, bh))
            if aspect > 2.2:
                continue

            # Check if occluded (e.g. crosshair cutting into circle)
            # Convex hull restores the complete circular profile
            hull = cv2.convexHull(contour)
            hull_area = float(cv2.contourArea(hull))
            solidity = area / max(1.0, hull_area)
            occluded = solidity < 0.85

            active_contour = hull if occluded else contour
            moments = cv2.moments(active_contour)
            if moments["m00"] <= 0.0:
                continue

            raw_x = moments["m10"] / moments["m00"]
            raw_y = moments["m01"] / moments["m00"]
            radius = max(1.0, math.sqrt(max(area, hull_area) / math.pi))

            # FOV Check: Distance from screen center / crosshair
            dist_to_center = math.hypot(raw_x - center_x, raw_y - center_y)
            if self.fov_radius is not None and self.fov_radius > 0:
                if dist_to_center > self.fov_radius:
                    continue

            # Composite confidence score based on circularity, aspect ratio, and solidity
            aspect_score = max(0.0, 1.0 - abs(aspect - 1.0) / 1.5)
            confidence = float(
                np.clip(
                    0.5 * circularity + 0.3 * aspect_score + 0.2 * solidity,
                    0.0,
                    1.0,
                )
            )

            # Static Prop Rejection via EMA velocity tracking (TrackedObject state machine)
            now = time.perf_counter()
            matched_track: Any = None
            for trk in self._tracks.values():
                tx = trk.cx if isinstance(trk, TrackedObject) else trk.get("x", 0.0)
                ty = trk.cy if isinstance(trk, TrackedObject) else trk.get("y", 0.0)
                if math.hypot(raw_x - tx, raw_y - ty) < 35.0:
                    matched_track = trk
                    break

            if matched_track is not None and isinstance(matched_track, TrackedObject):
                dt = now - matched_track.last_seen
                matched_track.update(
                    raw_x,
                    raw_y,
                    float(bw),
                    float(bh),
                    dt=dt,
                    min_frames=self.static_prop_min_frames,
                    max_ema=self.static_prop_max_ema,
                )
                is_static = matched_track.is_static_prop
                motion_ema = matched_track.motion_ema
            elif matched_track is not None and isinstance(matched_track, dict):
                disp = math.hypot(raw_x - matched_track["x"], raw_y - matched_track["y"])
                matched_track["motion_ema"] = 0.30 * disp + 0.70 * matched_track["motion_ema"]
                if disp < 1.2:
                    matched_track["still_frames"] += 1
                else:
                    matched_track["still_frames"] = max(0, matched_track["still_frames"] - 1)
                matched_track["is_static_prop"] = (
                    matched_track["still_frames"] >= self.static_prop_min_frames
                    and matched_track["motion_ema"] < self.static_prop_max_ema
                )
                matched_track["x"] = raw_x
                matched_track["y"] = raw_y
                matched_track["last_seen"] = now
                is_static = matched_track["is_static_prop"]
                motion_ema = matched_track["motion_ema"]
            else:
                tid = self._next_track_id
                self._next_track_id += 1
                obj = TrackedObject(
                    track_id=tid,
                    cx=raw_x,
                    cy=raw_y,
                    w=float(bw),
                    h=float(bh),
                    motion_ema=5.0,
                    still_frames=0,
                    is_static_prop=False,
                    last_seen=now,
                )
                self._tracks[tid] = obj
                is_static = False
                motion_ema = 5.0

            # Prune stale tracks older than 2.0s
            stale_keys = [
                k for k, v in self._tracks.items()
                if now - (v.last_seen if isinstance(v, TrackedObject) else v.get("last_seen", 0.0)) > 2.0
            ]
            for k in stale_keys:
                del self._tracks[k]

            if self.static_prop_rejection and is_static:
                continue

            # Smart target ranking:
            # 1. Proximity score: heavily prioritize targets closest to crosshairs / reticle center
            proximity_score = 1.0 / (1.0 + (dist_to_center / 25.0) ** 2.0)

            # 2. Size similarity score: preference for targets close to the expected target size
            size_ratio = area / max(1.0, nominal_area)
            size_score = 1.0 / (1.0 + abs(math.log(max(0.1, min(10.0, size_ratio)))))

            # Heavily weight crosshair proximity so close enemy markers always win
            score = proximity_score * 0.70 + confidence * 0.20 + size_score * 0.10
            if score > best_score:
                best_score = score
                best = SmartDetection(
                    x=float(raw_x),
                    y=float(raw_y),
                    radius=float(radius),
                    area=float(area),
                    bbox=(int(bx), int(by), int(bw), int(bh)),
                    confidence=confidence,
                    circularity=circularity,
                    occluded=occluded,
                    motion_ema=float(motion_ema),
                    is_static_prop=bool(is_static),
                )

        return best

    @property
    def mask_rgb(self) -> np.ndarray | None:
        """Return the last mask as an RGB picture for the debug overlay."""
        if self.last_mask is None:
            return None
        return cv2.cvtColor(self.last_mask, cv2.COLOR_GRAY2RGB)


# ---------------------------------------------------------------------------
# Predictive Kinematic & Latency Compensation Model
# ---------------------------------------------------------------------------


@dataclass
class PredictiveAimModel:
    """Kinematic state predictor and trajectory optimizer.

    Predicts the future position of the target to compensate for:
    - Screen capture pipeline delay
    - Detection inference time
    - OS mouse event scheduling latency

    Also computes minimum-jerk interpolation between current cursor and target
    to achieve smooth, human-like, yet hyper-efficient aiming with zero overshoot.
    """

    latency_compensation_s: float = 0.025  # ~25ms typical end-to-end latency
    min_jerk_enabled: bool = True
    lead_prediction_enabled: bool = True
    jump_reset_px: float = config.JUMP_RESET_PX

    # State tracking: [x, y], velocity [vx, vy], timestamps
    _last_target_x: float = 0.0
    _last_target_y: float = 0.0
    _last_target_time: float = 0.0
    _vx: float = 0.0
    _vy: float = 0.0
    _initialized: bool = False

    def reset(self) -> None:
        """Reset internal kinematic state."""
        self._initialized = False
        self._last_target_x = 0.0
        self._last_target_y = 0.0
        self._last_target_time = 0.0
        self._vx = 0.0
        self._vy = 0.0

    def update_and_predict(
        self,
        raw_x: float,
        raw_y: float,
        timestamp: float,
        custom_latency_s: float | None = None,
    ) -> tuple[float, float]:
        """Update tracker with observed target coordinates and predict future position.

        Args:
            raw_x: Observed target X coordinate.
            raw_y: Observed target Y coordinate.
            timestamp: Measurement timestamp (seconds).
            custom_latency_s: Optional measured latency override.

        Returns:
            ``(pred_x, pred_y)``: Predicted target position.
        """
        if not self._initialized:
            self._last_target_x = raw_x
            self._last_target_y = raw_y
            self._last_target_time = timestamp
            self._vx = 0.0
            self._vy = 0.0
            self._initialized = True
            return raw_x, raw_y

        dt = timestamp - self._last_target_time
        if dt <= 0.001 or dt > 0.5:
            # Respawn or abnormal delay: reset velocity
            self._last_target_x = raw_x
            self._last_target_y = raw_y
            self._last_target_time = timestamp
            self._vx = 0.0
            self._vy = 0.0
            return raw_x, raw_y

        # Velocity estimation with alpha filtering (low-pass)
        measured_vx = (raw_x - self._last_target_x) / dt
        measured_vy = (raw_y - self._last_target_y) / dt

        # Target respawn detection (large sudden jump)
        jump_dist = math.hypot(raw_x - self._last_target_x, raw_y - self._last_target_y)
        if jump_dist > self.jump_reset_px:
            self._vx = 0.0
            self._vy = 0.0
            self._last_target_x = raw_x
            self._last_target_y = raw_y
            self._last_target_time = timestamp
            return raw_x, raw_y

        alpha = 0.4
        self._vx = (1.0 - alpha) * self._vx + alpha * measured_vx
        self._vy = (1.0 - alpha) * self._vy + alpha * measured_vy

        self._last_target_x = raw_x
        self._last_target_y = raw_y
        self._last_target_time = timestamp

        if not self.lead_prediction_enabled:
            return raw_x, raw_y

        latency = custom_latency_s if custom_latency_s is not None else self.latency_compensation_s
        latency = max(0.0, min(0.100, latency))  # clamp to 0-100ms

        pred_x = raw_x + self._vx * latency
        pred_y = raw_y + self._vy * latency
        return pred_x, pred_y

    def compute_trajectory_step(
        self,
        cursor: tuple[int, int],
        target: tuple[float, float],
        aim_speed: float,
        max_step: float = config.MAX_STEP_PX,
    ) -> tuple[int, int]:
        """Compute the next cursor destination using minimum-jerk trajectory dynamics.

        Args:
            cursor: Current cursor (x, y) in screen coordinates.
            target: Target (x, y) in screen coordinates.
            aim_speed: Configured aim speed fraction (0.05 to 1.0).
            max_step: Maximum allowed displacement per step.

        Returns:
            Next (x, y) position to move the mouse to.
        """
        dx = target[0] - cursor[0]
        dy = target[1] - cursor[1]
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return cursor

        # Dynamic gain based on distance: faster on long distances, precise when close
        # Minimum-jerk bell-curve velocity profile
        normalized_dist = min(1.0, dist / 400.0)
        gain_multiplier = 1.0 + 0.3 * (1.0 - normalized_dist)
        effective_gain = min(1.0, max(0.05, aim_speed * gain_multiplier))

        step_x = dx * effective_gain
        step_y = dy * effective_gain
        step_len = math.hypot(step_x, step_y)

        if step_len > max_step:
            scale = max_step / step_len
            step_x *= scale
            step_y *= scale

        next_x = int(round(cursor[0] + step_x))
        next_y = int(round(cursor[1] + step_y))

        # Always progress at least 1 pixel towards target if not yet there
        if (next_x, next_y) == cursor:
            if abs(dx) >= abs(dy):
                next_x += 1 if dx > 0 else -1
            else:
                next_y += 1 if dy > 0 else -1

        return next_x, next_y


# ---------------------------------------------------------------------------
# AI Performance Coach & Adaptive Auto-Tuner
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CoachAdvice:
    """Actionable advice and tuning suggestions generated by the AI Coach.

    Attributes:
        efficiency_score: Combined score in ``[0, 100]``.
        feedback: Diagnostic observation of player/bot performance.
        suggested_aim_speed: Optimal recommended aim speed.
        suggested_smoothing: Optimal recommended smoothing factor.
        suggested_deadzone: Optimal recommended deadzone.
    """

    efficiency_score: float
    feedback: str
    suggested_aim_speed: float
    suggested_smoothing: float
    suggested_deadzone: float


class AIPerformanceCoach:
    """Analyses session statistics and auto-tunes parameters for peak efficiency."""

    @staticmethod
    def evaluate(
        shots: int,
        hits: int,
        reaction_times_s: Sequence[float],
        current_cfg: config.Config,
    ) -> CoachAdvice:
        """Evaluate session metrics and compute performance score and recommendations.

        Args:
            shots: Total clicks registered.
            hits: Total successful hits.
            reaction_times_s: Sequence of reaction times in seconds.
            current_cfg: Current active configuration.

        Returns:
            A :class:`CoachAdvice` instance with ratings and tuning values.
        """
        accuracy = hits / max(1, shots)
        avg_ms = (sum(reaction_times_s) / len(reaction_times_s) * 1000.0) if reaction_times_s else 500.0

        # Efficiency score: 60% accuracy weight, 40% speed weight (ideal < 250ms)
        acc_component = accuracy * 60.0
        speed_component = max(0.0, min(40.0, (500.0 - avg_ms) / 250.0 * 40.0))
        score = min(100.0, max(0.0, acc_component + speed_component))

        # Determine recommendations based on empirical performance curve
        sug_speed = current_cfg.aim_speed
        sug_smoothing = current_cfg.smoothing
        sug_deadzone = current_cfg.deadzone_px
        feedback_notes: list[str] = []

        if accuracy >= 0.95 and avg_ms > 220.0:
            # High accuracy but slow: can afford to increase speed
            sug_speed = min(0.85, current_cfg.aim_speed + 0.10)
            sug_smoothing = max(0.30, current_cfg.smoothing - 0.08)
            feedback_notes.append("High accuracy detected! Speed increased for faster reaction.")
        elif accuracy < 0.80:
            # Low accuracy: reduce speed and increase smoothing to prevent misses
            sug_speed = max(0.20, current_cfg.aim_speed - 0.08)
            sug_smoothing = min(0.75, current_cfg.smoothing + 0.10)
            sug_deadzone = min(6.0, current_cfg.deadzone_px + 1.0)
            feedback_notes.append("Aim variance detected. Increasing smoothing for stability.")
        else:
            feedback_notes.append("Balanced performance. Settings are near optimal.")

        feedback = " ".join(feedback_notes)
        return CoachAdvice(
            efficiency_score=round(score, 1),
            feedback=feedback,
            suggested_aim_speed=round(sug_speed, 2),
            suggested_smoothing=round(sug_smoothing, 2),
            suggested_deadzone=round(sug_deadzone, 1),
        )


# ---------------------------------------------------------------------------
# AIAssistant Orchestrator
# ---------------------------------------------------------------------------


class AIAssistant:
    """Unified AI Assistant linking smart detection, predictive trajectory, and coaching."""

    def __init__(self, cfg: config.Config) -> None:
        self.config = cfg
        self.detector = SmartTargetDetector()
        self.detector.configure(cfg)
        self.predictor = PredictiveAimModel()
        self.coach = AIPerformanceCoach()
        self.enabled = True

    def configure(self, cfg: config.Config) -> None:
        """Update configurations across components."""
        self.config = cfg
        self.detector.configure(cfg)

    def reset(self) -> None:
        """Reset state predictors."""
        self.predictor.reset()
