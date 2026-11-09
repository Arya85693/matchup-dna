"""Official tour headshots: atptour.com for ATP players and wtatennis.com for WTA players (used with permission).

They are the main photo source; Wikimedia Commons photos come next (see below), ESPN headshots fill the remaining
gaps and initials cover the rest. Images are linked to, never
downloaded into the site, and never feed any model. Requests are paced, identify the project, and are cached with
their retrieval time (data/raw/headshots/), so a player is re-checked at most once a week.

Identity, never a guess:
- ATP: TennisIsMyLife ids are ATP player codes. A code is mapped to our player id through the same validated
  crosswalk the forecasting job uses (matchup_dna.merge.resolve), and kept only if it is the player's only code and
  no other player has it.
- WTA: WTA's ranked-player list gives each player's WTA id, name, country and date of birth. A player is matched on
  their full name plus date of birth, or, where we have no date of birth, plus country; a disagreeing date of birth
  rejects the match, and a name shared by two people on either side is never matched.
- ATP serves a grey silhouette for unknown codes; an image identical to it is not a photo.
Ranking positions are read only to list the players; they are not stored or shown.

Wikimedia Commons (freely licensed photos) is the next source. Wikidata records each player's ATP player code (P536)
and WTA player id (P597), so a photo is found through the same ids, never by name. A code held by more than one
Wikidata item is skipped. Each photo keeps its author, licence and Commons page, which the site shows as its credit.
"""
import datetime
import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "raw" / "headshots" / "official.json"
ARCHIVE = ROOT / "data" / "raw" / "headshots"
USER_AGENT = ("MatchupDNA-research/1.0 (https://matchup-dna.vercel.app; player headshots for a "
              "non-commercial tennis research site)")
COMMONS_CACHE = ROOT / "data" / "raw" / "headshots" / "commons.json"
WIKIDATA = "https://query.wikidata.org/sparql?format=json&query="
COMMONS_API = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo"
               "&iiprop=url|size|extmetadata&iiurlwidth=240&iiextmetadatafilter=Artist|LicenseShortName|LicenseUrl"
               "&titles=")
WIKIDATA_PROPERTY = {"ATP": "P536", "WTA": "P597"}
WIKIDATA_BATCH = 100
COMMONS_BATCH = 50
ATP_IMAGE = "https://www.atptour.com/-/media/alias/player-headshot/{code}"
ATP_UNKNOWN = "zzzz"                     # a code no player has: the silhouette ATP serves for unknown players
WTA_RANKED = ("https://api.wtatennis.com/tennis/players/ranked?metric=SINGLES&type=rankSingles&sort=asc"
              "&page={page}&pageSize=100")
WTA_PHOTO = ("https://api.wtatennis.com/content/wta/photo/EN/?references=TENNIS_PLAYER%3A{id}"
             "&tagNames=head-cropped-photo&pageSize=1")
WTA_SIZE = "?width=240"
RECHECK_DAYS = 7
PAUSE = 0.5
MAX_WTA_PAGES = 40


def fetch(url, timeout=20):
    """(status, body bytes); (0, b"") when the request fails."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except Exception:            # an unreachable photo is simply not shown; the export never fails on it
        return 0, b""


def norm(name):
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(text.replace("-", " ").replace(".", " ").replace("'", "").split())


# --- identities -------------------------------------------------------------------------------------------------

def atp_codes(tml_rows, tml_links):
    """{("ATP", our id): ATP code} through the job's validated crosswalk; one code per player, one player per code."""
    from matchup_dna.merge import resolve
    codes, owners = defaultdict(set), defaultdict(set)
    for row in tml_rows:
        if row.get("tour") != "ATP" or "winner_id" not in row:
            continue
        for side in ("winner", "loser"):
            code = (row.get(f"{side}_id") or "").strip()
            if not code:
                continue
            ours = resolve("tml", "ATP", code, tml_links)
            codes[ours].add(code.lower())
            owners[code.lower()].add(ours)
    return {("ATP", ours): next(iter(found)) for ours, found in codes.items()
            if len(found) == 1 and len(owners[next(iter(found))]) == 1}


def wta_people(tml_rows, tml_links, sackmann_players):
    """{our WTA id: {"names" (every spelling seen), "dob" (YYYY-MM-DD or None), "country"}} from Sackmann's player
    file and TML rows."""
    from matchup_dna.merge import resolve
    people = {}
    for p in sackmann_players:
        dob = p.get("dob") or ""
        people[int(p["player_id"])] = {"names": {f"{p.get('name_first', '')} {p.get('name_last', '')}".strip()},
                                       "dob": f"{dob[:4]}-{dob[4:6]}-{dob[6:8]}" if len(dob) == 8 and dob[4:] != "0000" else None,
                                       "country": p.get("ioc") or None}
    for row in tml_rows:
        if row.get("tour") != "WTA" or "winner_id" not in row:
            continue
        for side in ("winner", "loser"):
            ours = resolve("tml", "WTA", (row.get(f"{side}_id") or "").strip(), tml_links)
            known = people.setdefault(ours, {"names": set(), "dob": None, "country": None})
            known["country"] = known["country"] or row.get(f"{side}_ioc") or None
            if row.get(f"{side}_name"):
                known["names"].add(row[f"{side}_name"])
    return people


def match_wta(wanted, people, ranked):
    """{("WTA", our id): WTA id} for the players in `wanted` (our ids), under the rules in the module docstring."""
    theirs, ours = defaultdict(list), defaultdict(set)
    for entry in ranked:
        theirs[norm(entry["fullName"])].append(entry)
    for pid, person in people.items():
        for name in person["names"]:
            ours[norm(name)].add(pid)
    claims = {}
    for pid in wanted:
        me = people.get(pid)
        if not me:
            continue
        names = {norm(n) for n in me["names"]}
        if any(len(ours[n]) > 1 for n in names):
            continue                             # one of their names belongs to someone else too: never guess
        candidates = {e["id"]: e for n in names for e in theirs.get(n, [])}
        if len(candidates) != 1:
            continue
        them = next(iter(candidates.values()))
        if me["dob"] and them.get("dateOfBirth"):
            ok = me["dob"] == them["dateOfBirth"][:10]
        elif me["country"] and them.get("countryCode"):
            ok = me["country"].upper() == them["countryCode"].upper()
        else:
            ok = False
        if ok:
            claims.setdefault(int(them["id"]), []).append(pid)
    return {("WTA", pids[0]): wta_id for wta_id, pids in claims.items() if len(pids) == 1}


# --- fetching (paced, cached) ---------------------------------------------------------------------------------

def wta_ranked(get=fetch, pause=PAUSE, archive=ARCHIVE, now=None):
    """Every player on WTA's singles list: [{"id", "fullName", "countryCode", "dateOfBirth"}]."""
    players, raw = [], []
    for page in range(MAX_WTA_PAGES):
        status, body = get(WTA_RANKED.format(page=page))
        if status != 200:
            break
        rows = json.loads(body)
        if not rows:
            break
        raw.extend(rows)
        players += [{k: r["player"].get(k) for k in ("id", "fullName", "countryCode", "dateOfBirth")} for r in rows]
        time.sleep(pause)
    if archive and raw:
        stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
        Path(archive).mkdir(parents=True, exist_ok=True)
        (Path(archive) / f"wta_ranked_{stamp}.json").write_text(json.dumps(raw), encoding="utf-8")
    return players


def load_cache(path=CACHE):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"entries": {}}


def official(atp, wta, now, get=fetch, cache_path=CACHE, pause=PAUSE):
    """{(tour, our id): image URL} for players with an official headshot. `atp` maps keys to ATP codes and `wta` to
    WTA ids. Each lookup is cached with its retrieval time and repeated after RECHECK_DAYS."""
    cache = load_cache(cache_path)
    entries = cache.setdefault("entries", {})
    fresh_after = (now - datetime.timedelta(days=RECHECK_DAYS)).isoformat()

    def stale(key):
        return key not in entries or entries[key].get("checked", "") < fresh_after

    if atp and (not cache.get("atp_silhouette_sha256") or stale("ATP:" + ATP_UNKNOWN)):
        status, body = get(ATP_IMAGE.format(code=ATP_UNKNOWN))
        if status == 200 and body:
            cache["atp_silhouette_sha256"] = hashlib.sha256(body).hexdigest()
            entries["ATP:" + ATP_UNKNOWN] = {"url": None, "checked": now.isoformat()}
    silhouette = cache.get("atp_silhouette_sha256")

    for code in sorted(set(atp.values())):
        key = f"ATP:{code}"
        if not silhouette or not stale(key):
            continue
        status, body = get(ATP_IMAGE.format(code=code))
        if status == 0:
            continue                             # unreachable: try again next run, keep any earlier answer
        real = status == 200 and body[:4] == b"\x89PNG" and hashlib.sha256(body).hexdigest() != silhouette
        entries[key] = {"url": ATP_IMAGE.format(code=code) if real else None, "checked": now.isoformat()}
        time.sleep(pause)

    for wta_id in sorted(set(wta.values())):
        key = f"WTA:{wta_id}"
        if not stale(key):
            continue
        status, body = get(WTA_PHOTO.format(id=wta_id))
        if status != 200:
            continue
        content = json.loads(body).get("content") or []
        url = next((c.get("onDemandUrl") for c in content
                    if any(r.get("type") == "TENNIS_PLAYER" and str(r.get("id")) == str(wta_id) for r in c.get("references", []))
                    and (c.get("onDemandUrl") or "").startswith("https://")), None)
        entries[key] = {"url": url + WTA_SIZE if url else None, "checked": now.isoformat()}
        time.sleep(pause)

    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    found = {}
    for key, code in atp.items():
        url = entries.get(f"ATP:{code}", {}).get("url")
        if url:
            found[key] = url
    for key, wta_id in wta.items():
        url = entries.get(f"WTA:{wta_id}", {}).get("url")
        if url:
            found[key] = url
    return found


# --- Wikimedia Commons, through Wikidata ------------------------------------------------------------------------

def plain(text, limit=160):
    """Commons credit fields are HTML: keep the words only."""
    parts = re.sub(r"</p>|<li[^>]*>|<br\s*/?>", ";", text or "", flags=re.I)        # paragraphs and list items
    words = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", parts)).split())
    words = "; ".join(p.strip() for p in words.split(";") if p.strip())
    return words if len(words) <= limit else words[:limit - 1].rstrip() + "…"


def choose(files):
    """One photo per player: portrait-shaped first (they suit a round crop), then cropped versions, then by name."""
    return min(files, key=lambda f: (f["width"] > f["height"], "crop" not in f["title"].lower(), f["title"]))


def commons(ids, now, get=fetch, cache_path=COMMONS_CACHE, pause=1.0):
    """{(tour, our id): {"url", "credit": {"author", "license", "license_url", "source"}}} for players whose
    Wikidata item, found by `ids` {(tour, our id): tour id (ATP code or WTA id)}, has a Commons image."""
    cache = load_cache(cache_path)
    people, files = cache.setdefault("entries", {}), cache.setdefault("files", {})
    fresh_after = (now - datetime.timedelta(days=RECHECK_DAYS)).isoformat()
    checked = now.isoformat()

    def stale(store, key):
        return key not in store or store[key].get("checked", "") < fresh_after

    for tour, prop in WIKIDATA_PROPERTY.items():
        wanted = sorted({str(v) for (t, _), v in ids.items() if t == tour and stale(people, f"{tour}:{str(v).upper()}")})
        for i in range(0, len(wanted), WIKIDATA_BATCH):
            batch = wanted[i:i + WIKIDATA_BATCH]
            values = " ".join(json.dumps(v.upper() if tour == "ATP" else v) for v in batch)
            query = (f"SELECT ?item ?id ?image WHERE {{ VALUES ?id {{ {values} }} ?item wdt:{prop} ?id . "
                     f"OPTIONAL {{ ?item wdt:P18 ?image }} }}")
            status, body = get(WIKIDATA + urllib.parse.quote(query))
            if status != 200:
                continue                             # Wikidata unreachable: keep earlier answers, try next run
            items, images = defaultdict(set), defaultdict(set)
            for row in json.loads(body)["results"]["bindings"]:
                key = f"{tour}:{row['id']['value'].upper()}"
                items[key].add(row["item"]["value"])
                if "image" in row:
                    images[key].add("File:" + urllib.parse.unquote(row["image"]["value"].rsplit("/", 1)[1]))
            for v in batch:
                key = f"{tour}:{v.upper()}"
                one = len(items[key]) == 1           # a code on two Wikidata items is ambiguous: no photo
                people[key] = {"files": sorted(images[key]) if one else [], "checked": checked}
            time.sleep(pause)

    needed = sorted({f for (t, _), v in ids.items() for f in people.get(f"{t}:{str(v).upper()}", {}).get("files", [])
                     if stale(files, f)})
    for i in range(0, len(needed), COMMONS_BATCH):
        batch = needed[i:i + COMMONS_BATCH]
        status, body = get(COMMONS_API + urllib.parse.quote("|".join(batch)))
        if status != 200:
            continue
        query = json.loads(body).get("query", {})
        asked = {n["to"]: n["from"] for n in query.get("normalized", [])}
        for page in query.get("pages", {}).values():
            title = asked.get(page.get("title"), page.get("title"))
            info = (page.get("imageinfo") or [{}])[0]
            meta = {k: v.get("value") for k, v in (info.get("extmetadata") or {}).items()}
            url = (info.get("thumburl") or "").split("?")[0]
            licence = plain(meta.get("LicenseShortName"), 40)
            usable = url.startswith("https://") and licence and (info.get("descriptionurl") or "").startswith("https://")
            files[title] = {"url": url if usable else None, "width": info.get("width", 0), "height": info.get("height", 0),
                            "artist_html": meta.get("Artist"), "license": licence or None,
                            "license_url": meta.get("LicenseUrl") if (meta.get("LicenseUrl") or "").startswith("https://") else None,
                            "source": info.get("descriptionurl"), "checked": checked}
        time.sleep(pause)

    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(cache, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    found = {}
    for key, v in ids.items():
        options = [dict(files[f], title=f) for f in people.get(f"{key[0]}:{str(v).upper()}", {}).get("files", [])
                   if files.get(f, {}).get("url")]
        if options:
            best = choose(options)
            found[key] = {"url": best["url"], "credit": {"author": plain(best.get("artist_html")) or "Unknown author",
                                                         "license": best["license"], "license_url": best["license_url"],
                                                         "source": best["source"]}}
    return found
