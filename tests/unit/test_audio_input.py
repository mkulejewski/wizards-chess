from array import array
from collections.abc import Iterable
from types import TracebackType
from typing import Self

import pytest

import wizard_chess.speech.audio as audio_module
from wizard_chess.speech.audio import SoundDeviceAudioInput
from wizard_chess.speech.exceptions import NoSpeechDetectedError


class FakeRawInputStream:
    def __init__(self, blocks: Iterable[list[float]]) -> None:
        self.blocks = iter(blocks)
        self.closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        self.closed = True

    def read(self, frames: int) -> tuple[memoryview, bool]:
        values = next(self.blocks, [0.0] * frames)
        return memoryview(array("f", values).tobytes()), False


class FakeSoundDeviceModule:
    def __init__(self, blocks: Iterable[list[float]]) -> None:
        self.stream = FakeRawInputStream(blocks)
        self.queried_device: int | str | None = None

    def query_devices(self, device: int | str | None, kind: str) -> object:
        assert kind == "input"
        self.queried_device = device
        return object()

    def RawInputStream(self, **options: object) -> FakeRawInputStream:
        assert options["channels"] == 1
        assert options["dtype"] == "float32"
        return self.stream


def _install_fake_sounddevice(
    monkeypatch: pytest.MonkeyPatch, module: FakeSoundDeviceModule
) -> None:
    def fake_import(_name: str) -> object:
        return module

    monkeypatch.setattr(audio_module, "import_module", fake_import)


def test_audio_capture_stops_after_speech_and_trailing_silence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sounddevice = FakeSoundDeviceModule(([0.0] * 5, [0.1] * 5, [0.0] * 5, [0.0] * 5))
    _install_fake_sounddevice(monkeypatch, sounddevice)
    audio_input = SoundDeviceAudioInput(
        device=3,
        sample_rate=100,
        maximum_seconds=1.0,
        speech_start_timeout_seconds=0.5,
        silence_seconds=0.1,
        silence_threshold=0.05,
    )

    recording = audio_input.record(lambda: False)

    assert recording.sample_rate == 100
    assert recording.duration_seconds == pytest.approx(0.2)
    assert sounddevice.queried_device == 3
    assert sounddevice.stream.closed


def test_silent_audio_is_controlled_and_stream_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sounddevice = FakeSoundDeviceModule([0.0] * 5 for _ in range(10))
    _install_fake_sounddevice(monkeypatch, sounddevice)
    audio_input = SoundDeviceAudioInput(
        sample_rate=100,
        maximum_seconds=1.0,
        speech_start_timeout_seconds=0.1,
        silence_seconds=0.1,
        silence_threshold=0.05,
    )

    with pytest.raises(NoSpeechDetectedError, match="Could not detect speech"):
        audio_input.record(lambda: False)

    assert sounddevice.stream.closed
