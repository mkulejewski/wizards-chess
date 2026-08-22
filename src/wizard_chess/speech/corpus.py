"""Small representative corpus for deterministic normalization and backend evaluation."""

VOICE_COMMAND_CORPUS: tuple[tuple[str, str], ...] = (
    ("e four", "e4"),
    ("e five", "e5"),
    ("pawn to e four", "pawn to e4"),
    ("knight f three", "knight f3"),
    ("night f three", "knight f3"),
    ("knight c six", "knight c6"),
    ("bishop c four", "bishop c4"),
    ("bishop to b five", "bishop to b5"),
    ("queen h five", "queen h5"),
    ("queen takes d five", "queen takes d5"),
    ("rook takes e eight check", "rook takes e8 check"),
    ("castle kingside", "castle kingside"),
    ("castle queenside", "castle queenside"),
    ("promote to queen", "promote to queen"),
)
