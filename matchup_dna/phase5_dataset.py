"""The model side of Phase 5: every model match from January 2021 to October 2026, with the chronological
probabilities the earlier phases already saved, ready to be joined to market prices.

Nothing is refitted. The probabilities come from results/phase4/experiments/posthoc_longrun_predictions_corrected.csv,
where every prediction was made by a model fitted only on earlier matches:

    2021-2023 (validation)          Elo and surface Elo from Phase 3; Phase 3 and Phase 4 fitted on 2010-2020
    2024 - May 2026 (retrospective) Elo, surface Elo, Phase 3 saved by the Phase 3 final run; Phase 4 fitted 2010-2023
    June - October 2026 (held-out)  Phase 3 and Phase 4 from the corrected held-out rebuild (Phase 4 erratum 1),
                                    fitted on 2010 to May 2026

The match details (players, names, round, level, surface) come from the files those predictions were made from:
results/phase3/validation.csv, results/phase3/reserved_features.csv, and for June-October 2026 the corrected
held-out predictions plus the corrected post-hoc match table. Every match must be found, with the same outcome.
"""
import csv

from matchup_dna.elo import RESULTS_DIR

PHASE4_EXPERIMENTS = RESULTS_DIR / "phase4" / "experiments"
PREDICTIONS = PHASE4_EXPERIMENTS / "posthoc_longrun_predictions_corrected.csv"
SOURCES = {
    "2021-2023 validation": RESULTS_DIR / "phase3" / "validation.csv",
    "2024-May 2026 retrospective": RESULTS_DIR / "phase3" / "reserved_features.csv",
    "Jun-Oct 2026 held-out": (RESULTS_DIR / "phase4" / "corrected" / "heldout_predictions.csv",
                              PHASE4_EXPERIMENTS / "posthoc_disagreement_matches_corrected.csv"),
}
PERIODS = tuple(SOURCES)
MODELS = ("Elo", "Surface Elo", "Phase 3", "Phase 4")
PHASE5_DIR = RESULTS_DIR / "phase5"


def read(path):
    with open(path, encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def number(text):
    text = (text or "").strip()
    if text == "":
        return None
    value = float(text)
    return int(value) if value.is_integer() and "." not in text else value


def details():
    """{match_id: details} for every period, from the files the saved predictions were made from."""
    found = {}
    for period in PERIODS[:2]:
        for row in read(SOURCES[period]):
            found[row["match_id"]] = {
                "tourney_level": row["tourney_level"], "surface": row["surface"], "round": row["round"],
                "best_of": number(row["best_of"]), "a_id": int(row["a_id"]), "b_id": int(row["b_id"]),
                "a_name": row["a_name"], "b_name": row["b_name"]}
    ids_file, table_file = SOURCES[PERIODS[2]]
    ids = {row["match_id"]: row for row in read(ids_file)}
    for row in read(table_file):
        found[row["match_id"]] = {
            "tourney_level": row["tourney_level"], "surface": row["surface"], "round": row["round"],
            "best_of": number(row["best_of"]), "a_id": int(ids[row["match_id"]]["a_id"]),
            "b_id": int(ids[row["match_id"]]["b_id"]), "a_name": row["a_name"], "b_name": row["b_name"]}
    return found


DATASET_PATH = PHASE5_DIR / "dataset.csv"
SPLITS = {"2021-2023 validation": "development", "2024-May 2026 retrospective": "evaluation",
          "Jun-Oct 2026 held-out": "evaluation"}
FIELDS = ("match_id", "split", "period", "tour", "tourney_level", "surface", "round", "best_of", "tourney_date",
          "start", "a_id", "b_id", "a_name", "b_name", "a_rank", "b_rank", "a_won", *MODELS,
          "open_a", "open_b", "close_a", "close_b", "vb_id")


def build_dataset():
    """Every linked model match with usable opening prices, the prices turned to player A's side. Returns (rows,
    link result). Development is 2021-2023; evaluation is January 2024 to October 2026."""
    from matchup_dna import market_link, valuebetennis
    models = model_matches()
    result = market_link.link(valuebetennis.load_valuebetennis(), models)
    rows = []
    for vb_row, m, same in result["links"]:
        if not valuebetennis.has_prices(vb_row, "open"):
            continue
        order = (0, 1) if same else (1, 0)
        close_usable = valuebetennis.has_prices(vb_row, "close")
        rows.append({**{k: m[k] for k in ("match_id", "period", "tour", "tourney_level", "surface", "round",
                                          "best_of", "tourney_date", "a_id", "b_id", "a_name", "b_name", "a_rank",
                                          "b_rank", "a_won", *MODELS)},
                     "split": SPLITS[m["period"]], "start": vb_row["start"].strftime("%Y-%m-%d %H:%M:%S"),
                     "open_a": vb_row["open"][order[0]], "open_b": vb_row["open"][order[1]],
                     "close_a": vb_row["close"][order[0]] if close_usable else None,
                     "close_b": vb_row["close"][order[1]] if close_usable else None, "vb_id": vb_row["vb_id"]})
    rows.sort(key=lambda r: (r["start"], r["match_id"]))
    return rows, result


def save_dataset(rows):
    PHASE5_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATASET_PATH, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({k: ("" if row[k] is None else row[k]) for k in FIELDS} for row in rows)


def check_unlock(protocol_path):
    """Evaluation rows open only with a frozen Phase 5 protocol: a JSON file with "phase": 5 and a "frozen" date."""
    import json
    from pathlib import Path
    path = Path(protocol_path)
    if not path.exists():
        raise PermissionError(f"{path} does not exist; the evaluation rows stay closed until Phase 5 is frozen")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("phase") != 5 or not protocol.get("frozen"):
        raise PermissionError(f"{path} is not a frozen Phase 5 protocol")


def load(split, unseal_with=None):
    """Rows of one split. "development" is always open; "evaluation" needs a frozen Phase 5 protocol."""
    if split not in ("development", "evaluation"):
        raise ValueError(f"unknown split {split!r}")
    if split == "evaluation":
        check_unlock(unseal_with) if unseal_with is not None else check_unlock(PHASE5_DIR / "missing")
    found = []
    for row in read(DATASET_PATH):
        if row["split"] != split:
            continue
        parsed = {k: row[k] for k in ("match_id", "split", "period", "tour", "tourney_level", "surface", "round",
                                      "start", "a_name", "b_name")}
        for k in ("tourney_date", "a_won", "a_id", "b_id", "vb_id", "best_of"):
            parsed[k] = number(row[k])
        for k in ("a_rank", "b_rank", "open_a", "open_b", "close_a", "close_b", *MODELS):
            parsed[k] = None if row[k] == "" else float(row[k])
        found.append(parsed)
    return found


def model_matches():
    """Every model match, January 2021 to October 2026, in the order of the saved predictions file."""
    info = details()
    rows = []
    for row in read(PREDICTIONS):
        extra = info.get(row["match_id"])
        if extra is None:
            raise SystemExit(f"{row['match_id']} has a saved prediction but no match details; stopping.")
        rows.append({"match_id": row["match_id"], "period": row["period"], "tour": row["tour"],
                     "tourney_date": int(row["tourney_date"]), "a_won": int(row["a_won"]),
                     "a_rank": number(row["a_rank"]), "b_rank": number(row["b_rank"]), **extra,
                     **{model: float(row[model]) for model in MODELS}})
    return rows
