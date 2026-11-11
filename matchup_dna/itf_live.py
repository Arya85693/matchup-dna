"""ITF extension, stage I5: live ITF forecasts under the prospective protocol P2.

    python -m matchup_dna.itf_live model export      models/itf_m1.json: M1 refitted once on every ITF match before
                                                      June 2026 (never overwritten)
    python -m matchup_dna.itf_live model check       a refit reproduces the stored artifact byte for byte
    python -m matchup_dna.itf_live run [--no-fetch]   fetch this week's events and rankings, settle results, forecast
                                                      every eligible upcoming ITF main-draw match, export the ledger
    python -m matchup_dna.itf_live protocol freeze    experiments/itf_prospective_protocol.json (P2), on committed code
    python -m matchup_dna.itf_live status             what the store holds and whether it verifies
    python -m matchup_dna.itf_live due                exit 0 if an ITF run is due (about every two hours), else 1
    python -m matchup_dna.itf_live audit              how Flashscore players resolve, and the overlap with Sackmann

The live model is M1 (the ITF Model Report, section 7, says why not M2: no serve statistics are published for ITF
matches after June 2026). Each forecast is stored with an Elo-only forecast (B1) for the same match, so the live
record also measures what M1 adds over the ratings alone.

How a forecast is made, as the frozen model was trained:

- history: every Sackmann match to the end of its data (1 June 2026), then every finished Flashscore match after it
  (ITF, Challenger and main tour, men and women). A Flashscore match with the same players and round as a Sackmann
  match within 14 days is the same match and is not added twice;
- players: Flashscore players resolved to Sackmann ids (itf_identity); ambiguous or conflicting identities are not
  forecast;
- the replay: the upcoming match is added as a placeholder that moves nothing (no rating change, no rest or form),
  dated by its edition (the Monday of its first main-draw day), so its ratings are start-of-week and its history ends
  before the edition, the rule every training row followed;
- rank: each player's rank in the latest TennisExplorer weekly list published on or before both the edition date
  and the day the forecast is issued;
- a forecast is issued only before the scheduled start (at least 5 minutes); later it is "too_late".

Each run also writes the ITF players board (data/raw/itf/board.json): active ITF players by the same all-level
rating, with ATP or WTA rank and 52-week ITF record, for the website's Players page. It is display only.

Everything is stored in data/store/itf.sqlite with the main-tour store's code (matchup_dna.forecasting.store,
unchanged): forecasts cannot be edited, each is chained by hash, and the chain is exported to
forecasts/itf_ledger.jsonl. The P1 store, ledger and code are not touched.
"""
import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from matchup_dna import itf_data, itf_flashscore, itf_identity, itf_model, itf_rankings, itf_ratings, itf_splits
from matchup_dna.elo import RESULTS_DIR, expected_score
from matchup_dna.features import feature_row, match_id
from matchup_dna.itf_features import HISTORY_FROM, player_history
from matchup_dna.load import load_players

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "itf_m1.json"
MODEL_VERSION, BASELINE_VERSION = "itf-m1-v1", "itf-elo-v1"
STORE_PATH = ROOT / "data" / "store" / "itf.sqlite"
LEDGER_PATH = ROOT / "forecasts" / "itf_ledger.jsonl"
PROTOCOL_PATH = ROOT / "experiments" / "itf_prospective_protocol.json"
VARIANT = "decaying"
SACKMANN_END = 20260601
FLASHSCORE_FROM = 20260525          # a week of overlap with Sackmann, so duplicates can be seen and dropped
DUPLICATE_DAYS = 14
MIN_LEAD = datetime.timedelta(minutes=5)
FIT_ROWS = ("development", "validation", "held_out")
CODE_FILES = ("matchup_dna/itf_live.py", "matchup_dna/itf_flashscore.py", "matchup_dna/itf_rankings.py",
              "matchup_dna/itf_identity.py", "matchup_dna/itf_data.py", "matchup_dna/itf_ratings.py",
              "matchup_dna/itf_features.py", "matchup_dna/itf_model.py", "matchup_dna/itf_splits.py",
              "matchup_dna/elo.py", "matchup_dna/features.py", "matchup_dna/load.py", "matchup_dna/model.py",
              "matchup_dna/phase4_model.py", "matchup_dna/profiles.py", "matchup_dna/serve_stats.py",
              "matchup_dna/workload.py", "matchup_dna/periods.py", "matchup_dna/forecasting/store.py",
              "matchup_dna/forecasting/records.py", "models/itf_m1.json")
UTC = datetime.timezone.utc
RESOLVED = set(itf_identity.RESOLVED)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def iso(moment):
    return moment.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text):
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def ymd(day):
    return int(day.strftime("%Y%m%d"))


def code_hashes():
    from matchup_dna.itf_experiment import text_sha256
    return {name: text_sha256(ROOT / name) if (ROOT / name).exists() else None for name in CODE_FILES}


# ---------------------------------------------------------------- the model artifact

class FrozenITF:
    """M1 for one tour, rebuilt from stored numbers: the same design, scaling and coefficients as the fitted model."""

    def __init__(self, spec):
        self.names = tuple(spec["columns"])
        self.prep = dict(spec["preprocessing"])
        self.scale = np.array(spec["scale"], dtype=float)
        self.coefficients = np.array(spec["coefficients"], dtype=float)
        if self.names != itf_model.COLUMNS["M1"]:
            raise ValueError("stored columns do not match M1's definition")

    def predict(self, rows):
        return itf_model.sigmoid(itf_model.design(rows, self.names, self.prep) / self.scale @ self.coefficients)


def artifact_text():
    """The M1 artifact, refitted from the held-out run's rows (every ITF row before June 2026, decaying-K Elo)."""
    from matchup_dna.itf_experiment import load_rows, split_rows
    protocol = json.loads(itf_splits.PROTOCOL_PATH.read_text(encoding="utf-8"))
    tours = {}
    for tour in ("ATP", "WTA"):
        rows = split_rows(load_rows(tour, protocol["elo_variant"], "every_level", sealed=False), *FIT_ROWS)
        model = itf_model.ITFLogistic("M1", protocol["l2"][tour]["M1"]).fit(rows)
        spec = model.spec()
        spec.update(fit_rows=len(rows), fit_rows_sha256=sha(canonical([[r["match_id"], r["a_id"], r["b_id"], r["a_won"]]
                                                                       for r in rows])))
        tours[tour] = spec
    artifact = {"model_version": MODEL_VERSION, "kind": "itf_tournament_start", "research_name": "M1",
                "description": "ITF M1: all-level decaying-K Elo, surface Elo, rank, rest, form, Elo x tier; fitted "
                               "per tour on every rated ITF main-draw match from 2021 to 1 June 2026",
                "elo_variant": protocol["elo_variant"], "itf_protocol_sha256": itf_splits.sha256(itf_splits.PROTOCOL_PATH),
                "tours": tours}
    return json.dumps(artifact, indent=1, sort_keys=True) + "\n"


def export_model():
    if MODEL_PATH.exists():
        raise SystemExit(f"{MODEL_PATH.name} exists; artifacts are never overwritten")
    text = artifact_text()
    MODEL_PATH.write_text(text, encoding="utf-8")
    return sha(text)


def load_model():
    text = MODEL_PATH.read_text(encoding="utf-8")
    artifact = json.loads(text)
    return text, artifact, {tour: FrozenITF(spec) for tour, spec in artifact["tours"].items()}


# ---------------------------------------------------------------- history and fixtures

def edition_monday(starts):
    first = min(parse_iso(s) for s in starts).date()
    return first - datetime.timedelta(days=first.weekday())


def family_of(match):
    if match["itf"]:
        return "itf"
    return "challenger_qualifying" if match["category"].startswith("CHALLENGER") else "main"


def editions(fs_matches):
    """{(tour, category, slug, Monday)} -> Monday, grouping each slug's matches into editions by week of first play.
    A slug's matches more than 10 days apart from the previous ones start a new edition."""
    by_slug = defaultdict(list)
    for m in fs_matches:
        if m["start"]:
            by_slug[(m["tour"], m["page_category"], m["slug"])].append(m)
    found = {}
    for key, matches in by_slug.items():
        group, last = [], None
        for m in sorted(matches, key=lambda x: x["start"]):
            when = parse_iso(m["start"])
            if last and (when - last).days > 10:
                monday = edition_monday([x["start"] for x in group])
                found.update({x["provider_match_id"]: monday for x in group})
                group = []
            group.append(m)
            last = when
        if group:
            monday = edition_monday([x["start"] for x in group])
            found.update({x["provider_match_id"]: monday for x in group})
    return found


def resolver(sackmann, fs_matches):
    """An Identities object with countries learned from this run's Flashscore players."""
    active = {(m["tour"], pid) for m in sackmann if m["tourney_date"] >= 20150101 for pid in (m["winner_id"], m["loser_id"])}
    ids = itf_identity.Identities(load_players(), active)
    ids.learn_countries([(m["tour"], side["slug"] or side["name"], side["country"])
                         for m in fs_matches for side in (m["home"], m["away"])])
    return ids


def resolve_side(ids, tour, side):
    return ids.resolve(tour, "flashscore", side["id"], side["slug"] or side["name"], side["country"])


def sackmann_index(sackmann):
    found = defaultdict(list)
    for m in sackmann:
        if m["tourney_date"] >= FLASHSCORE_FROM - 10000:
            found[(m["tour"], frozenset((m["winner_id"], m["loser_id"])), m["round"])].append(m["tourney_date"])
    return found


def best_of(match):
    """5 for a men's main-tour match the winner took in three sets (the Grand Slams), else 3. Only completed matches
    are rated, so a retirement's value does not matter."""
    if match["tour"] == "ATP" and not match["itf"] and match["outcome"] == "completed" and _winner_sets(match["score"]) == 3:
        return 5
    return 3


def _winner_sets(score):
    """Sets the winner took, from a score written from the winner's side."""
    won = 0
    for part in score.split():
        games = part.split("(")[0].split("-")
        if len(games) == 2 and games[0].isdigit() and games[1].isdigit() and int(games[0]) > int(games[1]):
            won += 1
    return won


def flashscore_history(fs_matches, ids, index, monday_of):
    """Finished Flashscore matches as history records, both players resolved, not already in Sackmann."""
    found, skipped = [], defaultdict(int)
    for m in fs_matches:
        if m["status"] != "finished" or m["outcome"] is None or m["provider_match_id"] not in monday_of:
            continue
        home, away = resolve_side(ids, m["tour"], m["home"]), resolve_side(ids, m["tour"], m["away"])
        if home[0] not in RESOLVED or away[0] not in RESOLVED:
            skipped["unresolved player"] += 1
            continue
        if m["outcome"] == "walkover":
            winner, loser = (home[1], away[1]) if m["winner"] == "home" else (away[1], home[1])
        elif m["winner"] not in ("home", "away"):
            skipped["no winner"] += 1
            continue
        else:
            winner, loser = (home[1], away[1]) if m["winner"] == "home" else (away[1], home[1])
        monday = ymd(monday_of[m["provider_match_id"]])
        near = index.get((m["tour"], frozenset((winner, loser)), m["round"]), [])
        if any(abs((datetime.date(d // 10000, d // 100 % 100, d % 100) - monday_of[m["provider_match_id"]]).days)
               <= DUPLICATE_DAYS for d in near):
            skipped["already in Sackmann"] += 1
            continue
        found.append({"tour": m["tour"], "key": (m["tour"], f"fs:{m['slug']}:{monday}", m["provider_match_id"],
                                                  m["round"], "flashscore"),
                      "tourney_id": f"fs:{m['page_category']}:{m['slug']}:{monday}",
                      "tourney_level": m["level"] or m["category"], "tourney_date": monday, "surface": m["surface"],
                      "round": m["round"], "best_of": best_of(m), "outcome": m["outcome"], "winner_id": winner,
                      "loser_id": loser, "winner_rank": None, "loser_rank": None, "family": family_of(m),
                      "itf_scope": False, "tier": None, "outcome_note": None, "winner_name": "", "loser_name": "",
                      "provider_match_id": m["provider_match_id"]})
    return found, dict(skipped)


def rank_key(name, country):
    return (itf_identity.name_key(name), country)


def rank_index(lists):
    """{tour: {list date: {name key: [(country, rank)]}}} from itf_rankings.load() rows."""
    return {tour: {date: _by_name(rows) for date, rows in dates.items()} for tour, dates in lists.items()}


def _by_name(rows):
    found = defaultdict(list)
    for row in rows:
        found[itf_identity.name_key(row["name"])].append((row["country"], row["rank"]))
    return dict(found)


def lookup_rank(index, tour, name, country, day, max_age_days=21):
    """A player's rank in the latest weekly list published on or before `day` (YYYY-MM-DD, at most 21 days old).

    By name first: Flashscore and TennisExplorer write some countries differently ("World" and "Russia", "United
    Kingdom" and "Great Britain", "Taiwan" and "Chinese Taipei"), so the country only separates namesakes. A name not
    in the list may be a shorter form of one that is ("makhlouf-nazim", "Makhlouf Mohamed Nazim"): a unique longer
    name with the same country is accepted."""
    dates = sorted(d for d in index.get(tour, {}) if d <= day)
    if not dates or (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(dates[-1])).days > max_age_days:
        return None
    names, key = index[tour][dates[-1]], itf_identity.name_key(name)
    found = names.get(key, [])
    if len(found) > 1:
        found = [entry for entry in found if entry[0] == country]
    if not found and len(key) >= 2:
        found = [entry for k, entries in names.items() if key < k for entry in entries if entry[0] == country]
    return found[0][1] if len(found) == 1 else None


def fixtures(fs_matches, ids, ranks, monday_of, now):
    """(placeholder records, [(fixture, reason)] for upcoming ITF matches not forecast)."""
    found, refused = [], []
    for m in fs_matches:
        if not m["itf"] or m["status"] != "scheduled" or m["tier"] is None:
            continue
        start = parse_iso(m["start"]) if m["start"] else None
        if start is None or start - now < MIN_LEAD:
            refused.append((m, "too_late"))
            continue
        home, away = resolve_side(ids, m["tour"], m["home"]), resolve_side(ids, m["tour"], m["away"])
        if home[0] not in RESOLVED or away[0] not in RESOLVED:
            refused.append((m, f"identity {home[0]}/{away[0]}"))
            continue
        monday = monday_of.get(m["provider_match_id"]) or (start.date() - datetime.timedelta(days=start.weekday()))
        rank_day = min(monday, now.date()).isoformat()
        h_rank = lookup_rank(ranks, m["tour"], m["home"]["slug"] or m["home"]["name"], m["home"]["country"], rank_day)
        a_rank = lookup_rank(ranks, m["tour"], m["away"]["slug"] or m["away"]["name"], m["away"]["country"], rank_day)
        found.append({"tour": m["tour"], "key": (m["tour"], f"fs:{m['slug']}:{ymd(monday)}", m["provider_match_id"],
                                                  m["round"], "fixture"),
                      "tourney_id": f"fs:{m['page_category']}:{m['slug']}:{ymd(monday)}",
                      "tourney_level": m["level"], "tourney_date": ymd(monday), "surface": m["surface"],
                      "round": m["round"], "best_of": 3, "outcome": "completed", "placeholder": True,
                      "winner_id": home[1], "loser_id": away[1], "winner_rank": h_rank, "loser_rank": a_rank,
                      "family": "itf", "itf_scope": True, "tier": m["tier"], "outcome_note": None,
                      "winner_name": m["home"]["name"], "loser_name": m["away"]["name"],
                      "provider_match_id": m["provider_match_id"], "event": m["event"], "start": m["start"],
                      "identity": (home[0], away[0]), "home_provider_id": m["home"]["id"],
                      "away_provider_id": m["away"]["id"]})
    return found, refused


def placeholder_rows(history, placeholders, variant=VARIANT):
    """Phase 3 rows for the placeholders. Placeholders move nothing: no rating change, no rest, no form."""
    matches = history + placeholders

    def moves(match):
        return not match.get("placeholder")
    keys = {p["key"] for p in placeholders}
    elo, surface = itf_ratings.replay(matches, variant, updates=moves, keep=lambda m: m["tourney_date"] >= HISTORY_FROM,
                                      keep_surface=lambda m: m["key"] in keys)
    history_values = player_history([m for m in matches if m["tourney_date"] >= HISTORY_FROM], elo, moves,
                                    want=lambda m: m["key"] in keys)
    rows = {}
    for prediction in elo:
        match = prediction["match"]
        if match["key"] in keys:
            row = feature_row(prediction, surface[match["key"]], history_values)
            row.update(tier=match["tier"], a_serve_attempts=0, b_serve_attempts=0)   # M1 reads no serve values
            for side in ("a", "b"):
                for field in ("serve", "return", "serve_adjusted", "return_adjusted"):
                    row[f"{side}_{field}"] = 0.5
            rows[match["key"]] = row
    return rows


# ---------------------------------------------------------------- the ITF players board (display only)

BOARD_PATH = ROOT / "data" / "raw" / "itf" / "board.json"
BOARD_MIN_MATCHES = 5          # ITF main-draw matches in the last 52 weeks
BOARD_SIZE = 500               # per tour
PLAYED = ("completed", "retired")


def player_board(matches, ids, fs_matches, ranks, now, variant=VARIANT):
    """Active ITF players of one tour, ordered by the ITF rating (the all-level replay the forecasts use): at least
    BOARD_MIN_MATCHES ITF main-draw matches in the last 52 weeks. Each with name, country, rating, current ATP or WTA
    rank (the latest TennisExplorer list, matched by name and country), and the 52-week ITF record. Display only."""
    if not matches:
        return []
    tour = matches[0]["tour"]
    _, ratings = itf_ratings.run_elo(matches, itf_ratings.VARIANTS[variant]["k"])
    since = ymd(now.date() - datetime.timedelta(days=364))
    record = defaultdict(lambda: [0, 0, 0])            # wins, losses, last tourney_date
    for m in matches:
        itf = m["family"] == "itf" and (m["itf_scope"] or m["key"][-1] == "flashscore")
        if itf and m["outcome"] in PLAYED and m["tourney_date"] >= since and m["winner_id"] != m["loser_id"]:
            for pid, won in ((m["winner_id"], 1), (m["loser_id"], 0)):
                entry = record[pid]
                entry[0 if won else 1] += 1
                entry[2] = max(entry[2], m["tourney_date"])
    seen = {}                                          # player id -> (Flashscore name, slug, country) as last seen
    for m in sorted(fs_matches, key=lambda x: x["start"] or ""):
        for side in (m["home"], m["away"]):
            status, pid = resolve_side(ids, tour, side)
            if status in RESOLVED:
                seen[pid] = (side["name"], side["slug"] or side["name"], side["country"])
    country_of_ioc = {ioc: country for country, ioc in ids.countries.items()}
    latest = max(ranks.get(tour, {}), default=None)
    rows = []
    for pid, (wins, losses, last) in record.items():
        if wins + losses < BOARD_MIN_MATCHES or (tour, pid) not in ratings:
            continue
        person = ids.players.get((tour, pid))
        name = person["name"] if person else seen.get(pid, ("Unknown",))[0]
        country = (person or {}).get("ioc") or (seen.get(pid, (None, None, ""))[2])
        key_name, key_country = (seen[pid][1], seen[pid][2]) if pid in seen else (
            name, country_of_ioc.get((person or {}).get("ioc"), ""))
        rank = lookup_rank(ranks, tour, key_name, key_country, latest) if latest else None
        rows.append({"id": pid, "name": name, "country": country, "rating": round(ratings[(tour, pid)]["rating"], 1),
                     "rank": rank, "wins": wins, "losses": losses, "last_event": last})
    rows.sort(key=lambda r: -r["rating"])
    for i, r in enumerate(rows[:BOARD_SIZE], 1):
        r["position"] = i
    return rows[:BOARD_SIZE]


def write_board(boards, now, rank_dates, path=BOARD_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"generated_at": iso(now), "rank_lists": rank_dates, "min_matches": BOARD_MIN_MATCHES,
                                "tours": boards}, ensure_ascii=False, indent=0), encoding="utf-8")


# ---------------------------------------------------------------- store writes

def edition_uid(tour, slug, monday):
    return "IE-" + sha(canonical([tour, slug, monday]))[:24]


def match_uid(tour, edition, round_, a, b):
    low, high = sorted((a, b))
    return "I-" + sha(canonical([tour, edition, round_, low, high]))[:24]


INPUT_FIELDS = ("tourney_date", "tour", "surface", "round", "tier", "a_id", "b_id", "a_elo", "b_elo", "elo_diff",
                "surface_elo_diff", "a_rank", "b_rank", "a_elo_matches", "b_elo_matches", "a_days_since",
                "b_days_since", "a_form", "b_form", "a_surface_matches", "b_surface_matches")


def issue(store, run_id, now, placeholder, row, p_model, model_sha, baseline_sha):
    """Stores the edition, match, both forecasts and the decisions; returns the M1 decision."""
    tour = placeholder["tour"]
    ed = edition_uid(tour, placeholder["tourney_id"], placeholder["tourney_date"])
    store.ensure_edition(ed, tour, placeholder["event"], placeholder["tourney_date"], placeholder["tourney_level"],
                         placeholder["surface"], now)
    store.add_edition_alias("flashscore", placeholder["tourney_id"], ed, now)
    uid = match_uid(tour, ed, placeholder["round"], row["a_id"], row["b_id"])
    low, high = sorted((row["a_id"], row["b_id"]))
    store.ensure_match(uid, tour, ed, placeholder["round"], low, high, now)
    store.add_match_alias("flashscore", tour, placeholder["provider_match_id"], uid, now)
    for side, pid, status, name in (("home", placeholder["winner_id"], placeholder["identity"][0], placeholder["winner_name"]),
                                    ("away", placeholder["loser_id"], placeholder["identity"][1], placeholder["loser_name"])):
        store.observe_identity("flashscore", tour, placeholder[f"{side}_provider_id"], name, pid, status, "name+country",
                               run_id, now)
    inputs = {field: row[field] for field in INPUT_FIELDS}
    input_sha = sha(canonical(inputs))
    decision = None
    for version, p, model_sha256 in ((MODEL_VERSION, p_model, model_sha),
                                     (BASELINE_VERSION, expected_score(row["a_elo"], row["b_elo"]), baseline_sha)):
        content = {"match_uid": uid, "model_version": version, "model_sha256": model_sha256, "run_id": run_id,
                   "issued_at": iso(now), "scheduled_start": placeholder["start"], "player_a": row["a_id"],
                   "player_b": row["b_id"], "p_a": float(p), "input_sha256": input_sha, "inputs": inputs,
                   "provider": "flashscore", "provider_match_id": placeholder["provider_match_id"],
                   "event": placeholder["event"], "a_name": row["a_name"], "b_name": row["b_name"],
                   "identity": list(placeholder["identity"])}
        result, prediction_id = store.add_prediction(content)
        store.add_decision(run_id, uid, version, now, result, "eligible", prediction_id)
        if version == MODEL_VERSION:
            decision = result
    return decision


def settle(store, run_id, now, fs_matches, ids):
    """Adds each finished Flashscore match's result to the stored match it belongs to."""
    added = 0
    for m in fs_matches:
        if m["status"] != "finished" or m["outcome"] is None:
            continue
        uid = store.match_for_alias("flashscore", m["tour"], m["provider_match_id"])
        if uid is None:
            continue
        home, away = resolve_side(ids, m["tour"], m["home"]), resolve_side(ids, m["tour"], m["away"])
        winner = home[1] if m["winner"] == "home" else away[1] if m["winner"] == "away" else None
        added += store.add_outcome(uid, "flashscore", m["provider_match_id"], m["outcome"], winner, m["score"], 3,
                                   parse_iso(m["retrieved_at"]), now, run_id)
    return added


# ---------------------------------------------------------------- the run

def baseline_artifact():
    text = canonical({"model_version": BASELINE_VERSION, "kind": "itf_elo_only", "rule": "ordinary Elo probability "
                      "from the same all-level decaying-K replay as M1; nothing fitted"}) + "\n"
    return text


def run(now=None, store_path=STORE_PATH, fetch=True, ledger=LEDGER_PATH, log=print):
    from matchup_dna.forecasting.store import Store
    now = now or datetime.datetime.now(UTC).replace(microsecond=0)
    if fetch:
        slugs = itf_flashscore.current_slugs()
        itf_flashscore.fetch_all([(c, s) for c, ss in slugs.items() for s in ss], log=log)
        for tour in itf_rankings.LISTS:
            latest = itf_rankings.offered_dates(tour)[:1]
            if latest and latest[0] not in itf_rankings.load().get(tour, {}):
                itf_rankings.fetch_list(tour, latest[0])
    model_text, artifact, models = load_model()
    model_sha, base_text = sha(model_text), baseline_artifact()
    fs_all = itf_flashscore.load(since=FLASHSCORE_FROM)
    monday_of = editions(fs_all)
    ranks = rank_index(itf_rankings.load())
    store = Store(store_path, "live")
    run_id = f"itf-{iso(now)}"
    counts = defaultdict(int)
    boards = {}
    try:
        with store.transaction():
            store.start_run(run_id, "itf_forecast", iso(now), {"code_sha256": code_hashes(), "model_sha256": model_sha})
            store.register_model(MODEL_VERSION, "itf_tournament_start", model_text, model_sha)
            store.register_model(BASELINE_VERSION, "itf_elo_only", base_text, sha(base_text))
        for tour in ("ATP", "WTA"):
            sackmann = itf_data.load(allow_held_out=True, tours=(tour,))
            fs = [m for m in fs_all if m["tour"] == tour]
            ids = resolver(sackmann, fs)
            history, skipped = flashscore_history(fs, ids, sackmann_index(sackmann), monday_of)
            places, refused = fixtures(fs, ids, ranks, monday_of, now)
            rows = placeholder_rows(sackmann + history, places)
            with store.transaction():
                counts["results added"] += settle(store, run_id, now, fs, ids)
                for p in places:
                    row = rows.get(p["key"])
                    if row is None:                     # e.g. a player's only match is the placeholder itself
                        counts["no row"] += 1
                        continue
                    p_model = float(models[tour].predict([row])[0])
                    counts[f"{tour} {issue(store, run_id, now, p, row, p_model, model_sha, sha(base_text))}"] += 1
                for m, reason in refused:
                    counts[f"{tour} not forecast: {reason}"] += 1
            counts[f"{tour} history added"] = len(history)
            for reason, n in skipped.items():
                counts[f"{tour} history skipped: {reason}"] = n
            boards[tour] = player_board(sackmann + history, ids, fs, ranks, now)
            counts[f"{tour} board players"] = len(boards[tour])
            del sackmann, history, rows
        write_board(boards, now, {tour: max(ranks.get(tour, {}), default=None) for tour in ("ATP", "WTA")})
        problems = store.verify()
        with store.transaction():
            store.finish_run(run_id, "ok" if not problems else "failed", dict(counts, problems=len(problems)))
        if ledger:
            store.export_ledger(ledger)
    finally:
        store.close()
    return dict(counts)


# ---------------------------------------------------------------- protocol P2

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def freeze(now=None):
    if PROTOCOL_PATH.exists():
        raise SystemExit(f"{PROTOCOL_PATH.name} exists")
    dirty = [f for f in CODE_FILES if git("ls-files", "--error-unmatch", f).returncode
             or git("diff", "--quiet", "HEAD", "--", f).returncode]
    if dirty:
        raise SystemExit("commit these first: " + ", ".join(dirty))
    now = now or datetime.datetime.now(UTC).replace(microsecond=0)
    protocol = {
        "name": "P2: prospective ITF forecasts", "frozen_at": iso(now),
        "code_commit": git("rev-parse", "HEAD").stdout.strip(), "code_sha256": code_hashes(),
        "model": {"version": MODEL_VERSION, "sha256": sha(MODEL_PATH.read_text(encoding="utf-8"))},
        "baseline": BASELINE_VERSION,
        "population": "ITF men's and women's main-draw singles (M15, M25, W15-W100) listed on Flashscore, both players "
                      "resolved to one identity, forecast at least 5 minutes before the scheduled start",
        "counting_rule": "the first M1 forecast stored for a match counts; later revisions are recorded but not scored",
        "window": {"from": iso(now), "to": "2027-06-30T23:59:59Z"},
        "metrics": "log loss and Brier of M1 against the Elo-only forecast for the same matches (paired bootstrap by "
                   "edition); calibration; by tour and tier. Retirements and walkovers are not scored",
        "evaluation_not_before": "2027-07-15",
        "code_rule": "forecasts from runs whose code_sha256 differs from this protocol's are excluded unless a committed "
                     "amendment lists the change",
    }
    PROTOCOL_PATH.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    return protocol


def audit():
    """Identity and overlap check, per tour: how Flashscore players resolve, and, for the weeks both sources hold
    (editions of 25 May and 1 June 2026), how many Sackmann ITF matches Flashscore also lists, and whether the two
    agree on the winner. Read-only; no store is touched."""
    from collections import Counter
    fs_all = itf_flashscore.load(since=FLASHSCORE_FROM)
    monday_of = editions(fs_all)
    report = {}
    for tour in ("ATP", "WTA"):
        sackmann = itf_data.load(allow_held_out=True, tours=(tour,))
        fs = [m for m in fs_all if m["tour"] == tour]
        ids = resolver(sackmann, fs)
        statuses, players = Counter(), set()
        for m in fs:
            for side in (m["home"], m["away"]):
                if side["id"] not in players:
                    players.add(side["id"])
                    statuses[resolve_side(ids, tour, side)[0]] += 1
        overlap = [m for m in sackmann if m["itf_scope"] and m["tourney_date"] in (20260525, 20260601)]
        fs_pairs = {}
        for m in fs:
            if m["itf"] and m["status"] == "finished" and m["provider_match_id"] in monday_of:
                h, a = resolve_side(ids, tour, m["home"]), resolve_side(ids, tour, m["away"])
                if h[0] in RESOLVED and a[0] in RESOLVED and m["winner"] in ("home", "away"):
                    winner = h[1] if m["winner"] == "home" else a[1]
                    fs_pairs[(frozenset((h[1], a[1])), m["round"], ymd(monday_of[m["provider_match_id"]]))] = winner
        found = agree = 0
        for m in overlap:
            winner = fs_pairs.get((frozenset((m["winner_id"], m["loser_id"])), m["round"], m["tourney_date"]))
            if winner is not None:
                found += 1
                agree += winner == m["winner_id"]
        report[tour] = {"flashscore_players": len(players), "resolution": dict(statuses),
                        "countries_learned": len(ids.countries), "sackmann_matches_in_overlap_weeks": len(overlap),
                        "also_on_flashscore": found, "same_winner": agree}
        del sackmann
    return report


DUE_EVERY = datetime.timedelta(minutes=110)     # about every two hours, on the 15-minute job's clock


def due(store_path=STORE_PATH, now=None):
    """(due, why): an ITF run is due when the store has none in the last ~2 hours (or there is no store yet)."""
    from web.publisher.readonly import open_readonly
    now = now or datetime.datetime.now(UTC)
    if not Path(store_path).exists():
        return True, "no ITF store yet"
    store = open_readonly(store_path)
    try:
        runs = [r for r in store.runs("itf_forecast") if r["status"] != "running"]
    finally:
        store.close()
    if not runs:
        return True, "no ITF run yet"
    last = parse_iso(max(r["started_at"] for r in runs))
    return (now - last >= DUE_EVERY), f"last ITF run started {iso(last)}"


def status(store_path=STORE_PATH):
    from matchup_dna.forecasting.store import Store
    if not Path(store_path).exists():
        return {"store": "none yet"}
    store = Store(store_path)
    try:
        return {"mode": store.mode, "predictions": len(store.predictions(MODEL_VERSION)),
                "baseline_predictions": len(store.predictions(BASELINE_VERSION)),
                "settled": len(store.settled()), "runs": len(store.runs()), "verify_problems": store.verify()}
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("model", "run", "protocol", "status", "due", "audit"))
    parser.add_argument("action", nargs="?")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "model":
        if args.action == "export":
            print(f"wrote {MODEL_PATH.name} (sha256 {export_model()[:16]}...)")
        else:
            same = artifact_text() == MODEL_PATH.read_text(encoding="utf-8")
            print("model check: " + ("reproduced exactly" if same else "DIFFERS"))
            return 0 if same else 1
    elif args.command == "run":
        print(json.dumps(run(fetch=not args.no_fetch), indent=1))
    elif args.command == "protocol":
        print(json.dumps(freeze(), indent=1))
    elif args.command == "audit":
        print(json.dumps(audit(), indent=1))
    elif args.command == "due":
        is_due, why = due()
        print(f"{'due' if is_due else 'not due'}: {why}")
        return 0 if is_due else 1
    else:
        print(json.dumps(status(), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
