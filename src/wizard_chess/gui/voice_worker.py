"""Qt worker that keeps microphone capture and recognition off the GUI thread."""

from PySide6.QtCore import QThread, Signal

from wizard_chess.application.session import SessionResult
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.models import VoiceState


class VoiceWorker(QThread):
    """Run one synchronous voice-controller lifecycle on a background thread."""

    state_changed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, controller: VoiceController[SessionResult]) -> None:
        super().__init__()
        self._controller = controller

    def run(self) -> None:
        try:
            result = self._controller.listen_once(self._emit_state)
        except Exception as error:
            self.failed.emit(error)
            return
        self.succeeded.emit(result)

    def cancel(self) -> None:
        """Request cancellation at the next safe voice-pipeline boundary."""
        self._controller.cancel()

    def _emit_state(self, state: VoiceState) -> None:
        self.state_changed.emit(state)
