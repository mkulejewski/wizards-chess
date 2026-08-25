"""Validated runtime settings shared by composition roots and optional adapters."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum

LOGGER = logging.getLogger(__name__)


class VoiceLanguage(StrEnum):
    """Explicit language hints supported by the chess voice grammar."""

    ENGLISH = "en"
    POLISH = "pl"
    AUTO = "auto"


class ConfirmationPolicy(StrEnum):
    """When voice commands should pause for confirmation."""

    OFF = "off"
    AMBIGUOUS_OR_LOW_CONFIDENCE = "ambiguous_or_low_confidence"
    ALWAYS = "always"


class PlayerKind(StrEnum):
    """Who controls one side in a local game."""

    HUMAN = "human"
    ENGINE = "engine"


class PieceSet(StrEnum):
    """Locally rendered chess-piece artwork choices."""

    TATIANA = "tatiana"
    CLASSIC_SYMBOLS = "classic_symbols"


class BoardTheme(StrEnum):
    """Color palettes available to the desktop board adapter."""

    WALNUT = "walnut"
    BROWN = "brown"
    GREEN = "green"
    BLUE = "blue"
    SLATE = "slate"


class EngineStrength(StrEnum):
    """User-facing engine strength bands, not promised Elo ratings."""

    BEGINNER = "beginner"
    CASUAL = "casual"
    CLUB = "club"
    STRONG_CLUB = "strong_club"
    EXPERT = "expert"
    MASTER = "master"
    MAXIMUM = "maximum"


class StockfishPlayerMode(StrEnum):
    """How a Stockfish-controlled player receives its search budget."""

    FIXED_ANALYSIS_TIME = "fixed_analysis_time"
    GAME_CLOCK = "game_clock"


@dataclass(frozen=True, slots=True)
class EngineSettings:
    """Settings for optional UCI analysis and engine play."""

    enabled: bool = False
    path: str | None = None
    analysis_enabled: bool = False
    player_mode: StockfishPlayerMode = StockfishPlayerMode.FIXED_ANALYSIS_TIME
    player_move_analysis_time_ms: int = 500
    post_game_analysis_time_ms: int = 500
    analysis_depth: int | None = None
    multipv: int = 3
    strength: EngineStrength = EngineStrength.CLUB
    threads: int = 1
    hash_mb: int = 128
    syzygy_path: str | None = None
    syzygy_probe_limit: int = 7
    syzygy_50_move_rule: bool = True

    def __post_init__(self) -> None:
        if self.player_move_analysis_time_ms <= 0:
            raise ValueError("Stockfish player move analysis time must be positive")
        if self.post_game_analysis_time_ms <= 0:
            raise ValueError("Post-game analysis time must be positive")
        if self.analysis_depth is not None and self.analysis_depth <= 0:
            raise ValueError("Engine analysis depth must be positive")
        if self.multipv <= 0:
            raise ValueError("Engine MultiPV count must be positive")
        if self.threads <= 0 or self.hash_mb <= 0:
            raise ValueError("Engine thread and hash settings must be positive")
        if not 0 <= self.syzygy_probe_limit <= 7:
            raise ValueError("Syzygy probe limit must be between 0 and 7")


@dataclass(frozen=True, slots=True)
class PlayerSettings:
    """Local player names and controller types."""

    white_name: str = "White"
    black_name: str = "Black"
    white_kind: PlayerKind = PlayerKind.HUMAN
    black_kind: PlayerKind = PlayerKind.HUMAN


@dataclass(frozen=True, slots=True)
class ClockSettings:
    """Optional local chess-clock configuration."""

    enabled: bool = False
    initial_seconds: float = 600.0
    increment_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.initial_seconds <= 0:
            raise ValueError("Clock initial time must be positive")
        if self.increment_seconds < 0:
            raise ValueError("Clock increment cannot be negative")


@dataclass(frozen=True, slots=True)
class AppearanceSettings:
    """Presentation-only settings for the desktop chessboard."""

    piece_set: PieceSet = PieceSet.TATIANA
    board_theme: BoardTheme = BoardTheme.WALNUT


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    """Central configuration with conservative, dependency-free defaults."""

    voice_language: VoiceLanguage = VoiceLanguage.ENGLISH
    confirmation_policy: ConfirmationPolicy = ConfirmationPolicy.OFF
    confidence_threshold: float = 0.65
    engine: EngineSettings = field(default_factory=EngineSettings)
    players: PlayerSettings = field(default_factory=PlayerSettings)
    clock: ClockSettings = field(default_factory=ClockSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    game_setup_saved: bool = False
    show_game_setup_on_startup: bool = True
    autosave: bool = False
    logging_level: str = "INFO"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("Voice confidence threshold must be between 0 and 1")
        if self.logging_level.upper() not in logging.getLevelNamesMapping():
            raise ValueError(f"Invalid logging level: {self.logging_level}")

    @property
    def engine_required(self) -> bool:
        """Return whether any selected feature requires the engine adapter."""
        return (
            self.engine.enabled
            or self.engine.analysis_enabled
            or self.players.white_kind is PlayerKind.ENGINE
            or self.players.black_kind is PlayerKind.ENGINE
        )

    def with_required_engine(self) -> ApplicationSettings:
        """Derive the low-level engine flag from user-facing feature choices."""
        if self.engine.enabled == self.engine_required:
            return self
        return replace(self, engine=replace(self.engine, enabled=self.engine_required))

    @classmethod
    def from_environment(
        cls,
        base: ApplicationSettings | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> ApplicationSettings:
        """Overlay supported environment values on persisted settings or defaults."""
        defaults = base or cls()
        values = os.environ if environment is None else environment
        language = _enum_environment(
            values,
            "WIZARD_CHESS_VOICE_LANGUAGE",
            VoiceLanguage,
            defaults.voice_language,
        )
        strength = _enum_environment(
            values,
            "WIZARD_CHESS_ENGINE_STRENGTH",
            EngineStrength,
            defaults.engine.strength,
        )
        engine_enabled = _bool_environment(
            values, "WIZARD_CHESS_ENGINE_ENABLED", defaults.engine.enabled
        )
        analysis_default = (
            engine_enabled
            if "WIZARD_CHESS_ENGINE_ENABLED" in values
            else defaults.engine.analysis_enabled
        )
        analysis_enabled = _bool_environment(
            values, "WIZARD_CHESS_ANALYSIS_ENABLED", analysis_default
        )
        path = (
            values["WIZARD_CHESS_ENGINE_PATH"].strip() or None
            if "WIZARD_CHESS_ENGINE_PATH" in values
            else defaults.engine.path
        )
        white_kind = _enum_environment(
            values,
            "WIZARD_CHESS_WHITE_PLAYER",
            PlayerKind,
            defaults.players.white_kind,
        )
        black_kind = _enum_environment(
            values,
            "WIZARD_CHESS_BLACK_PLAYER",
            PlayerKind,
            defaults.players.black_kind,
        )
        clock_enabled = _bool_environment(
            values, "WIZARD_CHESS_CLOCK_ENABLED", defaults.clock.enabled
        )
        legacy_time_ms = _int_environment(
            values,
            "WIZARD_CHESS_ENGINE_TIME_MS",
            defaults.engine.player_move_analysis_time_ms,
            1,
        )
        player_time_default = (
            legacy_time_ms
            if "WIZARD_CHESS_ENGINE_TIME_MS" in values
            else defaults.engine.player_move_analysis_time_ms
        )
        post_game_time_default = (
            legacy_time_ms
            if "WIZARD_CHESS_ENGINE_TIME_MS" in values
            else defaults.engine.post_game_analysis_time_ms
        )
        settings = cls(
            voice_language=language,
            confirmation_policy=_enum_environment(
                values,
                "WIZARD_CHESS_VOICE_CONFIRMATION",
                ConfirmationPolicy,
                defaults.confirmation_policy,
            ),
            confidence_threshold=_float_environment(
                values,
                "WIZARD_CHESS_VOICE_CONFIDENCE",
                defaults.confidence_threshold,
                0.0,
                1.0,
            ),
            engine=EngineSettings(
                enabled=engine_enabled,
                path=path,
                analysis_enabled=analysis_enabled,
                player_mode=_enum_environment(
                    values,
                    "WIZARD_CHESS_STOCKFISH_PLAYER_MODE",
                    StockfishPlayerMode,
                    defaults.engine.player_mode,
                ),
                player_move_analysis_time_ms=_int_environment(
                    values,
                    "WIZARD_CHESS_PLAYER_MOVE_ANALYSIS_TIME_MS",
                    player_time_default,
                    1,
                ),
                post_game_analysis_time_ms=_int_environment(
                    values,
                    "WIZARD_CHESS_POST_GAME_ANALYSIS_TIME_MS",
                    post_game_time_default,
                    1,
                ),
                analysis_depth=_optional_positive_int_environment(
                    values,
                    "WIZARD_CHESS_ENGINE_DEPTH",
                    defaults.engine.analysis_depth,
                ),
                multipv=_int_environment(
                    values,
                    "WIZARD_CHESS_ENGINE_MULTIPV",
                    defaults.engine.multipv,
                    1,
                ),
                strength=strength,
                threads=_int_environment(
                    values,
                    "WIZARD_CHESS_ENGINE_THREADS",
                    defaults.engine.threads,
                    1,
                ),
                hash_mb=_int_environment(
                    values,
                    "WIZARD_CHESS_ENGINE_HASH_MB",
                    defaults.engine.hash_mb,
                    1,
                ),
                syzygy_path=(
                    values["WIZARD_CHESS_SYZYGY_PATH"].strip() or None
                    if "WIZARD_CHESS_SYZYGY_PATH" in values
                    else defaults.engine.syzygy_path
                ),
                syzygy_probe_limit=_bounded_int_environment(
                    values,
                    "WIZARD_CHESS_SYZYGY_PROBE_LIMIT",
                    defaults.engine.syzygy_probe_limit,
                    0,
                    7,
                ),
                syzygy_50_move_rule=_bool_environment(
                    values,
                    "WIZARD_CHESS_SYZYGY_50_MOVE_RULE",
                    defaults.engine.syzygy_50_move_rule,
                ),
            ),
            players=PlayerSettings(
                white_name=values.get(
                    "WIZARD_CHESS_WHITE_NAME", defaults.players.white_name
                ).strip()
                or defaults.players.white_name,
                black_name=values.get(
                    "WIZARD_CHESS_BLACK_NAME", defaults.players.black_name
                ).strip()
                or defaults.players.black_name,
                white_kind=white_kind,
                black_kind=black_kind,
            ),
            clock=ClockSettings(
                enabled=clock_enabled,
                initial_seconds=_float_environment(
                    values,
                    "WIZARD_CHESS_CLOCK_SECONDS",
                    defaults.clock.initial_seconds,
                    1.0,
                    86_400.0,
                ),
                increment_seconds=_float_environment(
                    values,
                    "WIZARD_CHESS_CLOCK_INCREMENT_SECONDS",
                    defaults.clock.increment_seconds,
                    0.0,
                    600.0,
                ),
            ),
            appearance=defaults.appearance,
            game_setup_saved=defaults.game_setup_saved,
            show_game_setup_on_startup=defaults.show_game_setup_on_startup,
            autosave=_bool_environment(values, "WIZARD_CHESS_AUTOSAVE", defaults.autosave),
            logging_level=values.get("WIZARD_CHESS_LOG_LEVEL", defaults.logging_level).upper(),
        )
        return settings.with_required_engine()


GAME_SETUP_ENVIRONMENT_VARIABLES = frozenset(
    {
        "WIZARD_CHESS_ENGINE_ENABLED",
        "WIZARD_CHESS_ENGINE_PATH",
        "WIZARD_CHESS_ANALYSIS_ENABLED",
        "WIZARD_CHESS_ENGINE_TIME_MS",
        "WIZARD_CHESS_PLAYER_MOVE_ANALYSIS_TIME_MS",
        "WIZARD_CHESS_POST_GAME_ANALYSIS_TIME_MS",
        "WIZARD_CHESS_STOCKFISH_PLAYER_MODE",
        "WIZARD_CHESS_SYZYGY_PATH",
        "WIZARD_CHESS_SYZYGY_PROBE_LIMIT",
        "WIZARD_CHESS_SYZYGY_50_MOVE_RULE",
        "WIZARD_CHESS_ENGINE_STRENGTH",
        "WIZARD_CHESS_WHITE_PLAYER",
        "WIZARD_CHESS_BLACK_PLAYER",
        "WIZARD_CHESS_WHITE_NAME",
        "WIZARD_CHESS_BLACK_NAME",
        "WIZARD_CHESS_CLOCK_ENABLED",
        "WIZARD_CHESS_CLOCK_SECONDS",
        "WIZARD_CHESS_CLOCK_INCREMENT_SECONDS",
    }
)


def should_show_game_setup(
    settings: ApplicationSettings,
    *,
    force: bool = False,
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Resolve first-run, saved, environment-only, and forced startup behavior."""
    if force:
        return True
    if settings.game_setup_saved:
        return settings.show_game_setup_on_startup
    values = os.environ if environment is None else environment
    return GAME_SETUP_ENVIRONMENT_VARIABLES.isdisjoint(values)


def _bool_environment(values: Mapping[str, str], name: str, default: bool) -> bool:
    value = values.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    LOGGER.warning("Ignoring invalid %s=%r", name, value)
    return default


def _int_environment(values: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    value = values.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        LOGGER.warning("Ignoring invalid %s=%r", name, value)
        return default
    if parsed < minimum:
        LOGGER.warning("Ignoring out-of-range %s=%r", name, value)
        return default
    return parsed


def _bounded_int_environment(
    values: Mapping[str, str],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    parsed = _int_environment(values, name, default, minimum)
    if parsed > maximum:
        LOGGER.warning("Ignoring out-of-range %s=%r", name, values.get(name))
        return default
    return parsed


def _optional_positive_int_environment(
    values: Mapping[str, str], name: str, default: int | None
) -> int | None:
    value = values.get(name)
    if value is None:
        return default
    if not value.strip():
        return None
    parsed = _int_environment(values, name, 0, 1)
    return parsed or default


def _float_environment(
    values: Mapping[str, str],
    name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    value = values.get(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        LOGGER.warning("Ignoring invalid %s=%r", name, value)
        return default
    if not minimum <= parsed <= maximum:
        LOGGER.warning("Ignoring out-of-range %s=%r", name, value)
        return default
    return parsed


def _enum_environment[EnumT: StrEnum](
    values: Mapping[str, str],
    name: str,
    enum_type: type[EnumT],
    default: EnumT,
) -> EnumT:
    value = values.get(name)
    if value is None:
        return default
    try:
        return enum_type(value.strip().lower())
    except ValueError:
        LOGGER.warning("Ignoring invalid %s=%r", name, value)
        return default
