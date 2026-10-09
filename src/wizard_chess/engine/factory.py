"""Composition helpers for the optional local chess engine."""

import logging
import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from wizard_chess.configuration import EngineSettings
from wizard_chess.domain.exceptions import EngineUnavailableError
from wizard_chess.engine.stockfish import StockfishEngine
from wizard_chess.persistence.engine_bundle import resolve_bundled_stockfish

LOGGER = logging.getLogger(__name__)


class StartableEngine(Protocol):
    """Small lifecycle surface needed for non-destructive validation."""

    def start(self) -> None: ...

    def close(self) -> None: ...


ValidationEngineFactory = Callable[[EngineSettings], StartableEngine]


def create_stockfish_engine(settings: EngineSettings) -> StockfishEngine | None:
    """Return a lazy adapter, preferring configured and then bundled Stockfish."""
    if not settings.enabled:
        LOGGER.debug("Stockfish adapter disabled by configuration")
        return None
    path = settings.path or resolve_stockfish_path(None)
    LOGGER.info("Stockfish adapter configured: path=%s", path or "unavailable")
    return StockfishEngine(replace(settings, path=path))


def resolve_stockfish_path(configured_path: str | None) -> str | None:
    """Resolve an explicit executable, bundled Stockfish, or the system ``PATH``."""
    if configured_path:
        candidate = Path(configured_path).expanduser()
        if candidate.parent != Path("."):
            resolved = str(candidate) if candidate.is_file() else None
        else:
            resolved = shutil.which(configured_path)
        LOGGER.debug(
            "Explicit Stockfish path resolution: requested=%s resolved=%s", candidate, resolved
        )
        return resolved
    bundled_path = resolve_bundled_stockfish()
    if bundled_path is not None:
        LOGGER.debug("Using bundled Stockfish executable: %s", bundled_path)
        return bundled_path
    system_path = shutil.which("stockfish")
    LOGGER.debug("System Stockfish path resolution: %s", system_path)
    return system_path


def validate_stockfish_engine(
    settings: EngineSettings,
    engine_factory: ValidationEngineFactory = StockfishEngine,
) -> None:
    """Perform a minimal UCI startup test and always close its temporary process."""
    path = resolve_stockfish_path(settings.path)
    if path is None:
        requested = (
            f" at {settings.path!r}" if settings.path else " in the application bundle or on PATH"
        )
        raise EngineUnavailableError(f"Stockfish executable was not found{requested}")
    engine = engine_factory(replace(settings, enabled=True, path=path))
    LOGGER.info("Validating Stockfish executable: %s", path)
    try:
        engine.start()
    finally:
        engine.close()
    LOGGER.info("Stockfish executable validated: %s", path)
