from math import isclose

import chess
import chess.engine
import pytest

from wizard_chess.analysis.live import (
    GameAnalysisCache,
    LiveAnalysisController,
    LiveAnalysisResult,
    position_key,
)
from wizard_chess.application.session import GameSession
from wizard_chess.configuration import ApplicationSettings, EngineAnalysisMode, EngineSettings
from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.mock import FakeEngine
from wizard_chess.engine.models import (
    EngineEvaluation,
    EngineLine,
    PositionAnalysis,
    evaluation_share,
)
from wizard_chess.engine.stockfish import normalize_score
from wizard_chess.gui.evaluation_widgets import MATE_PLOT_VALUE, evaluation_plot_value


def _position_analysis(fen: str, depth: int, score_cp: int) -> PositionAnalysis:
    board = chess.Board(fen)
    move = ChessMove.from_python_chess(next(iter(board.legal_moves)))
    return PositionAnalysis(
        fen=fen,
        lines=(
            EngineLine(
                move=move,
                evaluation=EngineEvaluation(score_cp=score_cp),
                principal_variation=(move,),
                depth=depth,
            ),
        ),
    )


def _live_result(fen: str, ply: int, depth: int, score_cp: int) -> LiveAnalysisResult:
    return LiveAnalysisResult(
        position_id=position_key(fen),
        ply=ply,
        fen=fen,
        depth=depth,
        evaluation=EngineEvaluation(score_cp=score_cp),
        sequence=depth,
    )


def test_normalization_and_display_preserve_white_centric_cp_and_mate() -> None:
    white_cp = chess.engine.PovScore(chess.engine.Cp(50), chess.WHITE)
    black_cp = chess.engine.PovScore(chess.engine.Cp(50), chess.BLACK)
    black_mate = chess.engine.PovScore(chess.engine.Mate(2), chess.BLACK)

    assert normalize_score(white_cp) == EngineEvaluation(score_cp=50)
    assert normalize_score(black_cp) == EngineEvaluation(score_cp=-50)
    assert normalize_score(black_mate) == EngineEvaluation(mate_in=-2)
    assert EngineEvaluation(mate_in=3).display() == "M3"
    assert EngineEvaluation(mate_in=-2).display() == "-M2"


@pytest.mark.parametrize("score_cp", [50, 300, 10_000])
def test_evaluation_bar_mapping_is_symmetric_and_bounded(score_cp: int) -> None:
    positive = evaluation_share(EngineEvaluation(score_cp=score_cp))
    negative = evaluation_share(EngineEvaluation(score_cp=-score_cp))

    assert 0.5 < positive < 1.0
    assert 0.0 < negative < 0.5
    assert isclose(positive, 1.0 - negative)
    assert evaluation_share(EngineEvaluation(score_cp=0)) == 0.5
    assert evaluation_share(EngineEvaluation(mate_in=1)) == 1.0
    assert evaluation_share(EngineEvaluation(mate_in=-1)) == 0.0


def test_plot_mapping_is_display_only_and_bounds_mate() -> None:
    mate = EngineEvaluation(mate_in=4)

    assert evaluation_plot_value(mate) == MATE_PLOT_VALUE
    assert evaluation_plot_value(EngineEvaluation(mate_in=-4)) == -MATE_PLOT_VALUE
    assert mate.mate_in == 4


def test_position_key_preserves_legality_fields_and_ignores_fullmove_number() -> None:
    fen = chess.Board().fen()
    fields = fen.split()
    later_fullmove = " ".join([*fields[:5], "99"])
    changed_castling = " ".join([fields[0], fields[1], "-", fields[3], fields[4], fields[5]])
    changed_halfmove = " ".join([*fields[:4], "50", fields[5]])

    assert position_key(fen) == position_key(later_fullmove)
    assert position_key(fen) != position_key(changed_castling)
    assert position_key(fen) != position_key(changed_halfmove)


def test_game_cache_keeps_only_deepest_results_for_distinct_positions() -> None:
    first = chess.Board()
    first_fen = first.fen()
    first.push_uci("e2e4")
    second_fen = first.fen()
    cache = GameAnalysisCache()

    assert cache.store(_live_result(first_fen, 0, 5, 10))
    assert cache.store(_live_result(first_fen, 0, 12, 24))
    assert not cache.store(_live_result(first_fen, 0, 8, 99))
    assert cache.store(_live_result(second_fen, 1, 7, 15))

    best_first = cache.get_best(first_fen)
    best_second = cache.get_best(second_fen)
    assert best_first is not None and best_first.depth == 12
    assert best_first.evaluation == EngineEvaluation(score_cp=24)
    assert best_second is not None and best_second.depth == 7
    assert best_second.evaluation == EngineEvaluation(score_cp=15)
    assert len(cache.get_all_for_game()) == 2
    cache.clear()
    assert len(cache) == 0


def test_controller_accepts_progressive_depths_and_rejects_stale_position() -> None:
    first = chess.Board()
    first_fen = first.fen()
    controller = LiveAnalysisController(max_depth=12)
    selected_first = controller.select(first_fen, 0)

    accepted_depths: list[int] = []
    for depth in (5, 8, 12):
        result = controller.make_result(
            selected_first,
            _position_analysis(first_fen, depth, depth * 2),
        )
        assert result is not None
        if controller.accept(selected_first.generation, result):
            accepted_depths.append(depth)

    first.push_uci("e2e4")
    selected_second = controller.select(first.fen(), 1)
    late = _live_result(first_fen, 0, 18, 80)

    assert accepted_depths == [5, 8, 12]
    assert not controller.needs_live_analysis(selected_first)
    assert not controller.accept(selected_first.generation, late)
    assert controller.selection == selected_second
    assert controller.cache.get_best(first.fen()) is None


def test_fake_live_engine_publishes_progressive_results() -> None:
    board = chess.Board()
    updates = tuple(_position_analysis(board.fen(), depth, depth) for depth in (5, 8, 12))
    engine = FakeEngine(live_updates={board.fen(): updates})
    received: list[int | None] = []

    engine.analyse_live(
        board,
        max_depth=12,
        on_update=lambda update: received.append(
            update.best_line.depth if update.best_line else None
        ),
    )

    assert received == [5, 8, 12]
    assert engine.live_requests == [(board.fen(), 12)]


def test_session_cache_survives_termination_and_clears_on_reset_and_close() -> None:
    settings = ApplicationSettings(engine=EngineSettings(analysis_mode=EngineAnalysisMode.LIVE))
    session = GameSession(settings=settings, engine=FakeEngine())
    fen = session.snapshot().fen
    session.live_analysis.cache.store(_live_result(fen, 0, 10, 15))

    session.play_text("resign")
    assert len(session.live_analysis.cache) == 1

    session.new_game()
    assert len(session.live_analysis.cache) == 0
    session.live_analysis.cache.store(_live_result(session.snapshot().fen, 0, 8, 5))
    session.close()
    assert len(session.live_analysis.cache) == 0
