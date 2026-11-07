"""Unit tests for Local DirectML AI detector."""

import numpy as np
import pytest

import config
from bot.assistant import SmartDetection
from bot.local_ai_detector import LocalAIDetector


def test_local_ai_detector_initialization() -> None:
    detector = LocalAIDetector()
    assert detector.conf_threshold == 0.45
    assert detector.iou_threshold == 0.45
    assert detector.head_bias_percent == 0.70
    assert detector.session is None
    # When no model is loaded, detect() returns None safely
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    assert detector.detect(dummy) is None


def test_local_ai_detector_preprocess() -> None:
    detector = LocalAIDetector(input_size=(640, 640))
    dummy_frame = np.ones((720, 1280, 3), dtype=np.uint8) * 120

    tensor, scale, (pad_x, pad_y) = detector.preprocess(dummy_frame)

    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert 0.0 <= np.min(tensor) <= np.max(tensor) <= 1.0
    assert scale == 640.0 / 1280.0
    assert pad_x == 0
    assert pad_y == (640 - int(720 * scale)) // 2


def test_local_ai_detector_postprocess() -> None:
    detector = LocalAIDetector(conf_threshold=0.40, head_bias_percent=0.70)

    # Synthetic YOLOv8 tensor: shape [1, 6, 8400] (cx, cy, w, h, class0_score, class1_score)
    # class 0: body, class 1: head
    output = np.zeros((1, 6, 8400), dtype=np.float32)

    # Anchor 10: High confidence body at (320, 320) with w=60, h=120
    output[0, 0, 10] = 320.0  # cx
    output[0, 1, 10] = 320.0  # cy
    output[0, 2, 10] = 60.0   # w
    output[0, 3, 10] = 120.0  # h
    output[0, 4, 10] = 0.88   # body conf
    output[0, 5, 10] = 0.10   # head conf

    # Anchor 20: High confidence head at (200, 200) with w=30, h=30
    output[0, 0, 20] = 200.0  # cx
    output[0, 1, 20] = 200.0  # cy
    output[0, 2, 20] = 30.0   # w
    output[0, 3, 20] = 30.0   # h
    output[0, 4, 20] = 0.05   # body conf
    output[0, 5, 20] = 0.95   # head conf

    detections = detector.postprocess([output], orig_shape=(640, 640), scale=1.0, pad=(0, 0))

    assert len(detections) == 2

    # Verify head detection (target_y should match center y)
    head_det = next((d for d in detections if d.confidence > 0.90), None)
    assert head_det is not None
    assert abs(head_det.x - 200.0) < 1.0
    assert abs(head_det.y - 200.0) < 1.0

    # Verify body detection with head bias vertical offset:
    # target_y = cy - (h * 0.35 * head_bias_percent) = 320 - (120 * 0.35 * 0.70) = 320 - 29.4 = 290.6
    body_det = next((d for d in detections if 0.85 < d.confidence < 0.90), None)
    assert body_det is not None
    assert abs(body_det.x - 320.0) < 1.0
    assert abs(body_det.y - 290.6) < 1.0


def test_local_ai_detector_configure() -> None:
    detector = LocalAIDetector()
    cfg = config.Config(
        local_ai_confidence=0.55,
        head_bias_percent=0.85,
    )
    detector.configure(cfg)
    assert detector.conf_threshold == 0.55
    assert detector.head_bias_percent == 0.85
