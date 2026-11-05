from collections import defaultdict
from itertools import groupby

from matchup_dna.load import SURFACES

START_RATING = 1500

# A K rule is (kind, value). "fixed" uses value as K for every match.
# "decaying" uses value / (matches played + 5) ** 0.4, so new players move fast and established ones settle.
# These must match what python -m matchup_dna.evaluate chooses on the tuning period.
ELO_K = ("fixed", 32)
SURFACE_ELO_K = ("fixed", 48)
SURFACE_WEIGHT = 0.5


def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_rating(rating, score, expected, k=32):
    return rating + k * (score - expected)


def k_factor(k_rule, played):
    kind, value = k_rule
    if kind == "fixed":
        return value
    if kind == "decaying":
        return value / (played + 5) ** 0.4
    raise ValueError(f"Unknown K rule: {k_rule}")


def is_rated(match):
    """Only completed matches of best-of-3 or best-of-5 move ratings or get scored.

    Retirements, walkovers, defaults, abandoned, unknown scores, and best-of-1 say little about who is stronger.
    """
    return (
        match["outcome"] == "completed"
        and match["best_of"] in (3, 5)
        and match["winner_id"] != match["loser_id"]
    )


def blended_rating(overall, surface, surface_weight):
    if surface is None:
        return overall
    return (1 - surface_weight) * overall + surface_weight * surface


def win_probability(prediction, surface_weight=0.0):
    """Pre-match probability that the eventual winner wins. surface_weight 0 is ordinary Elo."""
    winner = blended_rating(prediction["winner_rating"], prediction["winner_surface_rating"], surface_weight)
    loser = blended_rating(prediction["loser_rating"], prediction["loser_surface_rating"], surface_weight)
    return expected_score(winner, loser)


def run_elo(matches, k_rule=ELO_K, before=None):
    """Replays rated matches one tournament week at a time, oldest first.

    Every match in a week is predicted with the ratings from the start of that week, and the week's
    changes are applied together afterwards. This keeps the Phase 1 rule that a tournament week sees
    only earlier weeks. With `before` (YYYYMMDD), weeks on or after that date are not processed.

    Returns (predictions, ratings). Ratings map (tour, player_id) and (tour, player_id, surface)
    to {"rating", "played"}.
    """
    ratings = {}
    predictions = []

    def state(key):
        return ratings.get(key, {"rating": START_RATING, "played": 0})

    usable = sorted((match for match in matches if is_rated(match)), key=lambda match: match["tourney_date"])
    for week, week_matches in groupby(usable, key=lambda match: match["tourney_date"]):
        if before is not None and week >= before:
            break

        changes = defaultdict(float)
        played = defaultdict(int)
        for match in week_matches:
            winner = (match["tour"], match["winner_id"])
            loser = (match["tour"], match["loser_id"])
            keys = [(winner, loser)]
            if match["surface"] is not None:
                keys.append((winner + (match["surface"],), loser + (match["surface"],)))

            prediction = {"match": match}
            for (winner_key, loser_key), label in zip(keys, ("", "surface_")):
                winner_state, loser_state = state(winner_key), state(loser_key)
                expected = expected_score(winner_state["rating"], loser_state["rating"])
                changes[winner_key] += k_factor(k_rule, winner_state["played"]) * (1 - expected)
                changes[loser_key] -= k_factor(k_rule, loser_state["played"]) * (1 - expected)
                played[winner_key] += 1
                played[loser_key] += 1
                prediction[f"winner_{label}rating"] = winner_state["rating"]
                prediction[f"loser_{label}rating"] = loser_state["rating"]
                prediction[f"winner_{label}played"] = winner_state["played"]
                prediction[f"loser_{label}played"] = loser_state["played"]
            prediction.setdefault("winner_surface_rating", None)
            prediction.setdefault("loser_surface_rating", None)
            predictions.append(prediction)

        for key, change in changes.items():
            current = state(key)
            ratings[key] = {"rating": current["rating"] + change, "played": current["played"] + played[key]}

    return predictions, ratings


def player_ratings(ratings, player_key):
    """A player's overall and per-surface ratings from run_elo output; unseen entries are the start rating."""

    def lookup(key):
        return ratings.get(key, {"rating": START_RATING, "played": 0})

    return {
        "overall": lookup(player_key),
        "surfaces": {surface: lookup(player_key + (surface,)) for surface in SURFACES.values()},
    }
