"""Versioned JSON persistence for optional engine annotations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from wizard_chess.analysis.models import (
    GameAnalysis,
    MoveAnalysis,
    MoveClassification,
    SideStatistics,
)
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import PlayerColor
from wizard_chess.engine.models import EngineEvaluation


class AnalysisStore:
    """Keep analysis separate from ordinary compatible PGN files."""

    def save(self, analysis: GameAnalysis, destination: str | Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": analysis.schema_version,
            "engine_name": analysis.engine_name,
            "source_pgn": analysis.source_pgn,
            "moves": [_move_to_dict(move) for move in analysis.moves],
            "white": _statistics_to_dict(analysis.white),
            "black": _statistics_to_dict(analysis.black),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def load(self, source: str | Path) -> GameAnalysis:
        payload = cast(dict[str, object], json.loads(Path(source).read_text(encoding="utf-8")))
        version = int(cast(int, payload.get("schema_version", 0)))
        if version != 1:
            raise ValueError(f"Unsupported analysis schema version: {version}")
        raw_moves = cast(list[dict[str, object]], payload.get("moves", []))
        return GameAnalysis(
            source_pgn=str(payload.get("source_pgn", "")),
            moves=tuple(_move_from_dict(item) for item in raw_moves),
            white=_statistics_from_dict(cast(dict[str, object], payload["white"])),
            black=_statistics_from_dict(cast(dict[str, object], payload["black"])),
            engine_name=str(payload.get("engine_name", "uci")),
            schema_version=version,
        )


def _evaluation_to_dict(evaluation: EngineEvaluation | None) -> object:
    if evaluation is None:
        return None
    return {"score_cp": evaluation.score_cp, "mate_in": evaluation.mate_in}


def _evaluation_from_dict(raw: object) -> EngineEvaluation | None:
    if raw is None:
        return None
    values = cast(dict[str, int | None], raw)
    score = values.get("score_cp")
    mate = values.get("mate_in")
    return EngineEvaluation(score_cp=score) if score is not None else EngineEvaluation(mate_in=mate)


def _move_to_dict(move: MoveAnalysis) -> dict[str, object]:
    return {
        "ply": move.ply,
        "color": move.color.value,
        "san": move.san,
        "played_move": move.played_move.uci(),
        "preferred_move": move.preferred_move.uci() if move.preferred_move else None,
        "evaluation_before": _evaluation_to_dict(move.evaluation_before),
        "evaluation_after": _evaluation_to_dict(move.evaluation_after),
        "principal_variation": [item.uci() for item in move.principal_variation],
        "centipawn_loss": move.centipawn_loss,
        "classification": move.classification.value,
    }


def _move_from_dict(raw: dict[str, object]) -> MoveAnalysis:
    preferred = raw.get("preferred_move")
    pv = cast(list[str], raw.get("principal_variation", []))
    return MoveAnalysis(
        ply=int(cast(int, raw["ply"])),
        color=PlayerColor(str(raw["color"])),
        san=str(raw["san"]),
        played_move=ChessMove.from_uci(str(raw["played_move"])),
        preferred_move=ChessMove.from_uci(str(preferred)) if preferred else None,
        evaluation_before=_evaluation_from_dict(raw.get("evaluation_before")),
        evaluation_after=_evaluation_from_dict(raw.get("evaluation_after")),
        principal_variation=tuple(ChessMove.from_uci(item) for item in pv),
        centipawn_loss=int(cast(int, raw["centipawn_loss"])),
        classification=MoveClassification(str(raw["classification"])),
    )


def _statistics_to_dict(statistics: SideStatistics) -> dict[str, int | float]:
    return {
        "moves": statistics.moves,
        "average_centipawn_loss": statistics.average_centipawn_loss,
        "best_move_matches": statistics.best_move_matches,
        "inaccuracies": statistics.inaccuracies,
        "mistakes": statistics.mistakes,
        "blunders": statistics.blunders,
    }


def _statistics_from_dict(raw: dict[str, object]) -> SideStatistics:
    return SideStatistics(
        moves=int(cast(int, raw["moves"])),
        average_centipawn_loss=float(cast(float, raw["average_centipawn_loss"])),
        best_move_matches=int(cast(int, raw["best_move_matches"])),
        inaccuracies=int(cast(int, raw["inaccuracies"])),
        mistakes=int(cast(int, raw["mistakes"])),
        blunders=int(cast(int, raw["blunders"])),
    )
