"""Pygame presentation layer for the Aim Trainer & Vision Bot.

This module owns every pixel that reaches the window: the control panel with
its sliders, toggles and reset button, the play-area visuals (target, HUD,
countdown, results screen) and the optional vision debug overlay.

It deliberately contains **no game rules and no computer vision**. The game
engine decides when a target spawns and whether a click counts; the bot
decides where the target is. The UI only reads their data and draws it, which
keeps pygame confined to one file.

Typical usage::

    pygame.init()
    screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
    text = ui.TextRenderer(ui.load_fonts())
    panel = ui.ControlPanel(cfg, text)
    session = GameSession(cfg)

    for event in pygame.event.get():
        panel.handle_event(event)          # returns the keys that changed

    ui.draw_game_zone(screen, session, now, text, fps=60.0, debug=debug)
    panel.draw(screen)
    ui.draw_cursor(screen, pygame.mouse.get_pos(), hot=False)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import pygame

import config
from core.game import GameSession, GameState, Target

# ---------------------------------------------------------------------------
# Layout constants (UI-only; shared values live in ``config``)
# ---------------------------------------------------------------------------

GAME_RECT: pygame.Rect = pygame.Rect(*config.GAME_ZONE_BOUNDS)
"""Play-area rectangle in window coordinates."""

GRID_STEP_PX: int = 50
"""Spacing of the faint background grid drawn behind the targets."""

TRACK_HEIGHT_PX: int = 6
"""Thickness of a slider track."""

HANDLE_RADIUS_PX: int = 7
"""Radius of the draggable slider handle."""

TOGGLE_WIDTH_PX: int = 48
TOGGLE_HEIGHT_PX: int = 24
"""Size of the pill-shaped on/off switch."""

PANEL_HEADER_HEIGHT_PX: int = 74
"""Vertical space reserved for the panel title and bot status."""

PANEL_FOOTER_HEIGHT_PX: int = 62
"""Vertical space reserved for the contextual help and key hints."""

BUTTON_HEIGHT_PX: int = 42
"""Height of the ``Reset defaults`` button."""

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

RGB = config.RGB


def shade(color: RGB, factor: float) -> RGB:
    """Return ``color`` multiplied by ``factor`` and clamped to 0-255.

    Values above ``1.0`` lighten a colour, values below ``1.0`` darken it.
    The helper is used to derive borders, tracks and glows from the palette in
    :mod:`config` instead of hard-coding extra colours here.

    Args:
        color: Source RGB tuple.
        factor: Multiplier applied to every channel.

    Returns:
        A new RGB tuple with each channel clamped into ``[0, 255]``.
    """
    return tuple(int(max(0.0, min(255.0, channel * factor))) for channel in color)  # type: ignore[return-value]


def format_seconds(seconds: float) -> str:
    """Format a countdown for the HUD.

    Args:
        seconds: Remaining or elapsed seconds (negative values clamp to zero).

    Returns:
        ``"8.4"`` while fewer than ten seconds remain, otherwise ``"0:27"``.
    """
    value = max(0.0, float(seconds))
    if value < 10.0:
        return f"{value:.1f}"
    minutes, rest = divmod(int(value), 60)
    return f"{minutes}:{rest:02d}"


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Split ``text`` into lines that fit inside ``max_width`` pixels.

    Args:
        text: Unwrapped sentence.
        font: Font used to measure the words.
        max_width: Maximum line width in pixels.

    Returns:
        A list of lines; long single words are kept intact rather than cut.
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if not current or font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Fonts and text rendering
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Fonts:
    """Font set used across the interface.

    Attributes:
        title: Hero title on the idle screen and the panel header.
        heading: Section and overlay headings.
        label: Control labels and body text.
        value: Numeric readouts (bold for emphasis).
        small: Help text, hints and captions.
        hud_label: Uppercase captions inside the HUD strip.
        hud_value: Large HUD numbers.
        huge: Countdown digits and the result accuracy.
    """

    title: pygame.font.Font
    heading: pygame.font.Font
    label: pygame.font.Font
    value: pygame.font.Font
    small: pygame.font.Font
    hud_label: pygame.font.Font
    hud_value: pygame.font.Font
    huge: pygame.font.Font


def load_fonts() -> Fonts:
    """Build the interface font set, falling back to pygame's default font.

    Returns:
        A :class:`Fonts` instance. Missing system fonts never break the app;
        pygame's bundled font is used instead.
    """
    if not pygame.font.get_init():
        pygame.font.init()

    def build(size: int, bold: bool = False) -> pygame.font.Font:
        """Return a system font at ``size`` px, or pygame's built-in font."""
        try:
            return pygame.font.SysFont("segoeui,arial,helvetica", size, bold=bold)
        except Exception:  # pragma: no cover - depends on the host system
            return pygame.font.Font(None, size)

    return Fonts(
        title=build(34, True),
        heading=build(20, True),
        label=build(15),
        value=build(15, True),
        small=build(12),
        hud_label=build(11, True),
        hud_value=build(20, True),
        huge=build(72, True),
    )


class TextRenderer:
    """Draws text through a bounded surface cache.

    Rendering a text surface every frame is wasteful, so results are memoised
    by ``(font, text, colour)``. The cache is cleared wholesale once it grows
    past ``cache_limit`` entries, which bounds memory without the bookkeeping
    of an LRU.
    """

    def __init__(self, fonts: Fonts, cache_limit: int = 512) -> None:
        """Create the renderer.

        Args:
            fonts: Font set produced by :func:`load_fonts`.
            cache_limit: Maximum number of cached text surfaces.
        """
        self.fonts = fonts
        self._cache: dict[tuple[int, str, RGB], pygame.Surface] = {}
        self._cache_limit = cache_limit

    def render(self, text: str, font: pygame.font.Font, color: RGB) -> pygame.Surface:
        """Return a rendered (and cached) surface for ``text``.

        Args:
            text: String to render.
            font: Font to use.
            color: RGB foreground colour.

        Returns:
            An antialiased surface owned by the cache; do not mutate it.
        """
        key = (id(font), text, color)
        image = self._cache.get(key)
        if image is None:
            if len(self._cache) >= self._cache_limit:
                self._cache.clear()
            image = font.render(text, True, color)
            self._cache[key] = image
        return image

    def draw(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: RGB,
        pos: tuple[float, float] | tuple[int, int],
        anchor: str = "topleft",
    ) -> pygame.Rect:
        """Render ``text`` and blit it at ``pos`` using ``anchor``.

        Args:
            surface: Destination surface.
            text: String to draw.
            font: Font to use.
            color: RGB foreground colour.
            pos: Anchor position in destination coordinates.
            anchor: Any pygame rect anchor, e.g. ``"center"`` or ``"topright"``.

        Returns:
            The rectangle the text occupies on screen.
        """
        image = self.render(text, font, color)
        rect = image.get_rect()
        setattr(rect, anchor, pos)
        surface.blit(image, rect)
        return rect


# ---------------------------------------------------------------------------
# Control widgets
# ---------------------------------------------------------------------------


class Widget:
    """Base class for one interactive row in the control panel.

    Subclasses read and write a single control of the shared
    :class:`config.Config` and draw a label plus their own affordance.

    Attributes:
        spec: Declarative control description from :data:`config.CONTROLS`.
        rect: Row rectangle in window coordinates.
        cfg: Live configuration mutated through :meth:`config.Config.set_value`.
        hovered: Whether the mouse is currently over the row.
        focused: Whether the row is the keyboard focus.
    """

    def __init__(
        self,
        spec: config.ControlSpec,
        rect: pygame.Rect,
        cfg: config.Config,
    ) -> None:
        """Create the widget.

        Args:
            spec: Control description that defines the value and its range.
            rect: Row rectangle in window coordinates.
            cfg: Configuration instance the widget reads and writes.
        """
        self.spec = spec
        self.rect = pygame.Rect(rect)
        self.cfg = cfg
        self.hovered = False
        self.focused = False

    # -- value plumbing ----------------------------------------------------

    @property
    def value(self) -> object:
        """Return the control's current value from the configuration."""
        return self.cfg.value(self.spec.key)

    def store(self, value: object) -> bool:
        """Store a normalised value and report whether anything changed.

        Args:
            value: Raw value; :meth:`config.Config.set_value` clamps toggles
                and sliders to their legal range.

        Returns:
            ``True`` when the stored value differs from the previous one.
        """
        before = self.value
        after = self.cfg.set_value(self.spec.key, value)
        return after != before

    def format_value(self) -> str:
        """Return the value formatted for display (``"0.35"``, ``"120 ms"``)."""
        value = self.value
        if isinstance(value, bool):
            return "ON" if value else "OFF"
        number = f"{float(value):.{max(0, self.spec.decimals)}f}"
        return f"{number} {self.spec.unit}".strip()

    def hit(self, pos: Sequence[float]) -> bool:
        """Return ``True`` when ``pos`` lies inside the widget row."""
        return self.rect.collidepoint(pos)

    def help_text(self) -> str:
        """Return the explanation shown in the panel footer on hover."""
        return self.spec.help

    # -- pygame protocol ---------------------------------------------------

    def draw(self, surface: pygame.Surface, text: TextRenderer) -> None:
        """Draw the widget.

        Args:
            surface: Destination surface (the window).
            text: Shared text renderer.
        """
        raise NotImplementedError

    def handle_event(self, event: pygame.event.Event) -> bool:
        """React to one pygame event.

        Args:
            event: Event popped from the pygame queue.

        Returns:
            ``True`` when the control's value changed.
        """
        return False


class SliderWidget(Widget):
    """Horizontal slider bound to one numeric control.

    The whole row is clickable: pressing anywhere on it jumps the handle to
    that position and starts a drag. The mouse wheel nudges the value by one
    step while hovered, and the arrow keys adjust the focused slider.
    """

    def __init__(
        self,
        spec: config.ControlSpec,
        rect: pygame.Rect,
        cfg: config.Config,
    ) -> None:
        """Create the slider; see :class:`Widget` for the arguments."""
        super().__init__(spec, rect, cfg)
        self.dragging = False

    # -- geometry ----------------------------------------------------------

    @property
    def fraction(self) -> float:
        """Return the handle position as a fraction of the slider range."""
        span = self.spec.maximum - self.spec.minimum
        if span <= 0.0:
            return 0.0
        return min(1.0, max(0.0, (float(self.value) - self.spec.minimum) / span))

    @property
    def track_rect(self) -> pygame.Rect:
        """Return the drawn track rectangle (inset so the handle never clips)."""
        inset = HANDLE_RADIUS_PX + 2
        top = self.rect.top + max(28, self.rect.height - 20)
        return pygame.Rect(
            self.rect.left + inset,
            top,
            max(1, self.rect.width - 2 * inset),
            TRACK_HEIGHT_PX,
        )

    # -- interaction -------------------------------------------------------

    def _set_from_x(self, x: float) -> bool:
        """Move the handle to ``x`` (window pixels) and store the value."""
        track = self.track_rect
        span = self.spec.maximum - self.spec.minimum
        fraction = (x - track.left) / max(1, track.width)
        fraction = min(1.0, max(0.0, fraction))
        return self.store(self.spec.minimum + fraction * span)

    def _nudge(self, delta: float) -> bool:
        """Change the current value by ``delta`` (already in control units)."""
        return self.store(float(self.value) + delta)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle drag, wheel and keyboard input for the slider."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hit(event.pos):
                self.dragging = True
                return self._set_from_x(event.pos[0])
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            return self._set_from_x(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return False
        elif event.type == pygame.MOUSEWHEEL and self.hovered:
            return self._nudge(self.spec.step if event.y > 0 else -self.spec.step)
        elif event.type == pygame.KEYDOWN and self.focused:
            if event.key in (pygame.K_LEFT, pygame.K_DOWN):
                return self._nudge(-self.spec.step)
            if event.key in (pygame.K_RIGHT, pygame.K_UP):
                return self._nudge(self.spec.step)
            if event.key == pygame.K_PAGEUP:
                return self._nudge(self.spec.step * 5)
            if event.key == pygame.K_PAGEDOWN:
                return self._nudge(-self.spec.step * 5)
            if event.key == pygame.K_HOME:
                return self.store(self.spec.minimum)
            if event.key == pygame.K_END:
                return self.store(self.spec.maximum)
        return False

    # -- drawing -----------------------------------------------------------

    def draw(self, surface: pygame.Surface, text: TextRenderer) -> None:
        """Draw the label, value readout, track and handle."""
        active = self.hovered or self.focused or self.dragging
        track = self.track_rect

        text.draw(
            surface,
            self.spec.label,
            text.fonts.label,
            config.TEXT_PRIMARY,
            (self.rect.left, self.rect.top + 2),
        )
        text.draw(
            surface,
            self.format_value(),
            text.fonts.value,
            config.ACCENT if active else config.TEXT_PRIMARY,
            (self.rect.right, self.rect.top + 2),
            anchor="topright",
        )

        pygame.draw.rect(
            surface,
            shade(config.PANEL_BACKGROUND, 1.55),
            track,
            border_radius=TRACK_HEIGHT_PX // 2,
        )
        filled = pygame.Rect(
            track.left,
            track.top,
            int(track.width * self.fraction),
            TRACK_HEIGHT_PX,
        )
        if filled.width > 0:
            pygame.draw.rect(
                surface,
                config.ACCENT,
                filled,
                border_radius=TRACK_HEIGHT_PX // 2,
            )

        center = (track.left + int(round(track.width * self.fraction)), track.centery)
        if active:
            pygame.draw.circle(surface, config.ACCENT, center, HANDLE_RADIUS_PX + 4, 2)
        pygame.draw.circle(surface, config.TEXT_PRIMARY, center, HANDLE_RADIUS_PX)
        pygame.draw.circle(surface, config.ACCENT, center, HANDLE_RADIUS_PX - 3)


class ToggleWidget(Widget):
    """Pill-shaped on/off switch bound to one boolean control."""

    @property
    def pill_rect(self) -> pygame.Rect:
        """Return the switch rectangle, right-aligned inside the row."""
        return pygame.Rect(
            self.rect.right - TOGGLE_WIDTH_PX,
            self.rect.centery - TOGGLE_HEIGHT_PX // 2,
            TOGGLE_WIDTH_PX,
            TOGGLE_HEIGHT_PX,
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Toggle on left click anywhere on the row, or Space/Enter when focused."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hit(event.pos):
                return self.store(not bool(self.value))
        elif event.type == pygame.KEYDOWN and self.focused:
            if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                return self.store(not bool(self.value))
        return False

    def draw(self, surface: pygame.Surface, text: TextRenderer) -> None:
        """Draw the label, ON/OFF readout and the animated-looking switch."""
        on = bool(self.value)
        pill = self.pill_rect
        accent = config.ACCENT_ACTIVE if on else config.TEXT_MUTED

        text.draw(
            surface,
            self.spec.label,
            text.fonts.label,
            config.TEXT_PRIMARY,
            (self.rect.left, self.rect.centery),
            anchor="midleft",
        )
        text.draw(
            surface,
            self.format_value(),
            text.fonts.value,
            accent,
            (pill.left - 12, self.rect.centery),
            anchor="midright",
        )

        pygame.draw.rect(
            surface,
            config.ACCENT_ACTIVE if on else shade(config.PANEL_BACKGROUND, 1.75),
            pill,
            border_radius=TOGGLE_HEIGHT_PX // 2,
        )
        knob_x = pill.right - TOGGLE_HEIGHT_PX // 2 if on else pill.left + TOGGLE_HEIGHT_PX // 2
        knob = (knob_x, pill.centery)
        if self.hovered or self.focused:
            pygame.draw.circle(surface, accent, knob, TOGGLE_HEIGHT_PX // 2 + 4, 2)
        pygame.draw.circle(surface, config.TEXT_PRIMARY, knob, TOGGLE_HEIGHT_PX // 2 - 3)


class ButtonWidget:
    """Simple push button used for ``Reset defaults``.

    Attributes:
        rect: Button rectangle in window coordinates.
        label: Caption drawn inside the button.
        hovered: Whether the mouse is currently over the button.
    """

    def __init__(self, rect: pygame.Rect, label: str) -> None:
        """Create the button.

        Args:
            rect: Button rectangle in window coordinates.
            label: Caption drawn inside the button.
        """
        self.rect = pygame.Rect(rect)
        self.label = label
        self.hovered = False
        self._pressed = False

    def hit(self, pos: Sequence[float]) -> bool:
        """Return ``True`` when ``pos`` lies inside the button."""
        return self.rect.collidepoint(pos)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Track the press and report a completed click.

        A click only counts when the button is pressed and released over it.

        Args:
            event: Event popped from the pygame queue.

        Returns:
            ``True`` when a full click was completed.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._pressed = self.hit(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            clicked = self._pressed and self.hit(event.pos)
            self._pressed = False
            return clicked
        return False

    def draw(self, surface: pygame.Surface, text: TextRenderer) -> None:
        """Draw the button background, border and caption."""
        background = shade(config.PANEL_SECTION, 1.15 if self.hovered else 1.0)
        if self._pressed:
            background = shade(config.PANEL_SECTION, 0.85)
        pygame.draw.rect(surface, background, self.rect, border_radius=10)
        pygame.draw.rect(
            surface,
            config.ACCENT if self.hovered else shade(config.PANEL_SECTION, 1.6),
            self.rect,
            width=1,
            border_radius=10,
        )
        text.draw(
            surface,
            self.label,
            text.fonts.label,
            config.ACCENT if self.hovered else config.TEXT_PRIMARY,
            self.rect.center,
            anchor="center",
        )


# ---------------------------------------------------------------------------
# Control panel
# ---------------------------------------------------------------------------


class ControlPanel:
    """Interactive panel built automatically from :data:`config.CONTROLS`.

    The panel owns no window and no clock: it lays widgets out inside a
    rectangle, forwards pygame events to them and draws them. Every change is
    written straight into the shared :class:`config.Config`, so the game and
    the bot see new values on their next tick.

    Attributes:
        cfg: Configuration mutated by the widgets.
        text: Shared text renderer.
        rect: Panel rectangle in window coordinates.
        widgets: One widget per entry in :data:`config.CONTROLS`, in order.
        reset_button: Button that restores every default.
        hovered_widget: Widget under the mouse, used for the footer help.
        focused_key: Key of the widget that receives keyboard input.
    """

    RESET_LABEL = "Reset defaults"
    """Caption of the button that restores the factory configuration."""

    HELP_HINT = "Hover a control to read what it does."
    """Fallback text shown in the footer when nothing is hovered."""

    KEY_HINT = "B bot   ·   M AI assist   ·   D debug   ·   R restart   ·   Esc quit"
    """Keyboard cheatsheet shown at the bottom of the panel."""

    def __init__(
        self,
        cfg: config.Config,
        text: TextRenderer,
        rect: pygame.Rect | None = None,
    ) -> None:
        """Build the panel and lay its widgets out.

        Args:
            cfg: Shared configuration the widgets read and write.
            text: Shared text renderer.
            rect: Panel rectangle; defaults to :data:`config.PANEL_BOUNDS`.
        """
        self.cfg = cfg
        self.text = text
        self.rect = pygame.Rect(rect) if rect is not None else pygame.Rect(*config.PANEL_BOUNDS)
        self.widgets: list[Widget] = []
        self.reset_button: ButtonWidget | None = None
        self.hovered_widget: Widget | None = None
        self.focused_key: str | None = None
        self._footer_top = 0
        self._layout()

    # -- layout ------------------------------------------------------------

    def _layout(self) -> None:
        """Create the widgets and position them inside :attr:`rect`."""
        left = self.rect.left + config.PANEL_PADDING
        width = self.rect.width - 2 * config.PANEL_PADDING
        rows_top = self.rect.top + config.PANEL_PADDING + PANEL_HEADER_HEIGHT_PX

        self._footer_top = self.rect.bottom - config.PANEL_PADDING - PANEL_FOOTER_HEIGHT_PX
        button_top = self._footer_top - 14 - BUTTON_HEIGHT_PX
        self.reset_button = ButtonWidget(
            pygame.Rect(left, button_top, width, BUTTON_HEIGHT_PX),
            self.RESET_LABEL,
        )

        rows_bottom = button_top - 12
        count = max(1, len(config.CONTROLS))
        row_height = max(46, (rows_bottom - rows_top) // count)

        self.widgets = []
        for index, spec in enumerate(config.CONTROLS):
            row = pygame.Rect(left, rows_top + index * row_height, width, row_height)
            widget: Widget
            if spec.is_toggle():
                widget = ToggleWidget(spec, row, self.cfg)
            else:
                widget = SliderWidget(spec, row, self.cfg)
            self.widgets.append(widget)

    def widget_for(self, key: str) -> Widget | None:
        """Return the widget bound to ``key``, or ``None`` when unknown.

        Args:
            key: Control key from :data:`config.CONTROLS`.

        Returns:
            The matching widget if the panel contains one.
        """
        return next((widget for widget in self.widgets if widget.spec.key == key), None)

    @property
    def dragging(self) -> bool:
        """Return ``True`` while the user is dragging any slider."""
        return any(getattr(widget, "dragging", False) for widget in self.widgets)

    # -- interaction -------------------------------------------------------

    def _update_hover(self, pos: Sequence[float]) -> None:
        """Refresh hover flags for every widget and the reset button."""
        self.hovered_widget = None
        for widget in self.widgets:
            widget.hovered = widget.hit(pos)
            if widget.hovered:
                self.hovered_widget = widget
        if self.reset_button is not None:
            self.reset_button.hovered = self.reset_button.hit(pos)

    def _focus_at(self, pos: Sequence[float]) -> None:
        """Move the keyboard focus to the widget under ``pos``."""
        target = next((widget for widget in self.widgets if widget.hit(pos)), None)
        self.focused_key = target.spec.key if target is not None else None
        for widget in self.widgets:
            widget.focused = widget.spec.key == self.focused_key

    def handle_event(self, event: pygame.event.Event) -> list[str]:
        """Dispatch one event to the panel.

        Args:
            event: Event popped from the pygame queue.

        Returns:
            The keys whose values changed, ready for logging or live
            reactions. A completed ``Reset defaults`` click returns every key.
        """
        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._update_hover(event.pos)
            self._focus_at(event.pos)
        elif event.type == pygame.WINDOWLEAVE:
            # A release outside the window never reaches us: stop dragging and
            # drop hover states so the panel cannot stay in a stuck highlight.
            for widget in self.widgets:
                widget.hovered = False
                if isinstance(widget, SliderWidget):
                    widget.dragging = False
            self.hovered_widget = None
            if self.reset_button is not None:
                self.reset_button.hovered = False

        changed: list[str] = []
        for widget in self.widgets:
            if widget.handle_event(event):
                changed.append(widget.spec.key)

        if self.reset_button is not None and self.reset_button.handle_event(event):
            self.cfg.reset()
            changed = [spec.key for spec in config.CONTROLS]
        return changed

    def reset(self) -> list[str]:
        """Restore every control to its default and return the affected keys."""
        self.cfg.reset()
        return [spec.key for spec in config.CONTROLS]

    # -- drawing -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the whole panel: header, rows, reset button and footer.

        Args:
            surface: Destination surface (the window).
        """
        text = self.text
        left = self.rect.left + config.PANEL_PADDING
        content_width = self.rect.width - 2 * config.PANEL_PADDING

        pygame.draw.rect(surface, config.PANEL_BACKGROUND, self.rect)
        pygame.draw.line(
            surface,
            shade(config.ACCENT, 0.35),
            (self.rect.left, self.rect.top),
            (self.rect.left, self.rect.bottom),
            2,
        )

        text.draw(
            surface,
            "CONTROL PANEL",
            text.fonts.heading,
            config.TEXT_PRIMARY,
            (left, self.rect.top + config.PANEL_PADDING - 2),
        )

        status_color = config.ACCENT_ACTIVE if self.cfg.bot_enabled else config.TEXT_MUTED
        status_label = "BOT RUNNING" if self.cfg.bot_enabled else "BOT IDLE"
        status_pos = (left + 4, self.rect.top + config.PANEL_PADDING + 42)
        pygame.draw.circle(surface, status_color, status_pos, 4)
        text.draw(
            surface,
            status_label,
            text.fonts.small,
            status_color,
            (status_pos[0] + 12, status_pos[1]),
            anchor="midleft",
        )
        text.draw(
            surface,
            f"{self.cfg.target_size_px:.0f}px target   ·   {self.cfg.session_length_s:.0f}s session",
            text.fonts.small,
            config.TEXT_MUTED,
            (self.rect.right - config.PANEL_PADDING, status_pos[1]),
            anchor="midright",
        )

        divider = shade(config.PANEL_BACKGROUND, 1.22)
        for index, widget in enumerate(self.widgets):
            if index:
                pygame.draw.line(
                    surface,
                    divider,
                    (left, widget.rect.top),
                    (left + content_width, widget.rect.top),
                )
            widget.draw(surface, text)

        if self.reset_button is not None:
            self.reset_button.draw(surface, text)

        help_text = (
            self.hovered_widget.help_text()
            if self.hovered_widget is not None
            else self.HELP_HINT
        )
        line_y = self._footer_top
        for line in wrap_text(help_text, text.fonts.small, content_width)[:2]:
            text.draw(surface, line, text.fonts.small, config.TEXT_MUTED, (left, line_y))
            line_y += 17

        text.draw(
            surface,
            self.KEY_HINT,
            text.fonts.small,
            shade(config.TEXT_MUTED, 0.8),
            (left, self.rect.bottom - config.PANEL_PADDING - 14),
        )


# ---------------------------------------------------------------------------
# Play-area rendering
# ---------------------------------------------------------------------------


def _draw_grid(surface: pygame.Surface) -> None:
    """Paint the faint reference grid behind everything in the play area."""
    color = shade(config.GAME_BACKGROUND, 1.22)
    for x in range(GAME_RECT.left + GRID_STEP_PX, GAME_RECT.right, GRID_STEP_PX):
        pygame.draw.line(surface, color, (x, GAME_RECT.top), (x, GAME_RECT.bottom))
    for y in range(GAME_RECT.top + GRID_STEP_PX, GAME_RECT.bottom, GRID_STEP_PX):
        pygame.draw.line(surface, color, (GAME_RECT.left, y), (GAME_RECT.right, y))


def _draw_target(surface: pygame.Surface, target: Target, now: float) -> None:
    """Draw the current target with a short spawn animation and inner rings."""
    age = max(0.0, now - target.spawned_at)
    grow = min(1.0, age / 0.10)
    radius = max(2.0, target.radius * (0.72 + 0.28 * grow))
    center = (
        int(round(GAME_RECT.left + target.x)),
        int(round(GAME_RECT.top + target.y)),
    )

    pygame.draw.circle(surface, shade(config.TARGET_RED, 1.55), center, int(radius) + 5, 2)
    pygame.draw.circle(surface, config.TARGET_RED, center, int(radius))
    pygame.draw.circle(
        surface,
        shade(config.TARGET_RED, 1.4),
        center,
        max(2, int(radius * 0.62)),
        2,
    )
    pygame.draw.circle(
        surface,
        shade(config.TARGET_RED, 1.85),
        center,
        max(2, int(radius * 0.2)),
    )


def draw_hud(
    surface: pygame.Surface,
    session: GameSession,
    now: float,
    text: TextRenderer,
    *,
    fps: float = 0.0,
) -> None:
    """Draw the heads-up strip: timer, shots, accuracy, timings and FPS.

    Args:
        surface: Destination surface.
        session: Session whose live metrics are displayed.
        now: Current monotonic time in seconds.
        text: Shared text renderer.
        fps: Measured frame rate of the main loop.
    """
    bar = pygame.Rect(GAME_RECT.left, GAME_RECT.top, GAME_RECT.width, config.HUD_HEIGHT)
    pygame.draw.rect(surface, shade(config.GAME_BACKGROUND, 0.72), bar)
    pygame.draw.line(
        surface,
        shade(config.ACCENT, 0.45),
        (bar.left, bar.bottom - 1),
        (bar.right, bar.bottom - 1),
    )

    fonts = text.fonts
    stats = session.stats
    remaining = session.remaining(now)
    total = max(1e-6, session.cfg.session_length_s)
    progress = max(0.0, min(1.0, remaining / total))
    label_y = bar.top + 8
    value_y = bar.top + 22

    # -- timer ----------------------------------------------------------
    time_x = bar.left + 24
    text.draw(surface, "TIME", fonts.hud_label, config.TEXT_MUTED, (time_x, label_y))
    text.draw(
        surface,
        format_seconds(remaining),
        fonts.hud_value,
        config.TEXT_PRIMARY,
        (time_x, value_y),
    )
    track = pygame.Rect(time_x, bar.top + 47, 132, 4)
    pygame.draw.rect(surface, shade(config.GAME_BACKGROUND, 1.6), track, border_radius=2)
    filled = pygame.Rect(track.left, track.top, int(track.width * progress), track.height)
    if filled.width > 0:
        pygame.draw.rect(
            surface,
            config.ACCENT if progress > 0.25 else config.DANGER,
            filled,
            border_radius=2,
        )

    # -- counters -------------------------------------------------------
    columns = (
        ("HITS", f"{stats.hits}", bar.left + 200),
        ("SHOTS", f"{stats.shots}", bar.left + 320),
        ("ACCURACY", f"{stats.accuracy * 100:.0f}%", bar.left + 440),
        (
            "LAST",
            "—" if not session.reaction_times else f"{session.reaction_times[-1] * 1000:.0f} ms",
            bar.left + 600,
        ),
        (
            "P95",
            "—" if not session.reaction_times else f"{stats.p95_ms:.0f} ms",
            bar.left + 720,
        ),
    )
    for label, value, x in columns:
        text.draw(surface, label, fonts.hud_label, config.TEXT_MUTED, (x, label_y))
        text.draw(surface, value, fonts.hud_value, config.TEXT_PRIMARY, (x, value_y))

    # -- bot badge and FPS on the right ---------------------------------
    fps_right = bar.right - 24
    text.draw(
        surface,
        "FPS",
        fonts.hud_label,
        config.TEXT_MUTED,
        (fps_right, label_y),
        anchor="topright",
    )
    text.draw(
        surface,
        f"{fps:.0f}",
        fonts.hud_value,
        config.TEXT_PRIMARY,
        (fps_right, value_y),
        anchor="topright",
    )

    badge = pygame.Rect(bar.right - 24 - 74 - 16 - 30, bar.centery - 13, 74, 26)
    if session.cfg.bot_enabled:
        pygame.draw.rect(
            surface,
            shade(config.ACCENT_ACTIVE, 0.32),
            badge,
            border_radius=13,
        )
        pygame.draw.rect(surface, config.ACCENT_ACTIVE, badge, width=1, border_radius=13)
        pygame.draw.circle(
            surface,
            config.ACCENT_ACTIVE,
            (badge.left + 14, badge.centery),
            3,
        )
        text.draw(
            surface,
            "BOT ON",
            fonts.hud_label,
            config.ACCENT_ACTIVE,
            (badge.left + 24, badge.centery),
            anchor="midleft",
        )
    else:
        text.draw(
            surface,
            "BOT OFF",
            fonts.hud_label,
            config.TEXT_MUTED,
            (badge.right, badge.centery),
            anchor="midright",
        )


def draw_crosshair(
    surface: pygame.Surface,
    pos: Sequence[float],
    color: RGB = config.CROSSHAIR,
    *,
    hot: bool = False,
    gap: int = 4,
    length: int = 9,
    width: int = 2,
) -> None:
    """Draw the aiming crosshair at ``pos`` (window coordinates).

    Args:
        surface: Destination surface.
        pos: Cursor position in window pixels.
        color: Crosshair colour; ignored when ``hot`` is set.
        hot: Highlight the crosshair because it is over the target.
        gap: Empty space between the centre and each arm, in pixels.
        length: Length of each arm, in pixels.
        width: Line thickness, in pixels.
    """
    x, y = int(pos[0]), int(pos[1])
    accent = config.ACCENT_ACTIVE if hot else color
    arms = (
        ((x, y - gap - length), (x, y - gap)),
        ((x, y + gap), (x, y + gap + length)),
        ((x - gap - length, y), (x - gap, y)),
        ((x + gap, y), (x + gap + length, y)),
    )
    for start, end in arms:
        pygame.draw.line(
            surface,
            (0, 0, 0),
            (start[0] + 1, start[1] + 1),
            (end[0] + 1, end[1] + 1),
            width + 1,
        )
    for start, end in arms:
        pygame.draw.line(surface, accent, start, end, width)
    pygame.draw.circle(surface, (0, 0, 0), (x + 1, y + 1), 2)
    pygame.draw.circle(surface, accent, (x, y), 1)


def draw_cursor(surface: pygame.Surface, pos: Sequence[float], *, hot: bool = False) -> None:
    """Draw the software cursor (``main`` hides the hardware cursor).

    Inside the play area a full crosshair is drawn; over the control panel a
    small dot keeps the pointer visible without hiding the widgets.

    Args:
        surface: Destination surface.
        pos: Cursor position in window pixels.
        hot: Whether the crosshair currently overlaps the target.
    """
    if GAME_RECT.collidepoint(pos):
        draw_crosshair(surface, pos, hot=hot)
        return

    x, y = int(pos[0]), int(pos[1])
    pygame.draw.circle(surface, (0, 0, 0), (x + 1, y + 1), 4)
    pygame.draw.circle(surface, config.CROSSHAIR, (x, y), 3)
    pygame.draw.circle(surface, config.ACCENT, (x, y), 1)


def _draw_countdown(
    surface: pygame.Surface,
    session: GameSession,
    now: float,
    text: TextRenderer,
) -> None:
    """Fill the play area with the pre-session countdown."""
    pygame.draw.rect(surface, config.GAME_BACKGROUND, GAME_RECT)
    _draw_grid(surface)
    fonts = text.fonts
    center_x = GAME_RECT.centerx

    text.draw(
        surface,
        "GET READY",
        fonts.heading,
        config.TEXT_MUTED,
        (center_x, GAME_RECT.centery - 170),
        anchor="center",
    )
    remaining = session.countdown_remaining(now)
    label = str(int(math.ceil(remaining))) if remaining > 0.01 else "GO"
    text.draw(
        surface,
        label,
        fonts.huge,
        config.ACCENT,
        (center_x, GAME_RECT.centery - 40),
        anchor="center",
    )
    text.draw(
        surface,
        f"{session.cfg.session_length_s:.0f}s session   ·   "
        f"{session.cfg.target_size_px:.0f}px target",
        fonts.label,
        config.TEXT_PRIMARY,
        (center_x, GAME_RECT.centery + 80),
        anchor="center",
    )
    text.draw(
        surface,
        "Click the red target as soon as it appears",
        fonts.small,
        config.TEXT_MUTED,
        (center_x, GAME_RECT.centery + 116),
        anchor="center",
    )


def _draw_idle(surface: pygame.Surface, text: TextRenderer) -> None:
    """Fill the play area with the title screen."""
    pygame.draw.rect(surface, config.GAME_BACKGROUND, GAME_RECT)
    _draw_grid(surface)
    fonts = text.fonts
    center_x = GAME_RECT.centerx
    center_y = GAME_RECT.centery

    text.draw(
        surface,
        "CLOSED-LOOP AIM TRAINER",
        fonts.hud_label,
        config.ACCENT,
        (center_x, center_y - 205),
        anchor="center",
    )
    text.draw(
        surface,
        "AIM TRAINER",
        fonts.title,
        config.TEXT_PRIMARY,
        (center_x, center_y - 160),
        anchor="center",
    )
    text.draw(
        surface,
        "Train your aim, then watch a colour-vision bot do the same — through the screen only.",
        fonts.label,
        config.TEXT_MUTED,
        (center_x, center_y - 112),
        anchor="center",
    )

    demo_center = (center_x, center_y - 10)
    pygame.draw.circle(surface, shade(config.TARGET_RED, 1.55), demo_center, 34, 2)
    pygame.draw.circle(surface, config.TARGET_RED, demo_center, 29)
    pygame.draw.circle(surface, shade(config.TARGET_RED, 1.4), demo_center, 17, 2)
    pygame.draw.circle(surface, shade(config.TARGET_RED, 1.85), demo_center, 5)

    text.draw(
        surface,
        "PRESS SPACE TO START",
        fonts.heading,
        config.ACCENT_ACTIVE,
        (center_x, center_y + 92),
        anchor="center",
    )
    text.draw(
        surface,
        "B  bot on/off      M  AI assist      D  debug view      R  restart      Esc  quit",
        fonts.small,
        config.TEXT_MUTED,
        (center_x, center_y + 132),
        anchor="center",
    )


def _draw_results(surface: pygame.Surface, session: GameSession, text: TextRenderer) -> None:
    """Fill the play area with the end-of-session score card."""
    pygame.draw.rect(surface, config.GAME_BACKGROUND, GAME_RECT)
    _draw_grid(surface)
    fonts = text.fonts
    stats = session.stats

    card = pygame.Rect(0, 0, 560, 430)
    card.center = GAME_RECT.center
    pygame.draw.rect(surface, config.PANEL_BACKGROUND, card, border_radius=18)
    pygame.draw.rect(
        surface,
        shade(config.PANEL_BACKGROUND, 1.45),
        card,
        width=1,
        border_radius=18,
    )

    accuracy_color = (
        config.ACCENT_ACTIVE
        if stats.accuracy >= 0.7
        else config.ACCENT
        if stats.accuracy >= 0.4
        else config.DANGER
    )
    text.draw(
        surface,
        "SESSION COMPLETE",
        fonts.heading,
        config.TEXT_MUTED,
        (card.centerx, card.top + 38),
        anchor="center",
    )
    text.draw(
        surface,
        f"{stats.accuracy * 100:.0f}%",
        fonts.huge,
        accuracy_color,
        (card.centerx, card.top + 108),
        anchor="center",
    )
    text.draw(
        surface,
        f"{stats.hits} hits of {stats.shots} shots",
        fonts.label,
        config.TEXT_PRIMARY,
        (card.centerx, card.top + 168),
        anchor="center",
    )

    tiles = (
        ("AVERAGE", _format_ms(stats.avg_ms)),
        ("MEDIAN", _format_ms(stats.median_ms)),
        ("P95", _format_ms(stats.p95_ms)),
    )
    tile_width, tile_height, gap = 156, 64, 14
    start_x = card.centerx - (3 * tile_width + 2 * gap) // 2
    for index, (label, value) in enumerate(tiles):
        tile = pygame.Rect(
            start_x + index * (tile_width + gap),
            card.top + 204,
            tile_width,
            tile_height,
        )
        pygame.draw.rect(surface, shade(config.PANEL_BACKGROUND, 1.22), tile, border_radius=12)
        text.draw(
            surface,
            label,
            fonts.hud_label,
            config.TEXT_MUTED,
            (tile.centerx, tile.top + 12),
            anchor="midtop",
        )
        text.draw(
            surface,
            value,
            fonts.value,
            config.TEXT_PRIMARY,
            (tile.centerx, tile.top + 44),
            anchor="center",
        )

    text.draw(
        surface,
        f"fastest {_format_ms(stats.min_ms)}   ·   slowest {_format_ms(stats.max_ms)}",
        fonts.small,
        config.TEXT_MUTED,
        (card.centerx, card.top + 296),
        anchor="center",
    )
    text.draw(
        surface,
        "Press SPACE or R to play again",
        fonts.label,
        config.ACCENT,
        (card.centerx, card.bottom - 38),
        anchor="center",
    )


def _format_ms(value: float) -> str:
    """Return ``value`` as ``"412 ms"`` or ``"—"`` when nothing was recorded."""
    return "—" if value <= 0.0 else f"{value:.0f} ms"


def draw_game_zone(
    surface: pygame.Surface,
    session: GameSession,
    now: float,
    text: TextRenderer,
    *,
    fps: float = 0.0,
    debug: "DebugView | None" = None,
) -> None:
    """Draw the whole left-hand play area for the session's current state.

    Args:
        surface: Destination surface (the window).
        session: Session supplying targets, state and statistics.
        now: Current monotonic time in seconds.
        text: Shared text renderer.
        fps: Measured frame rate, shown in the HUD.
        debug: Optional bot diagnostics; drawn when ``debug.enabled`` is set.
    """
    pygame.draw.rect(surface, config.GAME_BACKGROUND, GAME_RECT)
    _draw_grid(surface)

    if session.state is GameState.RUNNING:
        if session.target is not None:
            _draw_target(surface, session.target, now)
        draw_hud(surface, session, now, text, fps=fps)
    elif session.state is GameState.COUNTDOWN:
        _draw_countdown(surface, session, now, text)
    elif session.state is GameState.IDLE:
        _draw_idle(surface, text)
    else:
        _draw_results(surface, session, text)

    if debug is not None and debug.enabled:
        draw_debug_overlay(surface, debug, text)


# ---------------------------------------------------------------------------
# Vision debug overlay
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DebugView:
    """Snapshot of the bot's vision pipeline for the on-screen overlay.

    The UI never touches OpenCV types: ``main`` copies the values it needs and
    draws them. Coordinates are play-area pixels, the same space targets use.

    Attributes:
        enabled: Master switch, mirrored from ``Config.debug_view``.
        mask: Optional preview surface of the red colour mask.
        centroid: Detected target centre in play-area coordinates.
        radius: Detected target radius in pixels.
        aim_point: Cursor destination chosen by the controller.
        path: Recent cursor/bot positions, oldest first.
        latency_ms: Duration of the last capture → detect → act cycle.
        loop_hz: Measured bot loop frequency.
        note: Optional single status line (e.g. ``"target lost"``).
    """

    enabled: bool = False
    mask: pygame.Surface | None = None
    centroid: tuple[float, float] | None = None
    radius: float = 0.0
    aim_point: tuple[float, float] | None = None
    path: Sequence[tuple[float, float]] = ()
    latency_ms: float = 0.0
    loop_hz: float = 0.0
    note: str = ""


def draw_debug_overlay(
    surface: pygame.Surface,
    debug: DebugView,
    text: TextRenderer,
) -> None:
    """Draw the vision diagnostics inside the play area.

    Renders the centroid, the recent aim path, the aim point and a compact
    card with the mask preview and loop timings. Nothing is drawn when
    ``debug.enabled`` is ``False``.

    Args:
        surface: Destination surface.
        debug: Snapshot published by the bot.
        text: Shared text renderer.
    """
    if not debug.enabled:
        return

    fonts = text.fonts

    if len(debug.path) >= 2:
        points = [
            (int(GAME_RECT.left + x), int(GAME_RECT.top + y)) for x, y in debug.path
        ]
        last = len(points) - 1
        for index in range(1, len(points)):
            color = shade(config.DEBUG_OUTLINE, 0.3 + 0.7 * (index / last))
            pygame.draw.line(surface, color, points[index - 1], points[index], 2)

    if debug.centroid is not None:
        center = (
            int(GAME_RECT.left + debug.centroid[0]),
            int(GAME_RECT.top + debug.centroid[1]),
        )
        radius = max(6, int(debug.radius))
        pygame.draw.circle(surface, config.DEBUG_OUTLINE, center, radius, 2)
        pygame.draw.line(
            surface,
            config.DEBUG_OUTLINE,
            (center[0] - radius - 6, center[1]),
            (center[0] + radius + 6, center[1]),
        )
        pygame.draw.line(
            surface,
            config.DEBUG_OUTLINE,
            (center[0], center[1] - radius - 6),
            (center[0], center[1] + radius + 6),
        )

    if debug.aim_point is not None:
        pygame.draw.circle(
            surface,
            config.ACCENT_ACTIVE,
            (int(GAME_RECT.left + debug.aim_point[0]), int(GAME_RECT.top + debug.aim_point[1])),
            4,
        )

    card = pygame.Rect(12, config.WINDOW_HEIGHT - 12 - 212, 320, 212)
    pygame.draw.rect(surface, shade(config.PANEL_BACKGROUND, 1.05), card, border_radius=12)
    pygame.draw.rect(surface, config.DEBUG_OUTLINE, card, width=1, border_radius=12)
    text.draw(
        surface,
        "VISION DEBUG",
        fonts.hud_label,
        config.DEBUG_OUTLINE,
        (card.left + 14, card.top + 12),
    )

    preview = pygame.Rect(card.left + 14, card.top + 34, 150, 104)
    pygame.draw.rect(surface, (0, 0, 0), preview, border_radius=6)
    if debug.mask is not None:
        try:
            surface.blit(pygame.transform.smoothscale(debug.mask, preview.size), preview.topleft)
        except (ValueError, pygame.error):
            text.draw(
                surface,
                "bad frame",
                fonts.small,
                config.DANGER,
                preview.center,
                anchor="center",
            )
    else:
        text.draw(
            surface,
            "no frame",
            fonts.small,
            config.TEXT_MUTED,
            preview.center,
            anchor="center",
        )

    stats_x = card.left + 180
    rows = (
        ("centroid", "—" if debug.centroid is None else f"{debug.centroid[0]:.0f}, {debug.centroid[1]:.0f}"),
        ("radius", f"{debug.radius:.0f} px"),
        ("loop", f"{debug.loop_hz:.0f} Hz"),
        ("latency", f"{debug.latency_ms:.1f} ms"),
        ("path", f"{len(debug.path)} pts"),
    )
    row_y = card.top + 34
    for label, value in rows:
        text.draw(surface, label, fonts.small, config.TEXT_MUTED, (stats_x, row_y))
        text.draw(surface, value, fonts.small, config.TEXT_PRIMARY, (stats_x + 64, row_y))
        row_y += 19

    if debug.note:
        note_y = preview.bottom + 10
        for line in wrap_text(debug.note, fonts.small, card.width - 28)[:2]:
            text.draw(surface, line, fonts.small, config.TEXT_MUTED, (card.left + 14, note_y))
            note_y += 16
