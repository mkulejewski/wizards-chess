"""Deterministic Polish chess-domain transcript normalization."""

import re
import unicodedata

_RANKS = {
    "jeden": "1",
    "dwa": "2",
    "trzy": "3",
    "cztery": "4",
    "pięć": "5",
    "piec": "5",
    "sześć": "6",
    "szesc": "6",
    "siedem": "7",
    "osiem": "8",
}
_FILES = {
    "a": "a",
    "be": "b",
    "b": "b",
    "ce": "c",
    "c": "c",
    "de": "d",
    "d": "d",
    "e": "e",
    "ef": "f",
    "f": "f",
    "gie": "g",
    "g": "g",
    "ha": "h",
    "h": "h",
}
_PUNCTUATION = re.compile(r"[^\wąćęłńóśźż]+", re.IGNORECASE)


class PolishTranscriptNormalizer:
    """Normalize Polish ranks and likely ASR file names without chess legality."""

    def normalize(self, transcript: str) -> str:
        text = unicodedata.normalize("NFC", transcript).lower()
        tokens = _PUNCTUATION.sub(" ", text).split()
        normalized: list[str] = []
        index = 0
        while index < len(tokens):
            file_name = _FILES.get(tokens[index])
            rank = _RANKS.get(tokens[index + 1]) if index + 1 < len(tokens) else None
            if file_name is not None and rank is not None:
                normalized.append(f"{file_name}{rank}")
                index += 2
                continue
            normalized.append(tokens[index])
            index += 1
        return " ".join(normalized)
