"""Composition helpers for the optional local chess engine."""

import shutil
from dataclasses import replace

from wizard_chess.configuration import EngineSettings
from wizard_chess.engine.stockfish import StockfishEngine


def create_stockfish_engine(settings: EngineSettings) -> StockfishEngine | None:
    """Return a lazy adapter when enabled, discovering Stockfish on PATH if needed."""
    if not settings.enabled:
        return None
    path = settings.path or shutil.which("stockfish")
    return StockfishEngine(replace(settings, path=path))
