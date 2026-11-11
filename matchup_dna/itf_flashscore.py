"""ITF extension, stage I4: men's and women's ITF fixtures and results from Flashscore event pages.

    python -m matchup_dna.itf_flashscore current          this week's ITF singles events: every event page
    python -m matchup_dna.itf_flashscore backfill --since 20260602
                                                         every ITF singles event in Flashscore's sitemap, once each
                                                         (resumable); editions before --since are kept but unused
    python -m matchup_dna.itf_flashscore summary          what the archive holds

What a page gives (checked on real pages, 11 November 2026). An event page, /tennis/itf-men-singles/<slug>/results/,
embeds its matches in the page as data blocks ("summary-results", "summary-fixtures" and, on the results page,
"results" with every finished match) in Flashscore's `KEY÷value¬` format. One request gives the event's finished
and scheduled main-draw matches:

    header  ZA "ITF MEN - SINGLES: M15 Antalya 7 (Turkey), clay": tour, level, country, surface
    match   AA match id; AD start (Unix seconds, UTC); AB status (1 scheduled, 2 live, 3 finished) and AC detail;
            ER round ("1/16-finals" ... "Final"); per side: PX/PY player id, AE/AF short name, WU/WV name slug
            ("dlimi-yassine"), FU/FV country; AS winner (1 home, 2 away); BA/BB, BC/BD ... games per set and
            DA/DB ... tiebreak points

No ranks and no serve statistics are on the page. A slug no longer in use shows its last edition (M15 Cordoba 2:
September 2024), so editions are told apart by their dates.

Every page is kept: the data blocks as text, with the URL, retrieval time and the SHA-256 of the whole page and of
the blocks (data/raw/flashscore/). Requests are one a second with an identifying User-Agent, to the pages robots.txt
allows (event pages, the event lists, the sitemap); nothing else is requested.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from matchup_dna import itf_data
from matchup_dna.load import DATA_DIR

BASE = "https://www.flashscore.com"
USER_AGENT = "matchup-dna-research/0.9 (+https://matchup-dna.vercel.app)"
PAUSE_SECONDS = 1.0
CATEGORIES = {"itf-men-singles": "ATP", "itf-women-singles": "WTA"}          # scored, and forecast
HISTORY_CATEGORIES = {"challenger-men-singles": "ATP", "atp-singles": "ATP", "wta-singles": "WTA",
                      "challenger-women-singles": "WTA"}                       # rating history only (WTA 125 is
                                                                               # "challenger-women"), never scored
ALL_CATEGORIES = {**CATEGORIES, **HISTORY_CATEGORIES}
ROUNDS = {"1/64-finals": "R128", "1/32-finals": "R64", "1/16-finals": "R32", "1/8-finals": "R16",
          "Quarter-finals": "QF", "Semi-finals": "SF", "Final": "F"}
HEADER = re.compile(r"^(?P<category>[A-Z0-9 ]+?) - SINGLES: (?P<name>.+?) \((?P<country>[^)]+)\), (?P<surface>[^,]+)$")
LEVEL = re.compile(r"^(?P<sex>[MW])(?P<money>\d+)\b")
SURFACES = {"clay": "Clay", "hard": "Hard", "grass": "Grass", "carpet": "Carpet", "hard (indoor)": "Hard",
            "clay (indoor)": "Clay", "indoor": "Hard"}
FEEDS = re.compile(r"""cjs\.initialFeeds\[["'](?P<name>[^"']+)["']\]\s*=\s*\{\s*data:\s*`(?P<data>.*?)`""", re.S)
SET_KEYS = (("BA", "BB", "DA", "DB"), ("BC", "BD", "DC", "DD"), ("BE", "BF", "DE", "DF"), ("BG", "BH", "DG", "DH"),
            ("BI", "BJ", "DI", "DJ"))
STATUS = {"1": "scheduled", "2": "in_progress", "3": "finished"}
UTC = datetime.timezone.utc


def archive_dir():
    return DATA_DIR / "raw" / "flashscore"


def now_text():
    return datetime.datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- fetching and the archive

def get(path, opener=urllib.request.urlopen, retries=2):
    """(bytes, status) for BASE + path. Pages are requested compressed (gzip) and stored decompressed."""
    request = urllib.request.Request(BASE + path, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    for attempt in range(retries + 1):
        try:
            with opener(request, timeout=30) as response:
                body = response.read()
                headers = getattr(response, "headers", None)
                if headers is not None and headers.get("Content-Encoding", "").lower() == "gzip":
                    body = gzip.decompress(body)
                return body, response.status
        except urllib.error.HTTPError as error:
            if error.code in (403, 404, 410):
                return b"", error.code
            if attempt == retries:
                raise
        except urllib.error.URLError:
            if attempt == retries:
                raise
        time.sleep(5 * (attempt + 1))


def extract_feeds(html):
    """{block name: data} for the data blocks an event page embeds."""
    return {m["name"]: m["data"] for m in FEEDS.finditer(html)}


def stem_for(path, retrieved_at):
    slug = path.strip("/").replace("/", "_") or "root"
    return f"{slug}_{retrieved_at.replace(':', '').replace('-', '')}"


def fetch_event(category, slug, directory=None, opener=urllib.request.urlopen, retrieved_at=None):
    """Fetches one event page and archives its data blocks. Returns the meta record."""
    directory = Path(directory or archive_dir())
    directory.mkdir(parents=True, exist_ok=True)
    path = f"/tennis/{category}/{slug}/results/"
    body, status = get(path, opener)
    retrieved_at = retrieved_at or now_text()
    html = body.decode("utf-8", errors="replace")
    feeds = extract_feeds(html)
    text = json.dumps(feeds, ensure_ascii=False, sort_keys=True)
    stem = stem_for(path, retrieved_at)
    meta = {"url": BASE + path, "category": category, "slug": slug, "retrieved_at": retrieved_at, "http_status": status,
            "page_sha256": hashlib.sha256(body).hexdigest(), "page_bytes": len(body),
            "feeds_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "feeds": sorted(feeds),
            "file": f"{stem}.feeds.json"}
    (directory / meta["file"]).write_text(text, encoding="utf-8")
    (directory / f"{stem}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def archived(directory=None):
    directory = Path(directory or archive_dir())
    if not directory.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.meta.json"))]


# ---------------------------------------------------------------- discovery

def current_slugs(opener=urllib.request.urlopen, pause=PAUSE_SECONDS, categories=None):
    """{category: [slug]} of the events Flashscore lists this week (default: every category read)."""
    found = {}
    for category in categories or ALL_CATEGORIES:
        body, _ = get(f"/tennis/{category}/", opener)
        found[category] = sorted(set(re.findall(rf"/tennis/{category}/([a-z0-9-]+)/", body.decode("utf-8", "replace"))))
        time.sleep(pause)
    return found


def sitemap_slugs(opener=urllib.request.urlopen, categories=None):
    """{category: [slug]} of every event of these categories (default: all) in Flashscore's core sitemap."""
    body, _ = get("/sitemap/core.xml", opener)
    text = body.decode("utf-8", "replace")
    return {category: sorted(set(re.findall(rf"/tennis/{category}/([a-z0-9-]+)/", text)))
            for category in (categories or ALL_CATEGORIES)}


# ---------------------------------------------------------------- parsing

def segments(data):
    """[{key: value}] for each `~`-separated segment of a data block."""
    found = []
    for segment in data.split("~"):
        fields = {}
        for part in segment.split("¬"):
            if "÷" in part:
                key, value = part.split("÷", 1)
                fields[key] = value
        if fields:
            found.append(fields)
    return found


def parse_header(text):
    """{name, country, surface, level, tier, tour, itf} from a ZA line ("ITF MEN - SINGLES: M15 Antalya 7 (Turkey),
    clay"; also Challenger, ATP, WTA and WTA 125 singles), or None for anything else (doubles, team events)."""
    m = HEADER.match(text or "")
    if not m:
        return None
    category = m["category"].strip()
    itf = category.startswith("ITF ")
    tour = "WTA" if "WOMEN" in category or category.startswith("WTA") else "ATP"
    level = LEVEL.match(m["name"]) if itf else None
    money = level["money"] if level else None
    return {"name": m["name"], "country": m["country"], "surface": SURFACES.get(m["surface"].strip().lower()),
            "raw_surface": m["surface"], "level": money, "tour": tour, "itf": itf, "category": category,
            "tier": itf_data.TIERS[tour].get(money) if money else None}


def number(value):
    value = (value or "").strip()
    return int(value) if value.lstrip("-").isdigit() else None


def sets_of(record):
    """[(home games, away games, home tiebreak, away tiebreak)] for the sets played."""
    found = []
    for home, away, home_tb, away_tb in SET_KEYS:
        h, a = number(record.get(home)), number(record.get(away))
        if h is None or a is None:
            break
        found.append((h, a, number(record.get(home_tb)), number(record.get(away_tb))))
    return found


def score_text(sets, winner):
    """The score from the winner's side, Sackmann style ("7-6(3) 6-4")."""
    parts = []
    for h, a, htb, atb in sets:
        w, l = (h, a) if winner == "home" else (a, h)
        tiebreak = min(x for x in (htb, atb) if x is not None) if (htb is not None or atb is not None) else None
        parts.append(f"{w}-{l}" + (f"({tiebreak})" if tiebreak is not None and {w, l} == {6, 7} else ""))
    return " ".join(parts)


def outcome_of(record, sets, winner):
    """completed, retired, walkover, or None while unfinished. A finished match whose winner did not win a majority
    of finished sets is a retirement (the I1 audit's rule); a finished match with no sets is a walkover."""
    if STATUS.get(record.get("AB")) != "finished":
        return None
    if not sets:
        return "walkover"
    won = sum(itf_data.set_won_by_winner(*((h, a) if winner == "home" else (a, h)), "set") for h, a, _, _ in sets)
    return "completed" if won >= 2 else "retired"


def to_match(header, record, retrieved_at):
    """One match in the shape the ITF pipeline reads, or None for a round it does not score (qualifying etc.)."""
    round_ = ROUNDS.get(record.get("ER", "").strip())
    if round_ is None or header is None:
        return None
    winner = {"1": "home", "2": "away"}.get(record.get("AS"))
    sets = sets_of(record)
    outcome = outcome_of(record, sets, winner)
    start = number(record.get("AD"))
    return {
        "provider": "flashscore", "provider_match_id": record.get("AA"), "tour": header["tour"],
        "itf": header["itf"], "category": header["category"],
        "event": header["name"], "level": header["level"], "tier": header["tier"], "country": header["country"],
        "surface": header["surface"], "round": round_,
        "start": datetime.datetime.fromtimestamp(start, UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if start else None,
        "status": STATUS.get(record.get("AB"), "unknown"), "status_detail": record.get("AC"),
        "home": {"id": record.get("PX"), "name": record.get("AE"), "slug": record.get("WU"), "country": record.get("FU")},
        "away": {"id": record.get("PY"), "name": record.get("AF"), "slug": record.get("WV"), "country": record.get("FV")},
        "winner": winner, "outcome": outcome, "score": score_text(sets, winner) if winner else "",
        "retrieved_at": retrieved_at,
    }


def parse_page(feeds, retrieved_at):
    """(header, [matches], Counter of skipped rounds) from one page's data blocks; each match once."""
    header, matches, skipped = None, {}, Counter()
    for data in feeds.values():
        current = None
        for fields in segments(data):
            if "ZA" in fields:
                current = parse_header(fields["ZA"])
                header = header or current
            elif "AA" in fields:
                match = to_match(current, fields, retrieved_at)
                if match is None:
                    skipped[fields.get("ER", "?")] += 1
                elif match["provider_match_id"] not in matches:
                    matches[match["provider_match_id"]] = match
    return header, list(matches.values()), skipped


def load(directory=None, since=None):
    """The latest archived state of every match (by retrieval time), optionally starting on or after `since`
    (YYYYMMDD)."""
    directory = Path(directory or archive_dir())
    latest = {}
    for meta in sorted(archived(directory), key=lambda m: m["retrieved_at"]):
        feeds = json.loads((directory / meta["file"]).read_text(encoding="utf-8"))
        _, matches, _ = parse_page(feeds, meta["retrieved_at"])
        for match in matches:
            if since and match["start"] and int(match["start"][:10].replace("-", "")) < since:
                continue
            match["slug"], match["page_category"] = meta["slug"], meta["category"]
            latest[match["provider_match_id"]] = match
    return list(latest.values())


# ---------------------------------------------------------------- commands

def fetch_all(pairs, directory=None, skip_archived=False, pause=PAUSE_SECONDS, log=print):
    done = {(m["category"], m["slug"]) for m in archived(directory)} if skip_archived else set()
    fetched = 0
    for category, slug in pairs:
        if (category, slug) in done:
            continue
        meta = fetch_event(category, slug, directory)
        fetched += 1
        if fetched % 100 == 0:
            log(f"{fetched} pages ({category}/{slug}, HTTP {meta['http_status']})")
        time.sleep(pause)
    return fetched


def summary(directory=None, since=None):
    matches = load(directory, since)
    return {"pages": len(archived(directory)), "matches": len(matches),
            "by_tour_status": dict(Counter(f"{m['tour']} {m['status']}" for m in matches)),
            "by_outcome": dict(Counter(f"{m['tour']} {m['outcome']}" for m in matches)),
            "status_detail": dict(Counter(f"{m['status']}/{m['status_detail']}" for m in matches)),
            "first_start": min((m["start"] for m in matches if m["start"]), default=None),
            "last_start": max((m["start"] for m in matches if m["start"]), default=None)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("current", "backfill", "summary"))
    parser.add_argument("--since", type=int, default=None)
    args = parser.parse_args(argv)
    if args.command == "current":
        slugs = current_slugs()
        print({c: len(s) for c, s in slugs.items()})
        print(f"fetched {fetch_all([(c, s) for c, ss in slugs.items() for s in ss])} event pages")
    elif args.command == "backfill":
        slugs = sitemap_slugs()
        print({c: len(s) for c, s in slugs.items()})
        print(f"fetched {fetch_all([(c, s) for c, ss in slugs.items() for s in ss], skip_archived=True)} event pages")
    print(json.dumps(summary(since=args.since), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
