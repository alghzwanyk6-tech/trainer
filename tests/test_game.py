"""Unit tests for core game logic."""

import config
from core.game import GameSession, GameState, percentile


def test_percentile() -> None:
    assert percentile([], 0.5) == 0.0
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(values, 0.5) == 30.0
    assert percentile(values, 0.0) == 10.0
    assert percentile(values, 1.0) == 50.0


def test_game_session_lifecycle() -> None:
    cfg = config.Config(session_length_s=10.0)
    session = GameSession(cfg, seed=42)
    assert session.state == GameState.IDLE

    # Start countdown
    session.start(now=0.0)
    assert session.state == GameState.COUNTDOWN
    assert session.countdown_remaining(now=1.0) > 0.0

    # Advance past countdown -> RUNNING
    session.update(now=config.COUNTDOWN_SECONDS + 0.1)
    assert session.state == GameState.RUNNING
    assert session.target is not None

    # Clicking outside RUNNING or missed
    res_miss = session.register_click(x=0.0, y=0.0, now=config.COUNTDOWN_SECONDS + 0.2)
    assert res_miss.counted is True
    assert res_miss.hit is False
    assert session.shots == 1
    assert session.hits == 0

    # Successful hit
    target = session.target
    res_hit = session.register_click(x=target.x, y=target.y, now=config.COUNTDOWN_SECONDS + 0.5)
    assert res_hit.counted is True
    assert res_hit.hit is True
    assert session.hits == 1
    assert session.accuracy == 0.5

    # Advance past session duration -> FINISHED
    session.update(now=config.COUNTDOWN_SECONDS + 10.1)
    assert session.state == GameState.FINISHED
    assert session.target is None

    stats = session.stats
    assert stats.shots == 2
    assert stats.hits == 1
    assert stats.accuracy == 0.5


def test_game_session_determinism() -> None:
    cfg = config.Config()
    s1 = GameSession(cfg, seed=1234)
    s2 = GameSession(cfg, seed=1234)

    s1.start(0.0)
    s2.start(0.0)
    s1.update(config.COUNTDOWN_SECONDS + 0.1)
    s2.update(config.COUNTDOWN_SECONDS + 0.1)

    assert s1.target is not None and s2.target is not None
    assert s1.target.x == s2.target.x
    assert s1.target.y == s2.target.y
