"""Versioned JSON persistence for user preferences with tolerant defaulting."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

from wizard_chess.configuration import (
    ApplicationSettings,
    ClockSettings,
    ConfirmationPolicy,
    EngineSettings,
    EngineStrength,
    PlayerKind,
    PlayerSettings,
    VoiceLanguage,
)


class SettingsStore:
    """Read current settings and tolerate missing fields from older schemas."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, settings: ApplicationSettings) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": self.SCHEMA_VERSION, "settings": asdict(settings)}
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
        return self.path

    def load(self, defaults: ApplicationSettings | None = None) -> ApplicationSettings:
        fallback = defaults or ApplicationSettings()
        if not self.path.exists():
            return fallback
        try:
            payload = cast(dict[str, object], json.loads(self.path.read_text(encoding="utf-8")))
            raw = cast(dict[str, object], payload.get("settings", {}))
            engine = cast(dict[str, object], raw.get("engine", {}))
            players = cast(dict[str, object], raw.get("players", {}))
            clock = cast(dict[str, object], raw.get("clock", {}))
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
                    enabled=bool(engine.get("enabled", fallback.engine.enabled)),
                    path=_optional_string(engine.get("path", fallback.engine.path)),
                    analysis_enabled=bool(
                        engine.get("analysis_enabled", fallback.engine.analysis_enabled)
                    ),
                    analysis_time_ms=_int_value(
                        engine.get("analysis_time_ms"), fallback.engine.analysis_time_ms
                    ),
                    analysis_depth=_optional_int(
                        engine.get("analysis_depth", fallback.engine.analysis_depth)
                    ),
                    multipv=_int_value(engine.get("multipv"), fallback.engine.multipv),
                    strength=EngineStrength(str(engine.get("strength", fallback.engine.strength))),
                    threads=_int_value(engine.get("threads"), fallback.engine.threads),
                    hash_mb=_int_value(engine.get("hash_mb"), fallback.engine.hash_mb),
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
                    enabled=bool(clock.get("enabled", fallback.clock.enabled)),
                    initial_seconds=_float_value(
                        clock.get("initial_seconds"), fallback.clock.initial_seconds
                    ),
                    increment_seconds=_float_value(
                        clock.get("increment_seconds"), fallback.clock.increment_seconds
                    ),
                ),
                autosave=bool(raw.get("autosave", fallback.autosave)),
                logging_level=str(raw.get("logging_level", fallback.logging_level)),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return fallback


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else _int_value(value, 0)


def _int_value(value: object, default: int) -> int:
    if isinstance(value, (str, int, float)):
        return int(value)
    return default


def _float_value(value: object, default: float) -> float:
    if isinstance(value, (str, int, float)):
        return float(value)
    return default
