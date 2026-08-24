from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from wizard_chess.application.session import GameSession
from wizard_chess.configuration import (
    ApplicationSettings,
    EngineSettings,
    EngineStrength,
    PlayerKind,
    PlayerSettings,
)
from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.mock import FakeEngine
from wizard_chess.engine.models import EngineEvaluation, EngineLine, PositionAnalysis
from wizard_chess.gui.engine_preferences import EnginePreferencesDialog
from wizard_chess.gui.game_setup import GameSetupDialog
from wizard_chess.gui.main_window import MainWindow
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard
from wizard_chess.persistence.settings_store import SettingsStore


@pytest.fixture(scope="module")
def qt_application() -> Iterator[QApplication]:
    existing = QApplication.instance()
    application = existing if isinstance(existing, QApplication) else QApplication([])
    yield application


@pytest.mark.parametrize(
    ("preset_index", "white_kind", "black_kind"),
    [
        (1, PlayerKind.HUMAN, PlayerKind.HUMAN),
        (2, PlayerKind.HUMAN, PlayerKind.ENGINE),
        (3, PlayerKind.ENGINE, PlayerKind.HUMAN),
        (4, PlayerKind.ENGINE, PlayerKind.ENGINE),
    ],
)
def test_game_setup_presets_apply_through_session_configuration(
    qt_application: QApplication,
    preset_index: int,
    white_kind: PlayerKind,
    black_kind: PlayerKind,
) -> None:
    del qt_application
    session = GameSession(engine_factory=lambda _settings: None)
    dialog = GameSetupDialog(ApplicationSettings())
    dialog.preset_combo.setCurrentIndex(preset_index)
    dialog.accepted.connect(lambda: session.new_game(dialog.selected_settings()))

    dialog.accept()

    assert session.settings.players.white_kind is white_kind
    assert session.settings.players.black_kind is black_kind
    assert session.settings.engine.enabled == (
        white_kind is PlayerKind.ENGINE or black_kind is PlayerKind.ENGINE
    )
    session.close()


def test_game_setup_cancel_does_not_mutate_active_game(
    qt_application: QApplication,
) -> None:
    del qt_application
    session = GameSession()
    session.play_text("e4")
    original_settings = session.settings
    original_fen = session.snapshot().fen
    dialog = GameSetupDialog(original_settings)
    dialog.preset_combo.setCurrentIndex(3)
    dialog.accepted.connect(lambda: session.new_game(dialog.selected_settings()))

    dialog.reject()

    assert session.settings == original_settings
    assert session.snapshot().fen == original_fen
    assert session.snapshot().move_history == ("e4",)
    session.close()


def test_main_window_game_setup_persists_and_starts_selected_game(
    qt_application: QApplication,
    tmp_path: Path,
) -> None:
    del qt_application
    store = SettingsStore(tmp_path / "settings.json")
    session = GameSession()
    session.play_text("e4")
    window = MainWindow(session, settings_store=store)

    QTest.mouseClick(window.new_button, Qt.MouseButton.LeftButton)
    dialog = window.game_setup_dialog
    assert dialog is not None
    dialog.white_name_edit.setText("Merlin")
    dialog.black_name_edit.setText("Morgana")
    dialog.clock_enabled_checkbox.setChecked(True)
    dialog.initial_time_spin.setValue(300)
    dialog.increment_spin.setValue(3)
    dialog.remember_checkbox.setChecked(True)
    dialog.auto_start_checkbox.setChecked(True)
    dialog.accept()

    assert session.snapshot().move_history == ()
    assert session.settings.players.white_name == "Merlin"
    assert session.settings.clock.enabled
    persisted = store.load()
    assert persisted.players.black_name == "Morgana"
    assert persisted.game_setup_saved
    assert not persisted.show_game_setup_on_startup
    window.close()


def test_engine_preferences_exposes_path_defaults_and_advanced_values(
    qt_application: QApplication,
) -> None:
    del qt_application
    dialog = EnginePreferencesDialog(ApplicationSettings(), validator=lambda _settings: None)
    dialog.path_edit.setText("/opt/custom-stockfish")
    dialog.strength_combo.setCurrentIndex(
        dialog.strength_combo.findData(EngineStrength.EXPERT.value)
    )
    dialog.think_time_spin.setValue(2.5)
    dialog.live_analysis_checkbox.setChecked(True)
    dialog.multipv_spin.setValue(5)
    dialog.depth_spin.setValue(18)
    dialog.threads_spin.setValue(4)
    dialog.hash_spin.setValue(256)

    selected = dialog.selected_settings()

    assert selected.engine == EngineSettings(
        enabled=True,
        path="/opt/custom-stockfish",
        analysis_enabled=True,
        analysis_time_ms=2500,
        analysis_depth=18,
        multipv=5,
        strength=EngineStrength.EXPERT,
        threads=4,
        hash_mb=256,
    )


def test_engine_as_white_uses_async_canonical_move_path(
    qt_application: QApplication,
) -> None:
    physical_board = SimulatedPhysicalBoard()
    move = ChessMove.from_uci("e2e4")
    engine = FakeEngine(
        default=PositionAnalysis(
            fen="ignored",
            lines=(
                EngineLine(
                    move=move,
                    evaluation=EngineEvaluation(score_cp=0),
                    principal_variation=(move,),
                ),
            ),
        )
    )
    settings = ApplicationSettings(
        engine=EngineSettings(enabled=True),
        players=PlayerSettings(white_kind=PlayerKind.ENGINE),
    )
    session = GameSession(physical_board, settings=settings, engine=engine)
    window = MainWindow(session)

    _wait_for(qt_application, lambda: session.snapshot().move_history == ("e4",))

    assert [event.uci for event in physical_board.events] == ["e2e4"]
    assert session.snapshot().turn.value == "black"
    window.close()


def test_startup_setup_defers_engine_white_until_dialog_is_resolved(
    qt_application: QApplication,
) -> None:
    move = ChessMove.from_uci("e2e4")
    engine = FakeEngine(
        default=PositionAnalysis(
            fen="ignored",
            lines=(EngineLine(move, EngineEvaluation(score_cp=0), (move,)),),
        )
    )
    settings = ApplicationSettings(
        engine=EngineSettings(enabled=True),
        players=PlayerSettings(white_kind=PlayerKind.ENGINE),
        game_setup_saved=True,
    )
    session = GameSession(settings=settings, engine=engine)
    window = MainWindow(session, startup_setup_pending=True)

    qt_application.processEvents()
    assert engine.requests == []
    window.show_startup_setup()
    dialog = window.game_setup_dialog
    assert dialog is not None
    dialog.reject()
    _wait_for(qt_application, lambda: session.snapshot().move_history == ("e4",))
    window.close()


def _wait_for(
    application: QApplication,
    condition: Callable[[], bool],
    *,
    timeout_milliseconds: int = 2000,
) -> None:
    elapsed = 0
    while elapsed < timeout_milliseconds and not condition():
        application.processEvents()
        QTest.qWait(5)
        elapsed += 5
    application.processEvents()
    assert condition()
