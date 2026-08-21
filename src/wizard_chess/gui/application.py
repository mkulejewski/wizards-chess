"""Qt application bootstrap."""

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from wizard_chess.application.session import GameSession
from wizard_chess.gui.main_window import MainWindow


def run_gui(argv: Sequence[str] | None = None, session: GameSession | None = None) -> int:
    """Create and run the desktop application."""
    existing = QApplication.instance()
    application = (
        existing if isinstance(existing, QApplication) else QApplication(list(argv or sys.argv))
    )
    window = MainWindow(session)
    window.show()
    return application.exec()
