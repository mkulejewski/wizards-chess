import sys
from collections.abc import Iterable

import pytest

import wizard_chess.speech.audio as audio_module
import wizard_chess.speech.faster_whisper as faster_whisper_module
from wizard_chess.configuration import VoiceLanguage
from wizard_chess.speech.audio import SoundDeviceAudioInput
from wizard_chess.speech.config import VoiceConfig
from wizard_chess.speech.exceptions import VoiceDependencyError
from wizard_chess.speech.factory import create_default_voice_controller
from wizard_chess.speech.faster_whisper import FasterWhisperRecognizer
from wizard_chess.speech.models import AudioRecording


class FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeModel:
    def transcribe(self, audio: object, **options: object) -> tuple[Iterable[FakeSegment], object]:
        del audio, options
        return iter((FakeSegment(" e four "),)), object()


class FakeModelFactory:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, model: str, **options: object) -> FakeModel:
        del model, options
        self.calls += 1
        return FakeModel()


class FakeFasterWhisperModule:
    def __init__(self, factory: FakeModelFactory) -> None:
        self.WhisperModel = factory


class FakeNumpyModule:
    float32 = object()

    def asarray(self, samples: object, *, dtype: object) -> object:
        del dtype
        return samples


@pytest.mark.parametrize(
    ("language", "expected_model"),
    [
        (VoiceLanguage.ENGLISH, "base.en"),
        (VoiceLanguage.POLISH, "base"),
        (VoiceLanguage.AUTO, "base"),
    ],
)
def test_voice_config_uses_a_model_compatible_with_the_effective_language(
    monkeypatch: pytest.MonkeyPatch,
    language: VoiceLanguage,
    expected_model: str,
) -> None:
    monkeypatch.delenv("WIZARD_CHESS_VOICE_LANGUAGE", raising=False)
    monkeypatch.delenv("WIZARD_CHESS_VOICE_MODEL", raising=False)

    config = VoiceConfig.from_environment(language=language)

    assert config.language is language
    assert config.model == expected_model


def test_voice_config_keeps_an_explicit_model_for_a_selected_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIZARD_CHESS_VOICE_LANGUAGE", VoiceLanguage.ENGLISH.value)
    monkeypatch.setenv("WIZARD_CHESS_VOICE_MODEL", "large-v3")

    config = VoiceConfig.from_environment(language=VoiceLanguage.POLISH)

    assert config.language is VoiceLanguage.POLISH
    assert config.model == "large-v3"


def test_faster_whisper_model_loads_lazily_and_is_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = FakeModelFactory()
    modules: dict[str, object] = {
        "faster_whisper": FakeFasterWhisperModule(factory),
        "numpy": FakeNumpyModule(),
    }

    def fake_import(name: str) -> object:
        return modules[name]

    monkeypatch.setattr(faster_whisper_module, "import_module", fake_import)
    recognizer = FasterWhisperRecognizer()
    recording = AudioRecording((0.0,), 16_000, 0.1)

    assert factory.calls == 0
    assert recognizer.transcribe(recording, lambda: False).text == "e four"
    assert recognizer.transcribe(recording, lambda: False).text == "e four"
    assert factory.calls == 1


def test_missing_audio_dependency_is_controlled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_import(name: str) -> object:
        del name
        raise ImportError("sounddevice unavailable")

    monkeypatch.setattr(audio_module, "import_module", missing_import)

    with pytest.raises(VoiceDependencyError, match="uv sync --extra voice"):
        SoundDeviceAudioInput().record(lambda: False)


def test_importing_core_does_not_import_optional_voice_packages() -> None:
    controller = create_default_voice_controller(str)

    assert controller.state.value == "idle"
    assert "faster_whisper" not in sys.modules
    assert "sounddevice" not in sys.modules
