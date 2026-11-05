import csv
import datetime
import math
from collections import Counter, defaultdict
from matchup_dna.elo import ELO_K, RESULTS_DIR, SURFACE_ELO_K, SURFACE_WEIGHT, run_elo, win_probability
from matchup_dna.load import TOURS, load_matches
from matchup_dna.periods import DEVELOPMENT_END, DEVELOPMENT_START, PERIODS, TRAIN_START, TUNING_START, period

K_RULES = [("fixed", k) for k in (16, 24, 32, 48, 64)] + [("decaying", v) for v in (150, 250, 350)]
SURFACE_WEIGHTS = (0.25, 0.5, 0.75, 1.0)

SCORED_PERIODS = ("tuning", "train", "validation")
TOUR_GROUPS = (("ATP", ("ATP",)), ("WTA", ("WTA",)), ("Both tours", TOURS))

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


def log_loss_differences(probabilities_a, probabilities_b):
    """Per-match log loss of B minus log loss of A. Negative means B was better on that match."""
    return [math.log(a) - math.log(b) for a, b in zip(probabilities_a, probabilities_b)]


def paired_log_loss_difference(probabilities_a, probabilities_b):
    """Mean per-match log loss of B minus A on the same matches, with its standard error.

    Negative means B is better. The standard error treats matches as independent, which they are not
    quite (players repeat), so read it as a rough guide.
    """
    differences = log_loss_differences(probabilities_a, probabilities_b)
    n = len(differences)
    mean = sum(differences) / n
    variance = sum((d - mean) ** 2 for d in differences) / (n - 1)
    return mean, math.sqrt(variance / n)


def clustered_standard_error(values, clusters):
    """Standard error of the mean of `values` when values in the same cluster may be correlated.

    Values in different clusters are still assumed independent. With G clusters the G / (G - 1)
    factor is the usual small-sample correction.
    """
    n = len(values)
    mean = sum(values) / n
    totals = defaultdict(float)
    for value, cluster in zip(values, clusters):
        totals[cluster] += value - mean
    groups = len(totals)
    return math.sqrt(groups / (groups - 1) * sum(total * total for total in totals.values())) / n


def exclusion_reason(match):
    """Why a match neither moves ratings nor gets scored, or None if it does. Agrees with elo.is_rated."""
    if match["winner_id"] == match["loser_id"]:
        return "same winner and loser id"
    if match["outcome"] != "completed":
        return match["outcome"]
    if match["best_of"] not in (3, 5):
        return f"best of {match['best_of']}"
    return None


def exclusion_counts(matches, start, end):
    """Counter of exclusion reasons for matches in [start, end); rated matches count under None."""
    return Counter(exclusion_reason(match) for match in matches if start <= match["tourney_date"] < end)


def is_monday(date):
    return datetime.date(date // 10000, date // 100 % 100, date % 100).weekday() == 0


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
    """Log loss on the tuning period for every K rule, ordinary and surface-blended.

    Ratings stop at TRAIN_START. Later weeks cannot change a tuning-period prediction, so this only saves time.
    """
    table = []
    for rule in K_RULES:
        predictions, _ = run_elo(matches, rule, before=TRAIN_START)
        tuning = [p for p in predictions if in_period(p, TUNING_START, TRAIN_START)]
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


def print_period_counts(matches):
    """Rows, rated matches, and exclusions in every period and tour. Counts only, so the reserved period is safe to show."""
    print("\nTour-level rows by period")
    for name, start, end in PERIODS:
        for tour in TOURS:
            rows = [m for m in matches if m["tour"] == tour and period(m["tourney_date"]) == name]
            if not rows:
                continue
            reasons = Counter(exclusion_reason(match) for match in rows)
            off_monday = sum(1 for m in rows if exclusion_reason(m) is None and not is_monday(m["tourney_date"]))
            excluded = ", ".join(f"{reason} {count:,}" for reason, count in reasons.most_common() if reason is not None)
            dates = [m["tourney_date"] for m in rows]
            print(
                f"   {name:<11}{tour}  weeks {min(dates)} to {max(dates)}  rows {len(rows):>7,}  rated {reasons[None]:>7,}"
                f"  rated off-Monday {off_monday:>6,}  excluded: {excluded}"
            )


def select(predictions, probabilities, keep):
    pairs = [(prediction, p) for prediction, p in zip(predictions, probabilities) if keep(prediction["match"])]
    return [prediction for prediction, _ in pairs], [p for _, p in pairs]


def print_comparison(title, predictions, elo_p, surface_predictions, surface_p):
    print_header(title)
    print_scores("Always 0.5", score([0.5] * len(predictions)))
    print_scores("Elo", score(elo_p))
    print_scores("Surface Elo", score(surface_p))

    difference, error = paired_log_loss_difference(elo_p, surface_p)
    weeks = [prediction["match"]["tourney_date"] for prediction in predictions]
    week_error = clustered_standard_error(log_loss_differences(elo_p, surface_p), weeks)
    print(f"   Surface Elo minus Elo, log loss per match {difference:+.4f}")
    print(f"      standard error, matches independent        {error:.4f}")
    print(f"      standard error, clustered by tourney_date  {week_error:.4f} ({len(set(weeks)):,} clusters)")

    ranks = rank_accuracy(predictions, elo_p)
    surface_ranks = rank_accuracy(surface_predictions, surface_p)
    print(
        f"   Both ranks known and different, {ranks['matches']:,} matches: higher-ranked {ranks['rank']:.2%},"
        f" Elo {ranks['elo']:.2%}, surface Elo {surface_ranks['elo']:.2%}"
    )


def print_groups(title, predictions, elo_p, surface_predictions, surface_p, key):
    elo_groups = grouped(predictions, elo_p, key)
    surface_groups = grouped(surface_predictions, surface_p, key)
    print_header(title)
    for group in elo_groups:
        print_scores(f"{group} Elo", elo_groups[group])
        print_scores(f"{group} Surface Elo", surface_groups[group])
    better = sum(surface_groups[g]["log_loss"] < elo_groups[g]["log_loss"] for g in elo_groups)
    print(f"   Surface Elo has the lower log loss in {better} of {len(elo_groups)} groups")


def print_calibration(title, elo_p, surface_p):
    print(f"\nCalibration, {title}")
    print(f"   {'favorite p':<12} {'Elo n':>8}  predicted  observed  {'Surface n':>9}  predicted  observed")
    elo_rows = {round(row[0], 1): row for row in calibration(elo_p)}
    surface_rows = {round(row[0], 1): row for row in calibration(surface_p)}
    for low in sorted(set(elo_rows) | set(surface_rows)):
        parts = []
        for rows, width in ((elo_rows, 8), (surface_rows, 9)):
            if low in rows:
                _, _, count, predicted, observed = rows[low]
                parts.append(f"{count:>{width},}  {predicted:>9.3f}  {observed:>8.3f}")
            else:
                parts.append(f"{'':>{width}}  {'':>9}  {'':>8}")
        print(f"   {low:.1f}-{low + 0.1:.1f}      {'  '.join(parts)}")


def main():
    matches = load_matches()

    table = tuning_scores(matches)
    print(f"Tuning period {TUNING_START} to {TRAIN_START} (log loss, lower is better)")
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

    print_period_counts(matches)

    # Weeks from DEVELOPMENT_END on are the reserved final evaluation. They are not replayed here.
    elo_predictions, _ = run_elo(matches, elo_rule, before=DEVELOPMENT_END)
    surface_predictions, _ = run_elo(matches, surface_rule, before=DEVELOPMENT_END)
    elo_all = [win_probability(p) for p in elo_predictions]
    surface_all = [win_probability(p, surface_weight) for p in surface_predictions]

    windows = [(name, start, end) for name, start, end in PERIODS if name in SCORED_PERIODS]
    windows.append(("development", DEVELOPMENT_START, DEVELOPMENT_END))
    for name, start, end in windows:
        for tour_label, tours in TOUR_GROUPS:
            def keep(match, start=start, end=end, tours=tours):
                return start <= match["tourney_date"] < end and match["tour"] in tours

            predictions, elo_p = select(elo_predictions, elo_all, keep)
            surface_predictions_in, surface_p = select(surface_predictions, surface_all, keep)
            title = f"{name} {start} to {end}, {tour_label}"
            print_comparison(title, predictions, elo_p, surface_predictions_in, surface_p)
            if name in ("train", "validation"):
                print_groups(
                    f"{title}, by surface", predictions, elo_p, surface_predictions_in, surface_p,
                    lambda match: match["surface"] or "missing",
                )
                print_calibration(title, elo_p, surface_p)
            if name == "development" and tour_label != "Both tours":
                print_groups(
                    f"{title}, by year", predictions, elo_p, surface_predictions_in, surface_p,
                    lambda match: match["tourney_date"] // 10000,
                )

    window, elo_p = select(elo_predictions, elo_all, lambda m: DEVELOPMENT_START <= m["tourney_date"] < DEVELOPMENT_END)
    _, surface_p = select(surface_predictions, surface_all, lambda m: DEVELOPMENT_START <= m["tourney_date"] < DEVELOPMENT_END)
    path = RESULTS_DIR / "phase2_development_predictions.csv"
    save_predictions(path, window, elo_p, surface_p)
    print(f"\nDevelopment-period predictions written to {path}")


if __name__ == "__main__":
    main()
