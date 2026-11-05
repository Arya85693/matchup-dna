import csv
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TOURS = ("ATP", "WTA")

SURFACES = {"hard": "Hard", "clay": "Clay", "grass": "Grass", "carpet": "Carpet"}

# Score text that means no real score was recorded.
UNKNOWN_SCORES = {"", "&NBSP;", "UNK", "NA", "?"}


def match_files(tour, data_dir=DATA_DIR):
    """Tour-level singles files only: atp_matches_YYYY.csv or wta_matches_YYYY.csv."""
    prefix = tour.lower()
    pattern = re.compile(prefix + r"_matches_\d{4}\.csv")
    folder = Path(data_dir) / prefix
    return sorted(path for path in folder.iterdir() if pattern.fullmatch(path.name))


def to_int(value):
    """An empty cell is missing (None), never zero."""
    value = value.strip()
    if value == "":
        return None
    return int(float(value))


def normalize_surface(value):
    return SURFACES.get(value.strip().lower())


def match_outcome(score):
    """The one place that decides how a match ended.

    Returns "completed", "retired", "walkover", "default", "abandoned", or "unknown".
    """
    text = score.strip().upper()
    if text in UNKNOWN_SCORES:
        return "unknown"
    tokens = text.split()
    if "W/O" in tokens or "WALKOVER" in tokens:
        return "walkover"
    if any(token.startswith("DEF") for token in tokens):
        return "default"
    if any(token.startswith("RET") for token in tokens):
        return "retired"
    if "ABD" in tokens or "AB" in tokens or "ABANDONED" in tokens or "UNFINISHED" in tokens:
        return "abandoned"
    return "completed"


def parse_match(row, tour):
    return {
        "tour": tour,
        # A few older WTA events reuse match_num across rounds, so the round is part of the key.
        "key": (tour, row["tourney_id"], row["match_num"], row["round"]),
        "tourney_id": row["tourney_id"],
        "tourney_name": row["tourney_name"],
        "tourney_level": row["tourney_level"],
        "tourney_date": int(row["tourney_date"]),
        "match_num": row["match_num"],
        "surface": normalize_surface(row["surface"]),
        "round": row["round"],
        "best_of": to_int(row["best_of"]),
        "score": row["score"].strip(),
        "outcome": match_outcome(row["score"]),
        "winner_id": int(row["winner_id"]),
        "winner_name": row["winner_name"],
        "winner_rank": to_int(row["winner_rank"]),
        "loser_id": int(row["loser_id"]),
        "loser_name": row["loser_name"],
        "loser_rank": to_int(row["loser_rank"]),
        "w_ace": to_int(row["w_ace"]),
        "w_svpt": to_int(row["w_svpt"]),
        "w_first_in": to_int(row["w_1stIn"]),
        "l_ace": to_int(row["l_ace"]),
        "l_svpt": to_int(row["l_svpt"]),
        "l_first_in": to_int(row["l_1stIn"]),
    }


def load_matches(tours=TOURS, data_dir=DATA_DIR):
    matches = []
    for tour in tours:
        for path in match_files(tour, data_dir):
            with open(path, "r", encoding="utf-8", newline="") as file:
                for row in csv.DictReader(file):
                    matches.append(parse_match(row, tour))
    return matches


def load_players(tours=TOURS, data_dir=DATA_DIR):
    """Player lookup keyed by (tour, player_id). ATP and WTA ids overlap, so the tour is part of the key."""
    players = {}
    for tour in tours:
        path = Path(data_dir) / tour.lower() / f"{tour.lower()}_players.csv"
        with open(path, "r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                name = f"{row['name_first']} {row['name_last']}".strip()
                players[(tour, int(row["player_id"]))] = {
                    "name": name,
                    "hand": row["hand"],
                    "ioc": row["ioc"],
                    "dob": to_int(row["dob"]),
                }
    return players


if __name__ == "__main__":
    matches = load_matches()
    players = load_players()
    for tour in TOURS:
        count = sum(1 for match in matches if match["tour"] == tour)
        print(f"{tour} matches: {count:,}")
    print(f"Total matches: {len(matches):,}")
    print(f"Players: {len(players):,}")
