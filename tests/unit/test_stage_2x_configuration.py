from pathlib import Path

import pytest

from wizard_chess.configuration import (
    ApplicationSettings,
    ClockSettings,
    EngineSettings,
    EngineStrength,
    PlayerKind,
    PlayerSettings,
    VoiceLanguage,
    should_show_game_setup,
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
        engine=EngineSettings(
            enabled=True,
            path="stockfish",
            analysis_time_ms=2500,
            multipv=2,
            strength=EngineStrength.STRONG_CLUB,
        ),
        players=PlayerSettings(
            white_kind=PlayerKind.ENGINE,
            black_kind=PlayerKind.HUMAN,
        ),
        game_setup_saved=True,
        show_game_setup_on_startup=False,
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


def test_environment_values_override_persisted_values_without_replacing_them() -> None:
    persisted = ApplicationSettings(
        engine=EngineSettings(
            path="/persisted/stockfish",
            strength=EngineStrength.CLUB,
            analysis_time_ms=1500,
            analysis_depth=12,
        ),
        players=PlayerSettings(black_kind=PlayerKind.ENGINE),
    )

    effective = ApplicationSettings.from_environment(
        persisted,
        {
            "WIZARD_CHESS_ENGINE_STRENGTH": "expert",
            "WIZARD_CHESS_ENGINE_TIME_MS": "3000",
            "WIZARD_CHESS_ENGINE_PATH": "",
            "WIZARD_CHESS_ENGINE_DEPTH": "",
            "WIZARD_CHESS_WHITE_PLAYER": "engine",
            "WIZARD_CHESS_BLACK_PLAYER": "human",
        },
    )

    assert effective.engine.strength is EngineStrength.EXPERT
    assert effective.engine.analysis_time_ms == 3000
    assert effective.engine.path is None
    assert effective.engine.analysis_depth is None
    assert effective.engine.enabled
    assert effective.players.white_kind is PlayerKind.ENGINE
    assert effective.players.black_kind is PlayerKind.HUMAN
    assert persisted.engine.strength is EngineStrength.CLUB
    assert (
        ApplicationSettings.from_environment(persisted, {}).engine.strength is EngineStrength.CLUB
    )


def test_startup_setup_policy_covers_first_run_saved_reuse_and_forcing() -> None:
    first_run = ApplicationSettings()
    ask_each_time = ApplicationSettings(
        game_setup_saved=True,
        show_game_setup_on_startup=True,
    )
    automatic = ApplicationSettings(
        game_setup_saved=True,
        show_game_setup_on_startup=False,
    )

    assert should_show_game_setup(first_run, environment={})
    assert not should_show_game_setup(
        first_run,
        environment={"WIZARD_CHESS_WHITE_PLAYER": "engine"},
    )
    assert should_show_game_setup(ask_each_time, environment={})
    assert not should_show_game_setup(automatic, environment={})
    assert should_show_game_setup(automatic, force=True, environment={})


def test_invalid_settings_file_gracefully_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("not json", encoding="utf-8")

    assert SettingsStore(path).load() == ApplicationSettings()


def test_malformed_optional_startup_settings_use_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"schema_version": 2, "settings": {'
        '"game_setup_saved": "not-a-boolean", '
        '"show_game_setup_on_startup": "also-invalid"}}',
        encoding="utf-8",
    )

    loaded = SettingsStore(path).load()

    assert not loaded.game_setup_saved
    assert loaded.show_game_setup_on_startup
