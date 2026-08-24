"""Pure voice confirmation policy used by any presentation adapter."""

from wizard_chess.configuration import ConfirmationPolicy


def should_confirm(
    confidence: float | None,
    policy: ConfirmationPolicy,
    *,
    confidence_threshold: float = 0.65,
    ambiguous: bool = False,
) -> bool:
    """Return whether the UI should confirm before submitting a recognized action."""
    if policy is ConfirmationPolicy.ALWAYS:
        return True
    if policy is ConfirmationPolicy.OFF:
        return False
    return ambiguous or (confidence is not None and confidence < confidence_threshold)
