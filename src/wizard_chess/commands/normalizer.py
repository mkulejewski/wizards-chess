"""Conservative normalization for typed and future speech input."""

import re


def normalize_command(text: str) -> str:
    """Normalize case, spacing, and coordinate separators."""
    normalized = text.strip().lower().replace("-", " ")
    return re.sub(r"\s+", " ", normalized)
