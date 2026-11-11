"""ITF extension, stage I4: weekly ATP and WTA singles rankings from TennisExplorer, for the rank features.

    python -m matchup_dna.itf_rankings fetch [--date YYYY-MM-DD ...]   the ranking lists of those weeks (default:
                                                                       the latest), every page; archived
    python -m matchup_dna.itf_rankings backfill --since 2026-06-01     every weekly list from that date on
                                                                       (resumable)

A ranking page (/ranking/atp-men/?date=YYYY-MM-DD&page=N, likewise wta-women) lists 50 players: rank, full name
written surname first ("Yazdani Ali"), the TennisExplorer player path, country (in English, as Flashscore writes
it) and points. The page offers every weekly list of the season, so a match can take the rank published before it,
never a later one. Pages are archived like Flashscore's (data/raw/tennisexplorer/rankings/), one a second.
"""
import argparse
import datetime
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from matchup_dna.itf_flashscore import PAUSE_SECONDS, USER_AGENT, get as _get
from matchup_dna.load import DATA_DIR

BASE = "https://www.tennisexplorer.com"
LISTS = {"ATP": "atp-men", "WTA": "wta-women"}
ROW = re.compile(r'<td class="rank first">\s*(?P<rank>\d+)\.\s*</td>.*?<td class="t-name"><a href="(?P<path>/player/[^"]+)">'
                 r'(?P<name>[^<]+)</a></td>\s*<td class="tl"><a [^>]*>(?:\s*<span[^>]*>&nbsp;</span>)?(?P<country>[^<]*)</a>'
                 r'</td>\s*<td class="long-point">(?P<points>\d+)</td>', re.S)
DATES = re.compile(r'<option value="(?P<date>\d{4}-\d{2}-\d{2})"')


def archive_dir():
    return DATA_DIR / "raw" / "tennisexplorer" / "rankings"


def get(path, opener=urllib.request.urlopen):
    request = urllib.request.Request(BASE + path, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=30) as response:
        return response.read(), response.status


def parse(html):
    """([{rank, name, path, country, points}], [list dates offered])."""
    rows = [{"rank": int(m["rank"]), "name": m["name"].strip(), "path": m["path"], "country": m["country"].strip(),
             "points": int(m["points"])} for m in ROW.finditer(html)]
    return rows, sorted(set(DATES.findall(html)), reverse=True)


def fetch_list(tour, date=None, directory=None, opener=urllib.request.urlopen, pause=PAUSE_SECONDS, max_pages=200):
    """Every page of one weekly list; returns (date, rows). The list date is the one the page marks as selected."""
    directory = Path(directory or archive_dir())
    directory.mkdir(parents=True, exist_ok=True)
    rows, chosen = [], date
    for page in range(1, max_pages + 1):
        query = f"?page={page}" + (f"&date={date}" if date else "")
        body, status = get(f"/ranking/{LISTS[tour]}/{query}", opener)
        html = body.decode("utf-8", "replace")
        found, _ = parse(html)
        if chosen is None:
            selected = re.search(r'<option value="(\d{4}-\d{2}-\d{2})" selected', html)
            chosen = selected.group(1) if selected else "unknown"
        rows += found
        time.sleep(pause)
        if len(found) < 50:
            break
    record = {"tour": tour, "date": chosen, "rows": rows, "retrieved_at":
              datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")}
    text = json.dumps(record, ensure_ascii=False, sort_keys=True)
    record["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (directory / f"{tour}_{chosen}.json").write_text(json.dumps(record, ensure_ascii=False, indent=0), encoding="utf-8")
    return chosen, rows


def offered_dates(tour, opener=urllib.request.urlopen):
    body, _ = get(f"/ranking/{LISTS[tour]}/", opener)
    return parse(body.decode("utf-8", "replace"))[1]


def load(directory=None, key=None):
    """{tour: {date: [rows]}} from the archive; with `key` (row -> hashable), {tour: {date: {key(row): rank}}}."""
    directory = Path(directory or archive_dir())
    found = {}
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        record = json.loads(path.read_text(encoding="utf-8"))
        rows = record["rows"]
        found.setdefault(record["tour"], {})[record["date"]] = (
            rows if key is None else {key(row): row["rank"] for row in rows})
    return found


def rank_before(lists, tour, key, day, max_age_days=21):
    """The rank of `key` in the latest list published on or before `day` (YYYY-MM-DD), if that list is at most
    `max_age_days` old. `lists` is load(..., key=...). Returns (rank, list date) or (None, None)."""
    dates = sorted(d for d in lists.get(tour, {}) if d <= day)
    if not dates:
        return None, None
    latest = dates[-1]
    age = (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(latest)).days
    if age > max_age_days:
        return None, None
    return lists[tour][latest].get(key), latest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("fetch", "backfill"))
    parser.add_argument("--date", action="append")
    parser.add_argument("--since", default="2026-06-01")
    args = parser.parse_args(argv)
    for tour in LISTS:
        if args.command == "fetch":
            for date in args.date or [None]:
                chosen, rows = fetch_list(tour, date)
                print(f"{tour} {chosen}: {len(rows)} players")
        else:
            have = set(load().get(tour, {}))
            for date in sorted(d for d in offered_dates(tour) if d >= args.since and d not in have):
                chosen, rows = fetch_list(tour, date)
                print(f"{tour} {chosen}: {len(rows)} players")
    return 0


if __name__ == "__main__":
    sys.exit(main())
