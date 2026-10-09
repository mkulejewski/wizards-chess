"""Versioned JSON persistence for user preferences with tolerant defaulting."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import cast

from wizard_chess.configuration import (
    AppearanceSettings,
    ApplicationSettings,
    BoardTheme,
    ClockSettings,
    ConfirmationPolicy,
    EngineAnalysisMode,
    EngineSettings,
    EngineStrength,
    PieceSet,
    PlayerKind,
    PlayerSettings,
    StockfishPlayerMode,
    VoiceLanguage,
)
from wizard_chess.logging_config import LogLevel

LOGGER = logging.getLogger(__name__)


class SettingsStore:
    """Read current settings and tolerate missing fields from older schemas."""

    SCHEMA_VERSION = 6

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, settings: ApplicationSettings) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": self.SCHEMA_VERSION, "settings": asdict(settings)}
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
        LOGGER.debug("Application settings saved: %s", self.path)
        return self.path

    def load(self, defaults: ApplicationSettings | None = None) -> ApplicationSettings:
        fallback = defaults or ApplicationSettings()
        if not self.path.exists():
            LOGGER.debug("Application settings file not found; using defaults: %s", self.path)
            return fallback
        try:
            payload = cast(dict[str, object], json.loads(self.path.read_text(encoding="utf-8")))
            raw = cast(dict[str, object], payload.get("settings", {}))
            engine = cast(dict[str, object], raw.get("engine", {}))
            players = cast(dict[str, object], raw.get("players", {}))
            clock = cast(dict[str, object], raw.get("clock", {}))
            appearance = cast(dict[str, object], raw.get("appearance", {}))
            legacy_analysis_time = engine.get("analysis_time_ms")
            player_time_default = (
                _int_value(
                    legacy_analysis_time,
                    fallback.engine.player_move_analysis_time_ms,
                )
                if legacy_analysis_time is not None
                else fallback.engine.player_move_analysis_time_ms
            )
            post_game_time_default = (
                _int_value(
                    legacy_analysis_time,
                    fallback.engine.post_game_analysis_time_ms,
                )
                if legacy_analysis_time is not None
                else fallback.engine.post_game_analysis_time_ms
            )
            return ApplicationSettings(
                voice_language=VoiceLanguage(
                    str(raw.get("voice_language", fallback.voice_language))
                ),
                confirmation_policy=ConfirmationPolicy(
                    str(raw.get("confirmation_policy", fallback.confirmation_policy))
                ),
                confidence_threshold=_float_value(
                    raw.get("confidence_threshold"), fallback.confidence_threshold
                ),
                engine=EngineSettings(
                    enabled=_bool_value(engine.get("enabled"), fallback.engine.enabled),
                    path=_optional_string(engine.get("path", fallback.engine.path)),
                    analysis_mode=_analysis_mode_value(
                        engine,
                        fallback.engine.analysis_mode,
                    ),
                    analysis_enabled=_bool_value(
                        engine.get("analysis_enabled"), fallback.engine.analysis_enabled
                    ),
                    live_analysis_max_depth=_int_value(
                        engine.get("live_analysis_max_depth"),
                        fallback.engine.live_analysis_max_depth,
                    ),
                    player_mode=StockfishPlayerMode(
                        str(engine.get("player_mode", fallback.engine.player_mode))
                    ),
                    player_move_analysis_time_ms=_int_value(
                        engine.get("player_move_analysis_time_ms"),
                        player_time_default,
                    ),
                    post_game_analysis_time_ms=_int_value(
                        engine.get("post_game_analysis_time_ms"),
                        post_game_time_default,
                    ),
                    analysis_depth=_optional_int(
                        engine.get("analysis_depth", fallback.engine.analysis_depth)
                    ),
                    multipv=_int_value(engine.get("multipv"), fallback.engine.multipv),
                    strength=EngineStrength(str(engine.get("strength", fallback.engine.strength))),
                    threads=_int_value(engine.get("threads"), fallback.engine.threads),
                    hash_mb=_int_value(engine.get("hash_mb"), fallback.engine.hash_mb),
                    syzygy_path=_optional_string(
                        engine.get("syzygy_path", fallback.engine.syzygy_path)
                    ),
                    syzygy_probe_limit=_bounded_int_value(
                        engine.get("syzygy_probe_limit"),
                        fallback.engine.syzygy_probe_limit,
                        0,
                        7,
                    ),
                    syzygy_50_move_rule=_bool_value(
                        engine.get("syzygy_50_move_rule"),
                        fallback.engine.syzygy_50_move_rule,
                    ),
                ),
                players=PlayerSettings(
                    white_name=str(players.get("white_name", fallback.players.white_name)),
                    black_name=str(players.get("black_name", fallback.players.black_name)),
                    white_kind=PlayerKind(
                        str(players.get("white_kind", fallback.players.white_kind))
                    ),
                    black_kind=PlayerKind(
                        str(players.get("black_kind", fallback.players.black_kind))
                    ),
                ),
                clock=ClockSettings(
                    enabled=_bool_value(clock.get("enabled"), fallback.clock.enabled),
                    initial_seconds=_float_value(
                        clock.get("initial_seconds"), fallback.clock.initial_seconds
                    ),
                    increment_seconds=_float_value(
                        clock.get("increment_seconds"), fallback.clock.increment_seconds
                    ),
                ),
                appearance=AppearanceSettings(
                    piece_set=PieceSet(
                        str(appearance.get("piece_set", fallback.appearance.piece_set))
                    ),
                    board_theme=BoardTheme(
                        str(appearance.get("board_theme", fallback.appearance.board_theme))
                    ),
                ),
                game_setup_saved=_bool_value(
                    raw.get("game_setup_saved"), fallback.game_setup_saved
                ),
                show_game_setup_on_startup=_bool_value(
                    raw.get("show_game_setup_on_startup"),
                    fallback.show_game_setup_on_startup,
                ),
                autosave=_bool_value(raw.get("autosave"), fallback.autosave),
                logging_level=LogLevel.parse(str(raw.get("logging_level", fallback.logging_level))),
                terminal_log_enabled=_bool_value(
                    raw.get("terminal_log_enabled"),
                    fallback.terminal_log_enabled,
                ),
                file_log_enabled=_bool_value(
                    raw.get("file_log_enabled"),
                    fallback.file_log_enabled,
                ),
                log_file_path=_optional_string(raw.get("log_file_path", fallback.log_file_path)),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            LOGGER.warning(
                "Application settings could not be loaded from %s; using defaults: %s",
                self.path,
                error,
                exc_info=LOGGER.isEnabledFor(logging.DEBUG),
            )
            return fallback


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _analysis_mode_value(
    values: dict[str, object],
    default: EngineAnalysisMode,
) -> EngineAnalysisMode:
    raw_mode = values.get("analysis_mode")
    if raw_mode is not None:
        return EngineAnalysisMode(str(raw_mode))
    if "analysis_enabled" not in values:
        return default
    return (
        EngineAnalysisMode.FIXED_TIME
        if _bool_value(values["analysis_enabled"], False)
        else EngineAnalysisMode.OFF
    )


def _optional_int(value: object) -> int | None:
    return None if value is None else _int_value(value, 0)


def _int_value(value: object, default: int) -> int:
    if isinstance(value, (str, int, float)):
        return int(value)
    return default


def _bounded_int_value(
    value: object,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    parsed = _int_value(value, default)
    return parsed if minimum <= parsed <= maximum else default


def _bool_value(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
    return default


def _float_value(value: object, default: float) -> float:
    if isinstance(value, (str, int, float)):
        return float(value)
    return default
