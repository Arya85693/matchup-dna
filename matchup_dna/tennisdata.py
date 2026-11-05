"""TennisData.app season CSVs, read from data/external/tennisdata_app/.

Source: https://tennisdata.app/downloads/ (free season files). The user located the site's terms of service at
https://tennisdata.app/terms/ (updated 2 November 2026). The files are private raw data: they stay out of git,
and only aggregate results derived from them are published.

The seal. Every row whose match date (UTC) is on or after SEAL_START belongs to the candidate Phase 4 held-out
period. load_provider() removes those rows' outcome, score, odds, and statistic columns before returning them,
so code written before the Phase 4 protocol is frozen cannot see how a sealed match ended. Only a frozen Phase 4
protocol file unlocks them.
"""
import csv
import datetime
import json
from pathlib import Path

from matchup_dna.load import DATA_DIR

PROVIDER_DIR = DATA_DIR / "external" / "tennisdata_app"
SEAL_START = datetime.date(2026, 6, 1)
SIDES = ("home", "away")

EXPECTED_COLUMNS = (
    "match_id", "season_year", "tour_type", "tour_type_human", "date_timestamp", "date_human", "tournament",
    "round", "surface", "surface_id", "status", "status_extra", "home_name", "away_name", "home_id", "away_id",
    "home_rank", "away_rank", "home_points", "away_points", "winner_code", "home_set_score", "away_set_score",
    *(f"{side}_set_{number}_score" for number in range(1, 6) for side in SIDES),
    "home_odds_match_winner", "away_odds_match_winner", "home_odds_first_set_winner", "away_odds_first_set_winner",
    *(f"{side}_{field}" for field in ("aces", "double_faults", "service_points_won_perc", "return_points_won_perc",
                                      "break_points_won_perc", "break_points_saved_perc") for side in SIDES),
)

STAT_FIELDS = ("aces", "double_faults", "service_points_won_perc", "return_points_won_perc",
               "break_points_won_perc", "break_points_saved_perc")
OUTCOME_COLUMNS = ("status", "status_extra", "winner_code", "home_set_score", "away_set_score") + tuple(
    f"{side}_set_{number}_score" for number in range(1, 6) for side in SIDES)
ODDS_COLUMNS = ("home_odds_match_winner", "away_odds_match_winner",
                "home_odds_first_set_winner", "away_odds_first_set_winner")
STAT_COLUMNS = tuple(f"{side}_{field}" for field in STAT_FIELDS for side in SIDES)
SEALED_COLUMNS = OUTCOME_COLUMNS + ODDS_COLUMNS + STAT_COLUMNS

# tour_type -> (tour, circuit). Circuit "tour" is ATP Tour / WTA Tour; "challenger" is ATP Challenger / WTA 125.
TOUR_TYPES = {"1": ("ATP", "tour"), "2": ("WTA", "tour"), "3": ("ATP", "challenger"), "4": ("WTA", "challenger")}

# Provider round names and the Sackmann round codes they correspond to. Team events and round robins have no round.
ROUNDS = {"1/64-finals": "R128", "1/32-finals": "R64", "1/16-finals": "R32", "1/8-finals": "R16",
          "Quarter-finals": "QF", "Semi-finals": "SF", "Final": "F", "3rd place": "BR", "Qualifier": "Q", "": None}

GRAND_SLAMS = ("Australian Open", "French Open", "Wimbledon", "US Open")


def number(value):
    """A blank cell is missing (None), never zero."""
    value = (value or "").strip()
    return None if value == "" else float(value)


def provider_files(directory=PROVIDER_DIR):
    """The season files, after checking that each has exactly the 49 expected columns in order."""
    paths = sorted(Path(directory).glob("*-season.csv"))
    for path in paths:
        with open(path, encoding="utf-8", newline="") as file:
            header = tuple(next(csv.reader(file)))
        if header != EXPECTED_COLUMNS:
            raise ValueError(f"{path.name} does not have the expected {len(EXPECTED_COLUMNS)} columns")
    return paths


def match_day(row):
    """The match's calendar date in UTC, from date_timestamp (seconds since 1970)."""
    return datetime.datetime.fromtimestamp(int(float(row["date_timestamp"])), datetime.timezone.utc).date()


def is_qualifying(row):
    return "Qualification" in row["tournament"]


def is_wheelchair(row):
    return " - WIC" in row["tournament"] or "Wheelchair" in row["tournament"]


def is_grand_slam(row):
    return any(name in row["tournament"] for name in GRAND_SLAMS)


def best_of(row):
    """Best-of from the tournament, never from the sets played: ATP Grand Slam main draws are best of 5."""
    main_slam = is_grand_slam(row) and not is_qualifying(row) and not is_wheelchair(row)
    return 5 if row["tour"] == "ATP" and row["circuit"] == "tour" and main_slam else 3


def annotate(row, path):
    """Adds derived fields. The raw columns are left as the strings in the file."""
    tour, circuit = TOUR_TYPES[row["tour_type"]]
    row["tour"] = tour
    row["circuit"] = circuit
    row["day"] = match_day(row)
    row["sealed"] = row["day"] >= SEAL_START
    row["qualifying"] = is_qualifying(row)
    row["wheelchair"] = is_wheelchair(row)
    row["source_file"] = Path(path).name
    return row


def seal(row):
    """Removes everything that reveals how the match went. Keeps only whether serve statistics exist."""
    row["has_serve_stats"] = all(row[f"{side}_service_points_won_perc"].strip() != "" for side in SIDES)
    for column in SEALED_COLUMNS:
        del row[column]
    return row


def check_unseal(protocol_path):
    """Sealed outcomes open only with a frozen Phase 4 protocol: a JSON file with "phase": 4 and a "frozen" date."""
    path = Path(protocol_path)
    if not path.exists():
        raise PermissionError(f"{path} does not exist, so the June 2026 onward outcomes stay sealed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("phase") != 4 or not protocol.get("frozen"):
        raise PermissionError(f"{path} is not a frozen Phase 4 protocol")


def load_provider(directory=PROVIDER_DIR, unseal_with=None):
    """Every provider row with derived fields. Sealed rows lose SEALED_COLUMNS unless unseal_with is a frozen
    Phase 4 protocol path. This is the only reader of the provider files."""
    if unseal_with is not None:
        check_unseal(unseal_with)
    rows = []
    for path in provider_files(directory):
        with open(path, encoding="utf-8", newline="") as file:
            for raw in csv.DictReader(file):
                row = annotate(raw, path)
                if row["sealed"] and unseal_with is None:
                    row = seal(row)
                rows.append(row)
    return rows


def row_key(row):
    """A provider match is identified by tour and match_id: the same match_id is reused across the ATP and
    WTA files for different matches."""
    return row["tour"], row["match_id"]


def is_main_draw(row):
    """Main tour (ATP Tour, WTA Tour) main-draw singles: no Challenger, qualifying, or wheelchair rows."""
    return row["circuit"] == "tour" and not row["qualifying"] and not row["wheelchair"]


def edition_name(tournament):
    """The event a row belongs to. Knockout stages of team events and finals are filed under their own name,
    e.g. "Finals - Turin ATP - Play Offs (indoor)", and belong to the same edition as the group stage."""
    return tournament.replace(" - Play Offs", "")


EDITION_GAP_DAYS = 7


def editions(rows):
    """Groups rows into tournament editions: same tour and edition name, with no gap over EDITION_GAP_DAYS
    between consecutive match days (so Davis Cup ties months apart are separate editions).

    An edition's tourney_date is its first main-draw match day (UTC), as YYYYMMDD. On the 2025 to May 2026
    overlap this equals Sackmann's tourney_date for 82% of editions and is within a day for 96%; Sackmann itself
    dates some Sunday starts on the Sunday and others on the Monday.

    Returns {(tour, match_id): edition}, where an edition is a dict with tour, name, first_day, last_day,
    tourney_date, and rows.
    """
    grouped = {}
    for row in rows:
        grouped.setdefault((row["tour"], edition_name(row["tournament"])), []).append(row)
    by_match = {}
    for (tour, name), members in grouped.items():
        members.sort(key=lambda row: row["day"])
        current = []
        for row in members:
            if current and (row["day"] - current[-1]["day"]).days > EDITION_GAP_DAYS:
                _close(tour, name, current, by_match)
                current = []
            current.append(row)
        _close(tour, name, current, by_match)
    return by_match


def _close(tour, name, members, by_match):
    first, last = members[0]["day"], members[-1]["day"]
    edition = {"tour": tour, "name": name, "first_day": first, "last_day": last,
               "tourney_date": int(first.strftime("%Y%m%d")), "rows": len(members)}
    for row in members:
        by_match[row_key(row)] = edition
