"""Small keyed message catalog for English and Polish user feedback."""

from collections.abc import Mapping

from wizard_chess.configuration import VoiceLanguage

_MESSAGES: Mapping[str, Mapping[VoiceLanguage, str]] = {
    "voice.illegal_move": {
        VoiceLanguage.ENGLISH: "Illegal move.",
        VoiceLanguage.POLISH: "Nielegalny ruch.",
    },
    "voice.ambiguous_move": {
        VoiceLanguage.ENGLISH: "Which piece?",
        VoiceLanguage.POLISH: "Która figura?",
    },
    "voice.unrecognized": {
        VoiceLanguage.ENGLISH: "Command not recognized.",
        VoiceLanguage.POLISH: "Nie rozpoznano polecenia.",
    },
    "voice.confirm_move": {
        VoiceLanguage.ENGLISH: "Confirm move.",
        VoiceLanguage.POLISH: "Potwierdź ruch.",
    },
    "game.check": {
        VoiceLanguage.ENGLISH: "Check.",
        VoiceLanguage.POLISH: "Szach.",
    },
    "game.checkmate": {
        VoiceLanguage.ENGLISH: "Checkmate.",
        VoiceLanguage.POLISH: "Mat.",
    },
    "game.stalemate": {
        VoiceLanguage.ENGLISH: "Stalemate.",
        VoiceLanguage.POLISH: "Pat.",
    },
    "game.resigned": {
        VoiceLanguage.ENGLISH: "Game resigned.",
        VoiceLanguage.POLISH: "Partia poddana.",
    },
    "engine.unavailable": {
        VoiceLanguage.ENGLISH: "Chess engine unavailable.",
        VoiceLanguage.POLISH: "Silnik szachowy jest niedostępny.",
    },
    "session.played": {
        VoiceLanguage.ENGLISH: "Played: {san}",
        VoiceLanguage.POLISH: "Zagrano: {san}",
    },
    "session.new_game": {
        VoiceLanguage.ENGLISH: "Started a new game.",
        VoiceLanguage.POLISH: "Rozpoczęto nową grę.",
    },
    "session.undo": {
        VoiceLanguage.ENGLISH: "Undid: {move}",
        VoiceLanguage.POLISH: "Cofnięto: {move}",
    },
    "session.redo": {
        VoiceLanguage.ENGLISH: "Redid: {san}",
        VoiceLanguage.POLISH: "Ponowiono: {san}",
    },
    "session.resigned": {
        VoiceLanguage.ENGLISH: "Game resigned. {winner} wins.",
        VoiceLanguage.POLISH: "Partia poddana. Wygrywa: {winner}.",
    },
    "session.draw": {
        VoiceLanguage.ENGLISH: "Game drawn by agreement.",
        VoiceLanguage.POLISH: "Remis za porozumieniem.",
    },
    "session.saved": {
        VoiceLanguage.ENGLISH: "Saved: {path}",
        VoiceLanguage.POLISH: "Zapisano: {path}",
    },
    "session.nothing_to_repeat": {
        VoiceLanguage.ENGLISH: "Nothing to repeat.",
        VoiceLanguage.POLISH: "Nie ma czego powtórzyć.",
    },
    "session.analysis_enabled": {
        VoiceLanguage.ENGLISH: "Analysis enabled.",
        VoiceLanguage.POLISH: "Analiza włączona.",
    },
    "session.analysis_disabled": {
        VoiceLanguage.ENGLISH: "Analysis disabled.",
        VoiceLanguage.POLISH: "Analiza wyłączona.",
    },
}


def translate(
    key: str,
    language: VoiceLanguage = VoiceLanguage.ENGLISH,
    **values: object,
) -> str:
    """Resolve a message key with English fallback and visible unknown keys."""
    translations = _MESSAGES.get(key)
    if translations is None:
        return key.format(**values)
    selected = VoiceLanguage.ENGLISH if language is VoiceLanguage.AUTO else language
    return translations.get(selected, translations[VoiceLanguage.ENGLISH]).format(**values)
