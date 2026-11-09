"""Point-in-time features for unplayed fixtures, eligibility for each model, and inference.

How a fixture gets its features. Every Phase 3 and Phase 4 feature is produced by a chronological replay of
completed matches (features.build_rows and phase4_features.augment), and every feature of a match is computed from
strictly earlier information:

    Elo, surface Elo, form, days since last match, serve-return profiles   matches dated before the edition's date
    round-aware Elo shifts and earlier-round dominance (R0 only)           strictly earlier rounds of the same edition
    rank                                                                   the rank carried on the match record

So a fixture is appended to the history as a placeholder match (with a placeholder result that is never read for
its own row) and the unchanged research code computes its row. Player A is chosen by a hash of the match id and the
two player ids, never by the result, exactly as in Phase 3. The placeholder's result could only affect matches dated
after it, so each replay holds the history up to one edition date plus that date's fixtures, and nothing later:

    history used for fixtures dated D = completed matches dated before D
                                        + completed matches of the fixtures' own editions (dated D)
                                        + the placeholders

`verify_placeholder_neutrality` (in the tests) checks that changing a placeholder's result does not change any
fixture's features.

Eligibility. Model A (tournament start) forecasts a fixture only if:
    - it is a pending main-draw singles match of a known best-of-3 or best-of-5 format;
    - both players have a verified identity, or are new players with no plausible existing identity;
    - it is issued at least MIN_LEAD before the scheduled start;
    - neither player may still be playing an earlier-dated event (their latest results would be missing: deferred);
    - its features exist.
Model B (round-aware R0) additionally needs a knockout round with both players' earlier rounds of this edition
complete in the history, and at least one player who has already played in the edition (Phase 4's later-round
sample). Otherwise only Model A's forecast exists. Model B is never filled in with Model A's number.
"""
import datetime
import hashlib
from collections import defaultdict

from matchup_dna.features import build_rows, match_id
from matchup_dna.forecasting.frozen_models import ROUND_AWARE, TOURNAMENT_START
from matchup_dna.forecasting.history import alive_elsewhere
from matchup_dna.forecasting.records import canonical_json, iso, sha256_text, utc
from matchup_dna.phase4_features import augment
from matchup_dna.round_aware import EXCLUDED_LEVELS, KNOCKOUT

MIN_LEAD = datetime.timedelta(minutes=30)
FORECASTABLE_IDENTITY = ("verified", "new_player")
STAT_FIELDS = ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")


def match_uid(tour, edition, round_name, player_one, player_two):
    low, high = sorted((player_one, player_two))
    return "M-" + sha256_text(f"{tour}|{edition}|{round_name}|{low}|{high}")[:24]


def fixture_uid(fixture):
    return match_uid(fixture["tour"], fixture["edition_uid"], fixture["round"], fixture["home"]["player_id"],
                     fixture["away"]["player_id"])


def placeholder(fixture):
    """A fixture as a Sackmann-shaped match. Its result fields are placeholders: the fixture's own row never reads
    them (see the module notes), and nothing dated after the fixture is replayed with it."""
    home, away = fixture["home"], fixture["away"]
    number = f"FIXTURE-{fixture['provider']}-{fixture['provider_match_id']}"
    blank_line = {field: None for field in STAT_FIELDS}
    return {
        "tour": fixture["tour"], "key": (fixture["tour"], fixture["tourney_id"], number, fixture["round"]),
        "tourney_id": fixture["tourney_id"], "tourney_name": fixture["tourney_name"],
        "tourney_level": fixture["tourney_level"], "tourney_date": fixture["tourney_date"], "match_num": number,
        "surface": fixture["surface"], "round": fixture["round"], "best_of": fixture["best_of"],
        "score": "", "outcome": "completed",
        "winner_id": home["player_id"], "winner_name": home["name"], "winner_rank": home["rank"],
        "loser_id": away["player_id"], "loser_name": away["name"], "loser_rank": away["rank"],
        "w_ace": None, "w_svpt": None, "w_first_in": None, "l_ace": None, "l_svpt": None, "l_first_in": None,
        "minutes": None, "draw_size": "", "winner_entry": "", "loser_entry": "", "source": "fixture",
        "stats": {"w": dict(blank_line), "l": dict(blank_line)}, "match_day": fixture["match_day"],
        "placeholder": True,
    }


def fixture_rows(history, fixtures, settings_path):
    """{fixture uid: Phase 4 feature row (without a label)} for each fixture, one replay per (tour, edition date)."""
    groups = defaultdict(list)
    for fixture in fixtures:
        groups[(fixture["tour"], fixture["tourney_date"])].append(fixture)
    found = {}
    for (tour, date), members in sorted(groups.items()):
        editions = {f["tourney_id"] for f in members}
        base = [m for m in history if m["tour"] == tour and not m.get("placeholder") and (
            m["tourney_date"] < date or (m["tourney_date"] == date and m["tourney_id"] in editions))]
        placeholders = [placeholder(f) for f in members]
        matches = base + placeholders
        rows = augment(build_rows(matches, start=date), matches, settings_path, start=date)
        by_id = {row["match_id"]: row for row in rows}
        for fixture, match in zip(members, placeholders):
            row = by_id.get(match_id(match))
            if row is None:
                continue
            row = dict(row)
            row.pop("a_won", None)
            found[fixture_uid(fixture)] = row
    return found


def history_digest(history):
    """sha256 over every completed match the replay can read: key, date, players, result, score and statistics."""
    digest = hashlib.sha256()
    for m in sorted(history, key=lambda m: tuple(map(str, m["key"]))):
        digest.update(canonical_json([list(map(str, m["key"])), m["tourney_date"], m["winner_id"], m["loser_id"],
                                      m["score"], m["outcome"], m["best_of"], m.get("winner_rank"),
                                      m.get("loser_rank"), m.get("stats"), m.get("minutes")]).encode())
    return digest.hexdigest()


# ---------------------------------------------------------------- eligibility

def common_checks(fixture, issued_at, assembly):
    """(decision, reason) for the conditions both models share, or None if they pass."""
    if fixture["status"] == "already_played":
        return "too_late", "the match has already been played (a source reports its result)"
    if fixture["status"] == "started":
        return "too_late", "the match is already in progress"
    if fixture["status"] == "duplicate":
        return "ineligible", "duplicate listing of a match already listed"
    if fixture["best_of"] not in (3, 5):
        return "ineligible", f"format best-of-{fixture['best_of']} is outside the models' population"
    for side in ("home", "away"):
        person = fixture[side]
        if person["status"] not in FORECASTABLE_IDENTITY:
            return "ineligible", f"identity {person['status']} for {person['name']} ({person['method']})"
    if fixture["home"]["player_id"] == fixture["away"]["player_id"]:
        return "ineligible", "both sides resolve to the same player"
    start = utc(fixture["scheduled_start"])
    if start is None:
        return "deferred", "no confirmed start time yet (forecast once the provider publishes one)"
    if utc(issued_at) > start - MIN_LEAD:
        return "too_late", f"issued {iso(issued_at)}, less than {MIN_LEAD} before the scheduled start {iso(start)}"
    pending = alive_elsewhere(assembly, fixture)
    if pending:
        return "deferred", "; ".join(f"{fixture[side]['name']} {reason}" for side, reason in pending.items())
    return None


def round_aware_check(fixture, row):
    """None if R0 applies to this fixture's row, else the reason it does not."""
    if fixture["round"] not in KNOCKOUT:
        return f"round {fixture['round']}: R0 covers knockout rounds only"
    if fixture["tourney_level"] in EXCLUDED_LEVELS:
        return "team event: rounds cannot be ordered"
    if not row["ra_eligible"]:
        return f"earlier rounds unusable: {row['ra_reason']}"
    if not row["ra_later_round"]:
        return "neither player has played earlier in this edition (first match): nothing for R0 to add"
    return None


def decide(fixture, row, model, issued_at, assembly):
    """(decision, reason) for one model on one fixture: issued, ineligible, deferred or too_late."""
    common = common_checks(fixture, issued_at, assembly)
    if common:
        return common
    if row is None:
        return "ineligible", "no feature row (the replay did not produce one)"
    if fixture["tour"] not in model.tours:
        return "ineligible", f"no {fixture['tour']} model"
    if model.kind == ROUND_AWARE:
        reason = round_aware_check(fixture, row)
        if reason:
            return "ineligible", reason
    return "issued", "eligible"


# ---------------------------------------------------------------- the prediction record

def player_view(fixture, player_id):
    for side in ("home", "away"):
        person = fixture[side]
        if person["player_id"] == player_id:
            return {"player_id": player_id, "name": person["name"], "side": side, "provider_id": person["provider_id"],
                    "identity": person["status"], "identity_method": person["method"], "rank": person["rank"],
                    "rank_as_of": person.get("rank_as_of"), "seed": person.get("seed")}
    raise ValueError("player not on the fixture")


def snapshot(fixture, row, model, history_info):
    """Everything the prediction used, stored with it: the feature row, the model's inputs and contributions, the
    players and their identity evidence, the fixture as listed, and the history it was computed from."""
    terms = model.explain(row)
    features = {name: value for name, value, _ in terms}
    return {
        "features": features,
        "contributions": {name: contribution for name, _, contribution in terms},
        "row": {k: v for k, v in row.items()},
        "players": {"a": player_view(fixture, row["a_id"]), "b": player_view(fixture, row["b_id"])},
        "fixture": {k: fixture[k] for k in ("provider", "provider_match_id", "tour", "edition_uid", "tourney_name",
                                            "tourney_id", "tourney_date", "tourney_level", "surface", "best_of",
                                            "round", "scheduled_start")},
        "history": history_info,
    }


def input_hash(uid, model, row, features):
    """What determines the probability: the match, the model, the two players in order, and the model's inputs."""
    return sha256_text(canonical_json({"match_uid": uid, "model_version": model.version, "player_a": row["a_id"],
                                       "player_b": row["b_id"], "features": features}))


def prediction_content(uid, fixture, row, model, issued_at, run_id, mode, history_info, code_commit, code_sha=None):
    p = float(model.predict([row])[0])
    if not 0.0 < p < 1.0:
        raise ValueError(f"probability {p} out of range for {uid}")
    inputs = snapshot(fixture, row, model, history_info)
    return {
        "schema": 1, "mode": mode, "match_uid": uid, "model_version": model.version, "model_sha256": model.sha256,
        "model_kind": model.kind, "run_id": run_id, "issued_at": iso(issued_at),
        "scheduled_start": fixture["scheduled_start"], "player_a": row["a_id"], "player_b": row["b_id"], "p_a": p,
        "input_sha256": input_hash(uid, model, row, inputs["features"]), "inputs": inputs,
        "code_commit": code_commit, "code_sha256": code_sha,
    }


def reproduce(content, model):
    """The probability recomputed from a stored prediction's own input row and its model artifact."""
    if model.sha256 != content["model_sha256"]:
        raise ValueError("this is not the model artifact the prediction names")
    return float(model.predict([content["inputs"]["row"]])[0])


KIND_ORDER = (TOURNAMENT_START, ROUND_AWARE)
