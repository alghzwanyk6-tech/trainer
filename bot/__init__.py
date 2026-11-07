"""Vision bot: screen capture, colour detection, AI assistant and mouse control.

Modules
-------
capture:
    Fast screen grabs of the play area using ``mss``.
vision:
    OpenCV masking and target localisation.
controller:
    Cursor movement, smoothing and humanisation.
assistant:
    AI assistant models: smart detection, kinematic prediction, and performance coaching.
"""

from bot.assistant import (
    AIAssistant,
    AIPerformanceCoach,
    CoachAdvice,
    PredictiveAimModel,
    SmartDetection,
    SmartTargetDetector,
)
from bot.capture import ScreenCapture, ScreenRegion
from bot.controller import BotController
from bot.vision import ColorDetector, Detection, Detector

__all__ = [
    "AIAssistant",
    "AIPerformanceCoach",
    "BotController",
    "CoachAdvice",
    "ColorDetector",
    "Detection",
    "Detector",
    "PredictiveAimModel",
    "ScreenCapture",
    "ScreenRegion",
    "SmartDetection",
    "SmartTargetDetector",
]
