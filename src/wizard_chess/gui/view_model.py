"""Pure formatting helpers for GUI presentation."""

from wizard_chess.application.session import PositionSnapshot
from wizard_chess.domain.results import GameStatus


def format_move_history(moves: tuple[str, ...]) -> str:
    """Format SAN history as conventional numbered move pairs."""
    rows: list[str] = []
    for index in range(0, len(moves), 2):
        move_number = index // 2 + 1
        black_move = f"  {moves[index + 1]}" if index + 1 < len(moves) else ""
        rows.append(f"{move_number}. {moves[index]}{black_move}")
    return "\n".join(rows)


def format_game_status(snapshot: PositionSnapshot) -> str:
    """Present the authoritative result without calculating chess state."""
    result = snapshot.result
    if result.status is GameStatus.CHECKMATE:
        winner = result.winner.value.title() if result.winner is not None else "Unknown"
        return f"Checkmate — {winner} wins"
    if result.status is GameStatus.STALEMATE:
        return "Stalemate — Draw"
    if result.status is GameStatus.CHECK:
        return f"{snapshot.turn.value.title()} to move — Check"
    if result.is_over:
        label = result.status.value.replace("_", " ").title()
        if result.winner is not None:
            return f"{label} — {result.winner.value.title()} wins"
        return f"{label} — Draw"
    if snapshot.pending_draw_offer is not None:
        proposer = snapshot.pending_draw_offer.value.title()
        return f"{snapshot.turn.value.title()} to move — Draw offered by {proposer}"
    return f"{snapshot.turn.value.title()} to move"
