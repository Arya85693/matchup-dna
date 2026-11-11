"""ITF extension, stage I2: one Elo pool across every level, and the variants tried on development.

`run_elo` is Phase 2's replay (matchup_dna.elo.run_elo, which is hash-locked and not edited) with three options:

    start_rating(match, side)  a player's first rating (Phase 2: always 1500)
    updates(match)             whether a rated match moves the ratings (Phase 2: every rated match). Matches that
                               do not update are still predicted; the "main tour only" baseline uses this.
    keep(match)                whether the match's prediction is kept (memory: the history holds about half a
                               million matches per tour, and the features need only recent ones)

With the defaults it gives exactly Phase 2's predictions and ratings; a test checks this.

Variants (I1 plan, section 4), chosen on development by the log loss of the ordinary Elo probability on scored
ITF matches:

    phase2      K 32, surface K 48, start 1500 (Phases 2-4)
    decaying    K = 250 / (matches played + 5) ** 0.4 for both, start 1500: new players move fast
    rank_start  Phase 2's K, and a first rating of 1500 + 100 * ln(1000 / rank) from the player's rank in their
                first match (clipped to 1100-1900; unranked counts as rank 2000), so a newcomer ranked 300th does
                not start level with one ranked 1,800th
"""
import math
from collections import defaultdict
from itertools import groupby

from matchup_dna.elo import ELO_K, SURFACE_ELO_K, START_RATING, expected_score, is_rated, k_factor

UNRANKED_AS = 2000
RANK_START_SCALE = 100
RANK_START_CENTER = 1000
RANK_START_BOUNDS = (1100, 1900)


def rank_start(match, side):
    rank = match[f"{side}_rank"] or UNRANKED_AS
    rating = START_RATING + RANK_START_SCALE * math.log(RANK_START_CENTER / rank)
    return min(max(rating, RANK_START_BOUNDS[0]), RANK_START_BOUNDS[1])


VARIANTS = {
    "phase2": {"k": ELO_K, "surface_k": SURFACE_ELO_K, "start": None},
    "decaying": {"k": ("decaying", 250), "surface_k": ("decaying", 250), "start": None},
    "rank_start": {"k": ELO_K, "surface_k": SURFACE_ELO_K, "start": rank_start},
}


def run_elo(matches, k_rule=ELO_K, before=None, start_rating=None, updates=None, keep=None):
    """Phase 2's week-by-week replay (see matchup_dna.elo.run_elo) with the options above. Returns (predictions,
    ratings); ratings map (tour, player_id) and (tour, player_id, surface) to {"rating", "played"}."""
    ratings = {}
    predictions = []
    firsts = {}           # a player's first rating, fixed the first time they are seen

    def state(key, match, side):
        if key in ratings:
            return ratings[key]
        if key not in firsts:
            firsts[key] = START_RATING if start_rating is None else start_rating(match, side)
        return {"rating": firsts[key], "played": 0}

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
            moves = updates is None or updates(match)

            prediction = {"match": match}
            for (winner_key, loser_key), label in zip(keys, ("", "surface_")):
                winner_state, loser_state = state(winner_key, match, "winner"), state(loser_key, match, "loser")
                expected = expected_score(winner_state["rating"], loser_state["rating"])
                if moves:
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
            if keep is None or keep(match):
                predictions.append(prediction)

        for key in played:
            current = ratings[key] if key in ratings else {"rating": firsts[key], "played": 0}
            ratings[key] = {"rating": current["rating"] + changes[key], "played": current["played"] + played[key]}

    return predictions, ratings


def replay(matches, variant, updates=None, keep=None, keep_surface=None):
    """(ordinary Elo predictions, surface Elo predictions by match key) for a variant."""
    spec = VARIANTS[variant]
    elo, _ = run_elo(matches, spec["k"], start_rating=spec["start"], updates=updates, keep=keep)
    surface, _ = run_elo(matches, spec["surface_k"], start_rating=spec["start"], updates=updates, keep=keep_surface)
    return elo, {p["match"]["key"]: p for p in surface}
