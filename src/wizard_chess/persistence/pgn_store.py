"""Filesystem persistence for portable game notation."""

from pathlib import Path


class PgnStore:
    """Save rendered PGN without coupling the domain to the filesystem."""

    def save(self, pgn: str, destination: str | Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pgn.rstrip() + "\n", encoding="utf-8")
        return path

    def load(self, source: str | Path) -> str:
        """Load UTF-8 PGN text for validation by the domain layer."""
        return Path(source).read_text(encoding="utf-8")
