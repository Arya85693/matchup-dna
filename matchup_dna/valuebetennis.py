"""Reader for the Valuebetennis open odds files (Phase 5).

Source: https://www.valuebetennis.com/en/donnees.htm, CC BY 4.0 (attribution required). Six season files,
valuebetennis-matchs-2021.csv to valuebetennis-matchs-2026.csv, in data/external/valuebetennis/. They are private
copies and are never committed (data/ is gitignored).

Each row is one match: a UTC start time, the tournament (one tournoi_id per edition), its category and gender, the
surface (in French), a round code, the two players with Valuebetennis ids, an opening and a closing decimal price
for each player, the winner's id, the score, and a mostly empty duration.

What the files do not say, and the reader does not assume:
- When the opening and closing prices were recorded. "Opening" is treated as the earliest recorded price and
  "closing" as the last one before the start; neither has its own timestamp.
- Which rows are doubles. The download page says singles only, but some doubles teams appear as two "players"
  (Makoto Ninomiya v Ena Shibahara, Abu Dhabi 2021). No text rule detects them; they fall out at the join, where no
  singles match between the two names exists.

Round codes are ordinal. At tour level 1-3 are qualifying rounds, 4 is the first main-draw round, then 5, 6, 7 (8 at
some events), 9 the quarterfinal, 10 the semifinal and 12 the final; team events use 13-17.
"""
import csv
import datetime
import hashlib
from pathlib import Path

from matchup_dna.load import DATA_DIR

VALUEBET_DIR = DATA_DIR / "external" / "valuebetennis"
YEARS = tuple(range(2021, 2027))
EXPECTED_COLUMNS = (
    "match_id", "date", "tournoi", "tournoi_id", "categorie", "genre", "surface", "tour", "joueur1", "joueur1_id",
    "joueur2", "joueur2_id", "cote1_ouverture", "cote2_ouverture", "cote1_cloture", "cote2_cloture", "vainqueur_id",
    "score", "duree_min",
)
# Valuebetennis category -> Sackmann tourney_level ("C" and "ITF" have no Sackmann counterpart).
LEVELS = {"Grand Chelem": "G", "Masters": "M", "Main tour": "A", "Coupe Davis / BJK Cup": "D", "Challenger": "C",
          "ITF": "ITF", "": None}
TOUR_LEVELS = ("G", "M", "A", "D")  # the levels Sackmann's tour-level files (and so the model) cover
SURFACES = {"dur": ("Hard", False), "dur intérieur": ("Hard", True), "terre battue": ("Clay", False),
            "gazon": ("Grass", False), "moquette intérieur": ("Carpet", True)}
TOURS = {"atp": "ATP", "wta": "WTA"}
QUALIFYING_ROUNDS = (1, 2, 3)
ROUND_NAMES = {9: "QF", 10: "SF", 12: "F"}  # the codes that are the same round at every event


def file_path(year, directory=VALUEBET_DIR):
    return Path(directory) / f"valuebetennis-matchs-{year}.csv"


def files(directory=VALUEBET_DIR):
    return [file_path(year, directory) for year in YEARS if file_path(year, directory).exists()]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def price(text):
    """A decimal price above 1.0, else None (blank, unparseable, or impossible)."""
    try:
        value = float((text or "").strip())
    except ValueError:
        return None
    return value if value > 1.0 else None


def integer(text):
    text = (text or "").strip()
    return int(text) if text.lstrip("-").isdigit() else None


def parse(row, source=""):
    """One file row as a dict of typed fields. Raw text fields are kept under their original names."""
    start = datetime.datetime.strptime(row["date"].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    surface, indoor = SURFACES.get(row["surface"].strip(), (None, None))
    first, second = row["joueur1_id"].strip(), row["joueur2_id"].strip()
    winner = row["vainqueur_id"].strip()
    return {
        "vb_id": int(row["match_id"]), "start": start, "day": start.date(),
        "midnight": start.time() == datetime.time(0, 0),  # no real clock time recorded
        "tournament": row["tournoi"].strip(), "edition": row["tournoi_id"].strip(),
        "category": row["categorie"].strip(), "level": LEVELS.get(row["categorie"].strip()),
        "tour": TOURS.get(row["genre"].strip()), "surface": surface, "indoor": indoor,
        "round_code": integer(row["tour"]),
        "names": (row["joueur1"].strip(), row["joueur2"].strip()), "ids": (first, second),
        "open": (price(row["cote1_ouverture"]), price(row["cote2_ouverture"])),
        "close": (price(row["cote1_cloture"]), price(row["cote2_cloture"])),
        "winner": 0 if winner == first else 1 if winner == second else None,
        "score": row["score"].strip(), "duration": integer(row["duree_min"]), "source": source,
    }


def is_qualifying(row):
    return row["level"] in ("G", "M", "A") and row["round_code"] in QUALIFYING_ROUNDS


def tour_level_singles(row):
    """Rows that can match a Sackmann tour-level main-draw match: tour levels, both tours, no qualifying, no
    obvious doubles pair ("A/B" names). Other doubles rows are removed by the join."""
    return (row["level"] in TOUR_LEVELS and row["tour"] is not None and not is_qualifying(row)
            and not any("/" in name for name in row["names"]))


def has_prices(row, which="open"):
    return None not in row[which]


def load_valuebetennis(directory=VALUEBET_DIR):
    """Every row of every season file, parsed. Raises if a file's header differs from EXPECTED_COLUMNS."""
    rows = []
    for path in files(directory):
        with open(path, encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, delimiter=";")
            if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
                raise ValueError(f"{path.name}: unexpected columns {reader.fieldnames}")
            rows.extend(parse(row, path.name) for row in reader)
    return rows
