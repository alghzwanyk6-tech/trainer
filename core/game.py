"""Pure game logic for the aim trainer.

The module owns the rules of the game — target spawning, hit detection,
timing and score keeping — and nothing else. It never imports ``pygame``,
``cv2`` or ``mss``, and it never reads the wall clock on its own: every
timing-sensitive method takes the current time as an argument, which keeps
the whole engine deterministic and testable without a display.

Typical usage::

    session = GameSession(Config())
    session.start(now=0.0)
    session.update(now=3.1)              # countdown finished, first target
    result = session.register_click(x, y, now=3.9)
    print(result.hit, session.stats.accuracy)
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Final

import config

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class GameState(Enum):
    """Lifecycle of one session."""

    IDLE = auto()
    """Nothing is running; waiting for :meth:`GameSession.start`."""

    COUNTDOWN = auto()
    """Countdown before the timer starts; clicks are ignored."""

    RUNNING = auto()
    """Targets spawn and shots are scored."""

    FINISHED = auto()
    """The timer elapsed; the result screen is shown."""


@dataclass(frozen=True, slots=True)
class Target:
    """A single circular target in play-area coordinates.

    Attributes:
        x: Centre X in pixels, relative to the play area.
        y: Centre Y in pixels, relative to the play area.
        radius: Radius in pixels.
        spawned_at: Session time (seconds) at which the target appeared.
    """

    x: float
    y: float
    radius: float
    spawned_at: float

    def distance_to(self, px: float, py: float) -> float:
        """Return the Euclidean distance between the target centre and a point.

        Args:
            px: Point X in the same coordinate space as the target.
            py: Point Y in the same coordinate space as the target.

        Returns:
            The distance in pixels.
        """
        return math.hypot(px - self.x, py - self.y)

    def contains(self, px: float, py: float, padding: float = 0.0) -> bool:
        """Return ``True`` when the point lies inside the target.

        Args:
            px: Point X.
            py: Point Y.
            padding: Extra tolerance added to the radius (pixels).

        Returns:
            Whether the point counts as a hit.
        """
        return self.distance_to(px, py) <= self.radius + padding


@dataclass(frozen=True, slots=True)
class ClickResult:
    """Outcome of a single shot, returned by :meth:`GameSession.register_click`.

    Attributes:
        counted: ``False`` when the click happened outside a running session
            (idle, countdown, finished) and therefore changed nothing.
        hit: Whether the shot landed inside the target.
        reaction_ms: Time from target spawn to this click, in milliseconds.
            ``None`` when the shot was not counted.
        target: The target that was being shot at, if any.
    """

    counted: bool
    hit: bool = False
    reaction_ms: float | None = None
    target: Target | None = None


@dataclass(frozen=True, slots=True)
class SessionStats:
    """Aggregated results of a session, suitable for logging and display.

    All reaction times are measured from the moment the target spawned to the
    moment the click was processed, so human and bot sessions are comparable.

    Attributes:
        shots: Total clicks registered inside the play area.
        hits: Clicks that landed inside the target.
        accuracy: ``hits / shots`` in ``[0, 1]`` (``0.0`` when no shots).
        avg_ms: Mean reaction time in milliseconds.
        median_ms: Median reaction time.
        p95_ms: 95th percentile reaction time.
        min_ms: Fastest hit.
        max_ms: Slowest hit.
    """

    shots: int
    hits: int
    accuracy: float
    avg_ms: float
    median_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float

    def as_dict(self) -> dict[str, float | int]:
        """Return the stats as a flat mapping (handy for CSV/JSON logging)."""
        return {
            "shots": self.shots,
            "hits": self.hits,
            "accuracy": round(self.accuracy, 4),
            "avg_ms": round(self.avg_ms, 2),
            "median_ms": round(self.median_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def percentile(values: list[float], fraction: float) -> float:
    """Return an interpolated percentile of ``values``.

    Args:
        values: Non-empty sequence of numbers (order is irrelevant).
        fraction: Position in ``[0, 1]`` — e.g. ``0.95`` for the 95th percentile.

    Returns:
        The percentile value, or ``0.0`` when ``values`` is empty.

    Raises:
        ValueError: If ``fraction`` is outside ``[0, 1]``.
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be within [0, 1], got {fraction!r}")
    if not values:
        return 0.0
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


# ---------------------------------------------------------------------------
# Session engine
# ---------------------------------------------------------------------------


@dataclass
class GameSession:
    """State machine that implements one scored aim-training session.

    The session is driven from the outside: :meth:`start` begins the countdown,
    :meth:`update` advances time, and :meth:`register_click` reports shots.
    Nothing happens unless the caller provides a timestamp, which makes the
    engine fully deterministic in tests.

    Attributes:
        cfg: Live configuration; slider changes (target size, session length)
            take effect on the next spawned target / next session.
        play_width: Width of the play area in pixels.
        play_height: Height of the play area in pixels.
        state: Current :class:`GameState`.
        target: The target currently in play, if any.
        shots: Number of scored shots so far.
        hits: Number of successful shots so far.
        reaction_times: Reaction time of every successful shot, in seconds.
        seed: RNG seed used for target placement (``None`` = random).
    """

    cfg: config.Config
    play_width: int = config.GAME_ZONE_WIDTH
    play_height: int = config.WINDOW_HEIGHT
    seed: int | None = None

    state: GameState = field(default=GameState.IDLE, init=False)
    target: Target | None = field(default=None, init=False)
    shots: int = field(default=0, init=False)
    hits: int = field(default=0, init=False)
    reaction_times: list[float] = field(default_factory=list, init=False)

    _rng: random.Random = field(init=False, repr=False)
    _countdown_ends_at: float = field(default=0.0, init=False, repr=False)
    _started_at: float = field(default=0.0, init=False, repr=False)
    _finished_at: float = field(default=0.0, init=False, repr=False)
    _last_click_at: float = field(default=-math.inf, init=False, repr=False)

    def __post_init__(self) -> None:
        """Create the RNG and normalise the configuration."""
        self._rng = random.Random(self.seed)
        self.cfg = self.cfg.clamped()

    # -- lifecycle ---------------------------------------------------------

    def start(self, now: float) -> None:
        """Begin a new session, resetting all scores and starting the countdown.

        Args:
            now: Current monotonic time in seconds.
        """
        self.shots = 0
        self.hits = 0
        self.reaction_times.clear()
        self.target = None
        self._rng = random.Random(self.seed)
        self._countdown_ends_at = now + config.COUNTDOWN_SECONDS
        self._started_at = self._countdown_ends_at
        self._finished_at = 0.0
        self._last_click_at = -math.inf
        self.state = GameState.COUNTDOWN

    def reset(self) -> None:
        """Return to :class:`GameState.IDLE` and discard the current scores."""
        self.state = GameState.IDLE
        self.target = None
        self.shots = 0
        self.hits = 0
        self.reaction_times.clear()

    def update(self, now: float) -> None:
        """Advance the state machine to ``now``.

        Transitions ``COUNTDOWN → RUNNING`` (spawning the first target) and
        ``RUNNING → FINISHED`` when the session timer elapses. Safe to call
        every frame.

        Args:
            now: Current monotonic time in seconds.
        """
        if self.state is GameState.COUNTDOWN and now >= self._countdown_ends_at:
            self.state = GameState.RUNNING
            self._started_at = now
            self._spawn_target(now)
        elif self.state is GameState.RUNNING and self.remaining(now) <= 0.0:
            self.state = GameState.FINISHED
            self._finished_at = now
            self.target = None

    # -- queries -----------------------------------------------------------

    def remaining(self, now: float) -> float:
        """Return the seconds left in the running session.

        Args:
            now: Current monotonic time in seconds.

        Returns:
            Remaining seconds, clamped to ``[0, session length]``.
        """
        if self.state in (GameState.IDLE, GameState.COUNTDOWN):
            return self.cfg.session_length_s
        if self.state is GameState.FINISHED:
            return 0.0
        elapsed = max(0.0, now - self._started_at)
        return max(0.0, self.cfg.session_length_s - elapsed)

    def countdown_remaining(self, now: float) -> float:
        """Return the seconds left before the session starts.

        Args:
            now: Current monotonic time in seconds.

        Returns:
            Countdown seconds clamped to ``[0, COUNTDOWN_SECONDS]``.
        """
        if self.state is not GameState.COUNTDOWN:
            return 0.0
        return max(0.0, self._countdown_ends_at - now)

    def elapsed(self, now: float) -> float:
        """Return how long the scored session has been running.

        Args:
            now: Current monotonic time in seconds.

        Returns:
            Elapsed seconds, ``0.0`` outside the running state.
        """
        if self.state is not GameState.RUNNING:
            return 0.0
        return max(0.0, now - self._started_at)

    def last_click_age(self, now: float) -> float:
        """Return seconds since the most recent counted click.

        Args:
            now: Current monotonic time in seconds.

        Returns:
            Age in seconds; ``inf`` when nothing has been clicked yet.
        """
        return now - self._last_click_at

    # -- input -------------------------------------------------------------

    def register_click(self, x: float, y: float, now: float) -> ClickResult:
        """Score one click at play-area coordinates ``(x, y)``.

        A click counts as a shot whenever the session is running — including
        clicks that miss the target — so accuracy cannot be inflated by
        clicking only when certain.

        Args:
            x: Click X in play-area pixels.
            y: Click Y in play-area pixels.
            now: Current monotonic time in seconds.

        Returns:
            A :class:`ClickResult`; ``counted`` is ``False`` when the session
            was not running and nothing changed.
        """
        target = self.target
        if self.state is not GameState.RUNNING or target is None:
            return ClickResult(counted=False)

        self.shots += 1
        self._last_click_at = now
        hit = target.contains(x, y, padding=config.HIT_PADDING_PX)
        reaction_ms = max(0.0, (now - target.spawned_at) * 1000.0)

        if not hit:
            return ClickResult(
                counted=True,
                hit=False,
                reaction_ms=reaction_ms,
                target=target,
            )

        self.hits += 1
        self.reaction_times.append(max(0.0, now - target.spawned_at))
        next_target = self._spawn_target(now)
        return ClickResult(
            counted=True,
            hit=True,
            reaction_ms=reaction_ms,
            target=next_target,
        )

    # -- scoring -----------------------------------------------------------

    @property
    def accuracy(self) -> float:
        """Return ``hits / shots`` as a fraction in ``[0, 1]``."""
        if self.shots <= 0:
            return 0.0
        return self.hits / self.shots

    @property
    def stats(self) -> SessionStats:
        """Return the aggregated metrics of the session so far."""
        times_ms = [value * 1000.0 for value in self.reaction_times]
        return SessionStats(
            shots=self.shots,
            hits=self.hits,
            accuracy=self.accuracy,
            avg_ms=statistics.fmean(times_ms) if times_ms else 0.0,
            median_ms=statistics.median(times_ms) if times_ms else 0.0,
            p95_ms=percentile(times_ms, 0.95),
            min_ms=min(times_ms) if times_ms else 0.0,
            max_ms=max(times_ms) if times_ms else 0.0,
        )

    # -- internal ----------------------------------------------------------

    def _spawn_target(self, now: float) -> Target:
        """Place a new target and store it as the active one.

        The target is kept fully inside the play area (``TARGET_MARGIN_PX``)
        and clear of the HUD strip at the top (``HUD_HEIGHT`` plus
        ``HUD_GAP_PX``), and at least ``MIN_TARGET_DISTANCE_PX`` away from the
        previous centre. If the constraint cannot be met after 32 attempts,
        the farthest candidate found is used, so spawning never fails.

        Args:
            now: Session time used as the spawn timestamp.

        Returns:
            The newly created :class:`Target`.
        """
        radius = min(self.cfg.target_radius_px, min(self.play_width, self.play_height) / 3.0)
        margin = config.TARGET_MARGIN_PX + radius
        top_margin = config.HUD_HEIGHT + config.HUD_GAP_PX + radius
        low_x, high_x = margin, max(margin, self.play_width - margin)
        low_y, high_y = top_margin, max(top_margin, self.play_height - margin)
        previous = self.target

        best: tuple[float, float] = (high_x, high_y)
        best_distance = -1.0
        for _ in range(32):
            candidate_x = self._rng.uniform(low_x, high_x)
            candidate_y = self._rng.uniform(low_y, high_y)
            if previous is None:
                best = (candidate_x, candidate_y)
                break
            distance = math.hypot(candidate_x - previous.x, candidate_y - previous.y)
            if distance >= config.MIN_TARGET_DISTANCE_PX:
                best = (candidate_x, candidate_y)
                break
            if distance > best_distance:
                best_distance = distance
                best = (candidate_x, candidate_y)

        self.target = Target(x=best[0], y=best[1], radius=radius, spawned_at=now)
        return self.target
