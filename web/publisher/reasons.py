"""Stored eligibility decisions mapped to the words a visitor reads.

The mapping is closed: a stored reason that matches no rule keeps its own text (code "other"), so a new reason is
shown as recorded rather than hidden or guessed at.
"""

RULES = (
    # (decision or None for any, start of the stored reason, code, text)
    ("deferred", "no confirmed start time", "start_unconfirmed",
     "Start time not confirmed yet. The forecast is issued once it is published, at least 30 minutes before play."),
    (None, "neither player has played earlier", "ra_first_match",
     "Neither player has played earlier in this tournament, so there is nothing for the round-aware update to add."),
    (None, "round RR", "ra_round_robin",
     "Round-robin match: the round-aware update covers knockout rounds only."),
    ("too_late", "the match is already in progress", "too_late_in_progress",
     "No forecast: the match had already started when it was first seen."),
    ("too_late", "the match has already been played", "too_late_played",
     "No forecast: the match had already been played when it was first seen."),
    ("too_late", "", "too_late",
     "No forecast: it was too close to the start (forecasts are issued at least 30 minutes before play)."),
)

IDENTITY = ("identity_review", "No forecast yet: a player's identity is being checked.")
NOT_EVALUATED = ("not_evaluated", "Not evaluated yet.")


def describe(decision, reason):
    """(code, text) for a stored decision and reason."""
    if decision is None:
        return NOT_EVALUATED
    text = reason or ""
    if text.startswith("identity "):        # engine: "identity <status> for <name> (<method>)"; method stays private
        return IDENTITY
    for wanted, start, code, shown in RULES:
        if (wanted is None or wanted == decision) and text.startswith(start):
            return code, shown
    return "other", text[:1].upper() + text[1:] if text else decision
