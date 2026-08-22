"""Deterministic speech-specific cleanup before the existing command parser."""

import re

_FILE_WORDS = {
    "a": "a",
    "ay": "a",
    "b": "b",
    "bee": "b",
    "c": "c",
    "sea": "c",
    "see": "c",
    "d": "d",
    "dee": "d",
    "e": "e",
    "f": "f",
    "eff": "f",
    "g": "g",
    "gee": "g",
    "h": "h",
    "aitch": "h",
}
_RANK_WORDS = {
    "1": "1",
    "one": "1",
    "2": "2",
    "two": "2",
    "to": "2",
    "too": "2",
    "3": "3",
    "three": "3",
    "4": "4",
    "four": "4",
    "for": "4",
    "5": "5",
    "five": "5",
    "6": "6",
    "six": "6",
    "7": "7",
    "seven": "7",
    "8": "8",
    "eight": "8",
    "ate": "8",
}
_SQUARE = re.compile(r"^[a-h][1-8]$")
_UNSUPPORTED_PUNCTUATION = re.compile(r"[^\w+#=\-]+")


class TranscriptNormalizer:
    """Normalize only deterministic artifacts of spoken chess commands."""

    def normalize(self, transcript: str) -> str:
        """Return conservative, parser-compatible text for one transcript."""
        compact = transcript.strip().lower().strip(".,!?;:\"'")
        if compact in {"o-o", "o-o-o"}:
            return compact.upper()
        cleaned = _UNSUPPORTED_PUNCTUATION.sub(" ", transcript.lower()).replace("-", " ")
        tokens = cleaned.split()
        normalized: list[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if index + 1 < len(tokens):
                file_name = _FILE_WORDS.get(token)
                rank = _RANK_WORDS.get(tokens[index + 1])
                if file_name is not None and rank is not None:
                    normalized.append(f"{file_name}{rank}")
                    index += 2
                    continue
            normalized.append(token)
            index += 1

        if (
            normalized
            and normalized[0] == "night"
            and any(_SQUARE.fullmatch(token) for token in normalized[1:])
        ):
            normalized[0] = "knight"

        normalized = self._normalize_phrases(normalized)
        return " ".join(normalized)

    @staticmethod
    def _normalize_phrases(tokens: list[str]) -> list[str]:
        replacements = {
            "capture": "takes",
            "captures": "takes",
            "captured": "takes",
        }
        tokens = [replacements.get(token, token) for token in tokens]

        collapsed: list[str] = []
        index = 0
        while index < len(tokens):
            pair = tuple(tokens[index : index + 2])
            if pair == ("king", "side"):
                collapsed.append("kingside")
                index += 2
                continue
            if pair == ("queen", "side"):
                collapsed.append("queenside")
                index += 2
                continue
            if pair == ("check", "mate"):
                collapsed.append("checkmate")
                index += 2
                continue
            collapsed.append(tokens[index])
            index += 1
        return collapsed
