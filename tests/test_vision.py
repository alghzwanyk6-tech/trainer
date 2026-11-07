"""Unit tests for vision pipeline."""

import cv2
import numpy as np
import pytest

import config
from bot.vision import (
    ColorDetector,
    apply_circular_fov_mask,
    build_hsv_ranges,
    build_mask,
    clean_mask,
    find_largest_blob,
    get_circular_stencil,
    rgb_to_hsv,
)


def test_rgb_to_hsv() -> None:
    # Red in RGB is (255, 0, 0) -> OpenCV hue 0
    h, s, v = rgb_to_hsv((255, 0, 0))
    assert h == 0
    assert s == 255
    assert v == 255


def test_build_hsv_ranges_wrap() -> None:
    # Target red hue is near 0/180 so wrap produces 2 ranges
    ranges = build_hsv_ranges(config.TARGET_RED, tolerance_h=10.0)
    assert len(ranges) == 2


def test_color_detector_synthetic_circle() -> None:
    # Create black image (300 x 300)
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    # Draw red circle in BGR: (0, 0, 255)
    center = (150, 120)
    radius = 30
    cv2.circle(img, center, radius, (0, 0, 255), -1)

    detector = ColorDetector(color=config.TARGET_RED, tolerance_h=10.0)
    detection = detector.detect(img)

    assert detection is not None
    assert abs(detection.x - 150) <= 2
    assert abs(detection.y - 120) <= 2
    assert abs(detection.radius - 30) <= 3


def test_color_detector_empty_frame() -> None:
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    detector = ColorDetector()
    detection = detector.detect(img)
    assert detection is None


def test_apply_circular_fov_mask() -> None:
    mask = np.ones((100, 100), dtype=np.uint8) * 255
    # Center at (50, 50), radius 20
    masked = apply_circular_fov_mask(mask, center=(50, 50), fov_radius=20)
    # Center pixel should be 255
    assert masked[50, 50] == 255
    # Pixel inside radius (dist 10) should be 255
    assert masked[50, 60] == 255
    # Pixel outside radius (dist 30, e.g. (50, 80)) must be 0
    assert masked[50, 80] == 0
    # Corner pixel must be 0
    assert masked[0, 0] == 0


def test_color_detector_strictly_ignores_outside_fov() -> None:
    # 400x400 image, center is (200, 200)
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    # Place a red circle far in the corner (350, 350)
    cv2.circle(img, (350, 350), 20, (0, 0, 255), -1)

    detector = ColorDetector(color=config.TARGET_RED, tolerance_h=10.0)
    detector.fov_radius = 80.0  # FOV only covers within 80px of center (200, 200)

    # Must be completely ignored because it's outside FOV circle
    assert detector.detect(img) is None

    # Now draw a red circle inside the FOV circle (210, 195)
    cv2.circle(img, (210, 195), 20, (0, 0, 255), -1)
    det = detector.detect(img)
    assert det is not None
    assert abs(det.x - 210) <= 2
    assert abs(det.y - 195) <= 2
