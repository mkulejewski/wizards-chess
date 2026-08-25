"""Engine-neutral values consumed by application, analysis, and presentation layers."""

from dataclasses import dataclass

from wizard_chess.domain.move import ChessMove


@dataclass(frozen=True, slots=True)
class EngineEvaluation:
    """A score normalized from White's perspective throughout the application."""

    score_cp: int | None = None
    mate_in: int | None = None
    perspective: str = "white"

    def __post_init__(self) -> None:
        if (self.score_cp is None) == (self.mate_in is None):
            raise ValueError("An evaluation must contain exactly one of score_cp or mate_in")
        if self.perspective != "white":
            raise ValueError("Engine scores must be normalized from White's perspective")

    def equivalent_cp(self, mate_value: int = 100_000) -> int:
        """Return a sortable score, mapping mate to a stable large value."""
        if self.score_cp is not None:
            return self.score_cp
        assert self.mate_in is not None
        return mate_value if self.mate_in >= 0 else -mate_value

    def display(self) -> str:
        """Return compact user-facing score text."""
        if self.mate_in is not None:
            return f"M{self.mate_in:+d}"
        assert self.score_cp is not None
        return f"{self.score_cp / 100:+.2f}"


@dataclass(frozen=True, slots=True)
class EngineLine:
    """One normalized candidate line from an engine request."""

    move: ChessMove
    evaluation: EngineEvaluation
    principal_variation: tuple[ChessMove, ...] = ()
    depth: int | None = None
    selective_depth: int | None = None
    nodes: int | None = None
    nps: int | None = None
    tablebase_hits: int | None = None
    search_time_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class EngineClockState:
    """Clock values passed to UCI without coupling the engine to the application clock."""

    white_seconds: float
    black_seconds: float
    white_increment_seconds: float
    black_increment_seconds: float


@dataclass(frozen=True, slots=True)
class EngineDecision:
    """A selected move plus the search information returned with it."""

    move: ChessMove
    evaluation: EngineEvaluation | None = None
    depth: int | None = None
    selective_depth: int | None = None
    nodes: int | None = None
    nps: int | None = None
    tablebase_hits: int | None = None
    search_time_seconds: float | None = None
    engine_name: str | None = None


@dataclass(frozen=True, slots=True)
class PositionAnalysis:
    """Normalized analysis for one immutable FEN position."""

    fen: str
    lines: tuple[EngineLine, ...] = ()
    terminal: bool = False

    @property
    def best_line(self) -> EngineLine | None:
        return self.lines[0] if self.lines else None


def evaluation_share(evaluation: EngineEvaluation | None) -> float:
    """Map evaluation to a stable 0..1 White share for UI bars and future LEDs."""
    if evaluation is None:
        return 0.5
    if evaluation.mate_in is not None:
        return 1.0 if evaluation.mate_in >= 0 else 0.0
    assert evaluation.score_cp is not None
    capped = max(-1_000, min(1_000, evaluation.score_cp))
    return 0.5 + capped / 2_000
