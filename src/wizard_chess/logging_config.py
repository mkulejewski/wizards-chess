"""Central configuration for Wizard Chess runtime logging."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from enum import StrEnum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

APPLICATION_LOGGER_NAME = "wizard_chess"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5
_OFF_LEVEL = logging.CRITICAL + 1


class LogLevel(StrEnum):
    """Supported user-facing application logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    OFF = "OFF"

    @classmethod
    def parse(cls, value: str) -> LogLevel:
        """Parse a case-insensitive user/configuration value."""
        try:
            return cls(value.strip().upper())
        except ValueError as error:
            supported = ", ".join(level.value for level in cls)
            raise ValueError(f"invalid log level {value!r}; choose from {supported}") from error

    @property
    def python_level(self) -> int:
        """Return the corresponding standard-library logging threshold."""
        if self is LogLevel.OFF:
            return _OFF_LEVEL
        return {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
        }[self]


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Resolved logging level and independent output destinations."""

    level: LogLevel = LogLevel.INFO
    terminal_enabled: bool = True
    file_enabled: bool = True
    file_path: Path | None = None


def configure_logging(
    config: LoggingConfig,
    *,
    terminal_stream: TextIO | None = None,
) -> logging.Logger:
    """Replace application handlers with the supplied deterministic configuration."""
    logger = logging.getLogger(APPLICATION_LOGGER_NAME)
    _remove_handlers(logger)
    logger.disabled = False
    logger.propagate = False
    logger.setLevel(config.level.python_level)

    if config.level is LogLevel.OFF:
        return logger

    if config.terminal_enabled:
        terminal_handler = logging.StreamHandler(terminal_stream or sys.stderr)
        terminal_handler.set_name("wizard-chess-terminal")
        terminal_handler.setLevel(config.level.python_level)
        terminal_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s - %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(terminal_handler)

    if config.file_enabled:
        if config.file_path is None:
            raise ValueError("File logging is enabled but no log file path was resolved")
        try:
            config.file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                config.file_path,
                maxBytes=DEFAULT_MAX_BYTES,
                backupCount=DEFAULT_BACKUP_COUNT,
                encoding="utf-8",
            )
        except OSError as error:
            logger.warning("File logging unavailable at %s: %s", config.file_path, error)
        else:
            file_handler.set_name("wizard-chess-file")
            file_handler.setLevel(config.level.python_level)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(file_handler)

    return logger


def _remove_handlers(logger: logging.Logger) -> None:
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
