"""Composition helpers that keep optional backend imports lazy."""

import logging
from collections.abc import Callable

from wizard_chess.configuration import VoiceLanguage
from wizard_chess.speech.audio import SoundDeviceAudioInput
from wizard_chess.speech.config import VoiceConfig
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.faster_whisper import FasterWhisperRecognizer
from wizard_chess.speech.normalizer import TranscriptNormalizer
from wizard_chess.speech.polish import PolishTranscriptNormalizer

LOGGER = logging.getLogger(__name__)


def create_default_voice_controller[CommandResultT](
    submit_command: Callable[[str], CommandResultT],
    config: VoiceConfig | None = None,
) -> VoiceController[CommandResultT]:
    """Compose local capture and recognition without loading either dependency yet."""
    settings = config or VoiceConfig.from_environment()
    LOGGER.info(
        "Voice adapter configured: language=%s model=%s device=%s",
        settings.language.value,
        settings.model,
        settings.device if settings.device is not None else "default",
    )
    audio_input = SoundDeviceAudioInput(
        device=settings.device,
        sample_rate=settings.sample_rate,
        maximum_seconds=settings.maximum_seconds,
        speech_start_timeout_seconds=settings.speech_start_timeout_seconds,
        silence_seconds=settings.silence_seconds,
        silence_threshold=settings.silence_threshold,
    )
    language = None if settings.language is VoiceLanguage.AUTO else settings.language.value
    recognizer = FasterWhisperRecognizer(settings.model, language=language)
    normalizer = (
        PolishTranscriptNormalizer()
        if settings.language is VoiceLanguage.POLISH
        else TranscriptNormalizer()
    )
    return VoiceController(audio_input, recognizer, submit_command, normalizer)
