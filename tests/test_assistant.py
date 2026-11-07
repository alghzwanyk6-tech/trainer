"""Unit tests for the AI Assistant model."""

import cv2
import numpy as np

import config
from bot.assistant import (
    AIAssistant,
    AIPerformanceCoach,
    PredictiveAimModel,
    SmartDetection,
    SmartTargetDetector,
)


def test_smart_target_detector_occlusion_recovery() -> None:
    # Synthetic frame with a red circle and a black crosshair bar drawn across it
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    center = (150, 150)
    radius = 35
    cv2.circle(img, center, radius, (0, 0, 255), -1)  # Solid red

    # Cut a crosshair line across it (occlusion)
    cv2.line(img, (150, 110), (150, 190), (0, 0, 0), 4)

    detector = SmartTargetDetector()
    detection = detector.detect(img)

    assert detection is not None
    assert isinstance(detection, SmartDetection)
    assert detection.confidence > 0.5
    # The centroid should remain near (150, 150) despite the black crosshair line
    assert abs(detection.x - 150) <= 2.5
    assert abs(detection.y - 150) <= 2.5


def test_predictive_aim_model_velocity_and_lead() -> None:
    model = PredictiveAimModel(latency_compensation_s=0.030)  # 30ms latency
    model.reset()

    # Step 1: Target at (100, 100) at t = 1.0
    p1 = model.update_and_predict(100.0, 100.0, timestamp=1.0)
    assert p1 == (100.0, 100.0)

    # Step 2: Target moved to (120, 100) at t = 1.1 (velocity = +200 px/s along X)
    p2 = model.update_and_predict(120.0, 100.0, timestamp=1.1)
    # Predicted position should lead target in X direction
    assert p2[0] > 120.0
    assert abs(p2[1] - 100.0) < 1.0


def test_predictive_aim_model_resets_on_target_respawn() -> None:
    model = PredictiveAimModel(
        latency_compensation_s=0.030,
        jump_reset_px=config.TRAINER_JUMP_RESET_PX,
    )
    model.update_and_predict(100.0, 100.0, timestamp=1.0)

    # A new trainer target can respawn 150+ px away; it is not target motion.
    respawn = model.update_and_predict(280.0, 100.0, timestamp=1.03)

    assert respawn == (280.0, 100.0)


def test_predictive_trajectory_step() -> None:
    model = PredictiveAimModel()
    cursor = (100, 100)
    target = (300.0, 100.0)

    next_cursor = model.compute_trajectory_step(cursor, target, aim_speed=0.4, max_step=100.0)
    assert next_cursor[0] > 100
    assert next_cursor[1] == 100
    assert next_cursor[0] <= 220


def test_ai_performance_coach() -> None:
    cfg = config.Config(aim_speed=0.35, smoothing=0.50)

    # 1. High accuracy session
    advice_high = AIPerformanceCoach.evaluate(
        shots=30,
        hits=30,
        reaction_times_s=[0.30] * 30,
        current_cfg=cfg,
    )
    assert advice_high.efficiency_score >= 80.0
    assert advice_high.suggested_aim_speed >= cfg.aim_speed

    # 2. Low accuracy session
    advice_low = AIPerformanceCoach.evaluate(
        shots=30,
        hits=10,
        reaction_times_s=[0.45] * 10,
        current_cfg=cfg,
    )
    assert advice_low.efficiency_score < 60.0
    assert advice_low.suggested_smoothing >= cfg.smoothing


def test_ai_assistant_orchestrator() -> None:
    cfg = config.Config()
    assistant = AIAssistant(cfg)
    assert assistant.enabled is True
    assert assistant.detector is not None
    assert assistant.predictor is not None
    assert assistant.coach is not None


def test_smart_target_detector_rejects_large_decoys() -> None:
    # 600x600 synthetic frame
    img = np.zeros((600, 600, 3), dtype=np.uint8)

    # 1. Giant red decoy rectangle (like a red window / banner / browser header): 300x200 = 60,000 px²
    cv2.rectangle(img, (20, 20), (320, 220), (0, 0, 255), -1)

    # 2. Legitimate small target circle near crosshair: center (300, 300), radius 28 = ~2,463 px²
    cv2.circle(img, (300, 300), 28, (0, 0, 255), -1)

    cfg = config.Config(max_target_area_px=5000.0, fov_radius_px=250.0)
    detector = SmartTargetDetector()
    detector.configure(cfg)

    detection = detector.detect(img)
    assert detection is not None
    # Must lock onto the real target (300, 300), NOT the giant decoy window!
    assert abs(detection.x - 300) <= 2
    assert abs(detection.y - 300) <= 2
    assert detection.area < 5000.0


def test_smart_target_detector_strictly_ignores_outside_fov() -> None:
    img = np.zeros((500, 500, 3), dtype=np.uint8)
    # Circle far outside (dist from 250, 250 to 450, 450 is ~282px)
    cv2.circle(img, (450, 450), 25, (0, 0, 255), -1)

    cfg = config.Config(fov_radius_px=100.0)
    detector = SmartTargetDetector()
    detector.configure(cfg)

    # Outside circle must be ignored completely
    assert detector.detect(img) is None

    # Inside FOV circle (dist is ~14px < 100px)
    cv2.circle(img, (260, 250), 25, (0, 0, 255), -1)
    det = detector.detect(img)
    assert det is not None
    assert abs(det.x - 260) <= 2
    assert abs(det.y - 250) <= 2


def test_smart_target_detector_static_prop_rejection() -> None:
    # Synthetic frame with a stationary target
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    cv2.circle(img, (200, 200), 20, (0, 0, 255), -1)

    cfg = config.Config(static_prop_rejection=True)
    detector = SmartTargetDetector()
    detector.configure(cfg)
    detector.static_prop_min_frames = 5  # lower for fast test execution

    # First detection is valid
    det1 = detector.detect(img)
    assert det1 is not None
    assert det1.is_static_prop is False

    # After 12 consecutive frames without any motion, motion_ema decays below 0.50 and still_frames exceeds 5
    det = None
    for _ in range(12):
        det = detector.detect(img)

    # When static_prop_rejection is enabled, the stationary target is rejected (returns None)
    assert det is None

    # Now if the target moves to a new location, it is immediately detected again
    img2 = np.zeros((400, 400, 3), dtype=np.uint8)
    cv2.circle(img2, (250, 200), 20, (0, 0, 255), -1)
    det_moving = detector.detect(img2)
    assert det_moving is not None
    assert abs(det_moving.x - 250) <= 2


