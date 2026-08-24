from pathlib import Path

import pytest

from wizard_chess.configuration import (
    ApplicationSettings,
    ClockSettings,
    EngineSettings,
    PlayerKind,
    PlayerSettings,
    VoiceLanguage,
)
from wizard_chess.persistence.settings_store import SettingsStore


def test_environment_configuration_covers_optional_subsystems(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "WIZARD_CHESS_VOICE_LANGUAGE": "pl",
        "WIZARD_CHESS_ENGINE_ENABLED": "true",
        "WIZARD_CHESS_ENGINE_PATH": "/opt/stockfish",
        "WIZARD_CHESS_ANALYSIS_ENABLED": "yes",
        "WIZARD_CHESS_ENGINE_MULTIPV": "4",
        "WIZARD_CHESS_BLACK_PLAYER": "engine",
        "WIZARD_CHESS_BLACK_NAME": "Komputer",
        "WIZARD_CHESS_CLOCK_ENABLED": "1",
        "WIZARD_CHESS_CLOCK_SECONDS": "300",
        "WIZARD_CHESS_CLOCK_INCREMENT_SECONDS": "3",
        "WIZARD_CHESS_AUTOSAVE": "on",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    settings = ApplicationSettings.from_environment()

    assert settings.voice_language is VoiceLanguage.POLISH
    assert settings.engine.path == "/opt/stockfish"
    assert settings.engine.multipv == 4
    assert settings.players.black_kind is PlayerKind.ENGINE
    assert settings.players.black_name == "Komputer"
    assert settings.clock == ClockSettings(enabled=True, initial_seconds=300, increment_seconds=3)
    assert settings.autosave


def test_settings_store_round_trip_and_missing_field_defaulting(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = ApplicationSettings(
        voice_language=VoiceLanguage.POLISH,
        engine=EngineSettings(enabled=True, path="stockfish", multipv=2),
        players=PlayerSettings(black_kind=PlayerKind.ENGINE),
        autosave=True,
    )
    store = SettingsStore(path)

    assert store.load() == ApplicationSettings()
    store.save(settings)
    assert store.load() == settings

    path.write_text('{"schema_version": 1, "settings": {"autosave": true}}\n')
    defaulted = store.load()
    assert defaulted.autosave
    assert defaulted.voice_language is VoiceLanguage.ENGLISH


def test_invalid_settings_file_gracefully_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("not json", encoding="utf-8")

    assert SettingsStore(path).load() == ApplicationSettings()
