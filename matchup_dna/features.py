import csv
import hashlib

from matchup_dna.elo import ELO_K, RESULTS_DIR, SURFACE_ELO_K, SURFACE_WEIGHT, blended_rating, expected_score, run_elo
from matchup_dna.load import load_matches
from matchup_dna.periods import PERIODS, TRAIN_START, period

DATASET_DIR = RESULTS_DIR / "phase3"
SPLITS = ("train", "validation", "reserved")
FILES = {"train": "train.csv", "validation": "validation.csv", "reserved": "reserved_features.csv"}
LABEL = "a_won"


def match_id(match):
    return "|".join(str(part) for part in match["key"])


def player_a_is_winner(match):
    """Player A is picked by a hash of the match id and the two player ids, so the choice never depends on who won."""
    low, high = sorted((match["winner_id"], match["loser_id"]))
    digest = hashlib.sha256(f"{match_id(match)}|{low}|{high}".encode()).digest()
    return (low, high)[digest[0] % 2] == match["winner_id"]


def difference(a, b):
    if a is None or b is None:
        return None
    return a - b


def feature_row(elo, surface):
    """One pre-match row from the same match's ordinary Elo and surface Elo predictions.

    Both predictions hold start-of-week ratings, so nothing here comes from this match or this week.
    Ranks are Sackmann's rank as of the tournament date.
    """
    match = elo["match"]
    a_won = player_a_is_winner(match)
    a, b = ("winner", "loser") if a_won else ("loser", "winner")

    a_blended = blended_rating(surface[f"{a}_rating"], surface[f"{a}_surface_rating"], SURFACE_WEIGHT)
    b_blended = blended_rating(surface[f"{b}_rating"], surface[f"{b}_surface_rating"], SURFACE_WEIGHT)
    return {
        "match_id": match_id(match),
        "tourney_date": match["tourney_date"],
        "period": period(match["tourney_date"]),
        "tour": match["tour"],
        "tourney_level": match["tourney_level"],
        "surface": match["surface"] or "",
        "round": match["round"],
        "best_of": match["best_of"],
        "a_id": match[f"{a}_id"],
        "a_name": match[f"{a}_name"],
        "b_id": match[f"{b}_id"],
        "b_name": match[f"{b}_name"],
        "a_elo": elo[f"{a}_rating"],
        "b_elo": elo[f"{b}_rating"],
        "elo_diff": elo[f"{a}_rating"] - elo[f"{b}_rating"],
        "a_elo_matches": elo[f"{a}_played"],
        "b_elo_matches": elo[f"{b}_played"],
        "a_surface_elo_overall": surface[f"{a}_rating"],
        "b_surface_elo_overall": surface[f"{b}_rating"],
        "a_surface_elo_surface": surface[f"{a}_surface_rating"],
        "b_surface_elo_surface": surface[f"{b}_surface_rating"],
        "a_surface_matches": surface.get(f"{a}_surface_played"),
        "b_surface_matches": surface.get(f"{b}_surface_played"),
        "a_surface_elo_blended": a_blended,
        "b_surface_elo_blended": b_blended,
        "surface_elo_diff": a_blended - b_blended,
        "elo_probability": expected_score(elo[f"{a}_rating"], elo[f"{b}_rating"]),
        "surface_elo_probability": expected_score(a_blended, b_blended),
        "a_rank": match[f"{a}_rank"],
        "b_rank": match[f"{b}_rank"],
        "rank_diff": difference(match[f"{a}_rank"], match[f"{b}_rank"]),
        LABEL: int(a_won),
    }


def build_rows(matches, start=TRAIN_START):
    """Feature rows for every rated match from `start` on, in replay order.

    Ratings are replayed from the first match with the fixed Phase 2 settings and keep updating week by
    week through the reserved period.
    """
    elo_predictions, _ = run_elo(matches, ELO_K)
    surface_predictions, _ = run_elo(matches, SURFACE_ELO_K)
    rows = []
    for elo, surface in zip(elo_predictions, surface_predictions):
        if elo["match"]["key"] != surface["match"]["key"]:
            raise ValueError("Elo and surface Elo replays are out of step")
        if elo["match"]["tourney_date"] >= start:
            rows.append(feature_row(elo, surface))
    return rows


def split_rows(rows):
    """Train, validation, and reserved rows. Reserved rows lose the label here, before anything is written."""
    splits = {name: [] for name in SPLITS}
    for row in rows:
        if row["period"] not in splits:
            raise ValueError(f"{row['match_id']} is in the {row['period']} period, which has no Phase 3 split")
        if row["period"] == "reserved":
            row = {field: value for field, value in row.items() if field != LABEL}
        splits[row["period"]].append(row)
    return splits


def split_problems(splits):
    """Every way the splits break the date boundaries or the label rule; an empty list means none."""
    bounds = {name: (start, end) for name, start, end in PERIODS}
    problems = []
    seen = {}
    for name in SPLITS:
        start, end = bounds[name]
        for row in splits[name]:
            date = row["tourney_date"]
            if date < start or (end is not None and date >= end):
                problems.append(f"{row['match_id']} dated {date} is outside {name}")
            if row["match_id"] in seen:
                problems.append(f"{row['match_id']} is in both {seen[row['match_id']]} and {name}")
            seen[row["match_id"]] = name
            if (LABEL in row) != (name != "reserved"):
                problems.append(f"{row['match_id']} in {name} has the wrong label columns")
    return problems


def save_split(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    splits = split_rows(build_rows(load_matches()))
    problems = split_problems(splits)
    if problems:
        raise SystemExit("Split check failed:\n" + "\n".join(problems[:20]))

    print(f"Phase 3 dataset written to {DATASET_DIR}")
    for name in SPLITS:
        rows = splits[name]
        dates = [row["tourney_date"] for row in rows]
        save_split(DATASET_DIR / FILES[name], rows)
        line = f"   {FILES[name]:<24} {len(rows):>7,} rows, tourney weeks {min(dates)} to {max(dates)}"
        if name != "reserved":
            line += f", player A won {sum(row[LABEL] for row in rows) / len(rows):.2%}"
        print(line)
    print("Reserved rows carry pre-match features only. Their outcomes are not written.")


if __name__ == "__main__":
    main()
