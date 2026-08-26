"""Reusable application session shared by every input and output adapter."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import chess

from wizard_chess.analysis.live import LiveAnalysisController
from wizard_chess.application.clock import ChessClock, ClockSnapshot
from wizard_chess.commands.intents import CommandIntent, CommandName, MoveCommandIntent
from wizard_chess.commands.language import LanguageCommandParser
from wizard_chess.commands.resolver import MoveResolver
from wizard_chess.configuration import (
    ApplicationSettings,
    EngineAnalysisMode,
    EngineSettings,
    PlayerKind,
    StockfishPlayerMode,
    VoiceLanguage,
)
from wizard_chess.domain.events import MoveAnnotation, MoveExecuted
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameResult, PlayerColor
from wizard_chess.engine.base import ChessEngine
from wizard_chess.engine.factory import create_stockfish_engine
from wizard_chess.engine.models import EngineClockState, EngineDecision
from wizard_chess.hardware.base import (
    ClosablePhysicalBoard,
    PhysicalBoard,
    PhysicalBoardPositionObserver,
)
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard
from wizard_chess.localization import translate
from wizard_chess.persistence.game_store import GameStore

LOGGER = logging.getLogger(__name__)

EngineFactory = Callable[[EngineSettings], ChessEngine | None]

HELP_TEXT = """Moves (SAN):
  e4 | Nf3 | exd5 | O-O | e8=Q
Coordinate forms:
  e2 e4 | e2-e4 | e2 to e4 | move e2 to e4
  e7 e8 queen (promotion: queen, rook, bishop, knight, or q/r/b/n)
Commands:
  undo, redo, fen, pgn, new game, resign, draw, save, repeat, legal, help, quit
Voice input (terminal):
  voice"""


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Immutable presentation data derived from one authoritative game state."""

    pieces: tuple[tuple[str, str], ...]
    legal_moves: tuple[ChessMove, ...]
    move_history: tuple[str, ...]
    last_move: ChessMove | None
    turn: PlayerColor
    result: GameResult
    fen: str
    pgn: str
    can_undo: bool
    can_redo: bool
    clock: ClockSnapshot | None = None
    viewed_ply: int | None = None
    revision: int = 0

    def piece_at(self, square: str) -> str | None:
        """Return a FEN piece symbol at a square, if occupied."""
        return dict(self.pieces).get(square.lower())


@dataclass(frozen=True, slots=True)
class SessionResult:
    """Result of interpreting one text command through the shared session."""

    message: str | None = None
    move_event: MoveExecuted | None = None
    quit_requested: bool = False


class GameSession:
    """Coordinate commands, direct moves, state changes, and output events."""

    def __init__(
        self,
        physical_board: PhysicalBoard | None = None,
        *,
        settings: ApplicationSettings | None = None,
        engine: ChessEngine | None = None,
        engine_factory: EngineFactory = create_stockfish_engine,
        game_store: GameStore | None = None,
        clock: ChessClock | None = None,
    ) -> None:
        self.settings = (settings or ApplicationSettings.from_environment()).with_required_engine()
        self._physical_board = (
            physical_board if physical_board is not None else SimulatedPhysicalBoard()
        )
        self._parser = LanguageCommandParser(self.settings.voice_language)
        self._resolver = MoveResolver()
        self._game = self._new_configured_game()
        self._engine_factory = engine_factory
        self._engine = engine if engine is not None else self._engine_factory(self.settings.engine)
        self._game_store = game_store
        self._clock = clock or ChessClock(self.settings.clock)
        self._analysis_mode = self.settings.engine.analysis_mode
        self.live_analysis = LiveAnalysisController(self.settings.engine.live_analysis_max_depth)
        self._last_feedback: str | None = None
        self._revision = 0

    @property
    def game(self) -> ChessGame:
        """Expose the authoritative game for compatibility and composition."""
        return self._game

    @property
    def engine(self) -> ChessEngine | None:
        return self._engine

    @property
    def analysis_enabled(self) -> bool:
        return self._analysis_mode is not EngineAnalysisMode.OFF

    @property
    def analysis_mode(self) -> EngineAnalysisMode:
        """Return the runtime mode, which commands may temporarily disable."""
        return self._analysis_mode

    @property
    def revision(self) -> int:
        """Monotonic state token used to reject late asynchronous results."""
        return self._revision

    @property
    def voice_language(self) -> VoiceLanguage:
        return self._parser.language

    def set_voice_language(self, language: VoiceLanguage) -> None:
        """Switch the language grammar used by subsequent voice/text submissions."""
        self._parser = LanguageCommandParser(language)
        self.settings = replace(self.settings, voice_language=language)

    def snapshot(self) -> PositionSnapshot:
        """Return all current read-only data needed by presentation adapters."""
        self._adjudicate_timeout()
        engine_name = getattr(self._engine, "engine_name", None)
        if isinstance(engine_name, str) and engine_name and "Engine" not in self._game.metadata:
            self._game.update_metadata(Engine=engine_name)
        return self._snapshot_for_game(self._game)

    def snapshot_at(self, ply: int) -> PositionSnapshot:
        """Inspect an earlier position without changing the authoritative live game."""
        board = self._game.board
        if not 0 <= ply <= len(board.move_stack):
            raise ValueError(f"History ply is out of range: {ply}")
        replay = ChessGame(board.root().fen(), metadata=self._game.metadata)
        for move in board.move_stack[:ply]:
            replay.make_move(ChessMove.from_python_chess(move))
        snapshot = self._snapshot_for_game(replay)
        return PositionSnapshot(
            pieces=snapshot.pieces,
            legal_moves=snapshot.legal_moves,
            move_history=snapshot.move_history,
            last_move=snapshot.last_move,
            turn=snapshot.turn,
            result=snapshot.result,
            fen=snapshot.fen,
            pgn=snapshot.pgn,
            can_undo=snapshot.can_undo,
            can_redo=snapshot.can_redo,
            clock=None,
            viewed_ply=ply,
            revision=self._revision,
        )

    def position_fens(self) -> tuple[str, ...]:
        """Return initial-through-current FENs for cached evaluation plotting."""
        source = self._game.board
        replay = source.root()
        fens = [replay.fen()]
        for move in source.move_stack:
            replay.push(move)
            fens.append(replay.fen())
        return tuple(fens)

    def _snapshot_for_game(self, game: ChessGame) -> PositionSnapshot:
        board = game.board
        pieces = tuple(
            sorted(
                (chess.square_name(square), piece.symbol())
                for square, piece in board.piece_map().items()
            )
        )
        return PositionSnapshot(
            pieces=pieces,
            legal_moves=game.legal_moves(),
            move_history=game.move_history(),
            last_move=game.last_move(),
            turn=game.turn,
            result=game.result(),
            fen=game.fen(),
            pgn=game.to_pgn(),
            can_undo=game.can_undo,
            can_redo=game.can_redo,
            clock=(
                self._clock.snapshot()
                if game is self._game and self.settings.clock.enabled
                else None
            ),
            revision=self._revision,
        )

    def play_text(self, text: str) -> SessionResult:
        """Interpret text and execute it through the authoritative application path."""
        intent = self._parser.parse(text)
        if isinstance(intent, MoveCommandIntent):
            move = self._resolver.resolve(intent, self._game)
            event = self.play_move(move)
            result = SessionResult(
                message=translate("session.played", self.voice_language, san=event.san),
                move_event=event,
            )
        else:
            result = self._execute_command(intent)
        is_repeat = isinstance(intent, CommandIntent) and intent.command is CommandName.REPEAT
        if result.message is not None and not is_repeat:
            self._last_feedback = result.message
        return result

    def play_move(
        self,
        move: ChessMove,
        *,
        engine_decision: EngineDecision | None = None,
    ) -> MoveExecuted:
        """Execute one direct/click move and emit the normal physical-board event."""
        self._adjudicate_timeout()
        mover = self._game.turn
        event = self._game.make_move(move)
        self._emit_physical_move(event)
        timing = self._clock.switch(self._game.turn)
        evaluation = engine_decision.evaluation if engine_decision is not None else None
        annotation = MoveAnnotation(
            elapsed_seconds=(
                timing.elapsed_seconds
                if timing is not None
                else engine_decision.search_time_seconds
                if engine_decision is not None
                else None
            ),
            remaining_seconds=timing.remaining_seconds if timing is not None else None,
            evaluation_cp=evaluation.score_cp if evaluation is not None else None,
            mate_in=evaluation.mate_in if evaluation is not None else None,
            depth=engine_decision.depth if engine_decision is not None else None,
            nodes=engine_decision.nodes if engine_decision is not None else None,
            tablebase_hits=(
                engine_decision.tablebase_hits if engine_decision is not None else None
            ),
        )
        if any(
            value is not None
            for value in (
                annotation.elapsed_seconds,
                annotation.remaining_seconds,
                annotation.evaluation_cp,
                annotation.mate_in,
                annotation.depth,
                annotation.nodes,
                annotation.tablebase_hits,
            )
        ):
            self._game.annotate_last_move(annotation)
        if engine_decision is not None and engine_decision.engine_name:
            player_engine_header = "WhiteEngine" if mover is PlayerColor.WHITE else "BlackEngine"
            self._game.update_metadata(
                Engine=engine_decision.engine_name,
                **{player_engine_header: engine_decision.engine_name},
            )
        self._revision += 1
        self._autosave()
        LOGGER.info("Move executed: %s", event.uci)
        return event

    def undo(self) -> ChessMove:
        """Undo through the authoritative domain history."""
        move = self._game.undo()
        self._notify_physical_position_replaced()
        self._clock.set_active(self._game.turn)
        self._revision += 1
        self._autosave()
        return move

    def redo(self) -> MoveExecuted:
        """Redo and emit the same event as any accepted move."""
        event = self._game.redo()
        self._emit_physical_move(event)
        self._clock.set_active(self._game.turn)
        self._revision += 1
        self._autosave()
        return event

    def new_game(self, settings: ApplicationSettings | None = None) -> None:
        """Atomically apply optional setup and replace the authoritative game."""
        if settings is not None:
            self._configure_new_game(settings)
            return
        self._game = self._new_configured_game()
        self._notify_physical_position_replaced()
        self._clock.reset(self._game.turn)
        self.live_analysis.reset(self.settings.engine.live_analysis_max_depth)
        self._revision += 1
        self._last_feedback = None
        self._autosave()
        LOGGER.info("New game")

    def _configure_new_game(self, settings: ApplicationSettings) -> None:
        configured = settings.with_required_engine()
        replacement_engine = self._engine_factory(configured.engine)
        replacement_clock = ChessClock(configured.clock)
        replacement_game = ChessGame(metadata=self._game_metadata(configured))

        self._clock.pause()
        previous_engine = self._engine
        self.settings = configured
        self._parser = LanguageCommandParser(configured.voice_language)
        self._engine = replacement_engine
        self._clock = replacement_clock
        self._game = replacement_game
        self._notify_physical_position_replaced()
        self._analysis_mode = configured.engine.analysis_mode
        self.live_analysis.reset(configured.engine.live_analysis_max_depth)
        self._last_feedback = None
        self._revision += 1
        if previous_engine is not None:
            previous_engine.close()
        self._autosave()
        LOGGER.info("New configured game")

    def load_fen(self, fen: str) -> None:
        """Load a validated position and clear its unavailable history."""
        self._game.load_fen(fen)
        self._notify_physical_position_replaced()
        self._clock.reset(self._game.turn)
        self.live_analysis.reset(self.settings.engine.live_analysis_max_depth)
        self._revision += 1
        self._autosave()

    def load_pgn(self, pgn: str) -> None:
        """Load one validated main-line game without bypassing domain rules."""
        replacement = ChessGame()
        replacement.load_pgn(pgn)
        self._game = replacement
        self._notify_physical_position_replaced()
        self._clock.reset(self._game.turn)
        self.live_analysis.reset(self.settings.engine.live_analysis_max_depth)
        self._revision += 1
        self._autosave()

    def save_game(self, destination: str | Path | None = None) -> Path:
        """Save PGN to an explicit path or a unique local game-store path."""
        if destination is not None:
            from wizard_chess.persistence.pgn_store import PgnStore

            path = PgnStore().save(self._game.to_pgn(), destination)
        else:
            store = self._game_store or GameStore(Path.cwd() / "saved-games")
            path = store.save(self._game.to_pgn())
        LOGGER.info("Game saved: %s", path.name)
        return path

    def play_engine_move(self) -> MoveExecuted | None:
        """Request and centrally commit an engine move for the current position."""
        if self._engine is None or not self.prepare_engine_turn():
            return None
        source_fen = self._game.fen()
        source_revision = self._revision
        decision = self._engine.play_move(
            self._game.board,
            clock=self.engine_clock_state(),
        )
        if decision is None:
            return None
        if isinstance(decision, ChessMove):  # Compatibility with older engine adapters.
            decision = EngineDecision(move=decision)
        return self.commit_engine_decision(
            decision,
            expected_fen=source_fen,
            expected_revision=source_revision,
        )

    def prepare_engine_turn(self) -> bool:
        """Adjudicate and start timing before an engine worker is requested."""
        self._adjudicate_timeout()
        if self._game.is_game_over() or not self.engine_controls_turn():
            return False
        claimable = self._game.result()
        if claimable.can_claim_draw:
            self._game.claim_draw()
            self._clock.pause()
            self._revision += 1
            self._autosave()
            LOGGER.info("Stockfish claimed a draw: %s", self._game.result().status.value)
            return False
        if self.settings.engine.player_mode is StockfishPlayerMode.GAME_CLOCK:
            self._clock.start(self._game.turn)
        return True

    def engine_clock_state(self) -> EngineClockState | None:
        """Return the authoritative clock values for one clock-managed engine request."""
        if self.settings.engine.player_mode is not StockfishPlayerMode.GAME_CLOCK:
            return None
        snapshot = self._clock.snapshot()
        if not self.settings.clock.enabled:
            return None
        increment = self.settings.clock.increment_seconds
        return EngineClockState(
            white_seconds=snapshot.white_seconds,
            black_seconds=snapshot.black_seconds,
            white_increment_seconds=increment,
            black_increment_seconds=increment,
        )

    def commit_engine_decision(
        self,
        decision: EngineDecision,
        *,
        expected_fen: str,
        expected_revision: int,
    ) -> MoveExecuted | None:
        """Commit only a current, legal engine result from a non-flagged worker."""
        self._adjudicate_timeout()
        if (
            expected_revision != self._revision
            or expected_fen != self._game.fen()
            or self._game.is_game_over()
            or not self.engine_controls_turn()
        ):
            LOGGER.info("Ignored stale or terminal engine decision")
            return None
        return self.play_move(decision.move, engine_decision=decision)

    def engine_controls_turn(self) -> bool:
        players = self.settings.players
        kind = players.white_kind if self._game.turn.value == "white" else players.black_kind
        return kind is PlayerKind.ENGINE

    def start_clock(self) -> None:
        """Start or resume the optional clock for the authoritative side to move."""
        if self._game.is_game_over():
            return
        self._clock.start(self._game.turn)

    def pause_clock(self) -> None:
        """Pause the optional clock after accounting for monotonic elapsed time."""
        self._clock.pause()

    def reset_clock(self) -> None:
        """Reset both clocks without changing the chess position."""
        self._clock.reset(self._game.turn)

    def close(self) -> None:
        """Close optional owned services at application shutdown."""
        self._clock.pause()
        self._autosave()
        if self._engine is not None:
            self._engine.close()
        self.live_analysis.reset()
        if isinstance(self._physical_board, ClosablePhysicalBoard):
            try:
                self._physical_board.close()
            except Exception:
                LOGGER.exception("Physical-board shutdown failed")

    def _emit_physical_move(self, event: MoveExecuted) -> None:
        """Keep optional output-adapter failures outside the chess transaction."""
        try:
            self._physical_board.execute_move(event)
        except Exception:
            LOGGER.exception("Physical-board execution failed after digital move %s", event.uci)

    def _notify_physical_position_replaced(self) -> None:
        """Tell capable adapters that digital state changed without physical motion."""
        if not isinstance(self._physical_board, PhysicalBoardPositionObserver):
            return
        try:
            self._physical_board.position_replaced()
        except Exception:
            LOGGER.exception("Physical-board replacement notification failed")

    def _execute_command(self, intent: CommandIntent) -> SessionResult:
        command = intent.command
        if command is CommandName.QUIT:
            return SessionResult(quit_requested=True)
        if command is CommandName.HELP:
            return SessionResult(message=HELP_TEXT)
        if command is CommandName.FEN:
            return SessionResult(message=self._game.fen())
        if command is CommandName.PGN:
            return SessionResult(message=self._game.to_pgn())
        if command is CommandName.LEGAL:
            return SessionResult(message=" ".join(move.uci() for move in self._game.legal_moves()))
        if command is CommandName.NEW:
            self.new_game()
            return SessionResult(message=translate("session.new_game", self.voice_language))
        if command is CommandName.UNDO:
            move = self.undo()
            return SessionResult(
                message=translate("session.undo", self.voice_language, move=move.uci())
            )
        if command is CommandName.REDO:
            event = self.redo()
            return SessionResult(
                message=translate("session.redo", self.voice_language, san=event.san),
                move_event=event,
            )
        if command is CommandName.RESIGN:
            result = self._game.resign()
            self._clock.pause()
            self._revision += 1
            self._autosave()
            winner = result.winner.value.title() if result.winner is not None else "Unknown"
            return SessionResult(
                message=translate("session.resigned", self.voice_language, winner=winner)
            )
        if command is CommandName.DRAW:
            self._game.agree_draw()
            self._clock.pause()
            self._revision += 1
            self._autosave()
            return SessionResult(message=translate("session.draw", self.voice_language))
        if command is CommandName.SAVE:
            return SessionResult(
                message=translate(
                    "session.saved",
                    self.voice_language,
                    path=self.save_game(),
                )
            )
        if command is CommandName.REPEAT:
            return SessionResult(
                message=self._last_feedback
                or translate("session.nothing_to_repeat", self.voice_language)
            )
        if command is CommandName.ANALYSIS_ON:
            configured = self.settings.engine.analysis_mode
            self._analysis_mode = (
                configured
                if configured is not EngineAnalysisMode.OFF
                else EngineAnalysisMode.FIXED_TIME
            )
            return SessionResult(message=translate("session.analysis_enabled", self.voice_language))
        self._analysis_mode = EngineAnalysisMode.OFF
        self.live_analysis.invalidate_selection()
        return SessionResult(message=translate("session.analysis_disabled", self.voice_language))

    def _autosave(self) -> None:
        if not self.settings.autosave or self._game_store is None:
            return
        try:
            self._game_store.autosave(self._game.to_pgn())
        except OSError:
            LOGGER.warning("Game autosave failed", exc_info=True)

    def _adjudicate_timeout(self) -> None:
        snapshot = self._clock.snapshot()
        if snapshot.expired is None or self._game.is_game_over():
            return
        self._game.forfeit_on_time(snapshot.expired)
        self._revision += 1
        self._autosave()
        LOGGER.info("Time forfeit: %s", snapshot.expired.value)

    def _new_configured_game(self) -> ChessGame:
        return ChessGame(metadata=self._game_metadata(self.settings))

    @staticmethod
    def _game_metadata(settings: ApplicationSettings) -> dict[str, str]:
        players = settings.players
        engine = settings.engine
        metadata = {
            "White": players.white_name,
            "Black": players.black_name,
            "WhiteType": "Stockfish" if players.white_kind is PlayerKind.ENGINE else "Human",
            "BlackType": "Stockfish" if players.black_kind is PlayerKind.ENGINE else "Human",
        }
        if settings.clock.enabled:
            metadata["TimeControl"] = (
                f"{_format_time_control(settings.clock.initial_seconds)}+"
                f"{_format_time_control(settings.clock.increment_seconds)}"
            )
        if PlayerKind.ENGINE in {players.white_kind, players.black_kind}:
            metadata.update(
                {
                    "EngineStrength": engine.strength.value,
                    "EngineThreads": str(engine.threads),
                    "EngineHashMB": str(engine.hash_mb),
                    "StockfishPlayerMode": engine.player_mode.value,
                }
            )
            if engine.player_mode is StockfishPlayerMode.FIXED_ANALYSIS_TIME:
                metadata["PlayerMoveAnalysisTimeMs"] = str(engine.player_move_analysis_time_ms)
            if engine.syzygy_path:
                metadata.update(
                    {
                        "SyzygyPath": engine.syzygy_path,
                        "SyzygyProbeLimit": str(engine.syzygy_probe_limit),
                        "Syzygy50MoveRule": str(engine.syzygy_50_move_rule).lower(),
                    }
                )
        return metadata


def _format_time_control(seconds: float) -> str:
    numeric = float(seconds)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:g}"
