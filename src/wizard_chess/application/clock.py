"""Monotonic chess-clock semantics independent of GUI refresh rate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from wizard_chess.configuration import ClockSettings
from wizard_chess.domain.results import PlayerColor


@dataclass(frozen=True, slots=True)
class ClockSnapshot:
    """One immutable rendering snapshot of both clocks."""

    white_seconds: float
    black_seconds: float
    active: PlayerColor | None
    running: bool
    expired: PlayerColor | None


@dataclass(frozen=True, slots=True)
class ClockMoveTiming:
    """Timing captured when one side completes a legal move."""

    color: PlayerColor
    elapsed_seconds: float
    remaining_seconds: float


class ChessClock:
    """Own start, pause, switch, and reset using an injected monotonic source."""

    def __init__(
        self,
        settings: ClockSettings,
        now: Callable[[], float] = monotonic,
    ) -> None:
        self.settings = settings
        self._now = now
        self._remaining = {
            PlayerColor.WHITE: settings.initial_seconds,
            PlayerColor.BLACK: settings.initial_seconds,
        }
        self._active: PlayerColor | None = None
        self._started_at: float | None = None
        self._expired: PlayerColor | None = None
        self._turn_elapsed = 0.0

    def start(self, active: PlayerColor) -> None:
        if not self.settings.enabled or self._expired is not None:
            return
        self._apply_elapsed()
        if self._active is not active:
            self._turn_elapsed = 0.0
        self._active = active
        self._started_at = self._now()

    def pause(self) -> None:
        self._apply_elapsed()
        self._started_at = None

    def switch(self, active: PlayerColor) -> ClockMoveTiming | None:
        """Finish the prior turn with increment, then start ``active``."""
        if not self.settings.enabled:
            self._active = active
            self._started_at = None
            self._turn_elapsed = 0.0
            return None
        previous = self._active
        was_running = self._started_at is not None
        self._apply_elapsed()
        timing: ClockMoveTiming | None = None
        if previous is not None and previous is not active and self._expired is None:
            self._remaining[previous] += self.settings.increment_seconds
            timing = ClockMoveTiming(
                color=previous,
                elapsed_seconds=self._turn_elapsed,
                remaining_seconds=self._remaining[previous],
            )
        self._active = active
        self._turn_elapsed = 0.0
        self._started_at = self._now() if was_running and self.settings.enabled else None
        return timing

    def set_active(self, active: PlayerColor) -> None:
        """Align turn after undo/load without awarding an increment."""
        was_running = self._started_at is not None
        self._apply_elapsed()
        self._active = active
        self._turn_elapsed = 0.0
        self._started_at = self._now() if was_running and self.settings.enabled else None

    def reset(self, active: PlayerColor | None = None) -> None:
        self._remaining = {
            PlayerColor.WHITE: self.settings.initial_seconds,
            PlayerColor.BLACK: self.settings.initial_seconds,
        }
        self._active = active
        self._started_at = None
        self._expired = None
        self._turn_elapsed = 0.0

    def snapshot(self) -> ClockSnapshot:
        self._apply_elapsed()
        return ClockSnapshot(
            white_seconds=self._remaining[PlayerColor.WHITE],
            black_seconds=self._remaining[PlayerColor.BLACK],
            active=self._active,
            running=self._started_at is not None,
            expired=self._expired,
        )

    def _apply_elapsed(self) -> None:
        if self._started_at is None or self._active is None:
            return
        now = self._now()
        elapsed = max(0.0, now - self._started_at)
        self._remaining[self._active] = max(0.0, self._remaining[self._active] - elapsed)
        self._turn_elapsed += elapsed
        self._started_at = now
        if self._remaining[self._active] <= 0:
            self._expired = self._active
            self._started_at = None
