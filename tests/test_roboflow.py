"""Unit tests for the Roboflow Workflow Detector integration."""

import json
from unittest.mock import MagicMock, patch

import numpy as np

from bot.roboflow_detector import RoboflowDetection, RoboflowDetector


def test_roboflow_detection_dataclass() -> None:
    det = RoboflowDetection(
        x=150.0,
        y=200.0,
        radius=25.0,
        area=2500.0,
        bbox=(125, 175, 50, 50),
        confidence=0.88,
        class_name="player",
        tracker_id=7,
        is_tracked=True,
    )
    assert det.x == 150.0
    assert det.y == 200.0
    assert det.confidence == 0.88
    assert det.class_name == "player"
    assert det.tracker_id == 7
    assert det.is_tracked is True


def test_select_best_target_filtering() -> None:
    detector = RoboflowDetector()

    # Target 1: Closest to center (160, 120), good area, tracked
    t1 = RoboflowDetection(
        x=170.0,
        y=125.0,
        radius=20.0,
        area=1600.0,
        bbox=(150, 105, 40, 40),
        confidence=0.9,
        class_name="player",
        tracker_id=1,
        is_tracked=True,
    )

    # Target 2: Outside FOV (dist > 250)
    t2 = RoboflowDetection(
        x=500.0,
        y=500.0,
        radius=20.0,
        area=1600.0,
        bbox=(480, 480, 40, 40),
        confidence=0.95,
        class_name="player",
    )

    # Target 3: Excessively large area (decoy)
    t3 = RoboflowDetection(
        x=165.0,
        y=122.0,
        radius=100.0,
        area=15000.0,
        bbox=(65, 22, 200, 200),
        confidence=0.99,
        class_name="player",
    )

    with detector._lock:
        detector._latest_detections = [t1, t2, t3]

    best = detector.select_best_target(center_x=160.0, center_y=120.0, fov_radius=200.0, max_area=5000.0)
    assert best is not None
    assert best == t1
    assert best.tracker_id == 1


def test_run_inference_mocked() -> None:
    detector = RoboflowDetector(api_key="test_key")

    mock_resp_data = {
        "outputs": [
            {
                "trained_marked_players": {
                    "predictions": [
                        {
                            "x": 300.0,
                            "y": 200.0,
                            "width": 60.0,
                            "height": 80.0,
                            "confidence": 0.85,
                            "class": "player",
                        }
                    ]
                },
                "trained_tracked_players": {
                    "predictions": [
                        {
                            "x": 300.0,
                            "y": 200.0,
                            "width": 60.0,
                            "height": 80.0,
                            "confidence": 0.85,
                            "class": "player",
                            "tracker_id": 42,
                        }
                    ]
                },
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.run_inference(test_frame)

        assert len(detections) == 1
        d = detections[0]
        assert d.x == 300.0
        assert d.y == 200.0
        assert d.confidence == 0.85
        assert d.tracker_id == 42
        assert d.is_tracked is True
