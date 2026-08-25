from pathlib import Path

import pytest

from wizard_chess.configuration import EngineSettings
from wizard_chess.domain.exceptions import EngineUnavailableError
from wizard_chess.engine import factory
from wizard_chess.engine.factory import resolve_stockfish_path, validate_stockfish_engine


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


def test_explicit_engine_path_wins_over_bundled_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "custom-uci-engine"
    executable.write_text("fake", encoding="utf-8")

    def unexpected_bundle_lookup() -> str | None:
        raise AssertionError("the bundle must not replace an explicit engine")

    monkeypatch.setattr(factory, "resolve_bundled_stockfish", unexpected_bundle_lookup)

    assert resolve_stockfish_path(str(executable)) == str(executable)


def test_bundled_engine_wins_over_system_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "resolve_bundled_stockfish", lambda: "/bundle/stockfish")

    def unexpected_path_lookup(_name: str) -> str | None:
        raise AssertionError("PATH must not replace the bundled default")

    monkeypatch.setattr(factory.shutil, "which", unexpected_path_lookup)

    assert resolve_stockfish_path(None) == "/bundle/stockfish"


def test_system_path_is_fallback_when_platform_has_no_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def system_engine_path(name: str) -> str:
        return f"/usr/bin/{name}"

    monkeypatch.setattr(factory, "resolve_bundled_stockfish", lambda: None)
    monkeypatch.setattr(factory.shutil, "which", system_engine_path)

    assert resolve_stockfish_path(None) == "/usr/bin/stockfish"


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
