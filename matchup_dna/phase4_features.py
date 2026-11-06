"""The Phase 4 dataset: Phase 3's pre-match rows plus serve-return profiles, round-aware values, recent workload,
and head-to-head, one row per rated match from 2010 to the week of 25 May 2026.

    python -m matchup_dna.phase4_experiment dataset

Steps:

1. Sackmann matches, with TML statistics and minutes filling Sackmann's blanks for 2025-May 2026 under the
   Phase 4 Data Audit precedence rules (merge.combine). Sackmann values are never replaced.
2. Phase 3 rows rebuilt with matchup_dna.features.build_rows. Their training and validation files must hash to the
   values recorded in experiments/frozen_protocol.json, or the build stops: Phase 3 is reproduced, not changed.
3. Profiles (profiles.replay with the settings chosen by the `profiles` command), round-aware values
   (round_aware.round_aware_features), the 14-day workload window (workload.recent_workload), and head-to-head.
4. Files: train.csv (2010-2020), validation.csv (2021-2023), retrospective.csv (2024 to the week of 25 May 2026).
   Development code reads them only through load_phase4(); the retrospective file needs a frozen Phase 4 protocol.
"""
import csv
import hashlib
import io
import json
from collections import defaultdict

from matchup_dna.elo import ELO_K, RESULTS_DIR, SURFACE_ELO_K, is_rated, run_elo, win_probability
from matchup_dna.features import LABEL, TEXT_FIELDS, build_rows, match_id
from matchup_dna.periods import TRAIN_START

DATASET_DIR = RESULTS_DIR / "phase4"
FILES = {"train": "train.csv", "validation": "validation.csv", "retrospective": "retrospective.csv"}
SPLIT_OF_PERIOD = {"train": "train", "validation": "validation", "reserved": "retrospective"}
PROFILE_FIELDS = ("serve", "return", "serve_adjusted", "return_adjusted", "serve_surface", "return_surface",
                  "serve_recent", "return_recent", "first_in", "first_won", "second_won", "ace", "df", "bp_saved",
                  "bp_converted", "serve_attempts", "bp_saved_attempts")
ROUND_FIELDS = ("elo_shift", "surface_elo_shift", "games_won_share", "games", "points", "minutes", "matches",
                "walkovers", "partial", "route_relative_elo", "max_opponent_elo", "unreliable_faced", "entry")
HEAD_TO_HEAD_SHRINK = 5
PHASE4_TEXT = TEXT_FIELDS + ("a_ra_entry", "b_ra_entry")


def backfilled_matches():
    """Sackmann matches with TML filling blank statistics and minutes, and the merge report."""
    from matchup_dna import tennisismylife as tml
    from matchup_dna.audit_tennisdata import sackmann_overlap
    from matchup_dna.audit_tennisismylife import to_sackmann
    from matchup_dna.crosswalk import build_links, load_player_names
    from matchup_dna.merge import combine, tml_match
    from matchup_dna.workload import load_matches_with_workload

    matches = load_matches_with_workload()
    by_key = {match["key"]: match for match in matches}
    rows = [row for row in tml.load_tml() if not row["sealed"]]
    editions = tml.editions(rows)
    linked = [r for r in to_sackmann(rows, sackmann_overlap(), load_player_names()) if r["status"] == "linked"]
    pairs = []
    for result in linked:
        row, target = result["item"], result["target"]
        winner, loser = (target["winner_id"], target["loser_id"]) if result["same_order"] else (
            target["loser_id"], target["winner_id"])
        pairs += [(row["tour"], row["winner_id"], winner), (row["tour"], row["loser_id"], loser)]
    links = build_links(pairs)["links"]
    additions = [(tml_match(r["item"], links, editions[(r["item"]["tour"], r["item"]["tourney_id"])]["start"]),
                  by_key[r["target"]["key"]], r["same_order"]) for r in linked]
    return combine(matches, additions)


def phase3_split_hashes(rows):
    """sha256 of the train and validation files exactly as matchup_dna.features would write them."""
    hashes = {}
    for name in ("train", "validation"):
        subset = [row for row in rows if row["period"] == name]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(subset[0]))
        writer.writeheader()
        writer.writerows(subset)
        hashes[name] = hashlib.sha256(buffer.getvalue().encode("utf-8")).hexdigest()
    return hashes


def check_phase3(rows, protocol_path):
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    frozen = {file_name(key): value for key, value in protocol["inputs"].items()}
    found = phase3_split_hashes(rows)
    problems = [name for name in found if frozen.get(f"{name}.csv") != found[name]]
    if problems:
        raise SystemExit(f"Rebuilt Phase 3 {problems} rows do not match the frozen Phase 3 hashes; stopping.")
    return found


def file_name(path_text):
    """The file name in a recorded path, whichever slash it uses."""
    return path_text.replace("\\", "/").rsplit("/", 1)[-1]


def head_to_head(elo_predictions, shrink=HEAD_TO_HEAD_SHRINK):
    """{match key: (lower player id, value)}: the lower-id player's earlier results against this opponent minus
    Elo's expectation, summed and divided by (meetings + shrink), from earlier tourney_dates only."""
    by_date = defaultdict(list)
    for prediction in elo_predictions:
        by_date[prediction["match"]["tourney_date"]].append(prediction)
    sums, found = {}, {}
    for date in sorted(by_date):
        for prediction in by_date[date]:
            match = prediction["match"]
            low, high = sorted((match["winner_id"], match["loser_id"]))
            total, meetings = sums.get((match["tour"], low, high), (0.0, 0))
            found[match["key"]] = (low, total / (meetings + shrink))
        for prediction in by_date[date]:
            match = prediction["match"]
            low, high = sorted((match["winner_id"], match["loser_id"]))
            p_winner = win_probability(prediction)
            surprise = (1 - p_winner) if match["winner_id"] == low else -(1 - p_winner)
            total, meetings = sums.get((match["tour"], low, high), (0.0, 0))
            sums[(match["tour"], low, high)] = (total + surprise, meetings + 1)
    return found


def load_settings(settings_path):
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    means = {tour: {stat: tuple(v) for stat, v in stats.items()} for tour, stats in settings["means"].items()}
    return settings["settings"], means


def augment(rows, matches, settings_path, start=TRAIN_START):
    """Adds the Phase 4 columns to Phase 3 rows built from `matches`. Used for development and, unchanged, for
    the held-out period, so both are computed by the same code."""
    from matchup_dna.profiles import ProfileEngine, replay
    from matchup_dna.round_aware import round_aware_features
    from matchup_dna.workload import recent_workload

    by_id = {match_id(m): m for m in matches}
    chosen_settings, means = load_settings(settings_path)
    profiles = {}
    for tour, chosen in chosen_settings.items():
        engine = ProfileEngine(means, chosen["half_life"], chosen["prior_matches"])
        found, _ = replay([m for m in matches if m["tour"] == tour], engine, keep_from=start)
        profiles.update(found)

    elo_run, surface_run = run_elo(matches, ELO_K), run_elo(matches, SURFACE_ELO_K)
    round_aware = round_aware_features([m for m in matches if m["tourney_date"] >= start - 10000], elo_run, surface_run)
    targets = [m for m in matches if is_rated(m) and m["tourney_date"] >= start]
    recent = recent_workload(matches, targets)
    h2h = head_to_head(elo_run[0])

    for row in rows:
        match = by_id[row["match_id"]]
        sides = ("winner", "loser") if row["a_id"] == match["winner_id"] else ("loser", "winner")
        for letter, side in zip(("a", "b"), sides):
            values = profiles[(match["key"], side)]
            for field in PROFILE_FIELDS:
                row[f"{letter}_{field}"] = values[field]
            window = recent[(match["key"], side)]
            row[f"{letter}_recent_games"] = window["games"]
            row[f"{letter}_recent_matches"] = window["matches"]
        entry = round_aware[match["key"]]
        row["ra_eligible"] = int(entry["eligible"])
        row["ra_reason"] = entry["reason"] or ""
        for letter, side in zip(("a", "b"), sides):
            values = entry[side] or {}
            for field in ROUND_FIELDS:
                row[f"{letter}_ra_{field}"] = values.get(field)
        row["ra_later_round"] = int(entry["eligible"] and max(
            entry[s]["matches"] + entry[s]["walkovers"] for s in ("winner", "loser")) > 0)
        low, value = h2h[match["key"]]
        row["h2h_a"] = value if row["a_id"] == low else -value
        row["a_qualifier"] = int(match.get(f"{sides[0]}_entry", "") in ("Q", "LL"))
        row["b_qualifier"] = int(match.get(f"{sides[1]}_entry", "") in ("Q", "LL"))
    return rows


def build_dataset(settings_path, phase3_protocol):
    matches, merge_report = backfilled_matches()
    rows = build_rows(matches)
    hashes = check_phase3(rows, phase3_protocol)
    return augment(rows, matches, settings_path), {"phase3_hashes": hashes, "merge": merge_report}


def save_dataset(rows):
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    written = {}
    for period, name in SPLIT_OF_PERIOD.items():
        subset = [row for row in rows if row["period"] == period]
        path = DATASET_DIR / FILES[name]
        with open(path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(subset[0]))
            writer.writeheader()
            writer.writerows(subset)
        written[name] = (path, len(subset))
    return written


def parse(row):
    parsed = {}
    for field, value in row.items():
        if field in PHASE4_TEXT or field == "ra_reason":
            parsed[field] = value
        elif value == "":
            parsed[field] = None
        else:
            number = float(value)
            parsed[field] = int(number) if number.is_integer() and "." not in value else number
    return parsed


def load_phase4(name, dataset_dir=DATASET_DIR, unseal_with=None):
    """Rows of a Phase 4 file. The retrospective file (2024-May 2026) opens only with a frozen Phase 4 protocol."""
    if name not in FILES:
        raise ValueError(f"no Phase 4 file {name!r}")
    if name == "retrospective":
        from matchup_dna.tennisdata import check_unseal
        if unseal_with is None:
            raise PermissionError("the retrospective rows open only after the Phase 4 protocol is frozen")
        check_unseal(unseal_with)
    with open(dataset_dir / FILES[name], encoding="utf-8", newline="") as file:
        rows = [parse(row) for row in csv.DictReader(file)]
    expected = {v: k for k, v in SPLIT_OF_PERIOD.items()}[name]
    if any(row["period"] != expected or LABEL not in row for row in rows):
        raise ValueError(f"{FILES[name]} holds rows outside {name} or without labels")
    return rows
