"""Composition helpers that keep optional backend imports lazy."""

from collections.abc import Callable

from wizard_chess.speech.audio import SoundDeviceAudioInput
from wizard_chess.speech.config import VoiceConfig
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.faster_whisper import FasterWhisperRecognizer


def create_default_voice_controller[CommandResultT](
    submit_command: Callable[[str], CommandResultT],
    config: VoiceConfig | None = None,
) -> VoiceController[CommandResultT]:
    """Compose local capture and recognition without loading either dependency yet."""
    settings = config or VoiceConfig.from_environment()
    audio_input = SoundDeviceAudioInput(
        device=settings.device,
        sample_rate=settings.sample_rate,
        maximum_seconds=settings.maximum_seconds,
        speech_start_timeout_seconds=settings.speech_start_timeout_seconds,
        silence_seconds=settings.silence_seconds,
        silence_threshold=settings.silence_threshold,
    )
    recognizer = FasterWhisperRecognizer(settings.model, language=settings.language)
    return VoiceController(audio_input, recognizer, submit_command)
