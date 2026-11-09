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
- this season's win-loss record by surface;
- an Elo trend;
- the last few results as win or loss against a named opponent (no scores, no statistics, no raw rows);
Players listed in web/content/retired.json (announced retirements, each with a source) are left out of the profiles,
the index and the Elo positions. Their matches still count everywhere else: in the Elo replay, in other players' results
and in every backtest.

- head-to-head meetings with every other active player on the same tour: date, event, round, surface, who won,
  and whether it ended in a retirement. Completed and retired matches count, as on the tours; walkovers do not.
"""
import datetime
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from matchup_dna.features import PLAYED_OUTCOMES
from matchup_dna.elo import ELO_K, SURFACE_ELO_K, SURFACE_WEIGHT, START_RATING, blended_rating, run_elo
from matchup_dna.forecasting.records import iso
from web.publisher import contract
from web.publisher.readonly import open_readonly, runs_in_progress

ROOT = Path(__file__).resolve().parents[2]
LIVE_STORE = ROOT / "data" / "store" / "live.sqlite"
OUT = ROOT / "web" / ".data" / "history"
RETIRED = ROOT / "web" / "content" / "retired.json"
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
    assembly = live_assembly(sources, now)
    return assembly.matches, sources, espn_photos(assembly)


PHOTO = "https://a.espncdn.com/combiner/i?img=/i/headshots/tennis/players/full/{id}.png&w=200&h=200"
PHOTO_CACHE = ROOT / "data" / "raw" / "espn_headshots.json"
PHOTO_RECHECK_DAYS = 7


def head_ok(url, opener=None):
    """True if the image exists (HTTP 200), False if it does not (404), None if the check itself failed."""
    import urllib.error
    import urllib.request
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "matchup-dna-research/1.0"})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=15) as response:
            return response.status == 200
    except urllib.error.HTTPError as error:
        return False if error.code == 404 else None
    except OSError:
        return None


def available(photos, now, check=head_ok, cache_path=PHOTO_CACHE, pause=0.15):
    """Keeps only headshots that exist. Results are cached for PHOTO_RECHECK_DAYS so later runs make few requests."""
    import time
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    fresh_after = now - datetime.timedelta(days=PHOTO_RECHECK_DAYS)
    kept = {}
    for key, url in photos.items():
        entry = cache.get(url)
        if entry is None or datetime.datetime.fromisoformat(entry["checked"].replace("Z", "+00:00")) < fresh_after:
            ok = check(url)
            if ok is None:
                continue                                  # unknown: leave it out this run, try again next run
            entry = cache[url] = {"ok": ok, "checked": iso(now)}
            time.sleep(pause)
        if entry["ok"]:
            kept[key] = url
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, sort_keys=True), encoding="utf-8")
    return kept


def espn_photos(assembly):
    """{(tour, player id): headshot URL} for players whose ESPN identity the job's resolver verified. One ESPN id per
    player only; the image is linked to, never downloaded or stored."""
    resolve = assembly.resolvers.get("espn")
    found = {}
    if resolve is None:
        return {}
    for record in assembly.records:
        if getattr(record, "provider", None) != "espn":
            continue
        for side in ("home", "away"):
            espn_id, name = getattr(record, f"{side}_id", None), getattr(record, f"{side}_name", None)
            if not espn_id:
                continue
            who = resolve(record.tour, espn_id, name)
            if who and who.get("status") == "verified" and who.get("player_id") is not None:
                found.setdefault((record.tour, who["player_id"]), set()).add(str(espn_id))
    return {key: PHOTO.format(id=next(iter(ids))) for key, ids in found.items() if len(ids) == 1}


def tour_headshots(sources, profiles, now):
    """Photos for the listed players, best source first: the official ATP or WTA headshot, else a Wikimedia Commons
    photo found through the same tour id (see headshots.py for the identity rules). Returns ({key: url},
    {key: credit}); only Commons photos carry a credit."""
    import csv
    from web.publisher import headshots
    listed = set(profiles)
    atp = {k: code for k, code in headshots.atp_codes(sources.tml_rows, sources.tml_links).items() if k in listed}
    with open(ROOT / "data" / "wta" / "wta_players.csv", encoding="utf-8", newline="") as f:
        people = headshots.wta_people(sources.tml_rows, sources.tml_links, csv.DictReader(f))
    for (tour, pid), p in profiles.items():
        if tour == "WTA":
            people.setdefault(pid, {"names": set(), "dob": None, "country": None})["names"].add(p["name"])
    wanted = [pid for tour, pid in listed if tour == "WTA"]
    wta = headshots.match_wta(wanted, people, headshots.wta_ranked(now=now))
    print(f"official headshots: {len(atp)} ATP codes, {len(wta)} of {len(wanted)} WTA players matched")
    official = headshots.official(atp, wta, now)
    free = headshots.commons({**atp, **wta}, now)
    photos = {k: v["url"] for k, v in free.items()}
    credits = {k: v["credit"] for k, v in free.items()}
    for key, url in official.items():                       # an official headshot outranks a Commons photo
        photos[key] = url
        credits.pop(key, None)
    print(f"photos: {len(official)} official, {len(set(free) - set(official))} from Wikimedia Commons")
    return photos, credits


def thin(points, limit=SERIES_POINTS):
    """At most `limit` points, evenly spaced, always keeping the first and last."""
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(i * step)] for i in range(limit)]


def load_retired(path=RETIRED):
    """(tour, id) -> listed name, for players with an announced retirement."""
    if not Path(path).exists():
        return {}
    return {(r["tour"], r["id"]): r["name"] for r in json.loads(Path(path).read_text(encoding="utf-8"))["players"]}


def build(matches, sources, now, photos=None, retired=None):
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

    for key, listed in (retired or {}).items():
        if key in names and names[key].strip().lower() != listed.strip().lower():
            raise ValueError(f"retired.json lists {key} as {listed!r}, but the history names them {names[key]!r}")
    active = [key for key, day in last.items() if day >= active_from and key not in (retired or {})]
    active_set = set(active)
    h2h = defaultdict(lambda: defaultdict(list))
    for m in sorted(matches, key=lambda m: (m["tourney_date"], m.get("match_day") or m["tourney_date"])):
        w, l = (m["tour"], m["winner_id"]), (m["tour"], m["loser_id"])
        if m.get("outcome") not in PLAYED_OUTCOMES or w == l or w not in active_set or l not in active_set:
            continue
        meeting = {"date": iso_day(m.get("match_day", m["tourney_date"])), "event": m.get("tourney_name") or "",
                   "round": m.get("round") or "", "surface": m.get("surface"), "retired": m["outcome"] == "retired"}
        h2h[w][str(l[1])].append(dict(meeting, won=True))
        h2h[l][str(w[1])].append(dict(meeting, won=False))
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
        trend = series[key] + [(today, overall["rating"])]
        ninety = int(ymd(now - datetime.timedelta(days=90)))
        before = [r for d, r in trend if d <= ninety]
        profiles[key] = {
            "id": pid, "tour": tour, "name": names.get(key, str(pid)), "photo": (photos or {}).get(key),
            "photo_credit": None, "elo": round(overall["rating"], 1), "rated_matches": overall["played"],
            "elo_change_90d": round(overall["rating"] - before[-1], 1) if before else None,
            "surfaces": surfaces, "season": {"year": now.year, **season[key]}, "last_match": iso_day(last[key]),
            "series": [[iso_day(d), round(r, 1)] for d, r in thin(trend)],
            "recent": [dict(r, opponent=names.get((tour, r["opponent_id"]), str(r["opponent_id"]))) for r in reversed(recent[key])],
            "h2h": {opp: list(reversed(meetings)) for opp, meetings in sorted(h2h[key].items())},   # newest first
        }
    for tour in ("ATP", "WTA"):
        ordered = sorted((p for p in profiles.values() if p["tour"] == tour), key=lambda p: -p["elo"])
        for i, p in enumerate(ordered, 1):
            p["elo_rank"] = i
    index = [{k: p[k] for k in ("id", "tour", "name", "photo", "elo", "elo_rank", "elo_change_90d",
                                "last_match", "rated_matches")}
             | {"surfaces": {s: p["surfaces"][s]["elo"] for s in SURFACES}, "season": p["season"]["All"],
                "surface_matches": {s: p["surfaces"][s]["matches"] for s in SURFACES},
                "spark": thin(p["series"], 24)}          # [date, rating] pairs: the trend with its real dates
             for p in profiles.values()]
    index.sort(key=lambda p: (p["tour"], p["elo_rank"]))
    return index, profiles


def write(index, profiles, now, out=OUT):
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    directory = Path(out) / "v1" / stamp
    files = {"players/index.json": {"schema_version": "1", "generated_at": iso(now), "players": index}}
    for p in profiles.values():
        files[f"players/{p['tour'].lower()}-{p['id']}.json"] = {"schema_version": "1", "generated_at": iso(now), "player": p}
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
    matches, sources, espn = load_history(now)
    espn = available(espn, now)
    index, profiles = build(matches, sources, now, None, load_retired())
    best, credits = tour_headshots(sources, profiles, now)
    photos = {**espn, **best}                  # official tour photos, then Wikimedia Commons; ESPN fills the gaps
    for p in index:
        p["photo"] = photos.get((p["tour"], p["id"]))
    for key, p in profiles.items():
        p["photo"] = photos.get(key)
        p["photo_credit"] = credits.get(key)
    manifest = write(index, profiles, now)
    print(f"{sum(1 for p in index if p['photo'])} with a verified photo; wrote {manifest['players']} player profiles ({sum(p['tour'] == 'ATP' for p in index)} ATP, "
          f"{sum(p['tour'] == 'WTA' for p in index)} WTA) to web/.data/history/v1/{manifest['snapshot']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
