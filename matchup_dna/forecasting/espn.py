"""ESPN scoreboards: fixtures and results that update without a manual download.

    https://site.api.espn.com/apis/site/v2/sports/tennis/{atp|wta}/scoreboard?dates=YYYYMMDD

One response per tour and day lists every match of every event running that day: scheduled ones with their UTC
start time and current ranks, finished ones with set scores (each player's tiebreak points per set) and a winner flag.
Every response is archived raw under data/raw/espn/ with its retrieval time and SHA-256 before it is parsed, so any
record can be traced to the exact bytes it came from.

What the responses do and do not give (checked on real responses, 8 November 2026):

- tour comes from the draw ("mens-singles" ATP, "womens-singles" WTA): the ATP feed also carries the women's draw of
  joint events (US Open, Bastad), so a match is taken from its draw, once, by competition id;
- rounds are numbered from the start of the draw ("Round 1", "Round 2", ... then "Quarterfinal", "Semifinal",
  "Final"); "Group Stage" is a round robin. The last numbered round is R16, the one before R32, and so on, exactly
  as Sackmann labels them; qualifying rounds are left out;
- no surface and no tour tier: WTA 125 and ITF events appear next to tour events. An event counts as main tour only
  with evidence: its matches link to TML or TennisData.app main-draw matches, or its ESPN tournament id did in an
  earlier edition (the registry). Level and surface come from the same evidence. Anything else is not forecast;
- no serve statistics: a result ESPN adds to the history moves Elo, form and rest, not serve-return profiles (as
  TennisData.app-only matches did in Phase 4's held-out period);
- unknown players appear as "TBD" before a draw is filled; those matches are skipped until both players are known.

Linking is the erratum 1 discipline applied to a third source. An ESPN match is the same real match as a history
match when the tour and round agree, the dates are within the window, and both players' names fit, in exactly one
orientation, with a unique candidate in both directions. Linked ESPN results are never added again; an unlinked ESPN
result that is still name-compatible with a history match is held back for review, never added.
"""
import bisect
import datetime
import functools
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from matchup_dna.forecasting import records as rec
from matchup_dna.forecasting.records import MatchRecord, canonical_json, iso, utc

URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/{league}/scoreboard?dates={day}"
LEAGUES = ("atp", "wta")
TOUR_OF_DRAW = {"mens-singles": "ATP", "womens-singles": "WTA"}
PROVIDER = "espn"
USER_AGENT = "matchup-dna-research/0.6"
PAUSE_SECONDS = 1.0
STATUS = {"STATUS_FINAL": rec.COMPLETED, "STATUS_RETIRED": rec.RETIRED, "STATUS_WALKOVER": rec.WALKOVER,
          "STATUS_SCHEDULED": rec.SCHEDULED, "STATUS_IN_PROGRESS": rec.IN_PROGRESS,
          "STATUS_SUSPENDED": rec.IN_PROGRESS, "STATUS_DELAYED": rec.SCHEDULED, "STATUS_POSTPONED": rec.SCHEDULED,
          "STATUS_CANCELED": rec.CANCELLED, "STATUS_ABANDONED": rec.CANCELLED, "STATUS_DEFAULT": rec.RETIRED}
FIXED_ROUNDS = {"Quarterfinal": "QF", "Semifinal": "SF", "Final": "F", "Group Stage": "RR"}
KNOCKOUT_BEFORE_QF = ("R16", "R32", "R64", "R128")
LINK_WINDOW = (-3, 16)        # ESPN match day minus the history match's tourney_date, as in Phase 4's crosswalks


def archive_dir():
    from matchup_dna.load import DATA_DIR
    return DATA_DIR / "raw" / "espn"


# ---------------------------------------------------------------- fetching (archived raw)

def fetch(league, day, directory=None, opener=urllib.request.urlopen, retries=2):
    """One scoreboard, archived as <league>_<day>_<retrieved>.json with a .meta.json beside it. Returns the meta."""
    directory = Path(directory or archive_dir())
    directory.mkdir(parents=True, exist_ok=True)
    url = URL.format(league=league, day=day.strftime("%Y%m%d"))
    for attempt in range(retries + 1):
        retrieved = datetime.datetime.now(datetime.timezone.utc)
        try:
            with opener(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as response:
                status, body = response.status, response.read()
            break
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == retries:
                raise RuntimeError(f"ESPN {league} {day}: {error}") from error
            time.sleep(2 * (attempt + 1))
    if status != 200:
        raise RuntimeError(f"ESPN {league} {day}: HTTP {status}")
    json.loads(body)  # refuse to archive anything that is not JSON
    stamp = retrieved.strftime("%Y%m%dT%H%M%SZ")
    name = f"{league}_{day.strftime('%Y%m%d')}_{stamp}"
    (directory / f"{name}.json").write_bytes(body)
    meta = {"league": league, "day": day.isoformat(), "url": url, "status": status, "retrieved_at": iso(retrieved),
            "body_sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "file": f"{name}.json"}
    (directory / f"{name}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def sync(first, last, directory=None, refresh_from=None, step=1, pause=PAUSE_SECONDS):
    """Fetches every `step`-th day in [first, last] for both tours (a day's response lists every match of every event
    running that day, so every third day covers finished events). Days already archived are skipped unless they are
    on or after `refresh_from`; those, and every day from refresh_from to `last`, are fetched (recent days change as
    matches finish). Returns the number of requests made."""
    directory = Path(directory or archive_dir())
    have = {(m["league"], m["day"]) for m in archived_meta(directory)}
    days, day = [], first
    while day <= last:
        if (day - first).days % step == 0 or (refresh_from is not None and day >= refresh_from):
            days.append(day)
        day += datetime.timedelta(days=1)
    requests, failures = 0, []
    for day in days:
        for league in LEAGUES:
            if (league, day.isoformat()) in have and (refresh_from is None or day < refresh_from):
                continue
            try:
                fetch(league, day, directory)
            except (RuntimeError, ValueError) as error:   # one failed day must not stop the job; it is retried next run
                failures.append(f"{league} {day}: {error}")
            requests += 1
            time.sleep(pause)
    if failures:
        print(f"ESPN: {len(failures)} of {requests} requests failed (retried on the next run):", *failures[:10], sep="\n  ")
    return requests


def archived_meta(directory=None):
    directory = Path(directory or archive_dir())
    found = []
    for path in sorted(directory.glob("*.meta.json")):
        found.append(json.loads(path.read_text(encoding="utf-8")))
    return found


def load_archive(directory=None, since=None, as_of=None):
    """Every archived response's records, latest retrieval winning for each competition. `as_of` keeps only responses
    retrieved at or before that moment, so a run never reads a response it could not have had."""
    directory = Path(directory or archive_dir())
    metas = [m for m in archived_meta(directory)
             if (since is None or m["day"] >= since.isoformat()) and (as_of is None or utc(m["retrieved_at"]) <= utc(as_of))]
    metas.sort(key=lambda m: m["retrieved_at"], reverse=True)   # newest first: the first sighting of a match wins
    newest = {}
    for meta in metas:
        newest.setdefault((meta["league"], meta["day"]), meta)    # one response per tour and day: the latest
    found, seen = [], set()
    for meta in sorted(newest.values(), key=lambda m: m["retrieved_at"], reverse=True):
        for record in cached_records(directory, meta):
            if record.provider_match_id not in seen:
                seen.add(record.provider_match_id)
                found.append(record)
    return found


PARSER_VERSION = "2"   # 2: seeds are no longer read as ranks


def cached_records(directory, meta):
    """The records of one archived response. The parse is cached beside the raw file, keyed by the raw file's hash and
    the parser version; the raw bytes are checked against the recorded hash before either is used."""
    raw = directory / meta["file"]
    body = raw.read_bytes()
    if hashlib.sha256(body).hexdigest() != meta["body_sha256"]:
        raise ValueError(f"{meta['file']} does not match its recorded hash")
    cache = raw.with_suffix(".records.json")
    if cache.exists():
        stored = json.loads(cache.read_text(encoding="utf-8"))
        if stored.get("body_sha256") == meta["body_sha256"] and stored.get("parser") == PARSER_VERSION:
            return [MatchRecord(**item) for item in stored["records"]]
    found = parse(json.loads(body), meta["retrieved_at"])
    cache.write_text(json.dumps({"body_sha256": meta["body_sha256"], "parser": PARSER_VERSION,
                                 "records": [r.payload() for r in found]}), encoding="utf-8")
    return found


# ---------------------------------------------------------------- parsing

def round_map(competitions):
    """{ESPN round name: Sackmann round} for one draw. Numbered rounds count back from the quarterfinal."""
    names = {c.get("round", {}).get("displayName", "") for c in competitions}
    numbered = sorted((int(m.group(1)), name) for name in names if (m := re.fullmatch(r"Round (\d+)", name)))
    found = {name: FIXED_ROUNDS[name] for name in names if name in FIXED_ROUNDS}
    for position, (_, name) in enumerate(reversed(numbered)):
        found[name] = KNOCKOUT_BEFORE_QF[position] if position < len(KNOCKOUT_BEFORE_QF) else "unknown"
    return found


def score_text(winner, loser, status):
    """Sackmann-style score from the winner's side: "7-6(3) 6-4", " RET" when the loser retired, "W/O" for a walkover."""
    if status == rec.WALKOVER:
        return "W/O"
    sets = []
    for w, l in zip(winner.get("linescores", []), loser.get("linescores", [])):
        text = f"{int(w['value'])}-{int(l['value'])}"
        tiebreaks = [x.get("tiebreak") for x in (w, l) if x.get("tiebreak") is not None]
        if tiebreaks:
            text += f"({min(tiebreaks)})"
        sets.append(text)
    if not sets:
        return None
    return " ".join(sets) + (" RET" if status == rec.RETIRED else "")


def athlete_ok(competitor):
    athlete = competitor.get("athlete") or {}
    name = athlete.get("displayName") or ""
    return bool(competitor.get("id")) and name and name.upper() != "TBD"


def parse(payload, retrieved_at, skip=None):
    """MatchRecords for every main-draw singles match with two known players. Competition ids in `skip` (a set,
    updated in place) are left out: an archive is read newest first, so a match already read is not read again."""
    found = []
    seen = skip if skip is not None else set()
    for event in payload.get("events", []):
        for grouping in event.get("groupings", []):
            tour = TOUR_OF_DRAW.get(grouping.get("grouping", {}).get("slug"))
            if tour is None:
                continue
            competitions = [c for c in grouping.get("competitions", [])
                            if not c.get("round", {}).get("displayName", "").startswith("Qualifying")]
            rounds = round_map(competitions)
            main_days = sorted(c["date"][:10] for c in competitions if c.get("date"))
            for c in competitions:
                if c["id"] in seen or len(c.get("competitors", [])) != 2:
                    continue
                if not all(athlete_ok(p) for p in c["competitors"]):
                    continue
                seen.add(c["id"])
                found.append(competition_record(event, c, tour, rounds, main_days[0] if main_days else None,
                                                retrieved_at))
    return found


def competition_record(event, c, tour, rounds, first_day, retrieved_at):
    side = {p.get("homeAway"): p for p in c["competitors"]}
    if set(side) != {"home", "away"}:
        ordered = sorted(c["competitors"], key=lambda p: p.get("order", 0))
        side = {"home": ordered[0], "away": ordered[1]}
    state = c["status"]["type"]
    status = STATUS.get(state.get("name"))
    if status is None:
        status = {"pre": rec.SCHEDULED, "in": rec.IN_PROGRESS}.get(state.get("state"), rec.UNKNOWN)
    winner_side = next((s for s, p in side.items() if p.get("winner")), None)
    if status in (rec.COMPLETED, rec.RETIRED, rec.WALKOVER) and winner_side is None:
        status = rec.UNKNOWN
    score = None
    if status in (rec.COMPLETED, rec.RETIRED, rec.WALKOVER):
        loser_side = "away" if winner_side == "home" else "home"
        score = score_text(side[winner_side], side[loser_side], status)
    # "curatedRank" is the tournament seed, not the world ranking (Stockholm 2026: Michelsen 6, unseeded players
    # blank). It is kept as the seed and never used as a rank; ranks come from the history (last_known_ranks).
    seed = lambda p: (p.get("curatedRank") or {}).get("current")
    best_of = 5 if tour == "ATP" and event.get("major") else 3
    # A start time is used only when ESPN marks it valid; otherwise the listed time is a date placeholder (midnight
    # US Eastern), and the match has no known start until ESPN publishes one.
    timed = c.get("date") and c.get("timeValid", True)
    return MatchRecord(
        provider=PROVIDER, provider_match_id=str(c["id"]), tour=tour, circuit="unknown", tournament=event["name"],
        round=rounds.get(c.get("round", {}).get("displayName", ""), "unknown"),
        home_id=str(side["home"]["id"]), home_name=side["home"]["athlete"]["displayName"],
        away_id=str(side["away"]["id"]), away_name=side["away"]["athlete"]["displayName"],
        status=status, retrieved_at=retrieved_at, event_time=iso(c["date"]) if timed else None,
        best_of=best_of, home_rank=None, away_rank=None,
        winner_side=winner_side if status in (rec.COMPLETED, rec.RETIRED, rec.WALKOVER) else None, score=score,
        raw_status=state.get("name", ""),
        raw_sha256=hashlib.sha256(canonical_json(c).encode()).hexdigest(),
        extra={"event_id": str(event["id"]), "tournament_id": str(c.get("tournamentId", event["id"].split("-")[0])),
               "major": bool(event.get("major")), "main_draw_first_day": first_day,
               "listed_date": (c.get("date") or "")[:10], "time_valid": bool(timed),
               "home_seed": seed(side["home"]), "away_seed": seed(side["away"])})


# ---------------------------------------------------------------- names and linking

@functools.lru_cache(maxsize=None)
def tokens(name):
    from matchup_dna.heldout import name_tokens
    return frozenset(name_tokens(name))


class HistoryIndex:
    """History matches by tour and round, sorted by date, so the candidates in a date window are found by bisection."""

    def __init__(self, history, since):
        from matchup_dna.workload import to_day
        groups = defaultdict(list)
        for m in history:
            if m["tourney_date"] >= since and m.get("source") != PROVIDER:
                groups[(m["tour"], m["round"])].append((to_day(m["tourney_date"]).toordinal(), m))
        self.groups = {}
        for key, items in groups.items():
            items.sort(key=lambda item: item[0])
            self.groups[key] = ([d for d, _ in items], [m for _, m in items])

    def near(self, record):
        """History matches in the record's tour and round whose tourney_date is inside LINK_WINDOW of its day."""
        days, matches = self.groups.get((record.tour, record.round), ((), ()))
        day = day_of(record).toordinal()
        low = bisect.bisect_left(days, day - LINK_WINDOW[1])
        high = bisect.bisect_right(days, day - LINK_WINDOW[0])
        return matches[low:high]


def names_fit(espn_name, other):
    """Is a full ESPN name the same person as a history name? TennisData.app-style names ("Merida Aguilar D.") use
    the erratum 1 rule; full names must have equal token sets, or one set (of at least two tokens) inside the other
    ("Daniel Merida" and "Daniel Merida Aguilar")."""
    from matchup_dna.heldout import names_compatible
    if "." in (other or ""):
        return names_compatible(other, espn_name)
    a, b = tokens(espn_name), tokens(other)
    if not a or not b:
        return False
    if a == b:
        return True
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    return len(small) >= 2 and small <= large


def day_of(record):
    """The match's UTC day: from its start time, else the day ESPN lists it under."""
    if record.event_time:
        return utc(record.event_time).date()
    listed = record.extra.get("listed_date")
    return datetime.date.fromisoformat(listed) if listed else None


def link(records, history, since, index=None):
    """[(record, history match, same_order)] for ESPN records describing a history match (module notes)."""
    index = index or HistoryIndex(history, since)
    found = []
    for record in records:
        if day_of(record) is None or record.round == "unknown":
            continue
        candidates = []
        for m in index.near(record):
            straight = names_fit(record.home_name, m["winner_name"]) and names_fit(record.away_name, m["loser_name"])
            crossed = names_fit(record.home_name, m["loser_name"]) and names_fit(record.away_name, m["winner_name"])
            if straight != crossed:
                candidates.append((m, straight))
        if len(candidates) == 1:
            found.append((record, *candidates[0]))
    claims = Counter(id(m) for _, m, _ in found)
    return [item for item in found if claims[id(item[1])] == 1]


# ---------------------------------------------------------------- what the links teach

class Evidence:
    """Player ids, events and tournaments learned from ESPN records linked to history matches."""

    def __init__(self, links):
        players, events, tournaments = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
        for record, match, same_order in links:
            home, away = (match["winner_id"], match["loser_id"]) if same_order else (match["loser_id"], match["winner_id"])
            players[(record.tour, record.home_id)][home] += 1
            players[(record.tour, record.away_id)][away] += 1
            events[(record.tour, record.extra["event_id"])][(match["tourney_id"], match["tourney_date"])] += 1
            tournaments[(record.tour, record.extra["tournament_id"])][(match["tourney_level"], match["surface"])] += 1
        self.players = {k: v for k, v in players.items()}
        self.events = {k: v for k, v in events.items()}
        self.tournaments = {k: v for k, v in tournaments.items()}

    def player(self, tour, espn_id):
        """(canonical id, "consistent" or "conflict") or None."""
        found = self.players.get((tour, espn_id))
        if not found:
            return None
        return (found.most_common(1)[0][0], "consistent" if len(found) == 1 else "conflict")

    def edition(self, tour, event_id):
        """(tourney_id, tourney_date) when every linked match of the event is in one history edition."""
        found = self.events.get((tour, event_id))
        if not found or len(found) != 1:
            return None
        return next(iter(found))

    def tournament(self, tour, tournament_id):
        """(level, surface) seen most often for this ESPN tournament, or None if it never linked (not main tour)."""
        found = self.tournaments.get((tour, tournament_id))
        return found.most_common(1)[0][0] if found else None


# ---------------------------------------------------------------- identities

class EspnIdentities:
    """Canonical id and identity status for an ESPN player (same statuses as history.FixtureIdentities):

        verified     linked ESPN matches always point to one history player; or, without links, a unique exact full
                     name among the history's TML and Sackmann players since 2015
        new_player   no evidence and no compatible existing name: a provider-only id
        ambiguous    no evidence, but an existing player's name is compatible (a possible split identity)
        conflict     linked matches point to two players, or the links and a unique name disagree
    """

    def __init__(self, evidence, assembly, sources, aliases=None):
        from matchup_dna.crosswalk import full_name_key
        from matchup_dna.heldout import NAME_HISTORY_START
        self.evidence, self.sources = evidence, sources
        self.aliases = aliases or {}     # (tour, ESPN id) -> canonical id, checked by a person (identity_aliases.csv)
        names = defaultdict(set)
        for m in assembly.matches:
            if m["tourney_date"] >= NAME_HISTORY_START and m.get("source") in ("tml", "sackmann"):
                for side in ("winner", "loser"):
                    names[(m["tour"], full_name_key(m[f"{side}_name"]))].add(m[f"{side}_id"])
        self.names = names
        self.active = {(m["tour"], m[side]) for m in sources.sackmann if m["tourney_date"] >= NAME_HISTORY_START
                       for side in ("winner_id", "loser_id")}
        if assembly.resolver is None:
            from matchup_dna.heldout import NameResolver
            assembly.resolver = NameResolver(sources.sackmann, sources.names)
        self.player_file = assembly.resolver   # unique exact full names of active Sackmann players (the TML rule)
        self.cache = {}

    def resolve(self, tour, espn_id, name):
        from matchup_dna.crosswalk import full_name_key
        from matchup_dna.forecasting.history import sackmann_candidates
        from matchup_dna.merge import provider_only_id
        key = (tour, str(espn_id))
        if key in self.cache:
            return self.cache[key]
        linked = self.evidence.player(tour, str(espn_id))
        manual = self.aliases.get((tour, str(espn_id)))
        if manual is not None:
            if linked and linked[0] != manual:
                found = {"player_id": manual, "status": "conflict",
                         "method": f"reviewed alias says {manual}, linked matches say {linked[0]}"}
            else:
                found = {"player_id": manual, "status": "verified", "method": "reviewed alias"}
            self.cache[key] = found
            return found
        by_name = self.names.get((tour, full_name_key(name)), set())
        unique_name = next(iter(by_name)) if len(by_name) == 1 else None
        if not by_name:
            unique_name = self.player_file.by_full_name(tour, name)
        if linked and linked[1] == "conflict":
            found = {"player_id": linked[0], "status": "conflict", "method": "linked ESPN matches name two players"}
        elif linked:
            if unique_name is not None and unique_name != linked[0]:
                found = {"player_id": linked[0], "status": "conflict",
                         "method": f"linked matches say {linked[0]}, the unique name says {unique_name}"}
            else:
                found = {"player_id": linked[0], "status": "verified", "method": "linked ESPN matches"}
        elif unique_name is not None:
            found = {"player_id": unique_name, "status": "verified", "method": "unique exact full name in the history"}
        else:
            player = provider_only_id(PROVIDER, tour, str(espn_id))
            candidates = sackmann_candidates(self.sources.names, self.active, tour, name)
            if candidates or len(by_name) > 1:
                found = {"player_id": player, "status": "ambiguous",
                         "method": f"no linked match; compatible existing players {sorted(candidates or by_name)[:5]}"}
            else:
                found = {"player_id": player, "status": "new_player", "method": "no linked match, no compatible name"}
        self.cache[key] = found
        return found


# ---------------------------------------------------------------- joining ESPN to the assembly

def match_dict(record, tourney_id, tourney_date, level, surface, winner, loser):
    """A finished ESPN record as a Sackmann-shaped history match (no statistics)."""
    from matchup_dna.load import match_outcome
    home_won = record.winner_side == "home"
    win, lose = (record.home_name, record.away_name) if home_won else (record.away_name, record.home_name)
    ranks = (record.home_rank, record.away_rank) if home_won else (record.away_rank, record.home_rank)
    blank = {f: None for f in ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")}
    number = f"ESPN-{record.provider_match_id}"
    return {"tour": record.tour, "key": (record.tour, tourney_id, number, record.round), "tourney_id": tourney_id,
            "tourney_name": record.tournament, "tourney_level": level, "tourney_date": tourney_date,
            "match_num": number, "surface": surface, "round": record.round, "best_of": record.best_of,
            "score": record.score, "outcome": match_outcome(record.score), "winner_id": winner, "winner_name": win,
            "winner_rank": ranks[0], "loser_id": loser, "loser_name": lose, "loser_rank": ranks[1],
            "w_ace": None, "w_svpt": None, "w_first_in": None, "l_ace": None, "l_svpt": None, "l_first_in": None,
            "minutes": None, "draw_size": "", "winner_entry": "", "loser_entry": "", "source": PROVIDER,
            "stats": {"w": dict(blank), "l": dict(blank)}, "match_day": int(day_of(record).strftime("%Y%m%d")),
            "provider_match_id": record.provider_match_id}


def last_known_ranks(history):
    """{(tour, player): [(match_day, rank)] sorted}: the rank printed on each of a player's history matches (Sackmann,
    TML, TennisData.app; never ESPN, which gives seeds). A fixture takes the latest one before its day."""
    found = defaultdict(list)
    for m in history:
        if m.get("source") == PROVIDER:
            continue
        for side in ("winner", "loser"):
            if m.get(f"{side}_rank") is not None:
                found[(m["tour"], m[f"{side}_id"])].append((m.get("match_day", m["tourney_date"]), m[f"{side}_rank"]))
    for items in found.values():
        items.sort()
    return found


def add_tennisdata_ranks(ranks, sources):
    """Adds the official rank TennisData.app shows on every row it has (Challenger and qualifying included), for players
    its validated crosswalk identifies. Players who play mostly below the tour would otherwise look unranked."""
    from matchup_dna import tennisdata as td
    for row in sources.td_rows:
        day = int(row["day"].strftime("%Y%m%d"))
        for side in ("home", "away"):
            player = sources.td_links.get((row["tour"], row.get(f"{side}_id")))
            rank = td.number(row.get(f"{side}_rank"))
            if player is not None and rank is not None:
                ranks.setdefault((row["tour"], player), []).append((day, int(rank)))
    for items in ranks.values():
        items.sort()
    return ranks


RANK_MAX_AGE_DAYS = 365


def rank_before(ranks, tour, player, day):
    """(rank, the day it was printed) from the player's latest history match before `day`, or (None, None) when there
    is none in the last RANK_MAX_AGE_DAYS (an unranked player, as the models treat a missing rank)."""
    from matchup_dna.workload import to_day
    items = ranks.get((tour, player), ())
    position = bisect.bisect_left(items, (day, -1))
    if position == 0:
        return None, None
    when, rank = items[position - 1]
    if (to_day(day) - to_day(when)).days > RANK_MAX_AGE_DAYS:
        return None, None
    return rank, when


def possible_duplicate(record, index):
    """True if some history match in the same round and window fits both names in either orientation, linked or not:
    such a record is held back for review, never added (erratum 1)."""
    for m in index.near(record):
        for a, b in ((record.home_name, record.away_name), (record.away_name, record.home_name)):
            if names_fit(a, m["winner_name"]) and names_fit(b, m["loser_name"]):
                return True
    return False


def load_aliases(path):
    """{(tour, ESPN athlete id): canonical id} from a reviewed CSV (columns tour, provider, provider_player_id,
    player_id, reviewed_on, note; rows whose provider is "espn")."""
    import csv
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as file:
        return {(r["tour"], r["provider_player_id"]): int(r["player_id"]) for r in csv.DictReader(file)
                if r["provider"] == PROVIDER}


def integrate(assembly, sources, records, evidence_since=20250101, aliases=None):
    """ESPN into an assembly: links to the history, the evidence they give, results the history lacks, and ESPN's
    scheduled matches as the fixtures (replacing TennisData.app's). Changes `assembly` in place and returns it.
    Evidence is learned from every archived record since `evidence_since`, so last year's edition of an event shows
    that this year's is a main-tour event before it has produced a linked result."""
    from matchup_dna.forecasting.history import PROVIDER_START, edition_uid, still_playing
    from matchup_dna.merge import assert_unique
    report = Counter()
    index = HistoryIndex(assembly.matches, evidence_since)
    links = link(records, assembly.matches, evidence_since, index)
    linked = {id(r): (m, same) for r, m, same in links}
    evidence = Evidence(links)
    people = EspnIdentities(evidence, assembly, sources, aliases)
    ranks = add_tennisdata_ranks(last_known_ranks(assembly.matches), sources)
    report["records (main-draw singles, both players known)"] = len(records)
    report["records linked to a history match"] = len(links)
    by_edition, by_pair = defaultdict(list), defaultdict(list)
    for m in assembly.matches:
        if m["tourney_date"] >= evidence_since:
            by_edition[(m["tour"], m["tourney_id"])].append(m)
            by_pair[(m["tour"], m["round"], frozenset((m["winner_id"], m["loser_id"])))].append(m["tourney_date"])

    def same_players_in_history(record, home, away, date):
        """The history already has these two canonical players in this round within MAX_EDITION_GAP_DAYS (the
        version-2 rule "dropped as duplicates by player ids"), even if the names did not link."""
        from matchup_dna.merge import MAX_EDITION_GAP_DAYS
        from matchup_dna.workload import to_day
        dates = by_pair.get((record.tour, record.round, frozenset((home["player_id"], away["player_id"]))), ())
        return any(abs((to_day(d) - to_day(date)).days) <= MAX_EDITION_GAP_DAYS for d in dates)

    def edition_of(record):
        """(tourney_id, tourney_date, level, surface, how) for the record's event, or None if not main tour."""
        mapped = evidence.edition(record.tour, record.extra["event_id"])
        if mapped is not None:
            tourney_id, date = mapped
            members = by_edition[(record.tour, tourney_id)]
            level = Counter(m["tourney_level"] for m in members).most_common(1)[0][0]
            surface = Counter(m["surface"] for m in members).most_common(1)[0][0]
            return tourney_id, date, level, surface, "linked to a history edition"
        known = evidence.tournament(record.tour, record.extra["tournament_id"])
        if known is None:
            return None
        first = record.extra.get("main_draw_first_day") or record.extra.get("listed_date")
        return (f"ESPN-{record.extra['event_id']}", int(first.replace("-", "")), known[0], known[1],
                "ESPN tournament seen on the main tour")

    additions, fixtures, held, seen = [], [], [], {}
    for record in sorted(records, key=lambda r: (r.tour, r.provider_match_id)):
        day = day_of(record)
        if day is None or int(day.strftime("%Y%m%d")) < PROVIDER_START:
            continue
        edition = edition_of(record)
        if edition is None:
            report["records outside the main tour (no evidence)"] += 1
            continue
        tourney_id, date, level, surface, how = edition
        home = people.resolve(record.tour, record.home_id, record.home_name)
        away = people.resolve(record.tour, record.away_id, record.away_name)
        if record.status in (rec.COMPLETED, rec.RETIRED, rec.WALKOVER):
            if id(record) in linked:
                report["results already in the history"] += 1
                continue
            if same_players_in_history(record, home, away, date):
                report["results already in the history (same players, round and edition)"] += 1
                continue
            if record.round == "unknown" or possible_duplicate(record, index):
                held.append({"reason": "round unknown" if record.round == "unknown" else "may duplicate a history match",
                             "espn_id": record.provider_match_id, "tournament": record.tournament,
                             "round": record.round, "home": record.home_name, "away": record.away_name})
                report["results held back for review"] += 1
                continue
            if {home["status"], away["status"]} - {"verified", "new_player"}:
                held.append({"reason": "identity not verified", "espn_id": record.provider_match_id,
                             "home": [record.home_name, home["status"]], "away": [record.away_name, away["status"]]})
                report["results held back for review"] += 1
                continue
            winner, loser = (home, away) if record.winner_side == "home" else (away, home)
            additions.append(match_dict(record, tourney_id, date, level, surface, winner["player_id"],
                                        loser["player_id"]))
            report["results added (missing from the history)"] += 1
            continue
        if record.status not in (rec.SCHEDULED, rec.IN_PROGRESS):
            report[f"records {record.status} (neither a result nor a fixture)"] += 1
            continue
        fixture = {
            "provider": PROVIDER, "provider_match_id": record.provider_match_id, "tour": record.tour,
            "edition_uid": edition_uid(record.tour, "espn", record.extra["event_id"]),
            "edition_aliases": [[PROVIDER, f"{record.tour}|{record.extra['event_id']}"]],
            "tourney_id": tourney_id, "tourney_date": date, "tourney_name": record.tournament,
            "tourney_level": level, "surface": surface, "best_of": record.best_of, "round": record.round,
            "scheduled_start": record.event_time, "match_day": int(day.strftime("%Y%m%d")),
            "status": "pending" if record.status == rec.SCHEDULED else "started", "notes": [how],
        }
        match_day = int(day.strftime("%Y%m%d"))
        for side, person, record_id, name in (("home", home, record.home_id, record.home_name),
                                              ("away", away, record.away_id, record.away_name)):
            rank, rank_day = rank_before(ranks, record.tour, person["player_id"], match_day)
            fixture[side] = {"provider_id": record_id, "name": name, "rank": rank, "rank_as_of": rank_day,
                             "seed": record.extra.get(f"{side}_seed"), **person}
        if id(record) in linked:
            fixture["status"] = "already_played"
            fixture["notes"].append("a history source reports it played")
        same = (record.tour, tourney_id, record.round, frozenset((home["player_id"], away["player_id"])))
        if fixture["status"] == "pending":
            if same in seen:
                fixture["status"] = "duplicate"
                fixture["notes"].append(f"same match as ESPN {seen[same]}")
            else:
                seen[same] = record.provider_match_id
        report[f"fixtures: {fixture['status']}"] += 1
        fixtures.append(fixture)

    assembly.matches = assembly.matches + additions
    assert_unique(assembly.matches)   # stops the run if an addition still duplicates a history match
    # Who may still be playing, worked out again over the history WITH the results ESPN just added, and replacing the
    # earlier answer: TML's ongoing file can stop mid-event (Paris 2026 stopped at R16), and the answer from TML alone
    # kept players who had since lost, or whose final had been played, "still in the draw" (amendment 1 to P1).
    ongoing = {(f["tour"], f["tourney_id"]) for f in fixtures if f["status"] in ("pending", "started")}
    assembly.ongoing_editions = set(assembly.ongoing_editions) | ongoing
    assembly.still_playing = still_playing(assembly.matches, assembly.ongoing_editions)
    assembly.fixtures = fixtures
    assembly.records = list(assembly.records) + list(records)
    assembly.resolvers[PROVIDER] = people.resolve
    for record in records:
        edition = evidence.edition(record.tour, record.extra["event_id"])
        ids = {f"ESPN-{record.extra['event_id']}"} | ({edition[0]} if edition else set())
        assembly.alias_tourney_ids.setdefault((PROVIDER, f"{record.tour}|{record.extra['event_id']}"), set()).update(ids)
    assembly.report.update({f"espn: {k}": v for k, v in report.items()})
    assembly.review["espn held back"] = held
    return assembly
