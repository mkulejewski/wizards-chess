import pytest

from wizard_chess.speech.corpus import VOICE_COMMAND_CORPUS
from wizard_chess.speech.normalizer import TranscriptNormalizer


@pytest.mark.parametrize(("transcript", "expected"), VOICE_COMMAND_CORPUS)
def test_voice_command_corpus_normalizes_deterministically(transcript: str, expected: str) -> None:
    assert TranscriptNormalizer().normalize(transcript) == expected


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("  KNIGHT   F   THREE  ", "knight f3"),
        ("Bishop to C four.", "bishop to c4"),
        ('Queen takes D five, "check"!', "queen takes d5 check"),
        ("e two e four", "e2 e4"),
        ("move e two to e four", "move e2 to e4"),
        ("knight g one f three", "knight g1 f3"),
        ("castle king side", "castle kingside"),
        ("castle queen side", "castle queenside"),
        ("rook captures e eight check mate", "rook takes e8 checkmate"),
        ("O-O.", "O-O"),
        ("o-o-o", "O-O-O"),
    ],
)
def test_normalizer_handles_spacing_punctuation_and_spoken_forms(
    transcript: str, expected: str
) -> None:
    assert TranscriptNormalizer().normalize(transcript) == expected


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("ay one", "a1"),
        ("bee two", "b2"),
        ("see three", "c3"),
        ("dee four", "d4"),
        ("e five", "e5"),
        ("eff six", "f6"),
        ("gee seven", "g7"),
        ("aitch ate", "h8"),
        ("a for", "a4"),
    ],
)
def test_normalizer_applies_homophones_only_in_coordinate_context(
    transcript: str, expected: str
) -> None:
    assert TranscriptNormalizer().normalize(transcript) == expected


@pytest.mark.parametrize(
    "transcript",
    [
        "undo",
        "promote to queen",
        "knight before",
        "see you at four",
        "check",
        "checkmate",
    ],
)
def test_normalizer_does_not_aggressively_rewrite_unrelated_words(transcript: str) -> None:
    assert TranscriptNormalizer().normalize(transcript) == transcript


def test_night_is_corrected_only_when_followed_by_a_coordinate() -> None:
    normalizer = TranscriptNormalizer()

    assert normalizer.normalize("night f three") == "knight f3"
    assert normalizer.normalize("night shift") == "night shift"
