from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import NoReturn, Self

import chess
import chess.engine
import pytest

from wizard_chess.analysis import AnalysisService, AnalysisStore, ClassificationPolicy
from wizard_chess.application.scripted_game import ScriptedGameRunner
from wizard_chess.configuration import EngineSettings
from wizard_chess.domain.exceptions import EngineCrashedError, EngineUnavailableError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.mock import FakeEngine
from wizard_chess.engine.models import EngineEvaluation, EngineLine, PositionAnalysis
from wizard_chess.engine.stockfish import StockfishEngine, normalize_score


class FakeUciProcess:
    def __init__(self, *, crash: bool = False) -> None:
        self.options = {"Threads": object(), "Hash": object(), "Skill Level": object()}
        self.configured: dict[str, object] = {}
        self.crash = crash
        self.quit_called = False

    def configure(self, options: dict[str, object]) -> None:
        self.configured = options

    def analyse(
        self,
        board: chess.Board,
        limit: chess.engine.Limit,
        *,
        multipv: int,
    ) -> list[chess.engine.InfoDict]:
        del limit
        if self.crash:
            raise chess.engine.EngineTerminatedError("dead")
        moves = list(board.legal_moves)[:multipv]
        return [
            {"score": chess.engine.PovScore(chess.engine.Cp(20 - index), board.turn), "pv": [move]}
            for index, move in enumerate(moves)
        ]

    def quit(self) -> None:
        self.quit_called = True


class FakeStreamingResult:
    def __init__(self, updates: list[chess.engine.InfoDict]) -> None:
        self.updates = updates
        self.exited = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        self.exited = True

    def __iter__(self) -> Iterator[chess.engine.InfoDict]:
        return iter(self.updates)


class FakeStreamingUciProcess(FakeUciProcess):
    def __init__(self) -> None:
        super().__init__()
        self.analysis_calls = 0
        self.stream: FakeStreamingResult | None = None

    def analysis(
        self,
        board: chess.Board,
        limit: chess.engine.Limit,
        *,
        multipv: int,
        info: chess.engine.Info,
    ) -> FakeStreamingResult:
        del limit, multipv, info
        move = next(iter(board.legal_moves))
        self.analysis_calls += 1
        self.stream = FakeStreamingResult(
            [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(depth), board.turn),
                    "pv": [move],
                    "depth": depth,
                }
                for depth in (5, 5, 8, 12)
            ]
        )
        return self.stream


def _analysis(board: chess.Board, move: str, score_cp: int) -> PositionAnalysis:
    chess_move = ChessMove.from_uci(move)
    return PositionAnalysis(
        fen=board.fen(),
        lines=(
            EngineLine(
                move=chess_move,
                evaluation=EngineEvaluation(score_cp=score_cp),
                principal_variation=(chess_move,),
            ),
        ),
    )


def test_engine_scores_are_normalized_from_white_perspective() -> None:
    white_cp = chess.engine.PovScore(chess.engine.Cp(84), chess.WHITE)
    black_cp = chess.engine.PovScore(chess.engine.Cp(84), chess.BLACK)
    mate = chess.engine.PovScore(chess.engine.Mate(3), chess.WHITE)

    assert normalize_score(white_cp) == EngineEvaluation(score_cp=84)
    assert normalize_score(black_cp) == EngineEvaluation(score_cp=-84)
    assert normalize_score(mate) == EngineEvaluation(mate_in=3)


def test_stockfish_adapter_configures_normalizes_and_closes_owned_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeUciProcess()

    def start_process(_path: str) -> FakeUciProcess:
        return process

    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        start_process,
    )
    engine = StockfishEngine(
        EngineSettings(enabled=True, path="fake-stockfish", multipv=2, threads=2, hash_mb=64)
    )
    board = chess.Board()
    original_fen = board.fen()

    analysis = engine.analyse_position(board)

    assert len(analysis.lines) == 2
    assert analysis.lines[0].evaluation == EngineEvaluation(score_cp=20)
    assert process.configured["Threads"] == 2
    assert process.configured["Hash"] == 64
    assert board.fen() == original_fen
    engine.close()
    assert process.quit_called


def test_stockfish_live_analysis_uses_one_stream_and_publishes_new_depths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeStreamingUciProcess()

    def start_streaming_process(_path: str) -> FakeStreamingUciProcess:
        return process

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start_streaming_process)
    engine = StockfishEngine(EngineSettings(enabled=True, path="fake-stockfish"))
    updates: list[int | None] = []

    engine.analyse_live(
        chess.Board(),
        max_depth=12,
        on_update=lambda result: updates.append(
            result.best_line.depth if result.best_line is not None else None
        ),
    )

    assert updates == [5, 8, 12]
    assert process.analysis_calls == 1
    assert process.stream is not None and process.stream.exited
    engine.close()


def test_stockfish_unavailable_and_crashed_are_controlled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_process(_path: str) -> NoReturn:
        raise OSError("missing")

    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        missing_process,
    )
    unavailable = StockfishEngine(EngineSettings(enabled=True, path="missing"))
    with pytest.raises(EngineUnavailableError):
        unavailable.analyse_position(chess.Board())

    crashed_process = FakeUciProcess(crash=True)

    def start_crashed_process(_path: str) -> FakeUciProcess:
        return crashed_process

    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        start_crashed_process,
    )
    crashed = StockfishEngine(EngineSettings(enabled=True, path="fake"))
    with pytest.raises(EngineCrashedError):
        crashed.analyse_position(chess.Board())
    assert not crashed.is_running


def test_terminal_position_does_not_require_stockfish() -> None:
    board = chess.Board("7k/5Q2/7K/8/8/8/8/8 b - - 0 1")
    engine = StockfishEngine(EngineSettings())

    analysis = engine.analyse_position(board)

    assert analysis.terminal
    assert analysis.lines == ()
    assert not engine.is_running


def test_analysis_service_replays_without_mutating_and_caches_positions() -> None:
    game = ChessGame()
    game.make_move(ChessMove.from_uci("e2e4"))
    game.make_move(ChessMove.from_uci("e7e5"))
    original_fen = game.fen()
    replay = game.board.root()
    analyses = {replay.fen(): _analysis(replay, "e2e4", 30)}
    replay.push_uci("e2e4")
    analyses[replay.fen()] = _analysis(replay, "e7e5", 15)
    replay.push_uci("e7e5")
    analyses[replay.fen()] = _analysis(replay, "g1f3", 25)
    engine = FakeEngine(analyses)
    progress: list[tuple[int, int]] = []

    result = AnalysisService(engine).analyse_game(
        game,
        on_progress=lambda completed, total: progress.append((completed, total)),
    )

    assert game.fen() == original_fen
    assert [move.san for move in result.moves] == ["e4", "e5"]
    assert [move.centipawn_loss for move in result.moves] == [15, 10]
    assert result.white.best_move_matches == 1
    assert result.black.best_move_matches == 1
    assert progress == [(1, 2), (2, 2)]
    assert len(engine.requests) == 3


def test_classification_thresholds_are_explicit_and_deterministic() -> None:
    policy = ClassificationPolicy()

    assert policy.classify(15).value == "best"
    assert policy.classify(35).value == "excellent"
    assert policy.classify(75).value == "good"
    assert policy.classify(150).value == "inaccuracy"
    assert policy.classify(300).value == "mistake"
    assert policy.classify(301).value == "blunder"


def test_analysis_json_round_trip_is_versioned(tmp_path: Path) -> None:
    game = ChessGame()
    game.make_move(ChessMove.from_uci("e2e4"))
    initial = game.board.root()
    after = initial.copy(stack=False)
    after.push_uci("e2e4")
    engine = FakeEngine(
        {
            initial.fen(): _analysis(initial, "e2e4", 20),
            after.fen(): _analysis(after, "e7e5", 10),
        }
    )
    analysis = AnalysisService(engine).analyse_game(game)
    path = AnalysisStore().save(analysis, tmp_path / "analysis.json")

    assert AnalysisStore().load(path) == analysis


def test_scripted_runner_uses_shared_path_for_a_complete_game() -> None:
    result = ScriptedGameRunner().run(("e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"))

    assert result.move_history[-1] == "Qxf7#"
    assert result.results[-1].move_event is not None
    assert result.final_fen.startswith("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3")
