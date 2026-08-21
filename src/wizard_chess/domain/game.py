"""Authoritative ownership of a chess game."""

from __future__ import annotations

import chess
import chess.pgn

from wizard_chess.domain.events import MoveExecuted
from wizard_chess.domain.exceptions import (
    InvalidFenError,
    InvalidMoveError,
    NoMoveToRedoError,
    NoMoveToUndoError,
)
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameResult, GameStatus, PlayerColor


class ChessGame:
    """The authoritative digital twin of a chessboard position and its history."""

    def __init__(self, fen: str | None = None) -> None:
        self._board = chess.Board()
        self._redo_stack: list[chess.Move] = []
        if fen is not None:
            self.load_fen(fen)

    @property
    def board(self) -> chess.Board:
        """Return a defensive copy for read-only integration with python-chess."""
        return self._board.copy(stack=True)

    @property
    def turn(self) -> PlayerColor:
        """Return the side whose turn it is."""
        return PlayerColor.WHITE if self._board.turn == chess.WHITE else PlayerColor.BLACK

    def legal_moves(self) -> tuple[ChessMove, ...]:
        """Return all legal moves in the current position."""
        return tuple(ChessMove.from_python_chess(move) for move in self._board.legal_moves)

    @property
    def can_undo(self) -> bool:
        """Whether the current main line contains a move to undo."""
        return bool(self._board.move_stack)

    @property
    def can_redo(self) -> bool:
        """Whether an undone move remains available to redo."""
        return bool(self._redo_stack)

    def last_move(self) -> ChessMove | None:
        """Return the latest authoritative move, if its history is known."""
        if not self._board.move_stack:
            return None
        return ChessMove.from_python_chess(self._board.peek())

    def move_history(self) -> tuple[str, ...]:
        """Render the authoritative main-line move history as SAN."""
        replay = self._board.root()
        history: list[str] = []
        for move in self._board.move_stack:
            history.append(replay.san(move))
            replay.push(move)
        return tuple(history)

    def make_move(self, move: ChessMove) -> MoveExecuted:
        """Validate and execute a move, returning facts for output adapters."""
        self.validate_move(move)
        python_move = move.to_python_chess()

        event = self._event_for(python_move)
        self._board.push(python_move)
        self._redo_stack.clear()
        return event

    def validate_move(self, move: ChessMove) -> None:
        """Raise a descriptive application error unless a move is currently legal."""
        if self._board.is_game_over(claim_draw=False):
            raise InvalidMoveError("The game is already over")
        python_move = move.to_python_chess()
        if python_move in self._board.legal_moves:
            return

        raise InvalidMoveError(self._illegal_move_message(move, python_move))

    def undo(self) -> ChessMove:
        """Restore the position before the latest move."""
        if not self._board.move_stack:
            raise NoMoveToUndoError("There is no move to undo")
        move = self._board.pop()
        self._redo_stack.append(move)
        return ChessMove.from_python_chess(move)

    def redo(self) -> MoveExecuted:
        """Reapply the most recently undone move."""
        if not self._redo_stack:
            raise NoMoveToRedoError("There is no move to redo")
        move = self._redo_stack.pop()
        if move not in self._board.legal_moves:
            self._redo_stack.append(move)
            raise InvalidMoveError(f"Undone move is no longer legal: {move.uci()}")
        event = self._event_for(move)
        self._board.push(move)
        return event

    def fen(self) -> str:
        """Return the complete current position in FEN form."""
        return self._board.fen()

    def load_fen(self, fen: str) -> None:
        """Replace the game with a validated FEN position and clear history."""
        try:
            board = chess.Board(fen)
        except (TypeError, ValueError) as error:
            raise InvalidFenError(f"Invalid FEN: {fen}") from error
        if not board.is_valid():
            raise InvalidFenError(f"FEN describes an invalid position: {fen}")
        self._board = board
        self._redo_stack.clear()

    def is_check(self) -> bool:
        return self._board.is_check()

    def is_checkmate(self) -> bool:
        return self._board.is_checkmate()

    def is_stalemate(self) -> bool:
        return self._board.is_stalemate()

    def is_game_over(self) -> bool:
        return self._board.is_game_over(claim_draw=False)

    def result(self) -> GameResult:
        """Return terminal status plus currently claimable draw conditions."""
        outcome = self._board.outcome(claim_draw=False)
        winner: PlayerColor | None = None
        if outcome is not None and outcome.winner is not None:
            winner = PlayerColor.WHITE if outcome.winner == chess.WHITE else PlayerColor.BLACK

        if self._board.is_checkmate():
            status = GameStatus.CHECKMATE
        elif self._board.is_stalemate():
            status = GameStatus.STALEMATE
        elif self._board.is_insufficient_material():
            status = GameStatus.INSUFFICIENT_MATERIAL
        elif self._board.is_seventyfive_moves():
            status = GameStatus.SEVENTY_FIVE_MOVE_DRAW
        elif self._board.is_fivefold_repetition():
            status = GameStatus.FIVEFOLD_REPETITION
        elif outcome is not None:
            status = GameStatus.OTHER_GAME_OVER
        elif self._board.is_check():
            status = GameStatus.CHECK
        else:
            status = GameStatus.ONGOING

        return GameResult(
            status=status,
            notation=self._board.result(claim_draw=False),
            winner=winner,
            can_claim_fifty_moves=self._board.can_claim_fifty_moves(),
            can_claim_threefold_repetition=self._board.can_claim_threefold_repetition(),
        )

    def to_pgn(self) -> str:
        """Render the current main line as portable game notation."""
        game = chess.pgn.Game.from_board(self._board)
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return game.accept(exporter)

    def _event_for(self, move: chess.Move) -> MoveExecuted:
        is_en_passant = self._board.is_en_passant(move)
        captured_square: str | None = None
        if self._board.is_capture(move):
            capture_index = move.to_square
            if is_en_passant:
                capture_index += -8 if self._board.turn == chess.WHITE else 8
            captured_square = chess.square_name(capture_index)

        return MoveExecuted(
            source_square=chess.square_name(move.from_square),
            target_square=chess.square_name(move.to_square),
            captured_square=captured_square,
            promotion=chess.piece_symbol(move.promotion) if move.promotion is not None else None,
            is_castling=self._board.is_castling(move),
            is_en_passant=is_en_passant,
            san=self._board.san(move),
            uci=move.uci(),
        )

    def _illegal_move_message(self, move: ChessMove, python_move: chess.Move) -> str:
        prefix = f"Illegal move {move.uci()}:"
        piece = self._board.piece_at(python_move.from_square)
        if piece is None:
            return f"{prefix} there is no piece on {move.source}"

        moving_side = "White" if piece.color == chess.WHITE else "Black"
        if piece.color != self._board.turn:
            return (
                f"{prefix} {move.source} contains a {moving_side.lower()} "
                f"{chess.piece_name(piece.piece_type)}; it is {self.turn.value.title()} to move"
            )

        target_piece = self._board.piece_at(python_move.to_square)
        if target_piece is not None and target_piece.color == piece.color:
            return (
                f"{prefix} {move.target} is occupied by {moving_side}'s own "
                f"{chess.piece_name(target_piece.piece_type)}"
            )

        promotion_moves = [
            legal_move
            for legal_move in self._board.legal_moves
            if legal_move.from_square == python_move.from_square
            and legal_move.to_square == python_move.to_square
            and legal_move.promotion is not None
        ]
        if move.promotion is None and promotion_moves:
            return f"{prefix} choose a promotion piece (queen, rook, bishop, or knight)"

        if python_move in self._board.pseudo_legal_moves:
            if self._board.is_check():
                return f"{prefix} the move does not resolve the current check"
            return f"{prefix} the move would leave {moving_side}'s king in check"

        piece_name = chess.piece_name(piece.piece_type)
        return f"{prefix} the {piece_name} cannot move from {move.source} to {move.target}"
