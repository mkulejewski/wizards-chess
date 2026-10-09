"""Qt worker that keeps microphone capture and recognition off the GUI thread."""

import logging

from PySide6.QtCore import QThread, Signal

from wizard_chess.application.session import SessionResult
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.models import VoiceState

LOGGER = logging.getLogger(__name__)


class VoiceWorker(QThread):
    """Run one synchronous voice-controller lifecycle on a background thread."""

    state_changed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, controller: VoiceController[SessionResult]) -> None:
        super().__init__()
        self._controller = controller

    def run(self) -> None:
        LOGGER.debug("Voice worker started")
        try:
            result = self._controller.listen_once(self._emit_state)
        except Exception as error:
            LOGGER.debug("Voice worker failed", exc_info=True)
            self.failed.emit(error)
            return
        LOGGER.debug("Voice worker completed")
        self.succeeded.emit(result)

    def cancel(self) -> None:
        """Request cancellation at the next safe voice-pipeline boundary."""
        self._controller.cancel()

    def _emit_state(self, state: VoiceState) -> None:
        self.state_changed.emit(state)
