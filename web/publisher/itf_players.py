"""Profiles for the ITF board's players, in the same format as the main-tour profiles (web/publisher/players.py).

    python -m web.publisher.itf_players    writes web/.data/itf-history/v1/<time>/ and v1/manifest.json

The same pages as the main tour (a sortable table, a profile per player, compare), built from the ITF model's own
history and rating:
- the history is the one each ITF run reads: the Sackmann files at every level, plus finished Flashscore matches
  with both players resolved and not already in Sackmann (matchup_dna.itf_live, read-only here);
- the rating is the ITF model's Elo: one pool across every level, K = 250 / (matches played + 5) ** 0.4
  (itf_ratings.VARIANTS["decaying"]); surface Elo is blended half and half with overall Elo, as on the main tour;
- listed: players with at least five ITF main-draw matches in the last 52 weeks (the ITF board's rule), the
  BOARD_SIZE highest rated per tour.

Display only. It never opens the ITF store and never changes a forecast. No photos: the ITF pages show initials.
"""
import datetime
import re
import sys
from collections import defaultdict
from pathlib import Path

from web.publisher import players

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / ".data" / "itf-history"


def ymd_int(day):
    return int(day.strftime("%Y%m%d"))


def tourney_names(tour):
    """{tourney_id: name} from the Sackmann files the ITF history reads (the slim records do not keep names)."""
    from matchup_dna import itf_data, itf_splits
    found = {}
    for file_tour, _family, path in itf_data.files():
        if file_tour != tour:
            continue
        for row in itf_splits.rows(path, allow_held_out=True):
            if row.get("tourney_name"):
                found[row["tourney_id"]] = row["tourney_name"]
    return found


def itf_replay(matches, keep_from):
    """(predictions from `keep_from` on, ratings, surface ratings) for the ITF model's Elo. The decaying variant uses
    one K rule for overall and surface Elo, so one replay gives both."""
    from matchup_dna import itf_ratings
    spec = itf_ratings.VARIANTS["decaying"]
    assert spec["k"] == spec["surface_k"] and spec["start"] is None
    predictions, ratings = itf_ratings.run_elo(matches, spec["k"], keep=lambda m: m["tourney_date"] >= keep_from)
    return predictions, ratings, ratings


def itf_record(matches, since):
    """{player id: ITF main-draw matches played since `since`}, counted as the ITF board counts them."""
    from matchup_dna.itf_live import PLAYED
    found = defaultdict(int)
    for m in matches:
        itf = m["family"] == "itf" and (m["itf_scope"] or m["key"][-1] == "flashscore")
        if itf and m["outcome"] in PLAYED and m["tourney_date"] >= since and m["winner_id"] != m["loser_id"]:
            found[m["winner_id"]] += 1
            found[m["loser_id"]] += 1
    return found


def listed_players(tour, matches, ratings, now):
    """The ITF board's players: BOARD_MIN_MATCHES ITF main-draw matches in 52 weeks, the BOARD_SIZE highest rated."""
    from matchup_dna.itf_live import BOARD_MIN_MATCHES, BOARD_SIZE
    record = itf_record(matches, ymd_int(now.date() - datetime.timedelta(days=364)))
    eligible = [(tour, pid) for pid, n in record.items() if n >= BOARD_MIN_MATCHES and (tour, pid) in ratings]
    eligible.sort(key=lambda key: -ratings[key]["rating"])
    return eligible[:BOARD_SIZE]


FLASHSCORE_NAME = re.compile(r"^(.*\S)\s+((?:[A-Z][a-z]?\.-?)+)$")      # "Wolf J.J.", "Meligeni Alves F."
ROUND_ORDER = {r: i for i, r in enumerate(("Q1", "Q2", "Q3", "Q4", "R128", "R64", "R32", "R16", "QF", "SF", "F"))}


def readable(name):
    """Flashscore's "Last F." as "F. Last"; any other name unchanged."""
    m = FLASHSCORE_NAME.match(name or "")
    return f"{m.group(2)} {m.group(1)}" if m else name


def played_order(match):
    """Week, then the day played (when known), then the round: the order recent results and meetings are listed in.
    The replay applies a week's matches together, so this order never changes a rating."""
    return (match["tourney_date"], match.get("match_day") or match["tourney_date"], ROUND_ORDER.get(match["round"], 99))


def display_names(tour, ids, fs_matches):
    """Full names from the Sackmann player files, else the name Flashscore last showed."""
    from matchup_dna.itf_live import RESOLVED, resolve_side
    found = {}
    for m in sorted(fs_matches, key=lambda x: x["start"] or ""):
        for side in (m["home"], m["away"]):
            status, pid = resolve_side(ids, tour, side)
            if status in RESOLVED and side["name"]:
                found[(tour, pid)] = readable(side["name"])
    for (person_tour, pid), person in ids.players.items():
        if person_tour == tour and person.get("name"):
            found[(tour, pid)] = person["name"]
    return found


def with_details(history, fs_matches):
    """Flashscore history records with the event name and the day the match was played."""
    by_id = {m["provider_match_id"]: m for m in fs_matches}
    out = []
    for record in history:
        m = by_id.get(record["provider_match_id"])
        extra = {"tourney_name": m["event"] if m else ""}
        if m and m["start"]:
            extra["match_day"] = int(m["start"][:10].replace("-", ""))
        out.append(dict(record, **extra))
    return out


def build_tour(tour, fs_all, monday_of, now, log=print):
    from matchup_dna import itf_data
    from matchup_dna.itf_live import flashscore_history, resolver, sackmann_index
    sackmann = itf_data.load(allow_held_out=True, tours=(tour,))
    names = tourney_names(tour)
    for m in sackmann:
        m["tourney_name"] = names.get(m["tourney_id"], "")
    fs = [m for m in fs_all if m["tour"] == tour]
    ids = resolver(sackmann, fs)
    history, _ = flashscore_history(fs, ids, sackmann_index(sackmann), monday_of)
    matches = sorted(sackmann + with_details(history, fs), key=played_order)
    series_from = ymd_int(now - datetime.timedelta(days=players.SERIES_DAYS))
    predictions, ratings, surface = itf_replay(matches, series_from)
    chosen = listed_players(tour, matches, ratings, now)
    index, profiles = players.build(matches, None, now, replay=lambda _: (predictions, ratings, surface),
                                    listed=lambda _last: chosen, names=display_names(tour, ids, fs))
    log(f"{tour}: {len(matches)} matches ({len(history)} from Flashscore), {len(profiles)} players listed")
    size = {"matches": len(matches), "sackmann": len(sackmann), "main_tour": sum(m["family"] == "main" for m in matches)}
    return index, profiles, size


def main():
    from matchup_dna import itf_flashscore
    from matchup_dna.itf_live import FLASHSCORE_FROM, editions
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    fs_all = itf_flashscore.load(since=FLASHSCORE_FROM)
    if not fs_all:
        print("skipped: no ITF pages on disk yet")
        return 0
    monday_of = editions(fs_all)
    from web.publisher.itf_view import ITF_SACKMANN_MATCHES
    index, profiles, size = [], {}, {"matches": 0, "sackmann": 0, "main_tour": 0}
    for tour in ("ATP", "WTA"):
        i, p, s = build_tour(tour, fs_all, monday_of, now)
        index += i
        profiles.update(p)
        size = {k: size[k] + s[k] for k in size}
    if size["sackmann"] != ITF_SACKMANN_MATCHES:
        print(f"warning: the Sackmann ITF history has {size['sackmann']} matches, not ITF_SACKMANN_MATCHES "
              f"({ITF_SACKMANN_MATCHES}); the ITF match count on the home page is off by the difference")
    index.sort(key=lambda p: (p["tour"], p["elo_rank"]))
    # The history's size, and how much of it is main-tour (also in the main tour's history): the home page subtracts
    # that part so the combined match count never counts a match twice.
    extra = {"history": {"matches": size["matches"], "main_tour_matches": size["main_tour"]}}
    manifest = players.write(index, profiles, now, out=OUT, extra=extra)
    print(f"wrote {manifest['players']} ITF player profiles to web/.data/itf-history/v1/{manifest['snapshot']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
