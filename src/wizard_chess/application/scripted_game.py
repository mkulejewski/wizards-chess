"""Developer runner that deliberately uses the ordinary shared command path."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from wizard_chess.application.session import GameSession, SessionResult

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScriptedGameResult:
    """Final state and per-line results from deterministic scripted play."""

    commands: tuple[str, ...]
    results: tuple[SessionResult, ...]
    final_fen: str
    move_history: tuple[str, ...]


class ScriptedGameRunner:
    """Feed non-comment script lines through ``GameSession.play_text``."""

    def __init__(self, session: GameSession | None = None) -> None:
        self.session = session or GameSession()

    def run(self, commands: Iterable[str]) -> ScriptedGameResult:
        LOGGER.info("Scripted game started")
        accepted: list[str] = []
        results: list[SessionResult] = []
        for raw in commands:
            command = raw.strip()
            if not command or command.startswith("#"):
                continue
            LOGGER.debug("Script command %d: %r", len(accepted) + 1, command)
            accepted.append(command)
            results.append(self.session.play_text(command))
        snapshot = self.session.snapshot()
        result = ScriptedGameResult(
            commands=tuple(accepted),
            results=tuple(results),
            final_fen=snapshot.fen,
            move_history=snapshot.move_history,
        )
        LOGGER.info(
            "Scripted game completed: commands=%d plies=%d", len(accepted), len(result.move_history)
        )
        return result

    def run_file(self, source: str | Path) -> ScriptedGameResult:
        path = Path(source)
        LOGGER.info("Loading UTF-8 command script: %s", path)
        return self.run(path.read_text(encoding="utf-8").splitlines())
