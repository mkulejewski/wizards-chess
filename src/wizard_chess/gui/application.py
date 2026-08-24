"""Qt application bootstrap."""

import sys
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from wizard_chess.application.session import GameSession
from wizard_chess.configuration import ApplicationSettings, should_show_game_setup
from wizard_chess.gui.main_window import MainWindow
from wizard_chess.persistence.settings_store import SettingsStore


def run_gui(
    argv: Sequence[str] | None = None,
    session: GameSession | None = None,
    settings_store: SettingsStore | None = None,
    persistent_settings: ApplicationSettings | None = None,
    force_setup: bool = False,
) -> int:
    """Create and run the desktop application."""
    existing = QApplication.instance()
    qt_arguments = [argument for argument in list(argv or sys.argv) if argument != "--setup"]
    application = existing if isinstance(existing, QApplication) else QApplication(qt_arguments)
    active_session = session or GameSession()
    setup_pending = should_show_game_setup(active_session.settings, force=force_setup)
    window = MainWindow(
        active_session,
        settings_store=settings_store,
        persistent_settings=persistent_settings,
        startup_setup_pending=setup_pending,
    )
    window.show()
    if setup_pending:
        QTimer.singleShot(0, window.show_startup_setup)
    return application.exec()
