"""Small environment-backed configuration for the optional voice adapter."""

import logging
import os
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VoiceConfig:
    """Settings for local microphone capture and CPU speech recognition."""

    model: str = "base.en"
    language: str = "en"
    device: int | str | None = None
    sample_rate: int = 16_000
    maximum_seconds: float = 6.0
    speech_start_timeout_seconds: float = 3.0
    silence_seconds: float = 0.8
    silence_threshold: float = 0.015

    @classmethod
    def from_environment(cls) -> "VoiceConfig":
        """Read optional overrides, retaining safe defaults for invalid values."""
        defaults = cls()
        raw_device = os.environ.get("WIZARD_CHESS_MICROPHONE", "").strip()
        device: int | str | None
        if not raw_device:
            device = None
        else:
            try:
                device = int(raw_device)
            except ValueError:
                device = raw_device

        return cls(
            model=os.environ.get("WIZARD_CHESS_VOICE_MODEL", defaults.model).strip()
            or defaults.model,
            language=os.environ.get("WIZARD_CHESS_VOICE_LANGUAGE", defaults.language).strip()
            or defaults.language,
            device=device,
            maximum_seconds=_positive_float_from_environment(
                "WIZARD_CHESS_VOICE_MAX_SECONDS", defaults.maximum_seconds
            ),
            speech_start_timeout_seconds=_positive_float_from_environment(
                "WIZARD_CHESS_VOICE_START_TIMEOUT_SECONDS",
                defaults.speech_start_timeout_seconds,
            ),
            silence_seconds=_positive_float_from_environment(
                "WIZARD_CHESS_VOICE_SILENCE_SECONDS", defaults.silence_seconds
            ),
            silence_threshold=_positive_float_from_environment(
                "WIZARD_CHESS_VOICE_SILENCE_THRESHOLD", defaults.silence_threshold
            ),
        )


def _positive_float_from_environment(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        LOGGER.warning("Ignoring invalid %s=%r", name, value)
        return default
    if parsed <= 0:
        LOGGER.warning("Ignoring non-positive %s=%r", name, value)
        return default
    return parsed
