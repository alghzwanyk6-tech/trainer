"""Tests for remote_play module (PS5 / Xbox streaming clients and helpers)."""

from __future__ import annotations

from unittest.mock import patch

from bot.remote_play import (
    PS5_EXE,
    XBOX_EXE,
    is_ps5_client_installed,
    is_xbox_client_installed,
    launch_ps5_client,
    launch_xbox_client,
    open_psn_lookup_tool,
    optimize_chiaki_settings,
)


def test_remote_play_binaries_installed():
    assert is_ps5_client_installed() is True
    assert PS5_EXE.exists()
    assert is_xbox_client_installed() is True
    assert XBOX_EXE.exists()


def test_open_psn_lookup_tool():
    with patch("webbrowser.open") as mock_open:
        open_psn_lookup_tool()
        mock_open.assert_called_once()


def test_launch_clients_mocked():
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = "mock_proc"
        proc = launch_ps5_client()
        assert proc == "mock_proc"
        mock_popen.assert_called_once()

    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = "mock_xbox"
        proc = launch_xbox_client()
        assert proc == "mock_xbox"
        mock_popen.assert_called_once()


def test_optimize_chiaki_settings():
    # Calling optimize_chiaki_settings on Windows writes to HKCU:\Software\Chiaki\Chiaki
    # or runs without crash
    res = optimize_chiaki_settings()
    assert isinstance(res, bool)
