from pathlib import Path

import pytest

from wizard_chess.configuration import EngineSettings
from wizard_chess.domain.exceptions import EngineUnavailableError
from wizard_chess.engine.factory import validate_stockfish_engine


class ValidationEngine:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.started = False
        self.closed = False

    def start(self) -> None:
        self.started = True
        if self.fail:
            raise EngineUnavailableError("UCI startup failed")

    def close(self) -> None:
        self.closed = True


def test_engine_validation_starts_and_closes_temporary_adapter(tmp_path: Path) -> None:
    executable = tmp_path / "stockfish"
    executable.write_text("fake", encoding="utf-8")
    engine = ValidationEngine()

    validate_stockfish_engine(
        EngineSettings(path=str(executable)),
        engine_factory=lambda _settings: engine,
    )

    assert engine.started
    assert engine.closed


def test_engine_validation_reports_unavailable_executable(tmp_path: Path) -> None:
    with pytest.raises(EngineUnavailableError, match="not found"):
        validate_stockfish_engine(EngineSettings(path=str(tmp_path / "missing")))


def test_engine_validation_closes_adapter_after_startup_failure(tmp_path: Path) -> None:
    executable = tmp_path / "stockfish"
    executable.write_text("fake", encoding="utf-8")
    engine = ValidationEngine(fail=True)

    with pytest.raises(EngineUnavailableError, match="UCI startup failed"):
        validate_stockfish_engine(
            EngineSettings(path=str(executable)),
            engine_factory=lambda _settings: engine,
        )

    assert engine.started
    assert engine.closed
