"""Unit tests for capture geometry and region."""

import pytest

from bot.capture import ScreenRegion


def test_screen_region_geometry() -> None:
    region = ScreenRegion(100, 200, 800, 600)
    assert region.right == 900
    assert region.bottom == 800
    assert region.center == (500.0, 500.0)

    # Coordinate translations
    assert region.to_screen(50.0, 60.0) == (150.0, 260.0)
    assert region.contains(150, 250) is True
    assert region.contains(50, 50) is False

    # MSS dict
    assert region.to_mss() == {"left": 100, "top": 200, "width": 800, "height": 600}


def test_screen_region_invalid() -> None:
    with pytest.raises(ValueError):
        ScreenRegion(0, 0, 0, 100)
    with pytest.raises(ValueError):
        ScreenRegion(0, 0, 100, -10)


def test_screen_fov_region() -> None:
    from bot.capture import screen_fov_region

    fov = screen_fov_region(width=400, height=400)
    assert fov.width == 400
    assert fov.height == 400
    assert fov.left >= 0
    assert fov.top >= 0


def test_find_window_info() -> None:
    from bot.capture import find_window_info, find_window_region

    # Testing non-existent window yields None gracefully
    assert find_window_region("NonExistentWindow_123456789") is None
    assert find_window_info(["NonExistent_A", "NonExistent_B"]) is None


def test_screen_capture_backends() -> None:
    from bot.capture import ScreenCapture, ScreenRegion

    region = ScreenRegion(0, 0, 100, 100)
    # Test auto backend gracefully initializes and grabs or falls back
    with ScreenCapture(region, backend="auto") as cap:
        assert cap.region == region
        # In a headless/CI environment, grab might fail if no display, but ensures no crash on construct
        assert cap._closed is False

    # Test mss backend directly
    with ScreenCapture(region, backend="mss") as cap_mss:
        assert cap_mss._backend == "mss"
        assert cap_mss.region.width == 100

