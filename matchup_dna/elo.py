import csv
from collections import defaultdict
from itertools import groupby
from pathlib import Path

from matchup_dna.load import SURFACES, TOURS, load_matches, load_players

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

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


def final_ratings(matches, players):
    """One row per rated player with both models' ratings after the last week in the data, best Elo first."""
    elo_predictions, elo_ratings = run_elo(matches, ELO_K)
    _, surface_ratings = run_elo(matches, SURFACE_ELO_K)

    last_match = {}
    for prediction in elo_predictions:
        match = prediction["match"]
        for side in ("winner_id", "loser_id"):
            last_match[(match["tour"], match[side])] = match["tourney_date"]

    rows = []
    for key in last_match:
        elo = player_ratings(elo_ratings, key)
        surface = player_ratings(surface_ratings, key)
        row = {
            "tour": key[0],
            "player_id": key[1],
            "name": players.get(key, {}).get("name", ""),
            "last_match": last_match[key],
            "elo": round(elo["overall"]["rating"], 1),
            "matches": elo["overall"]["played"],
            "surface_elo_overall": round(surface["overall"]["rating"], 1),
        }
        for name in SURFACES.values():
            surface_state = surface["surfaces"][name]
            row[f"{name.lower()}_blended"] = round(
                blended_rating(surface["overall"]["rating"], surface_state["rating"], SURFACE_WEIGHT), 1
            )
            row[f"{name.lower()}_rating"] = round(surface_state["rating"], 1)
            row[f"{name.lower()}_matches"] = surface_state["played"]
        rows.append(row)
    rows.sort(key=lambda row: (row["tour"], -row["elo"]))
    return rows


def save_ratings(path, rows):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def print_top(rows, since, count=10):
    for tour in TOURS:
        active = [row for row in rows if row["tour"] == tour and row["last_match"] >= since]
        print(f"\n{tour}: top {count} by Elo, last match on or after {since}")
        print(f"   {'':<4}{'Player':<26}{'Elo':>7}{'Hard':>8}{'Clay':>8}{'Grass':>8}")
        for place, row in enumerate(active[:count], 1):
            print(
                f"   {place:<4}{row['name']:<26}{row['elo']:>7.0f}"
                f"{row['hard_blended']:>8.0f}{row['clay_blended']:>8.0f}{row['grass_blended']:>8.0f}"
            )


if __name__ == "__main__":
    matches = load_matches()
    rows = final_ratings(matches, load_players())
    path = RESULTS_DIR / "final_ratings.csv"
    save_ratings(path, rows)
    latest = max(row["last_match"] for row in rows)
    print(f"Ratings after the week of {latest} for {len(rows):,} players, written to {path}")
    print("Hard, Clay, and Grass are surface Elo's blended ratings, the numbers its predictions use.")
    print_top(rows, since=latest - 10000)
