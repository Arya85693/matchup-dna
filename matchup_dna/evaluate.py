import csv
import math
from collections import defaultdict
from pathlib import Path

from matchup_dna.elo import ELO_K, SURFACE_ELO_K, SURFACE_WEIGHT, run_elo, win_probability
from matchup_dna.load import load_matches

# Ratings run from the first match. Weeks before TUNING_START are warm-up and never scored.
TUNING_START = 19900101
TEST_START = 20100101

K_RULES = [("fixed", k) for k in (16, 24, 32, 48, 64)] + [("decaying", v) for v in (150, 250, 350)]
SURFACE_WEIGHTS = (0.25, 0.5, 0.75, 1.0)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


# Every probability here is the pre-match probability given to the player who went on to win.

def log_loss(probabilities):
    return -sum(math.log(p) for p in probabilities) / len(probabilities)


def brier_score(probabilities):
    return sum((1 - p) ** 2 for p in probabilities) / len(probabilities)


def accuracy(probabilities):
    """Share of matches where the winner was the favorite. An exact 0.5 counts as half right."""
    return sum(1 if p > 0.5 else 0.5 if p == 0.5 else 0 for p in probabilities) / len(probabilities)


def score(probabilities):
    return {
        "matches": len(probabilities),
        "log_loss": log_loss(probabilities),
        "brier": brier_score(probabilities),
        "accuracy": accuracy(probabilities),
    }


def calibration(probabilities, width=0.1):
    """Groups matches by the favorite's probability and compares it with how often the favorite won.

    Returns (low, high, matches, mean predicted, observed win rate) for each non-empty bucket.
    """
    buckets = defaultdict(list)
    for p in probabilities:
        if p == 0.5:
            continue
        favorite = max(p, 1 - p)
        index = min(int((favorite - 0.5) / width), int(0.5 / width) - 1)
        buckets[index].append((favorite, p > 0.5))
    rows = []
    for index in sorted(buckets):
        pairs = buckets[index]
        low = 0.5 + index * width
        rows.append((
            low,
            low + width,
            len(pairs),
            sum(favorite for favorite, _ in pairs) / len(pairs),
            sum(won for _, won in pairs) / len(pairs),
        ))
    return rows


def paired_log_loss_difference(probabilities_a, probabilities_b):
    """Mean per-match log loss of B minus A on the same matches, with its standard error.

    Negative means B is better. The standard error treats matches as independent, which they are not
    quite (players repeat), so read it as a rough guide.
    """
    differences = [math.log(a) - math.log(b) for a, b in zip(probabilities_a, probabilities_b)]
    n = len(differences)
    mean = sum(differences) / n
    variance = sum((d - mean) ** 2 for d in differences) / (n - 1)
    return mean, math.sqrt(variance / n)


def rank_accuracy(predictions, probabilities):
    """Higher-ranked-player accuracy, and Elo accuracy on the same matches (both ranks known and different)."""
    rank_hits = []
    elo_on_same = []
    for prediction, p in zip(predictions, probabilities):
        match = prediction["match"]
        winner_rank, loser_rank = match["winner_rank"], match["loser_rank"]
        if winner_rank is None or loser_rank is None or winner_rank == loser_rank:
            continue
        rank_hits.append(winner_rank < loser_rank)
        elo_on_same.append(p)
    if not rank_hits:
        return {"matches": 0, "rank": None, "elo": None}
    return {"matches": len(rank_hits), "rank": sum(rank_hits) / len(rank_hits), "elo": accuracy(elo_on_same)}


def in_period(prediction, start, end=None):
    date = prediction["match"]["tourney_date"]
    return date >= start and (end is None or date < end)


def tuning_scores(matches):
    """Log loss on the tuning period for every K rule, ordinary and surface-blended."""
    table = []
    for rule in K_RULES:
        predictions, _ = run_elo(matches, rule)
        tuning = [p for p in predictions if in_period(p, TUNING_START, TEST_START)]
        row = {"rule": rule, "elo": log_loss([win_probability(p) for p in tuning])}
        for weight in SURFACE_WEIGHTS:
            row[weight] = log_loss([win_probability(p, weight) for p in tuning])
        table.append(row)
    return table


def grouped(predictions, probabilities, key):
    groups = defaultdict(list)
    for prediction, p in zip(predictions, probabilities):
        groups[key(prediction["match"])].append(p)
    return {group: score(values) for group, values in sorted(groups.items(), key=lambda item: str(item[0]))}


def rule_label(rule):
    kind, value = rule
    return f"K = {value}" if kind == "fixed" else f"K = {value} / (played + 5)^0.4"


def save_predictions(path, predictions, elo_probabilities, surface_probabilities):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "tour", "tourney_date", "tourney_name", "round", "surface",
            "winner_id", "winner_name", "loser_id", "loser_name",
            "winner_elo", "loser_elo", "elo_probability", "surface_elo_probability",
        ])
        for prediction, elo_p, surface_p in zip(predictions, elo_probabilities, surface_probabilities):
            match = prediction["match"]
            writer.writerow([
                match["tour"], match["tourney_date"], match["tourney_name"], match["round"], match["surface"] or "",
                match["winner_id"], match["winner_name"], match["loser_id"], match["loser_name"],
                f"{prediction['winner_rating']:.1f}", f"{prediction['loser_rating']:.1f}",
                f"{elo_p:.4f}", f"{surface_p:.4f}",
            ])


def print_scores(label, scores):
    print(f"   {label:<34} {scores['matches']:>8,}  {scores['log_loss']:.4f}  {scores['brier']:.4f}  {scores['accuracy']:.2%}")


def print_header(title):
    print(f"\n{title}")
    print(f"   {'':<34} {'matches':>8}  logloss  brier   accuracy")


def main():
    matches = load_matches()

    table = tuning_scores(matches)
    print(f"Tuning period {TUNING_START} to {TEST_START} (log loss, lower is better)")
    print(f"   {'K rule':<34} {'Elo':>7}" + "".join(f"  w={weight:<5}" for weight in SURFACE_WEIGHTS))
    for row in table:
        print(f"   {rule_label(row['rule']):<34} {row['elo']:.4f}" + "".join(f"  {row[weight]:.4f} " for weight in SURFACE_WEIGHTS))

    elo_rule = min(table, key=lambda row: row["elo"])["rule"]
    surface_rule, surface_weight, _ = min(
        ((row["rule"], weight, row[weight]) for row in table for weight in SURFACE_WEIGHTS),
        key=lambda candidate: candidate[2],
    )
    print(f"\nChosen Elo: {rule_label(elo_rule)}")
    print(f"Chosen surface Elo: {rule_label(surface_rule)}, surface weight {surface_weight}")
    if (elo_rule, surface_rule, surface_weight) != (ELO_K, SURFACE_ELO_K, SURFACE_WEIGHT):
        print("Warning: these differ from ELO_K, SURFACE_ELO_K, and SURFACE_WEIGHT in elo.py, which rate.py uses.")

    elo_predictions, _ = run_elo(matches, elo_rule)
    surface_predictions, _ = run_elo(matches, surface_rule)
    test = [p for p in elo_predictions if in_period(p, TEST_START)]
    surface_test = [p for p in surface_predictions if in_period(p, TEST_START)]
    elo_p = [win_probability(p) for p in test]
    surface_p = [win_probability(p, surface_weight) for p in surface_test]

    print_header(f"Test period from {TEST_START}")
    print_scores("Always 0.5", score([0.5] * len(test)))
    print_scores("Elo", score(elo_p))
    print_scores("Surface Elo", score(surface_p))

    difference, error = paired_log_loss_difference(elo_p, surface_p)
    print(f"\nSurface Elo minus Elo, log loss per match: {difference:+.4f} (standard error {error:.4f})")

    ranks = rank_accuracy(test, elo_p)
    surface_ranks = rank_accuracy(surface_test, surface_p)
    print(f"\nAccuracy where both ranks are known and differ ({ranks['matches']:,} matches)")
    print(f"   Higher-ranked player   {ranks['rank']:.2%}")
    print(f"   Elo                    {ranks['elo']:.2%}")
    print(f"   Surface Elo            {surface_ranks['elo']:.2%}")

    for title, key in (
        ("tour", lambda match: match["tour"]),
        ("surface", lambda match: match["surface"] or "missing"),
        ("year", lambda match: match["tourney_date"] // 10000),
    ):
        elo_groups = grouped(test, elo_p, key)
        surface_groups = grouped(surface_test, surface_p, key)
        print_header(f"Test period by {title}")
        for group in elo_groups:
            print_scores(f"{group} Elo", elo_groups[group])
            print_scores(f"{group} Surface Elo", surface_groups[group])

    for label, probabilities in (("Elo", elo_p), ("Surface Elo", surface_p)):
        print(f"\nCalibration, test period, {label}")
        print(f"   {'favorite p':<12} {'matches':>8}  predicted  observed")
        for low, high, count, predicted, observed in calibration(probabilities):
            print(f"   {low:.1f}-{high:.1f}      {count:>8,}  {predicted:>9.3f}  {observed:>8.3f}")

    path = RESULTS_DIR / "phase2_test_predictions.csv"
    save_predictions(path, test, elo_p, surface_p)
    print(f"\nTest-period predictions written to {path}")


if __name__ == "__main__":
    main()
