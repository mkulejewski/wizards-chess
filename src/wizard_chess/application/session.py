"""Reusable application session shared by CLI, GUI, and future input adapters."""

from dataclasses import dataclass

import chess

from wizard_chess.commands.intents import CommandIntent, CommandName, MoveIntent, SanMoveIntent
from wizard_chess.commands.parser import CommandParser
from wizard_chess.commands.resolver import MoveResolver
from wizard_chess.domain.events import MoveExecuted
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameResult, PlayerColor
from wizard_chess.hardware.base import PhysicalBoard
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard

HELP_TEXT = """Moves (SAN):
  e4 | Nf3 | exd5 | O-O | e8=Q
Coordinate forms:
  e2 e4 | e2-e4 | e2 to e4 | move e2 to e4
  e7 e8 queen (promotion: queen, rook, bishop, knight, or q/r/b/n)
Commands:
  undo, redo, fen, pgn, new, legal, help, quit
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

    def __init__(self, physical_board: PhysicalBoard | None = None) -> None:
        self._physical_board = (
            physical_board if physical_board is not None else SimulatedPhysicalBoard()
        )
        self._parser = CommandParser()
        self._resolver = MoveResolver()
        self._game = ChessGame()

    @property
    def game(self) -> ChessGame:
        """Expose the authoritative game for compatibility and composition."""
        return self._game

    def snapshot(self) -> PositionSnapshot:
        """Return all current read-only data needed by presentation adapters."""
        board = self._game.board
        pieces = tuple(
            sorted(
                (chess.square_name(square), piece.symbol())
                for square, piece in board.piece_map().items()
            )
        )
        return PositionSnapshot(
            pieces=pieces,
            legal_moves=self._game.legal_moves(),
            move_history=self._game.move_history(),
            last_move=self._game.last_move(),
            turn=self._game.turn,
            result=self._game.result(),
            fen=self._game.fen(),
            pgn=self._game.to_pgn(),
            can_undo=self._game.can_undo,
            can_redo=self._game.can_redo,
        )

    def play_text(self, text: str) -> SessionResult:
        """Interpret text and execute it through the authoritative application path."""
        intent = self._parser.parse(text)
        if isinstance(intent, (MoveIntent, SanMoveIntent)):
            move = self._resolver.resolve(intent, self._game)
            event = self.play_move(move)
            return SessionResult(message=f"Played: {event.san}", move_event=event)
        return self._execute_command(intent)

    def play_move(self, move: ChessMove) -> MoveExecuted:
        """Execute one direct/click move and emit the normal physical-board event."""
        event = self._game.make_move(move)
        self._physical_board.execute_move(event)
        return event

    def undo(self) -> ChessMove:
        """Undo through the authoritative domain history."""
        return self._game.undo()

    def redo(self) -> MoveExecuted:
        """Redo and emit the same event as any accepted move."""
        event = self._game.redo()
        self._physical_board.execute_move(event)
        return event

    def new_game(self) -> None:
        """Replace the authoritative game with a fresh starting position."""
        self._game = ChessGame()

    def load_fen(self, fen: str) -> None:
        """Load a validated position and clear its unavailable history."""
        self._game.load_fen(fen)

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
            return SessionResult(message="Started a new game.")
        if command is CommandName.UNDO:
            move = self.undo()
            return SessionResult(message=f"Undid: {move.uci()}")
        event = self.redo()
        return SessionResult(message=f"Redid: {event.san}", move_event=event)
