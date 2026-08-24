"""Collision-resistant local game saves and recoverable autosave slots."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from wizard_chess.persistence.pgn_store import PgnStore


class GameStore:
    """Own local save paths while keeping PGN rendering in the domain."""

    def __init__(self, directory: str | Path, pgn_store: PgnStore | None = None) -> None:
        self.directory = Path(directory)
        self._pgn_store = pgn_store or PgnStore()

    def save(self, pgn: str, identifier: str | None = None) -> Path:
        """Create a named or timestamped PGN without overwriting unrelated games."""
        self.directory.mkdir(parents=True, exist_ok=True)
        stem = identifier or datetime.now(UTC).strftime("game-%Y%m%dT%H%M%S-%fZ")
        candidate = self.directory / f"{stem}.pgn"
        suffix = 1
        while candidate.exists():
            candidate = self.directory / f"{stem}-{suffix}.pgn"
            suffix += 1
        return self._pgn_store.save(pgn, candidate)

    def autosave(self, pgn: str) -> Path:
        """Atomically replace only the dedicated recovery slot."""
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / "recovery.pgn"
        temporary = self.directory / "recovery.pgn.tmp"
        self._pgn_store.save(pgn, temporary)
        temporary.replace(target)
        return target

    def recover(self) -> str | None:
        path = self.directory / "recovery.pgn"
        return self._pgn_store.load(path) if path.exists() else None
