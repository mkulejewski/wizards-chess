"""Documented Wizard Chess move-classification policy."""

from dataclasses import dataclass

from wizard_chess.analysis.models import MoveClassification


@dataclass(frozen=True, slots=True)
class ClassificationPolicy:
    """Classify by mover-relative loss in centipawns.

    Thresholds are project heuristics, not replicas of proprietary chess services:
    best move match or <=15 cp; excellent <=35; good <=75; inaccuracy <=150;
    mistake <=300; otherwise blunder.
    """

    best_max_cp: int = 15
    excellent_max_cp: int = 35
    good_max_cp: int = 75
    inaccuracy_max_cp: int = 150
    mistake_max_cp: int = 300

    def classify(self, centipawn_loss: int, *, best_move_match: bool = False) -> MoveClassification:
        loss = max(0, centipawn_loss)
        if best_move_match or loss <= self.best_max_cp:
            return MoveClassification.BEST
        if loss <= self.excellent_max_cp:
            return MoveClassification.EXCELLENT
        if loss <= self.good_max_cp:
            return MoveClassification.GOOD
        if loss <= self.inaccuracy_max_cp:
            return MoveClassification.INACCURACY
        if loss <= self.mistake_max_cp:
            return MoveClassification.MISTAKE
        return MoveClassification.BLUNDER
