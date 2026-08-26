"""Authoritative ownership of a chess game."""

from __future__ import annotations

import re
from collections.abc import Mapping
from io import StringIO
from types import MappingProxyType

import chess
import chess.pgn

from wizard_chess.domain.events import MoveAnnotation, MoveExecuted
from wizard_chess.domain.exceptions import (
    GameTerminationError,
    InvalidFenError,
    InvalidMoveError,
    InvalidPgnError,
    NoMoveToRedoError,
    NoMoveToUndoError,
)
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameResult, GameStatus, PlayerColor


class ChessGame:
    """The authoritative digital twin of a chessboard position and its history."""

    def __init__(
        self,
        fen: str | None = None,
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        self._board = chess.Board()
        self._redo_stack: list[chess.Move] = []
        self._metadata = self._clean_metadata(metadata or {})
        self._move_annotations: dict[int, MoveAnnotation] = {}
        self._move_comments: dict[int, str] = {}
        self._manual_status: GameStatus | None = None
        self._manual_winner: PlayerColor | None = None
        self._pending_draw_offer: PlayerColor | None = None
        self._blocked_draw_offer_position: str | None = None
        self._redo_termination: tuple[int, GameStatus, PlayerColor | None] | None = None
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

    @property
    def metadata(self) -> Mapping[str, str]:
        """Return immutable portable game metadata."""
        return MappingProxyType(dict(self._metadata))

    @property
    def pending_draw_offer(self) -> PlayerColor | None:
        """Return the player who made the unresolved draw offer, if any."""
        return self._pending_draw_offer

    @property
    def can_propose_draw(self) -> bool:
        """Whether an unchanged rejected position is not blocking a new offer."""
        return (
            not self.is_game_over()
            and self._pending_draw_offer is None
            and self._draw_offer_position_key() != self._blocked_draw_offer_position
        )

    def update_metadata(self, **values: str) -> None:
        """Update recognized PGN headers without inventing unknown values."""
        self._metadata.update(self._clean_metadata(values))

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
        current_ply = len(self._board.move_stack)
        self._move_annotations = {
            ply: value for ply, value in self._move_annotations.items() if ply <= current_ply
        }
        self._move_comments = {
            ply: value for ply, value in self._move_comments.items() if ply <= current_ply
        }
        self._board.push(python_move)
        self._pending_draw_offer = None
        self._blocked_draw_offer_position = None
        self._redo_stack.clear()
        self._redo_termination = None
        return event

    def validate_move(self, move: ChessMove) -> None:
        """Raise a descriptive application error unless a move is currently legal."""
        if self._manual_status is not None or self._board.is_game_over(claim_draw=False):
            raise InvalidMoveError("The game is already over")
        python_move = move.to_python_chess()
        if python_move in self._board.legal_moves:
            return

        raise InvalidMoveError(self._illegal_move_message(move, python_move))

    def undo(self) -> ChessMove:
        """Restore the position before the latest move."""
        if not self._board.move_stack:
            raise NoMoveToUndoError("There is no move to undo")
        current_ply = len(self._board.move_stack)
        if self._manual_status is not None:
            self._redo_termination = (
                current_ply,
                self._manual_status,
                self._manual_winner,
            )
        move = self._board.pop()
        self._redo_stack.append(move)
        self._clear_manual_termination()
        self._blocked_draw_offer_position = None
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
        self._pending_draw_offer = None
        self._blocked_draw_offer_position = None
        if self._redo_termination is not None and self._redo_termination[0] == len(
            self._board.move_stack
        ):
            _ply, self._manual_status, self._manual_winner = self._redo_termination
            self._redo_termination = None
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
        self._move_annotations.clear()
        self._move_comments.clear()
        self._blocked_draw_offer_position = None
        self._redo_termination = None
        self._clear_manual_termination()

    def is_check(self) -> bool:
        return self._board.is_check()

    def is_checkmate(self) -> bool:
        return self._board.is_checkmate()

    def is_stalemate(self) -> bool:
        return self._board.is_stalemate()

    def is_game_over(self) -> bool:
        return self._manual_status is not None or self._board.is_game_over(claim_draw=False)

    def result(self) -> GameResult:
        """Return terminal status plus currently claimable draw conditions."""
        if self._manual_status is not None:
            notation = "1/2-1/2"
            if self._manual_winner is PlayerColor.WHITE:
                notation = "1-0"
            elif self._manual_winner is PlayerColor.BLACK:
                notation = "0-1"
            return GameResult(
                status=self._manual_status,
                notation=notation,
                winner=self._manual_winner,
                can_claim_fifty_moves=False,
                can_claim_threefold_repetition=False,
            )

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
        for name, value in self._metadata.items():
            game.headers[name] = value
        result = self.result()
        game.headers["Result"] = result.notation
        termination = self._termination_reason(result.status)
        if termination is not None:
            game.headers["Termination"] = termination
        for ply, node in enumerate(game.mainline(), start=1):
            comment = self._move_comments.get(ply, "").strip()
            annotation = self._move_annotations.get(ply)
            diagnostic_comment = _format_move_annotation(annotation) if annotation else ""
            node.comment = " ".join(part for part in (comment, diagnostic_comment) if part)
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
        return game.accept(exporter)

    def load_pgn(self, pgn: str) -> None:
        """Replace state with a validated PGN main line and preserve known metadata."""
        try:
            parsed = chess.pgn.read_game(StringIO(pgn))
        except (ValueError, UnicodeError) as error:
            raise InvalidPgnError("Invalid PGN") from error
        if parsed is None:
            raise InvalidPgnError("PGN does not contain a game")
        if parsed.errors:
            raise InvalidPgnError(f"Invalid PGN: {parsed.errors[0]}")

        board = parsed.board()
        try:
            for move in parsed.mainline_moves():
                if move not in board.legal_moves:
                    raise InvalidPgnError(f"PGN contains illegal move: {move.uci()}")
                board.push(move)
        except (AssertionError, ValueError) as error:
            raise InvalidPgnError("PGN contains an invalid main line") from error

        self._board = board
        self._redo_stack.clear()
        self._metadata = self._clean_metadata(parsed.headers)
        self._move_annotations.clear()
        self._move_comments.clear()
        self._blocked_draw_offer_position = None
        for ply, node in enumerate(parsed.mainline(), start=1):
            annotation, remaining_comment = _parse_move_annotation(node.comment)
            if annotation is not None:
                self._move_annotations[ply] = annotation
            if remaining_comment:
                self._move_comments[ply] = remaining_comment
        self._redo_termination = None
        self._clear_manual_termination()
        result = parsed.headers.get("Result", "*")
        termination = parsed.headers.get("Termination", "").strip().lower()
        if not self._board.is_game_over(claim_draw=False):
            if result == "1/2-1/2":
                if "fifty" in termination or "50-move" in termination:
                    self._manual_status = GameStatus.FIFTY_MOVE_RULE_CLAIM
                elif "threefold" in termination:
                    self._manual_status = GameStatus.THREEFOLD_REPETITION_CLAIM
                elif "time" in termination:
                    self._manual_status = GameStatus.TIME_FORFEIT
                else:
                    self._manual_status = GameStatus.AGREED_DRAW
            elif result in {"1-0", "0-1"}:
                self._manual_status = (
                    GameStatus.TIME_FORFEIT if "time" in termination else GameStatus.RESIGNED
                )
                self._manual_winner = PlayerColor.WHITE if result == "1-0" else PlayerColor.BLACK

    def annotate_last_move(self, annotation: MoveAnnotation) -> None:
        """Attach portable timing and engine facts to the latest move."""
        if not self._board.move_stack:
            raise InvalidMoveError("There is no move to annotate")
        self._move_annotations[len(self._board.move_stack)] = annotation

    def claim_draw(self) -> GameResult:
        """Validate and record an available fifty-move or threefold draw claim."""
        if self.is_game_over():
            raise GameTerminationError("The game is already over")
        if self._board.can_claim_fifty_moves():
            self._manual_status = GameStatus.FIFTY_MOVE_RULE_CLAIM
        elif self._board.can_claim_threefold_repetition():
            self._manual_status = GameStatus.THREEFOLD_REPETITION_CLAIM
        else:
            raise GameTerminationError("No draw can be claimed in the current position")
        self._manual_winner = None
        self._pending_draw_offer = None
        self._redo_stack.clear()
        self._redo_termination = None
        return self.result()

    def forfeit_on_time(self, color: PlayerColor) -> GameResult:
        """End an ongoing game when ``color`` exhausts its game clock."""
        if self.is_game_over():
            raise GameTerminationError("The game is already over")
        self._manual_status = GameStatus.TIME_FORFEIT
        opponent = PlayerColor.BLACK if color is PlayerColor.WHITE else PlayerColor.WHITE
        opponent_chess_color = chess.BLACK if opponent is PlayerColor.BLACK else chess.WHITE
        self._manual_winner = (
            None if self._board.has_insufficient_material(opponent_chess_color) else opponent
        )
        self._pending_draw_offer = None
        self._redo_stack.clear()
        self._redo_termination = None
        return self.result()

    def resign(self, color: PlayerColor | None = None) -> GameResult:
        """End an ongoing game by resignation of ``color`` or the side to move."""
        if self.is_game_over():
            raise GameTerminationError("The game is already over")
        resigned = color or self.turn
        self._manual_status = GameStatus.RESIGNED
        self._manual_winner = (
            PlayerColor.BLACK if resigned is PlayerColor.WHITE else PlayerColor.WHITE
        )
        self._pending_draw_offer = None
        self._redo_stack.clear()
        self._redo_termination = None
        return self.result()

    def agree_draw(self) -> GameResult:
        """End an ongoing game by mutual draw agreement."""
        if self.is_game_over():
            raise GameTerminationError("The game is already over")
        self._manual_status = GameStatus.AGREED_DRAW
        self._manual_winner = None
        self._pending_draw_offer = None
        self._redo_stack.clear()
        self._redo_termination = None
        return self.result()

    def propose_draw(self, color: PlayerColor | None = None) -> PlayerColor:
        """Record one player's non-terminal draw offer."""
        if self.is_game_over():
            raise GameTerminationError("The game is already over")
        if self._pending_draw_offer is not None:
            raise GameTerminationError("A draw offer is already pending")
        position_key = self._draw_offer_position_key()
        if position_key == self._blocked_draw_offer_position:
            raise GameTerminationError("A draw was already offered in this position")
        self._pending_draw_offer = color or self.turn
        return self._pending_draw_offer

    def accept_draw(self) -> GameResult:
        """Accept the pending offer and end the game by agreement."""
        if self._pending_draw_offer is None:
            raise GameTerminationError("There is no draw offer to accept")
        return self.agree_draw()

    def reject_draw(self) -> PlayerColor:
        """Reject and clear the pending draw offer without ending the game."""
        if self._pending_draw_offer is None:
            raise GameTerminationError("There is no draw offer to reject")
        proposer = self._pending_draw_offer
        self._pending_draw_offer = None
        self._blocked_draw_offer_position = self._draw_offer_position_key()
        return proposer

    def _clear_manual_termination(self) -> None:
        self._manual_status = None
        self._manual_winner = None
        self._pending_draw_offer = None

    def _draw_offer_position_key(self) -> str:
        """Identify a chess position independently of move counters."""
        return " ".join(self._board.fen(en_passant="fen").split()[:4])

    @classmethod
    def _clean_metadata(cls, values: Mapping[str, str]) -> dict[str, str]:
        placeholders = {
            "Event": "?",
            "Site": "?",
            "Date": "????.??.??",
            "Round": "?",
            "White": "?",
            "Black": "?",
        }
        return {
            str(name): str(value).strip()
            for name, value in values.items()
            if str(value).strip()
            and str(name) != "Result"
            and str(value).strip() != placeholders.get(str(name))
        }

    @staticmethod
    def _termination_reason(status: GameStatus) -> str | None:
        reasons = {
            GameStatus.CHECKMATE: "checkmate",
            GameStatus.STALEMATE: "stalemate",
            GameStatus.INSUFFICIENT_MATERIAL: "insufficient material",
            GameStatus.SEVENTY_FIVE_MOVE_DRAW: "seventy-five-move rule",
            GameStatus.FIVEFOLD_REPETITION: "fivefold repetition",
            GameStatus.FIFTY_MOVE_RULE_CLAIM: "fifty-move rule claim",
            GameStatus.THREEFOLD_REPETITION_CLAIM: "threefold repetition claim",
            GameStatus.TIME_FORFEIT: "time forfeit",
            GameStatus.RESIGNED: "resignation",
            GameStatus.AGREED_DRAW: "draw agreement",
            GameStatus.OTHER_GAME_OVER: "normal",
        }
        return reasons.get(status)

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


_ANNOTATION_PATTERN = re.compile(
    r"\[%(?P<name>emt|clk|eval|depth|nodes|tbhits)\s+(?P<value>[^\]]+)\]",
    re.IGNORECASE,
)


def _format_move_annotation(annotation: MoveAnnotation) -> str:
    tags: list[str] = []
    if annotation.elapsed_seconds is not None:
        tags.append(f"[%emt {_format_pgn_time(annotation.elapsed_seconds)}]")
    if annotation.remaining_seconds is not None:
        tags.append(f"[%clk {_format_pgn_time(annotation.remaining_seconds)}]")
    if annotation.mate_in is not None:
        tags.append(f"[%eval #{annotation.mate_in}]")
    elif annotation.evaluation_cp is not None:
        tags.append(f"[%eval {annotation.evaluation_cp / 100:.2f}]")
    if annotation.depth is not None:
        tags.append(f"[%depth {annotation.depth}]")
    if annotation.nodes is not None:
        tags.append(f"[%nodes {annotation.nodes}]")
    if annotation.tablebase_hits is not None:
        tags.append(f"[%tbhits {annotation.tablebase_hits}]")
    return " ".join(tags)


def _parse_move_annotation(comment: str) -> tuple[MoveAnnotation | None, str]:
    values: dict[str, str] = {}
    for match in _ANNOTATION_PATTERN.finditer(comment):
        values[match.group("name").lower()] = match.group("value").strip()
    remaining = " ".join(_ANNOTATION_PATTERN.sub("", comment).split())
    if not values:
        return None, remaining
    evaluation_cp: int | None = None
    mate_in: int | None = None
    evaluation = values.get("eval")
    if evaluation is not None:
        try:
            if evaluation.startswith("#"):
                mate_in = int(evaluation[1:])
            else:
                evaluation_cp = round(float(evaluation.split(",", 1)[0]) * 100)
        except ValueError:
            evaluation_cp = None
            mate_in = None
    evaluation_parts = evaluation.split(",", 1) if evaluation is not None else []
    combined_depth = (
        _parse_optional_int(evaluation_parts[1]) if len(evaluation_parts) == 2 else None
    )
    annotation = MoveAnnotation(
        elapsed_seconds=_parse_pgn_time(values.get("emt")),
        remaining_seconds=_parse_pgn_time(values.get("clk")),
        evaluation_cp=evaluation_cp,
        mate_in=mate_in,
        depth=_parse_optional_int(values.get("depth")) or combined_depth,
        nodes=_parse_optional_int(values.get("nodes")),
        tablebase_hits=_parse_optional_int(values.get("tbhits")),
    )
    return annotation, remaining


def _format_pgn_time(seconds: float) -> str:
    total = max(0.0, seconds)
    hours, remainder = divmod(total, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    rendered_seconds = f"{remaining_seconds:06.3f}".rstrip("0").rstrip(".")
    if remaining_seconds < 10 and not rendered_seconds.startswith("0"):
        rendered_seconds = f"0{rendered_seconds}"
    return f"{int(hours)}:{int(minutes):02d}:{rendered_seconds}"


def _parse_pgn_time(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parts = [float(part) for part in value.split(":")]
    except ValueError:
        return None
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:
        return parts[0]
    return None


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
