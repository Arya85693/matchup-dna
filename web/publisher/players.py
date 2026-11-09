"""Profiles for every active ATP and WTA player, from the same canonical history the forecasting job uses.

    python -m web.publisher.players        writes web/.data/history/v1/<time>/ and v1/manifest.json

Run it after the daily forecasting job (it takes a few minutes): profiles then include that day's results. It is
read-only:
- it never opens the forecast store;
- it builds the history with the job's own read path (`pipeline.live_assembly`);
- it refuses to run if a forecasting run is in progress;
- it refuses to run if loading the ESPN archive would have to write a parse cache the job has not yet written.

Ratings are a fresh chronological Elo replay over that history (the Phase 2 definitions in matchup_dna/elo.py),
recomputed for display. They are not official forecasts and are never used as one.

Published per player (aggregates only):
- current Elo, and Elo blended per surface;
- the latest official ranking;
- this season's win-loss record by surface;
- an Elo trend;
- the last few results as win or loss against a named opponent (no scores, no statistics, no raw rows).
"""
import datetime
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from matchup_dna.elo import ELO_K, SURFACE_ELO_K, SURFACE_WEIGHT, START_RATING, blended_rating, run_elo
from matchup_dna.forecasting.records import iso
from web.publisher import contract
from web.publisher.readonly import open_readonly, runs_in_progress

ROOT = Path(__file__).resolve().parents[2]
LIVE_STORE = ROOT / "data" / "store" / "live.sqlite"
OUT = ROOT / "web" / ".data" / "history"
ACTIVE_DAYS = 365          # "on the circuit": a rated tour-level match in the last year
SERIES_DAYS = 3 * 365      # Elo trend window
SERIES_POINTS = 80
RECENT = 12
SURFACES = ("Hard", "Clay", "Grass")


class Refused(Exception):
    pass


def ymd(day):
    return day.strftime("%Y%m%d")


def iso_day(yyyymmdd):
    s = str(yyyymmdd)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def preflight(store_path=LIVE_STORE):
    from matchup_dna.forecasting import espn
    if Path(store_path).exists():
        store = open_readonly(store_path)
        try:
            if runs_in_progress(store):
                raise Refused("a forecasting run is in progress; run this after it finishes")
        finally:
            store.close()
    from matchup_dna.forecasting.pipeline import ESPN_EVIDENCE_FROM
    directory = espn.archive_dir()
    # The responses load_archive would parse: since the evidence date, the newest one per tour and day.
    newest = {}
    for m in sorted(espn.archived_meta(directory), key=lambda m: m["retrieved_at"], reverse=True):
        if m["day"] >= ESPN_EVIDENCE_FROM.isoformat():
            newest.setdefault((m["league"], m["day"]), m)
    missing = [m["file"] for m in newest.values() if not (directory / m["file"]).with_suffix(".records.json").exists()]
    if missing:
        raise Refused(f"{len(missing)} ESPN responses have no parse cache yet; run this after the next forecasting job")


def load_history(now):
    from matchup_dna.forecasting.history import load_sources
    from matchup_dna.forecasting.pipeline import live_assembly
    from matchup_dna.phase4_experiment import PROTOCOL_PATH
    sources = load_sources(PROTOCOL_PATH)
    return live_assembly(sources, now).matches, sources


def thin(points, limit=SERIES_POINTS):
    """At most `limit` points, evenly spaced, always keeping the first and last."""
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(i * step)] for i in range(limit)]


def build(matches, sources, now):
    from matchup_dna.forecasting.espn import add_tennisdata_ranks, last_known_ranks, rank_before
    today = int(ymd(now))
    active_from = int(ymd(now - datetime.timedelta(days=ACTIVE_DAYS)))
    series_from = int(ymd(now - datetime.timedelta(days=SERIES_DAYS)))
    predictions, ratings = run_elo(matches, ELO_K)
    _, surface_ratings = run_elo(matches, SURFACE_ELO_K)

    names = {}
    for m in matches:
        for side in ("winner", "loser"):
            key = (m["tour"], m[f"{side}_id"])
            if m.get(f"{side}_name"):
                names[key] = m[f"{side}_name"]

    series, recent, last = defaultdict(list), defaultdict(list), {}
    season = defaultdict(lambda: {s: [0, 0] for s in ("All",) + SURFACES})
    for p in predictions:
        m = p["match"]
        for side, other, won in (("winner", "loser", True), ("loser", "winner", False)):
            key = (m["tour"], m[f"{side}_id"])
            last[key] = m.get("match_day", m["tourney_date"])
            if m["tourney_date"] >= series_from:
                points = series[key]
                if not points or points[-1][0] != m["tourney_date"]:
                    points.append((m["tourney_date"], p[f"{side}_rating"]))
            if str(m["tourney_date"])[:4] == str(now.year):
                for bucket in ("All", m.get("surface")):
                    if bucket in season[key]:
                        season[key][bucket][0 if won else 1] += 1
            recent[key].append({"date": iso_day(m.get("match_day", m["tourney_date"])),
                                "event": m.get("tourney_name") or "", "round": m.get("round") or "",
                                "surface": m.get("surface"), "opponent_id": m[f"{other}_id"], "won": won})
            if len(recent[key]) > RECENT:
                recent[key].pop(0)

    ranks = add_tennisdata_ranks(last_known_ranks(matches), sources)
    active = [key for key, day in last.items() if day >= active_from]
    profiles = {}
    for key in active:
        tour, pid = key
        overall = ratings.get(key, {"rating": START_RATING, "played": 0})
        s_overall = surface_ratings.get(key, {"rating": START_RATING, "played": 0})
        surfaces = {}
        for s in SURFACES:
            state = surface_ratings.get(key + (s,), {"rating": START_RATING, "played": 0})
            surfaces[s] = {"elo": round(blended_rating(s_overall["rating"], state["rating"], SURFACE_WEIGHT), 1),
                           "matches": state["played"]}
        rank, rank_day = rank_before(ranks, tour, pid, today + 1)
        trend = series[key] + [(today, overall["rating"])]
        ninety = int(ymd(now - datetime.timedelta(days=90)))
        before = [r for d, r in trend if d <= ninety]
        profiles[key] = {
            "id": pid, "tour": tour, "name": names.get(key, str(pid)),
            "rank": rank, "rank_as_of": iso_day(rank_day) if rank_day else None,
            "elo": round(overall["rating"], 1), "rated_matches": overall["played"],
            "elo_change_90d": round(overall["rating"] - before[-1], 1) if before else None,
            "surfaces": surfaces, "season": {"year": now.year, **season[key]}, "last_match": iso_day(last[key]),
            "series": [[iso_day(d), round(r, 1)] for d, r in thin(trend)],
            "recent": [dict(r, opponent=names.get((tour, r["opponent_id"]), str(r["opponent_id"]))) for r in reversed(recent[key])],
        }
    for tour in ("ATP", "WTA"):
        ordered = sorted((p for p in profiles.values() if p["tour"] == tour), key=lambda p: -p["elo"])
        for i, p in enumerate(ordered, 1):
            p["elo_rank"] = i
    index = [{k: p[k] for k in ("id", "tour", "name", "rank", "elo", "elo_rank", "elo_change_90d",
                                "last_match", "rated_matches")}
             | {"surfaces": {s: p["surfaces"][s]["elo"] for s in SURFACES}, "season": p["season"]["All"],
                "spark": [r for _, r in thin(p["series"], 24)]}
             for p in profiles.values()]
    index.sort(key=lambda p: (p["tour"], p["elo_rank"]))
    return index, profiles


def write(index, profiles, now, out=OUT):
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    directory = Path(out) / "v1" / stamp
    files = {"players/index.json": {"schema_version": "1", "generated_at": iso(now), "players": index}}
    for p in profiles.values():
        files[f"players/{p['id']}.json"] = {"schema_version": "1", "generated_at": iso(now), "player": p}
    hashes = {}
    for name, doc in files.items():
        contract.check_any(doc)
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        path.write_text(text, encoding="utf-8")
        hashes[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    manifest = {"schema_version": "1", "generated_at": iso(now), "snapshot": stamp, "files": hashes,
                "players": len(profiles)}
    staging = Path(out) / "v1" / "manifest.json.tmp"
    staging.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    os.replace(staging, Path(out) / "v1" / "manifest.json")
    for old in sorted((Path(out) / "v1").iterdir()):
        if old.is_dir() and old.name != stamp:
            shutil.rmtree(old, ignore_errors=True)        # keep only the newest local export
    return manifest


def main():
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    try:
        preflight()
    except Refused as refused:
        print(f"skipped: {refused}")
        return 0
    matches, sources = load_history(now)
    index, profiles = build(matches, sources, now)
    manifest = write(index, profiles, now)
    print(f"wrote {manifest['players']} player profiles ({sum(p['tour'] == 'ATP' for p in index)} ATP, "
          f"{sum(p['tour'] == 'WTA' for p in index)} WTA) to web/.data/history/v1/{manifest['snapshot']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
