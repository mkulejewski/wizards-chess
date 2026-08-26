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
    "session.draw_claimed_fifty": {
        VoiceLanguage.ENGLISH: "Draw claimed by the fifty-move rule.",
        VoiceLanguage.POLISH: "Remis na podstawie reguły pięćdziesięciu posunięć.",
    },
    "session.draw_claimed_threefold": {
        VoiceLanguage.ENGLISH: "Draw claimed by threefold repetition.",
        VoiceLanguage.POLISH: "Remis przez trzykrotne powtórzenie pozycji.",
    },
    "session.draw_offered": {
        VoiceLanguage.ENGLISH: "{player} offers a draw. Press Draw again to accept.",
        VoiceLanguage.POLISH: "{player} proponuje remis. Naciśnij Remis ponownie, aby przyjąć.",
    },
    "session.draw_rejected": {
        VoiceLanguage.ENGLISH: "Draw offer rejected.",
        VoiceLanguage.POLISH: "Propozycja remisu odrzucona.",
    },
    "session.no_draw_offer": {
        VoiceLanguage.ENGLISH: "There is no draw offer to accept or reject.",
        VoiceLanguage.POLISH: "Nie ma propozycji remisu do przyjęcia ani odrzucenia.",
    },
    "session.draw_offer_pending": {
        VoiceLanguage.ENGLISH: "A draw offer is already pending.",
        VoiceLanguage.POLISH: "Propozycja remisu już oczekuje na odpowiedź.",
    },
    "session.draw_already_offered_here": {
        VoiceLanguage.ENGLISH: "A draw was already offered in this position.",
        VoiceLanguage.POLISH: "W tej pozycji już zaproponowano remis.",
    },
    "session.draw_humans_only": {
        VoiceLanguage.ENGLISH: "Draw offers are available only in games with two human players.",
        VoiceLanguage.POLISH: "Propozycje remisu są dostępne tylko w grze dwóch ludzi.",
    },
    "session.draw_claim_human_only": {
        VoiceLanguage.ENGLISH: "Only the human player whose turn it is may claim a draw.",
        VoiceLanguage.POLISH: "Remisu może zażądać tylko gracz-człowiek, na którego przypada ruch.",
    },
    "session.resign_human_only": {
        VoiceLanguage.ENGLISH: "Only a human player whose turn it is may resign.",
        VoiceLanguage.POLISH: "Poddać się może tylko gracz-człowiek, na którego przypada ruch.",
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
