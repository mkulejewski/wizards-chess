from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from wizard_chess.configuration import ApplicationSettings
from wizard_chess.logging_config import (
    APPLICATION_LOGGER_NAME,
    LoggingConfig,
    LogLevel,
    configure_logging,
)
from wizard_chess.main import (
    apply_logging_arguments,
    build_argument_parser,
    default_log_file,
)
from wizard_chess.persistence.settings_store import SettingsStore


@pytest.fixture(autouse=True)
def reset_application_logger() -> Iterator[None]:
    yield
    logger = logging.getLogger(APPLICATION_LOGGER_NAME)
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    logger.disabled = False


def test_default_logging_level_and_destinations() -> None:
    settings = ApplicationSettings()

    assert settings.logging_level is LogLevel.INFO
    assert settings.terminal_log_enabled
    assert settings.file_log_enabled


@pytest.mark.parametrize("value", ["DEBUG", "debug", "Debug"])
def test_cli_accepts_debug_log_level_case_insensitively(value: str) -> None:
    arguments = build_argument_parser().parse_args(["--log-level", value])
    settings = apply_logging_arguments(ApplicationSettings(), arguments)

    assert settings.logging_level is LogLevel.DEBUG


def test_cli_accepts_off_log_level() -> None:
    arguments = build_argument_parser().parse_args(["--log-level", "OFF"])

    assert apply_logging_arguments(ApplicationSettings(), arguments).logging_level is LogLevel.OFF


def test_invalid_cli_log_level_has_clear_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        build_argument_parser().parse_args(["--log-level", "verbose"])

    error = capsys.readouterr().err
    assert "invalid log level 'verbose'" in error
    assert "DEBUG, INFO, WARNING, ERROR, OFF" in error


def test_cli_logging_overrides_environment_settings(tmp_path: Path) -> None:
    environment_settings = ApplicationSettings.from_environment(
        environment={
            "WIZARD_CHESS_LOG_LEVEL": "WARNING",
            "WIZARD_CHESS_TERMINAL_LOG": "false",
            "WIZARD_CHESS_LOG_FILE_ENABLED": "false",
        }
    )
    log_path = tmp_path / "custom" / "session.log"
    arguments = build_argument_parser().parse_args(
        [
            "--log-level",
            "debug",
            "--terminal-log",
            "--log-file",
            str(log_path),
        ]
    )

    resolved = apply_logging_arguments(environment_settings, arguments)

    assert resolved.logging_level is LogLevel.DEBUG
    assert resolved.terminal_log_enabled
    assert resolved.file_log_enabled
    assert resolved.log_file_path == str(log_path)


def test_terminal_handler_is_created_or_omitted_by_configuration(tmp_path: Path) -> None:
    stream = io.StringIO()
    enabled = configure_logging(
        LoggingConfig(
            level=LogLevel.INFO,
            terminal_enabled=True,
            file_enabled=False,
            file_path=tmp_path / "unused.log",
        ),
        terminal_stream=stream,
    )

    assert [handler.name for handler in enabled.handlers] == ["wizard-chess-terminal"]
    assert type(enabled.handlers[0]) is logging.StreamHandler

    disabled = configure_logging(
        LoggingConfig(
            level=LogLevel.INFO,
            terminal_enabled=False,
            file_enabled=False,
            file_path=tmp_path / "unused.log",
        )
    )

    assert disabled.handlers == []


def test_rotating_file_handler_creates_parent_and_writes_utf8(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "wizard-chess.log"
    logger = configure_logging(
        LoggingConfig(
            level=LogLevel.INFO,
            terminal_enabled=False,
            file_enabled=True,
            file_path=path,
        )
    )

    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, RotatingFileHandler)
    assert handler.name == "wizard-chess-file"
    logger.info("Unicode move accepted: zażółć")
    handler.flush()

    contents = path.read_text(encoding="utf-8")
    assert "INFO wizard_chess Unicode move accepted: zażółć" in contents


def test_no_log_file_configuration_creates_no_file_handler(tmp_path: Path) -> None:
    path = tmp_path / "disabled.log"
    logger = configure_logging(
        LoggingConfig(
            level=LogLevel.INFO,
            terminal_enabled=True,
            file_enabled=False,
            file_path=path,
        ),
        terminal_stream=io.StringIO(),
    )

    assert not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers)
    assert not path.exists()


def test_info_filters_debug_while_debug_level_emits_it(tmp_path: Path) -> None:
    info_stream = io.StringIO()
    info_logger = configure_logging(
        LoggingConfig(level=LogLevel.INFO, terminal_enabled=True, file_enabled=False),
        terminal_stream=info_stream,
    )
    info_logger.debug("hidden diagnostic")
    info_logger.info("visible operation")

    assert "hidden diagnostic" not in info_stream.getvalue()
    assert "visible operation" in info_stream.getvalue()

    debug_stream = io.StringIO()
    debug_logger = configure_logging(
        LoggingConfig(level=LogLevel.DEBUG, terminal_enabled=True, file_enabled=False),
        terminal_stream=debug_stream,
    )
    debug_logger.debug("visible diagnostic")

    assert "DEBUG" in debug_stream.getvalue()
    assert "visible diagnostic" in debug_stream.getvalue()


def test_off_removes_handlers_and_suppresses_application_logging() -> None:
    stream = io.StringIO()
    logger = configure_logging(
        LoggingConfig(level=LogLevel.INFO, terminal_enabled=True, file_enabled=False),
        terminal_stream=stream,
    )
    logger.info("before off")

    off_logger = configure_logging(
        LoggingConfig(level=LogLevel.OFF, terminal_enabled=True, file_enabled=True)
    )
    off_logger.error("after off")

    assert off_logger.handlers == []
    assert "before off" in stream.getvalue()
    assert "after off" not in stream.getvalue()


def test_repeated_configuration_does_not_duplicate_handlers_or_messages() -> None:
    stream = io.StringIO()
    config = LoggingConfig(level=LogLevel.INFO, terminal_enabled=True, file_enabled=False)

    configure_logging(config, terminal_stream=stream)
    logger = configure_logging(config, terminal_stream=stream)
    logger.info("one event")

    assert len(logger.handlers) == 1
    assert stream.getvalue().count("one event") == 1


def test_default_file_uses_xdg_state_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert default_log_file() == tmp_path / "wizard-chess" / "logs" / "wizard-chess.log"


def test_cli_can_disable_terminal_and_file_destinations() -> None:
    arguments = build_argument_parser().parse_args(["--no-terminal-log", "--no-log-file"])
    settings = apply_logging_arguments(ApplicationSettings(), arguments)

    assert not settings.terminal_log_enabled
    assert not settings.file_log_enabled


def test_logging_settings_persist_with_the_application_configuration(tmp_path: Path) -> None:
    settings = ApplicationSettings(
        logging_level=LogLevel.ERROR,
        terminal_log_enabled=False,
        file_log_enabled=True,
        log_file_path="logs/persisted.log",
    )
    store = SettingsStore(tmp_path / "settings.json")

    store.save(settings)

    assert store.load() == settings
