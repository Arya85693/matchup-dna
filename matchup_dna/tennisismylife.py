"""TennisIsMyLife (TML) CSVs, read from data/external/tennisismylife/.

The files use Jeff Sackmann's match layout plus an `indoor` column: one row per match, written from the
winner's side (winner_id, w_svpt, ...), with serve and return point counts. ATP player ids are the ATP's own
codes ("CD85"); WTA ids are numbers. They are private raw files: they stay out of git, and only aggregate
results derived from them are published.

The seal. In a winner/loser layout, knowing which player sits in winner_id is knowing the result. So every
row whose tourney_date is on or after SEAL_DATE (the first held-out tournament week) is rewritten by
load_tml() before any other code sees it. Its two players become player A and player B, ordered by id (so
the order says nothing about who won), with their pre-match fields (rank, seed, entry, age, ...). The score,
minutes, and every statistic column are deleted, leaving only flags saying whether statistics exist. Only a
frozen Phase 4 protocol file unlocks the original rows.

Tournaments dated before SEAL_DATE are not held out: the 2026 French Open (week of 24-25 May) is already in
Sackmann's files and in the Phase 3 reserved evaluation, so its rows stay open here.
"""
import csv
from pathlib import Path

from matchup_dna.load import DATA_DIR
from matchup_dna.tennisdata import check_unseal

TML_DIR = DATA_DIR / "external" / "tennisismylife"
SEAL_DATE = 20260601

PLAYER_FIELDS = ("id", "seed", "entry", "name", "hand", "ht", "ioc", "age", "rank", "rank_points")
STAT_FIELDS = ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")
EXPECTED_COLUMNS = (
    "tourney_id", "tourney_name", "surface", "draw_size", "tourney_level", "indoor", "tourney_date", "match_num",
    *(f"winner_{field}" for field in PLAYER_FIELDS), *(f"loser_{field}" for field in PLAYER_FIELDS),
    "score", "best_of", "round", "minutes",
    *(f"w_{field}" for field in STAT_FIELDS), *(f"l_{field}" for field in STAT_FIELDS),
)
METADATA_COLUMNS = ("tourney_id", "tourney_name", "surface", "draw_size", "tourney_level", "indoor",
                    "tourney_date", "match_num", "best_of", "round")
OUTCOME_COLUMNS = tuple(column for column in EXPECTED_COLUMNS if column not in METADATA_COLUMNS)

# File name -> tour. The ongoing-tournament files hold events still in progress when they were saved.
FILES = {
    "2025_atp.csv": ("ATP", False), "2026_atp.csv": ("ATP", False), "ongoing_tourneys.csv": ("ATP", True),
    "2025_wta.csv": ("WTA", False), "2026_wta.csv": ("WTA", False), "wta_ongoing_tourneys.csv": ("WTA", True),
}


def tml_files(directory=TML_DIR):
    """The six expected files, after checking each has exactly the 50 expected columns in order."""
    paths = []
    for name in FILES:
        path = Path(directory) / name
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing")
        with open(path, encoding="utf-8", newline="") as file:
            header = tuple(next(csv.reader(file)))
        if header != EXPECTED_COLUMNS:
            raise ValueError(f"{name} does not have the expected {len(EXPECTED_COLUMNS)} columns")
        paths.append(path)
    return paths


def blank(value):
    return (value or "").strip() == ""


def has_stats(row, prefix):
    """True when the serve-point total is present for that side ("w" or "l")."""
    return not blank(row[f"{prefix}_svpt"])


def seal(row):
    """Player A and B ordered by id, pre-match fields only, and flags for whether statistics exist."""
    sides = sorted(("winner", "loser"), key=lambda side: row[f"{side}_id"])
    sealed = {column: row[column] for column in METADATA_COLUMNS}
    for letter, side in zip(("a", "b"), sides):
        for field in PLAYER_FIELDS:
            sealed[f"{letter}_{field}"] = row[f"{side}_{field}"]
    sealed["has_serve_stats"] = has_stats(row, "w") and has_stats(row, "l")
    sealed["has_all_stats"] = all(not blank(row[f"{prefix}_{field}"]) for prefix in ("w", "l") for field in STAT_FIELDS)
    for key in ("tour", "ongoing", "source_file", "sealed"):
        sealed[key] = row[key]
    return sealed


def load_tml(directory=TML_DIR, unseal_with=None):
    """Every TML row with tour, ongoing, source_file, and sealed added. Rows dated SEAL_DATE or later are
    sealed (see the module notes) unless unseal_with is a frozen Phase 4 protocol path. This is the only
    reader of the TML files."""
    if unseal_with is not None:
        check_unseal(unseal_with)
    rows = []
    for path in tml_files(directory):
        tour, ongoing = FILES[path.name]
        with open(path, encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                row.update(tour=tour, ongoing=ongoing, source_file=path.name,
                           sealed=int(row["tourney_date"]) >= SEAL_DATE)
                rows.append(seal(row) if row["sealed"] and unseal_with is None else row)
    return rows


def editions(rows):
    """{(tour, tourney_id): edition} with start and end (the earliest and latest tourney_date on its rows),
    name, rows, and ongoing. TML's 2026 files date each round separately (the 2026 Australian Open runs from
    20260120 for R128 to 20260201 for the final), so an edition's start is its earliest date."""
    found = {}
    for row in rows:
        key = (row["tour"], row["tourney_id"])
        date = int(row["tourney_date"])
        edition = found.setdefault(key, {"tour": row["tour"], "tourney_id": row["tourney_id"],
                                         "name": row["tourney_name"], "start": date, "end": date, "rows": 0,
                                         "ongoing": False, "level": row["tourney_level"]})
        edition["start"], edition["end"] = min(edition["start"], date), max(edition["end"], date)
        edition["rows"] += 1
        edition["ongoing"] = edition["ongoing"] or row["ongoing"]
    return found


def players(row):
    """The two player ids of a row, open or sealed, in a fixed order that does not depend on the result."""
    if row["sealed"] and "a_id" in row:
        return row["a_id"], row["b_id"]
    return tuple(sorted((row["winner_id"], row["loser_id"])))
