"""Composition and entry points for the GUI and retained development CLI."""

import argparse
import logging
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

from wizard_chess.application.scripted_game import ScriptedGameRunner
from wizard_chess.application.session import GameSession, SessionResult
from wizard_chess.configuration import ApplicationSettings
from wizard_chess.domain.exceptions import WizardChessError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.results import GameStatus
from wizard_chess.hardware.base import PhysicalBoard
from wizard_chess.logging_config import LoggingConfig, LogLevel, configure_logging
from wizard_chess.persistence.game_store import GameStore
from wizard_chess.persistence.settings_store import SettingsStore
from wizard_chess.speech.config import VoiceConfig
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.exceptions import VoiceCommandRejected, VoiceError
from wizard_chess.speech.factory import create_default_voice_controller
from wizard_chess.speech.models import VoiceState

InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]
LOGGER = logging.getLogger(__name__)


class CliApplication:
    """Composition root for the temporary terminal interface."""

    def __init__(
        self,
        *,
        input_fn: InputFunction = input,
        output_fn: OutputFunction = print,
        physical_board: PhysicalBoard | None = None,
        session: GameSession | None = None,
        voice_controller: VoiceController[SessionResult] | None = None,
    ) -> None:
        self._input = input_fn
        self._output = output_fn
        self._session = session or GameSession(physical_board)
        self._voice_controller = voice_controller or create_default_voice_controller(
            self._session.play_text,
            VoiceConfig.from_environment(language=self._session.voice_language),
        )
        self._engine_failed = False

    @property
    def game(self) -> ChessGame:
        return self._session.game

    def run(self) -> int:
        LOGGER.info("Terminal interface started")
        self._output("Wizard Chess")
        self._output("Type 'help' for commands.")

        while True:
            if (
                not self._engine_failed
                and self._session.engine_controls_turn()
                and not self.game.is_game_over()
            ):
                self._play_engine_turn()
            try:
                text = self._input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                self._output("")
                self._shutdown()
                return 0

            try:
                if text.strip().lower() == "voice":
                    if self._run_voice_command():
                        self._shutdown()
                        return 0
                    continue

                if self._handle_session_result(self._session.play_text(text)):
                    self._shutdown()
                    return 0
            except WizardChessError as error:
                self._output(f"Error: {error}")

    def _run_voice_command(self) -> bool:
        try:
            result = self._voice_controller.listen_once(self._announce_voice_state)
        except VoiceCommandRejected as error:
            self._output(f'Heard: "{error.recognition.transcript}"')
            self._output(f"Error: {error.cause}")
            self._output("Please try again.")
            return False
        except VoiceError as error:
            self._output(str(error))
            return False

        self._output(f'Heard: "{result.recognition.transcript}"')
        return self._handle_session_result(result.command_result)

    def _announce_voice_state(self, state: VoiceState) -> None:
        if state is VoiceState.LISTENING:
            self._output("Listening...")
        elif state is VoiceState.PROCESSING:
            self._output("Processing...")

    def _handle_session_result(self, result: SessionResult) -> bool:
        if result.message is not None:
            self._output(result.message)
        if result.move_event is not None:
            self._announce_state()
            if self._session.engine_controls_turn() and not self.game.is_game_over():
                self._play_engine_turn()
        return result.quit_requested

    def _play_engine_turn(self) -> None:
        self._output("Engine thinking...")
        try:
            event = self._session.play_engine_move()
        except WizardChessError as error:
            self._engine_failed = True
            self._output(f"Engine unavailable: {error}. Typed play remains available.")
            return
        if event is not None:
            self._output(f"Engine played: {event.san}")
            self._announce_state()

    def _prompt(self) -> str:
        if self.game.is_game_over():
            return "\nGame over > "
        return f"\n{self.game.turn.value.title()} to move > "

    def _announce_state(self) -> None:
        result = self.game.result()
        if result.status is GameStatus.CHECK:
            self._output("Check.")
        elif result.is_over:
            label = result.status.value.replace("_", " ").title()
            self._output(f"{label}: {result.notation}")

    def _shutdown(self) -> None:
        self._session.close()
        LOGGER.info("Terminal interface stopped")


def run(argv: Sequence[str] | None = None) -> int:
    """Launch the desktop GUI by default, or the retained CLI with ``--cli``."""
    parser = build_argument_parser()
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    settings_store = SettingsStore(_configuration_directory() / "settings.json")
    persistent_settings = settings_store.load()
    settings = ApplicationSettings.from_environment(persistent_settings)
    settings = apply_logging_arguments(settings, arguments)
    logging_config = settings.logging_configuration(default_log_file())
    configure_logging(logging_config)
    mode = "script" if arguments.script else "terminal" if arguments.cli else "gui"
    _log_startup(settings, logging_config, mode)

    try:
        if arguments.script:
            scripted_session = _create_session(settings)
            try:
                result = ScriptedGameRunner(scripted_session).run_file(arguments.script)
                print(result.final_fen)
            finally:
                scripted_session.close()
            exit_code = 0
        elif arguments.cli:
            exit_code = CliApplication(session=_create_session(settings)).run()
        else:
            from wizard_chess.gui.application import run_gui

            exit_code = run_gui(
                [sys.argv[0]],
                session=_create_session(settings),
                settings_store=settings_store,
                persistent_settings=persistent_settings,
                force_setup=arguments.setup,
            )
    except Exception:
        LOGGER.exception("Wizard Chess terminated abnormally")
        raise
    LOGGER.info("Wizard Chess shutting down normally")
    return exit_code


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wizard Chess")
    parser.add_argument("--cli", action="store_true", help="run the terminal interface")
    parser.add_argument("--script", help="play a UTF-8 command script and exit")
    parser.add_argument("--setup", action="store_true", help="show Game Setup at GUI launch")
    parser.add_argument(
        "--log-level",
        type=_parse_log_level,
        metavar="LEVEL",
        help="terminal and file threshold: DEBUG, INFO, WARNING, ERROR, or OFF",
    )
    parser.add_argument(
        "--terminal-log",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="enable or disable terminal log output (enabled by default)",
    )
    file_group = parser.add_mutually_exclusive_group()
    file_group.add_argument(
        "--log-file",
        type=Path,
        metavar="PATH",
        help="enable file logging at PATH",
    )
    file_group.add_argument(
        "--no-log-file",
        action="store_true",
        help="disable persistent file logging",
    )
    return parser


def _parse_log_level(value: str) -> LogLevel:
    try:
        return LogLevel.parse(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def apply_logging_arguments(
    settings: ApplicationSettings,
    arguments: argparse.Namespace,
) -> ApplicationSettings:
    updates: dict[str, object] = {}
    log_level = cast(LogLevel | None, arguments.log_level)
    terminal_enabled = cast(bool | None, arguments.terminal_log)
    log_file = cast(Path | None, arguments.log_file)
    no_log_file = cast(bool, arguments.no_log_file)
    if log_level is not None:
        updates["logging_level"] = log_level
    if terminal_enabled is not None:
        updates["terminal_log_enabled"] = terminal_enabled
    if log_file is not None:
        updates["file_log_enabled"] = True
        updates["log_file_path"] = str(log_file)
    elif no_log_file:
        updates["file_log_enabled"] = False
    return replace(settings, **updates)


def _log_startup(
    settings: ApplicationSettings,
    logging_config: LoggingConfig,
    mode: str,
) -> None:
    players = settings.players
    engine = settings.engine
    file_destination = logging_config.file_path if logging_config.file_enabled else "disabled"
    LOGGER.info("Starting Wizard Chess: mode=%s", mode)
    LOGGER.info(
        "Logging: level=%s terminal=%s file=%s",
        logging_config.level.value,
        "enabled" if logging_config.terminal_enabled else "disabled",
        file_destination,
    )
    LOGGER.info(
        "Game configuration: White=%s (%s), Black=%s (%s)",
        players.white_name,
        players.white_kind.value,
        players.black_name,
        players.black_kind.value,
    )
    LOGGER.info(
        "Speech recognition: on demand; language=%s confirmation=%s",
        settings.voice_language.value,
        settings.confirmation_policy.value,
    )
    if settings.engine_required:
        LOGGER.info(
            "Stockfish enabled: path=%s strength=%s player_mode=%s move_time=%dms analysis=%s",
            engine.path or "automatic",
            engine.strength.value,
            engine.player_mode.value,
            engine.player_move_analysis_time_ms,
            engine.analysis_mode.value,
        )
    else:
        LOGGER.info("Stockfish disabled")
    LOGGER.info("Physical board backend: simulated")
    LOGGER.debug(
        "Runtime options: autosave=%s clock=%s analysis_depth=%s multipv=%d",
        settings.autosave,
        settings.clock.enabled,
        engine.analysis_depth,
        engine.multipv,
    )


def _create_session(settings: ApplicationSettings) -> GameSession:
    game_store = GameStore(_state_directory() / "games")
    session = GameSession(settings=settings, game_store=game_store)
    if settings.autosave:
        recovery = game_store.recover()
        if recovery is not None:
            try:
                session.load_pgn(recovery)
                LOGGER.info("Recovered autosaved game")
            except WizardChessError:
                LOGGER.warning("Autosaved game recovery failed", exc_info=True)
    return session


def _configuration_directory() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(configured) if configured else Path.home() / ".config"
    return root / "wizard-chess"


def _state_directory() -> Path:
    configured = os.environ.get("XDG_STATE_HOME", "").strip()
    root = Path(configured) if configured else Path.home() / ".local" / "state"
    return root / "wizard-chess"


def default_log_file() -> Path:
    return _state_directory() / "logs" / "wizard-chess.log"


if __name__ == "__main__":
    raise SystemExit(run())
