"""Main application entry point for the Closed-Loop Aim Trainer & AI Vision Bot.

This module initializes the application, sets up DPI awareness, creates the
display, starts the background vision/AI worker, and coordinates the 60 FPS
pygame main loop connecting the game engine, control panel, and AI assistant.
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path
from typing import Final

import pygame

import config
from bot.assistant import AIPerformanceCoach, CoachAdvice
from bot.capture import enable_dpi_awareness
from bot.worker import BotWorker
from core.game import GameSession, GameState
from core.ui import (
    GAME_RECT,
    ControlPanel,
    DebugView,
    TextRenderer,
    draw_cursor,
    draw_game_zone,
    load_fonts,
    shade,
)


def save_session_record(session: GameSession, cfg: config.Config, advice: CoachAdvice | None = None) -> Path:
    """Save session statistics and AI coach evaluation to disk as JSON.

    Args:
        session: Completed game session.
        cfg: Configuration active during the session.
        advice: Optional AI coach recommendations.

    Returns:
        The written Path.
    """
    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = config.SESSIONS_DIR / f"session_{timestamp}.json"

    data = {
        "timestamp": timestamp,
        "config": cfg.as_dict(),
        "stats": session.stats.as_dict(),
        "reaction_times_ms": [round(t * 1000.0, 1) for t in session.reaction_times],
        "ai_coach": (
            {
                "efficiency_score": advice.efficiency_score,
                "feedback": advice.feedback,
                "suggested_aim_speed": advice.suggested_aim_speed,
                "suggested_smoothing": advice.suggested_smoothing,
                "suggested_deadzone": advice.suggested_deadzone,
            }
            if advice is not None
            else None
        ),
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return filepath


def main() -> int:
    """Run the main application lifecycle."""
    # 1. Enable per-monitor DPI awareness before initializing pygame
    enable_dpi_awareness()

    # 2. Pygame setup
    pygame.init()
    pygame.font.init()

    pygame.display.set_caption(config.WINDOW_TITLE)
    screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
    pygame.mouse.set_visible(False)  # Custom crosshair cursor drawn by UI

    # 3. Load user configuration & instantiate core modules
    cfg = config.Config.load()
    fonts = load_fonts()
    text = TextRenderer(fonts)
    panel = ControlPanel(cfg, text)
    session = GameSession(cfg)

    # Toast notifications
    toast_text: str | None = None
    toast_until: float = 0.0

    def show_toast(msg: str) -> None:
        nonlocal toast_text, toast_until
        toast_text = msg
        toast_until = time.monotonic() + config.TOAST_SECONDS

    # 4. Initialize and start the background Bot/AI worker
    worker = BotWorker(
        cfg=cfg,
        window_handle_getter=lambda: pygame.display.get_wm_info()["window"],
        on_stop=show_toast,
        jump_reset_px=config.TRAINER_JUMP_RESET_PX,
    )
    worker.start()

    clock = pygame.time.Clock()
    running = True
    session_saved = False
    last_coach_advice: CoachAdvice | None = None

    # 5. Main Loop (60 FPS)
    while running:
        now = time.monotonic()
        previous_state = session.state

        # Update game rules
        session.update(now)

        # Handle session completion
        if session.state is GameState.FINISHED and not session_saved:
            session_saved = True
            last_coach_advice = AIPerformanceCoach.evaluate(
                session.shots, session.hits, session.reaction_times, cfg
            )
            save_session_record(session, cfg, last_coach_advice)
            show_toast(f"Session saved! AI Score: {last_coach_advice.efficiency_score}/100")
        elif session.state is not GameState.FINISHED:
            session_saved = False

        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            # Forward to control panel
            changed_keys = panel.handle_event(event)

            # Keyboard shortcuts
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    break
                elif event.key == pygame.K_SPACE:
                    if session.state in (GameState.IDLE, GameState.FINISHED):
                        session.start(now)
                elif event.key == pygame.K_r:
                    if session.state is GameState.FINISHED:
                        session.start(now)
                    else:
                        session.reset()
                elif event.key == pygame.K_b:
                    cfg.bot_enabled = not cfg.bot_enabled
                    show_toast("Bot ENABLED" if cfg.bot_enabled else "Bot DISABLED")
                elif event.key == pygame.K_m:
                    cfg.ai_assistant = not getattr(cfg, "ai_assistant", False)
                    show_toast("AI Assistant: ON" if cfg.ai_assistant else "AI Assistant: OFF")
                elif event.key == pygame.K_d:
                    cfg.debug_view = not cfg.debug_view

            # Human and bot mouse clicks
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                if GAME_RECT.collidepoint(mouse_pos):
                    # Click inside play area -> score it in session
                    local_x = float(mouse_pos[0] - GAME_RECT.left)
                    local_y = float(mouse_pos[1] - GAME_RECT.top)
                    session.register_click(local_x, local_y, now)

        # Rendering
        debug_view = worker.get_debug_view() if cfg.debug_view else None
        fps = clock.get_fps()

        # 1. Play area
        draw_game_zone(screen, session, now, text, fps=fps, debug=debug_view)

        # 2. Control panel
        panel.draw(screen)

        # 3. Toast banner if active
        if toast_text and now < toast_until:
            toast_rect = pygame.Rect(20, config.WINDOW_HEIGHT - 48, 480, 36)
            pygame.draw.rect(screen, config.PANEL_BACKGROUND, toast_rect, border_radius=8)
            pygame.draw.rect(screen, config.ACCENT, toast_rect, width=1, border_radius=8)
            text.draw(
                screen,
                toast_text,
                fonts.small,
                config.TEXT_PRIMARY,
                (toast_rect.left + 14, toast_rect.centery),
                anchor="midleft",
            )

        # 4. Custom cursor
        mouse_pos = pygame.mouse.get_pos()
        is_hot = False
        if session.target is not None and GAME_RECT.collidepoint(mouse_pos):
            local_x = float(mouse_pos[0] - GAME_RECT.left)
            local_y = float(mouse_pos[1] - GAME_RECT.top)
            is_hot = session.target.contains(local_x, local_y)

        draw_cursor(screen, mouse_pos, hot=is_hot)

        pygame.display.flip()
        clock.tick(config.TARGET_FPS)

    # 6. Clean shutdown
    worker.stop()
    cfg.save()
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
