"""PlayStation 5 and Console Streaming Subsystem Integration.

Automates launching, window tracking, and configuration of customized console
streaming clients (Chiaki PS4/PS5 and Xbox), and provides PSN Account ID
resolution helpers.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Final

import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PS5_DIR = PROJECT_ROOT / "remote_play" / "ps5"
PS5_EXE = PS5_DIR / "lu.exe"
XBOX_DIR = PROJECT_ROOT / "remote_play" / "xbox"
XBOX_EXE = XBOX_DIR / "xlu.exe"

PSN_LOOKUP_URL: Final[str] = "https://psn.flipscreen.games/"
PSN_TOOLS_URL: Final[str] = "https://www.psntools.com/psn/checker"

__all__ = [
    "PS5_DIR",
    "PS5_EXE",
    "XBOX_DIR",
    "XBOX_EXE",
    "is_ps5_client_installed",
    "is_xbox_client_installed",
    "launch_ps5_client",
    "launch_xbox_client",
    "open_psn_lookup_tool",
    "optimize_chiaki_settings",
]


def is_ps5_client_installed() -> bool:
    """Return True if the embedded PS5 streaming binary exists."""
    return PS5_EXE.is_file()


def is_xbox_client_installed() -> bool:
    """Return True if the embedded Xbox streaming binary exists."""
    return XBOX_EXE.is_file()


def launch_ps5_client() -> subprocess.Popen | None:
    """Launch embedded Chiaki PS5 streaming client in a detached process."""
    if not is_ps5_client_installed():
        return None

    try:
        flags = 0
        if sys.platform == "win32":
            # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
            flags = 0x00000008 | 0x00000200

        proc = subprocess.Popen(
            [str(PS5_EXE)],
            cwd=str(PS5_DIR),
            creationflags=flags,
            close_fds=True,
        )
        return proc
    except Exception:
        return None


def launch_xbox_client() -> subprocess.Popen | None:
    """Launch embedded Greenlight Xbox streaming client in a detached process."""
    if not is_xbox_client_installed():
        return None

    try:
        flags = 0
        if sys.platform == "win32":
            flags = 0x00000008 | 0x00000200

        proc = subprocess.Popen(
            [str(XBOX_EXE)],
            cwd=str(XBOX_DIR),
            creationflags=flags,
            close_fds=True,
        )
        return proc
    except Exception:
        return None


def open_psn_lookup_tool() -> None:
    """Open the PSN Account ID retrieval tool in the system browser."""
    try:
        webbrowser.open(PSN_LOOKUP_URL)
    except Exception:
        pass


def optimize_chiaki_settings() -> bool:
    """Configure Chiaki registry keys for maximum performance without chroma shift.

    Applies:
    - Video Decoder: Direct3D 11 VA (d3d11va) or software (prevents horizontal stride bug).
    - Codec: H.264 (lowest latency).
    """
    if sys.platform != "win32":
        return False

    try:
        import winreg

        reg_path = r"Software\Chiaki\Chiaki"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            # Set video codec and hardware decoder settings
            winreg.SetValueEx(key, "hardware_decoder", 0, winreg.REG_SZ, "d3d11va")
            winreg.SetValueEx(key, "codec", 0, winreg.REG_SZ, "h264")
            winreg.SetValueEx(key, "resolution", 0, winreg.REG_SZ, "1080p")
            winreg.SetValueEx(key, "fps", 0, winreg.REG_SZ, "60")
        return True
    except Exception:
        return False
