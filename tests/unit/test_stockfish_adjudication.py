from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chess
import chess.engine
import pytest

from wizard_chess.analysis.service import AnalysisService
from wizard_chess.application.clock import ChessClock
from wizard_chess.application.session import GameSession
from wizard_chess.configuration import (
    ApplicationSettings,
    ClockSettings,
    EngineSettings,
    PlayerKind,
    PlayerSettings,
    StockfishPlayerMode,
)
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameStatus, PlayerColor
from wizard_chess.engine.mock import FakeEngine
from wizard_chess.engine.models import (
    EngineClockState,
    EngineDecision,
    EngineEvaluation,
    EngineLine,
    PositionAnalysis,
)
from wizard_chess.engine.stockfish import StockfishEngine
from wizard_chess.persistence.settings_store import SettingsStore

FIRST_FIFTY_MOVE_CLAIM_FEN = "8/5kp1/4R2p/5P1P/6P1/5K2/8/5r2 w - - 99 152"
BEFORE_205_KH5_FEN = "8/3R2pk/7p/5P2/6K1/8/8/6r1 w - - 98 205"
BEFORE_207_RH8_FEN = "3R4/6pk/7p/5P1K/8/8/8/6r1 w - - 102 207"


class RecordingUciProcess:
    def __init__(self, options: dict[str, object] | None = None) -> None:
        self.options = options or {
            "Threads": object(),
            "Hash": object(),
            "Skill Level": object(),
        }
        self.id = {"name": "Stockfish 18 test"}
        self.configured: dict[str, object] = {}
        self.limits: list[chess.engine.Limit] = []
        self.quit_called = False
        self.close_called = False

    def configure(self, options: dict[str, object]) -> None:
        self.configured.update(options)

    def play(
        self,
        board: chess.Board,
        limit: chess.engine.Limit,
        **_kwargs: object,
    ) -> chess.engine.PlayResult:
        self.limits.append(limit)
        move = next(iter(board.legal_moves))
        info: chess.engine.InfoDict = {
            "score": chess.engine.PovScore(chess.engine.Cp(35), board.turn),
            "depth": 14,
            "nodes": 4321,
            "tbhits": 2,
            "time": 0.2,
        }
        return chess.engine.PlayResult(move, None, info)

    def quit(self) -> None:
        self.quit_called = True

    def close(self) -> None:
        self.close_called = True


def _engine_settings(**changes: Any) -> ApplicationSettings:
    engine = EngineSettings(enabled=True, path="fake-stockfish", **changes)
    return ApplicationSettings(
        engine=engine,
        players=PlayerSettings(white_kind=PlayerKind.ENGINE),
    )


@pytest.mark.parametrize(
    "fen",
    [FIRST_FIFTY_MOVE_CLAIM_FEN, BEFORE_207_RH8_FEN],
)
def test_bot_claims_supplied_fifty_move_positions_without_calling_engine(fen: str) -> None:
    engine = FakeEngine()
    session = GameSession(settings=_engine_settings(), engine=engine)
    session.load_fen(fen)

    assert session.play_engine_move() is None
    assert session.snapshot().result.status is GameStatus.FIFTY_MOVE_RULE_CLAIM
    assert session.snapshot().result.notation == "1/2-1/2"
    assert engine.play_requests == []
    assert 'Termination "fifty-move rule claim"' in session.snapshot().pgn


def test_second_supplied_regression_position_becomes_claimable_after_205_kh5() -> None:
    engine = FakeEngine()
    settings = ApplicationSettings(
        engine=EngineSettings(enabled=True),
        players=PlayerSettings(black_kind=PlayerKind.ENGINE),
    )
    session = GameSession(settings=settings, engine=engine)
    session.load_fen(BEFORE_205_KH5_FEN)

    assert not session.snapshot().result.can_claim_draw
    session.play_move(ChessMove.from_uci("g4h5"))

    assert session.play_engine_move() is None
    assert session.snapshot().result.status is GameStatus.FIFTY_MOVE_RULE_CLAIM
    assert engine.play_requests == []


def test_bot_claims_threefold_and_undo_redo_restores_claimed_termination() -> None:
    engine = FakeEngine()
    settings = ApplicationSettings(
        engine=EngineSettings(enabled=True),
        players=PlayerSettings(black_kind=PlayerKind.ENGINE),
    )
    session = GameSession(settings=settings, engine=engine)
    for move in ("g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"):
        session.play_move(ChessMove.from_uci(move))

    assert session.snapshot().result.can_claim_threefold_repetition
    assert session.play_engine_move() is None
    assert session.snapshot().result.status is GameStatus.THREEFOLD_REPETITION_CLAIM
    assert engine.play_requests == []

    session.undo()
    assert not session.snapshot().result.is_over
    session.redo()
    assert session.snapshot().result.status is GameStatus.THREEFOLD_REPETITION_CLAIM

    restored = ChessGame()
    restored.load_pgn(session.snapshot().pgn)
    assert restored.result().status is GameStatus.THREEFOLD_REPETITION_CLAIM


def test_stockfish_fixed_and_clock_modes_send_distinct_uci_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes: list[RecordingUciProcess] = []

    def start_process(_path: str) -> RecordingUciProcess:
        process = RecordingUciProcess()
        processes.append(process)
        return process

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start_process)
    fixed = StockfishEngine(
        EngineSettings(
            enabled=True,
            path="fixed",
            player_move_analysis_time_ms=750,
            post_game_analysis_time_ms=4200,
        )
    )
    fixed_decision = fixed.play_move(chess.Board())
    fixed_limit = processes[0].limits[0]
    assert fixed_limit.time == pytest.approx(0.75)
    assert fixed_limit.white_clock is None
    assert fixed_decision is not None
    assert fixed_decision.depth == 14
    assert fixed_decision.tablebase_hits == 2

    clocked = StockfishEngine(
        EngineSettings(
            enabled=True,
            path="clocked",
            player_mode=StockfishPlayerMode.GAME_CLOCK,
            player_move_analysis_time_ms=9999,
        )
    )
    clocked.play_move(
        chess.Board(),
        clock=EngineClockState(
            white_seconds=61.5,
            black_seconds=45.25,
            white_increment_seconds=2.0,
            black_increment_seconds=3.0,
        ),
    )
    clock_limit = processes[1].limits[0]
    assert clock_limit.time is None
    assert clock_limit.white_clock == pytest.approx(61.5)
    assert clock_limit.black_clock == pytest.approx(45.25)
    assert clock_limit.white_inc == pytest.approx(2.0)
    assert clock_limit.black_inc == pytest.approx(3.0)


def test_clock_runs_during_bot_search_then_increments_and_switches_side() -> None:
    current = [0.0]
    settings = ApplicationSettings(
        engine=EngineSettings(enabled=True, player_mode=StockfishPlayerMode.GAME_CLOCK),
        players=PlayerSettings(white_kind=PlayerKind.ENGINE),
        clock=ClockSettings(enabled=True, initial_seconds=10, increment_seconds=2),
    )
    clock = ChessClock(settings.clock, now=lambda: current[0])
    session = GameSession(settings=settings, engine=FakeEngine(), clock=clock)

    assert session.prepare_engine_turn()
    request_revision = session.revision
    request_fen = session.snapshot().fen
    current[0] = 3.0
    clock_state = session.engine_clock_state()
    assert clock_state is not None
    assert clock_state.white_seconds == pytest.approx(7.0)
    decision = EngineDecision(move=ChessMove.from_uci("e2e4"), search_time_seconds=3.0)

    assert (
        session.commit_engine_decision(
            decision,
            expected_fen=request_fen,
            expected_revision=request_revision,
        )
        is not None
    )
    snapshot = session.snapshot()
    assert snapshot.clock is not None
    assert snapshot.clock.white_seconds == pytest.approx(9.0)
    assert snapshot.clock.active is PlayerColor.BLACK
    assert "[%emt 0:00:03]" in snapshot.pgn
    assert "[%clk 0:00:09]" in snapshot.pgn


def test_engine_decision_cannot_commit_after_flag_or_same_fen_revision_change() -> None:
    current = [0.0]
    settings = ApplicationSettings(
        engine=EngineSettings(enabled=True, player_mode=StockfishPlayerMode.GAME_CLOCK),
        players=PlayerSettings(white_kind=PlayerKind.ENGINE),
        clock=ClockSettings(enabled=True, initial_seconds=1),
    )
    session = GameSession(
        settings=settings,
        engine=FakeEngine(),
        clock=ChessClock(settings.clock, now=lambda: current[0]),
    )
    assert session.prepare_engine_turn()
    revision = session.revision
    fen = session.snapshot().fen
    current[0] = 2.0

    assert (
        session.commit_engine_decision(
            EngineDecision(move=ChessMove.from_uci("e2e4")),
            expected_fen=fen,
            expected_revision=revision,
        )
        is None
    )
    result = session.snapshot().result
    assert result.status is GameStatus.TIME_FORFEIT
    assert result.winner is PlayerColor.BLACK
    assert "time forfeit" in session.snapshot().pgn

    fixed_settings = _engine_settings()
    fixed_session = GameSession(settings=fixed_settings, engine=FakeEngine())
    stale_revision = fixed_session.revision
    same_fen = fixed_session.snapshot().fen
    fixed_session.load_fen(same_fen)
    assert (
        fixed_session.commit_engine_decision(
            EngineDecision(move=ChessMove.from_uci("e2e4")),
            expected_fen=same_fen,
            expected_revision=stale_revision,
        )
        is None
    )


def test_time_forfeit_is_draw_when_opponent_has_no_mating_material() -> None:
    game = ChessGame("7k/8/8/8/8/8/8/R3K3 w - - 0 1")

    result = game.forfeit_on_time(PlayerColor.WHITE)

    assert result.status is GameStatus.TIME_FORFEIT
    assert result.winner is None
    assert result.notation == "1/2-1/2"
    restored = ChessGame()
    restored.load_pgn(game.to_pgn())
    assert restored.result().status is GameStatus.TIME_FORFEIT
    assert restored.result().winner is None


def test_player_and_post_game_analysis_budgets_are_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = RecordingUciProcess()

    def start_process(_path: str) -> RecordingUciProcess:
        return process

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start_process)
    engine = StockfishEngine(
        EngineSettings(
            enabled=True,
            path="fake",
            player_move_analysis_time_ms=300,
            post_game_analysis_time_ms=2700,
        )
    )

    engine.play_move(chess.Board())
    assert process.limits[-1].time == pytest.approx(0.3)

    fake = FakeEngine(
        default=PositionAnalysis(
            fen="ignored",
            lines=(
                EngineLine(
                    move=ChessMove.from_uci("e2e4"),
                    evaluation=EngineEvaluation(score_cp=0),
                ),
            ),
        )
    )
    game = ChessGame()
    game.make_move(ChessMove.from_uci("e2e4"))
    AnalysisService(fake, analysis_time_ms=2700).analyse_game(game)
    assert fake.analysis_times_ms
    assert set(fake.analysis_times_ms) == {2700}


def test_old_shared_analysis_time_migrates_to_both_new_settings(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "settings": {"engine": {"analysis_time_ms": 1350}},
            }
        ),
        encoding="utf-8",
    )

    loaded = SettingsStore(path).load()
    assert loaded.engine.player_move_analysis_time_ms == 1350
    assert loaded.engine.post_game_analysis_time_ms == 1350

    configured = ApplicationSettings(
        engine=EngineSettings(
            player_mode=StockfishPlayerMode.GAME_CLOCK,
            player_move_analysis_time_ms=700,
            post_game_analysis_time_ms=2100,
            syzygy_path="/tables",
            syzygy_probe_limit=6,
            syzygy_50_move_rule=False,
        )
    )
    SettingsStore(path).save(configured)
    assert SettingsStore(path).load() == configured


def test_syzygy_configuration_and_unsupported_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tables = tmp_path / "syzygy"
    tables.mkdir()
    (tables / "KQvK.rtbw").write_bytes(b"test")

    class ProbeOption:
        max = 6

    supported = RecordingUciProcess(
        {
            "SyzygyPath": object(),
            "SyzygyProbeLimit": ProbeOption(),
            "Syzygy50MoveRule": object(),
        }
    )

    def start_supported(_path: str) -> RecordingUciProcess:
        return supported

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start_supported)
    engine = StockfishEngine(
        EngineSettings(
            enabled=True,
            path="fake",
            syzygy_path=str(tables),
            syzygy_probe_limit=7,
            syzygy_50_move_rule=False,
        )
    )
    engine.start()
    assert supported.configured["SyzygyPath"] == str(tables)
    assert supported.configured["SyzygyProbeLimit"] == 6
    assert supported.configured["Syzygy50MoveRule"] is False
    assert engine.syzygy_status.startswith("ready with incomplete")

    missing = RecordingUciProcess()

    def start_missing(_path: str) -> RecordingUciProcess:
        return missing

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start_missing)
    missing_tables = StockfishEngine(
        EngineSettings(
            enabled=True,
            path="fake",
            syzygy_path=str(tmp_path / "does-not-exist"),
        )
    )
    missing_tables.start()
    assert missing_tables.is_running
    assert "directory not found" in missing_tables.syzygy_status

    unsupported = RecordingUciProcess()

    def start_unsupported(_path: str) -> RecordingUciProcess:
        return unsupported

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start_unsupported)
    fallback = StockfishEngine(EngineSettings(enabled=True, path="fake", syzygy_path=str(tables)))
    fallback.start()
    assert fallback.is_running
    assert fallback.syzygy_status == "unsupported by selected engine"


def test_pgn_diagnostics_and_unknown_content_round_trip() -> None:
    current = [0.0]
    settings = ApplicationSettings(
        engine=EngineSettings(
            enabled=True,
            player_move_analysis_time_ms=600,
            syzygy_path="/local/syzygy",
        ),
        players=PlayerSettings(white_kind=PlayerKind.ENGINE),
        clock=ClockSettings(enabled=True, initial_seconds=60, increment_seconds=1),
    )
    session = GameSession(
        settings=settings,
        engine=FakeEngine(),
        clock=ChessClock(settings.clock, now=lambda: current[0]),
    )
    session.start_clock()
    current[0] = 2.5
    session.play_move(
        ChessMove.from_uci("e2e4"),
        engine_decision=EngineDecision(
            move=ChessMove.from_uci("e2e4"),
            evaluation=EngineEvaluation(score_cp=28),
            depth=16,
            nodes=12345,
            tablebase_hits=4,
            engine_name="Stockfish 18",
        ),
    )
    pgn = session.snapshot().pgn
    assert '[TimeControl "60+1"]' in pgn
    assert '[WhiteType "Stockfish"]' in pgn
    assert '[Engine "Stockfish 18"]' in pgn
    assert '[WhiteEngine "Stockfish 18"]' in pgn
    assert '[StockfishPlayerMode "fixed_analysis_time"]' in pgn
    assert '[SyzygyPath "/local/syzygy"]' in pgn
    assert "[%emt 0:00:02.5]" in pgn
    assert "[%clk 0:00:58.5]" in pgn
    assert "[%eval 0.28]" in pgn
    assert "[%depth 16]" in pgn
    assert "[%nodes 12345]" in pgn
    assert "[%tbhits 4]" in pgn

    with_unknown = pgn.replace('[Event "?"]', '[Event "?"]\n[CustomHeader "kept"]')
    with_unknown = with_unknown.replace("[%emt", "human note [%emt")
    restored = ChessGame()
    restored.load_pgn(with_unknown)
    rendered = restored.to_pgn()
    assert '[CustomHeader "kept"]' in rendered
    assert "human note" in rendered
    assert "[%clk 0:00:58.5]" in rendered
