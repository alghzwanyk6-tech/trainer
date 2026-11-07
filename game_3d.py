"""3D FPS Aim Trainer & Real-Time Tracking Verification Entry Point.

Run this script to launch the 3D arena. Connect your PS4 / PS5 / Xbox controller
or use your mouse/keyboard.
- Hold L2 (or RMB) to engage Aim-Assist Lock on 3D targets.
- Press R2 (or LMB) to shoot.
- Press B to toggle autonomous Auto-Bot mode.
- Press M to switch target movement evasive patterns.
- Press ESC to exit.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.game_3d import Game3DSession


def main() -> None:
    session = Game3DSession(width=1280, height=720)
    session.run()


if __name__ == "__main__":
    main()
