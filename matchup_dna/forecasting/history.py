"""The canonical completed-match history, and the pending fixtures, as of one data snapshot.

History = Sackmann before PROVIDER_START (with Phase 4's TennisIsMyLife backfill of blank statistics), then every
completed match from TennisIsMyLife (TML) and TennisData.app (TD) for editions starting on or after PROVIDER_START,
assembled under the rules of Phase 4 erratum 1 (heldout.assemble version 2):

- TML is the record; a TD row is added only if no TML row describes the same real match (three linking passes:
  name keys, validated ids, then name-compatible players in the same round, day window and edition);
- one identity per real person, learned from linked matches (heldout.player_links, heldout.IdentityResolver);
- the build stops if a TD addition still looks like a TML match, or if one person has two canonical ids.

The research assembly (heldout.assemble_v2) is not changed or called with new rules. This module calls the same
linking and identity functions with a production window. It differs in three ways, each needed because a production
snapshot is taken while tournaments are still being played:

1. Ongoing editions are kept. The research window kept only editions finished before the file snapshot.
2. Only TD rows that carry a result take part in match linking. A scheduled TD row has no TML counterpart yet; linking
   it by names and a 19-day window could tie it to last week's meeting of the same two players.
3. Scheduled TD rows become fixtures. A fixture that TML already reports as played (TD lags) is marked
   "already played", never forecast. Two scheduled rows for one real match are merged into one fixture.

Every assembled match keeps `match_day` (TML: the row's round date; TD: the match's UTC day), so a replay can cut
the history at any day.
"""
import datetime
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from matchup_dna import heldout
from matchup_dna import tennisdata as td
from matchup_dna import tennisismylife as tml
from matchup_dna.heldout import (
    IdentityResolver, NameResolver, cross_source_duplicates, link_rows, name_tokens, names_compatible,
    player_links, td_edition_key, td_match, td_round, tml_people, ymd,
)
from matchup_dna.merge import MAX_EDITION_GAP_DAYS, combine, tml_match
from matchup_dna.workload import to_day

PROVIDER_START = 20260601          # the first edition date after Sackmann's snapshot (Phase 4's boundary)
SACKMANN_REPEAT_DAYS = 14          # provider matches already in Sackmann within this many days are dropped
FIXTURE_TML_WINDOW = (-3, 3)       # TD fixture day minus TML round date, for "already played" when editions are unlinked
TD_PROVIDER = "tennisdata_app"
TML_PROVIDER = "tml"


def slug(text):
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


def edition_uid(tour, tourney_date, name):
    """The stable canonical id of an edition first seen in TennisData.app: tour, first main-draw day, event name."""
    return f"{tour}-{tourney_date}-{slug(name)}"


def is_pending(row):
    """A TD row without a final status: scheduled (or any other non-final state)."""
    return row.get("status") != "FINISHED"


@dataclass
class Sources:
    """Everything the assembly reads, loaded once."""
    tml_rows: list
    td_rows: list
    sackmann: list
    names: dict
    tml_links: dict
    td_links: dict
    excluded: list
    retrieved_at: dict = field(default_factory=dict)   # file name -> ISO UTC modification time


def load_sources(unseal_with):
    """Reads Sackmann (with Phase 4's TML backfill), every TML and TD row (unsealed with the frozen Phase 4 protocol:
    Phase 4 is complete), the validated crosswalks, and the TD event families Sackmann omits."""
    from matchup_dna.audit_tennisdata import sackmann_overlap
    from matchup_dna.crosswalk import load_player_names
    from matchup_dna.phase4_features import backfilled_matches
    from matchup_dna.forecasting.records import iso

    sackmann, _ = backfilled_matches()
    overlap, names = sackmann_overlap(), load_player_names()
    tml_links, td_links = heldout.crosswalks(overlap, names)
    excluded = heldout.excluded_tournaments(overlap, names)
    retrieved = {}
    for path in list(tml.tml_files()) + list(td.provider_files()):
        retrieved[path.name] = iso(datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc))
    return Sources(tml.load_tml(unseal_with=unseal_with), td.load_provider(unseal_with=unseal_with), sackmann, names,
                   tml_links, td_links, excluded, retrieved)


@dataclass
class Assembly:
    matches: list            # canonical completed matches (Sackmann before start + providers), match_day on each
    fixtures: list           # pending TD rows as canonical fixtures (dicts), every status recorded
    tml_edition_of: dict     # TD edition key -> (tourney_id, tourney_date) of its matches in `matches`
    identities: object       # the IdentityResolver
    resolver: object         # NameResolver over active Sackmann players
    report: dict
    review: dict
    still_playing: dict = field(default_factory=dict)   # see still_playing()
    records: list = field(default_factory=list)          # provider MatchRecords this assembly read, for the store
    alias_tourney_ids: dict = field(default_factory=dict)  # (provider, edition key) -> history tourney ids
    resolvers: dict = field(default_factory=dict)        # provider -> resolve(tour, provider id, name) -> identity


def window(rows_tml, rows_td, excluded, start):
    tml_editions = tml.editions(rows_tml)
    tml_window = [r for r in rows_tml if tml_editions[(r["tour"], r["tourney_id"])]["start"] >= start]
    td_main = [r for r in rows_td if td.is_main_draw(r)]
    td_editions = td.editions(td_main)
    td_window = [r for r in td_main if td_editions[td.row_key(r)]["tourney_date"] >= start
                 and r["tournament"] not in excluded]
    return tml_window, td_window, tml_editions, td_editions


def assemble(sources, start=PROVIDER_START, tml_rows=None, td_rows=None):
    """The canonical history and fixtures from `sources` (or from the given TML and TD rows, for replays that cut
    the rows at a moment in time)."""
    rows_tml = sources.tml_rows if tml_rows is None else tml_rows
    rows_td = sources.td_rows if td_rows is None else td_rows
    report = Counter()
    resolver = NameResolver(sources.sackmann, sources.names)
    tml_window, td_window, tml_editions, td_editions = window(rows_tml, rows_td, sources.excluded, start)
    td_results = [r for r in td_window if not is_pending(r)]
    td_pending = [r for r in td_window if is_pending(r)]
    report["TML rows (editions from the start date, ongoing included)"] = len(tml_window)
    report["TD main-draw rows with a final status"] = len(td_results)
    report["TD main-draw rows pending (scheduled)"] = len(td_pending)

    pairs, third, review_rows, editions_of_tml, counts = link_rows(td_results, tml_window, sources.td_links,
                                                                   sources.tml_links, td_editions)
    report.update(counts)
    pair_of = {id(row): target for row, target, _ in pairs}
    held_back = {id(item["row"]) for item in review_rows}
    report["TD rows left out for review (possible duplicates, not merged)"] = len(held_back)

    people = player_links(pairs, sources.tml_links)
    tml_names = {(row["tour"], tml_id): name for row in tml_window for tml_id, name in tml_people(row)}
    identities = IdentityResolver(sources.tml_links, sources.td_links, people, tml_names, resolver, report)
    for conflict in people["conflicts"]:
        identities.flag("conflict: linked ids do not describe one person (not merged)", conflict["tour"],
                        tuple(conflict["td_ids"] + conflict["tml_ids"]), conflict)

    first_day = {}
    for row in td_results:
        target = pair_of.get(id(row))
        if target is not None:
            key = (target["tour"], target["tourney_id"])
            day = td_editions[td.row_key(row)]["first_day"]
            first_day[key] = min(day, first_day.get(key, day))

    matches, by_pair = [], defaultdict(list)
    for row in tml_window:
        key = (row["tour"], row["tourney_id"])
        date = ymd(first_day[key]) if key in first_day else tml_editions[key]["start"]
        match = tml_match(row, {}, date)
        for side in ("winner", "loser"):
            match[f"{side}_id"] = identities.tml(row["tour"], row[f"{side}_id"], row[f"{side}_name"])
        match["match_day"] = int(row["tourney_date"])
        match["source_file"] = row["source_file"]
        matches.append(match)
        by_pair[(match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"])].append(match)

    td_edition_of_match = {}
    for row in td_results:
        if id(row) in pair_of or id(row) in held_back:
            continue
        date = td_editions[td.row_key(row)]["tourney_date"]
        match = td_match(row, date, sources.td_links, resolver, report, resolve_player=identities.td)
        if match is None:
            continue
        near = [m for m in by_pair.get((match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"]), ())
                if abs((to_day(m["tourney_date"]) - to_day(date)).days) <= MAX_EDITION_GAP_DAYS]
        if near:
            report["TD rows dropped as duplicates of TML rows by player ids"] += 1
            continue
        match["match_day"] = ymd(row["day"])
        match["provider_match_id"] = row["match_id"]
        td_edition_of_match[match["key"]] = td_edition_key(row, td_editions)
        matches.append(match)
        report["TD rows added (no TML row)"] += 1

    problems = cross_source_duplicates(matches, dict(editions_of_tml), td_edition_of_match)
    if problems:
        raise ValueError(f"{len(problems)} TD additions still match TML rows: {problems[:5]}")
    checker = IdentityResolver(sources.tml_links, sources.td_links, people, tml_names, resolver, Counter())
    for (tour, td_id), tml_id in people["links"].items():
        if checker.td(tour, td_id, "") != checker.tml(tour, tml_id):
            raise ValueError(f"linked players {td_id} and {tml_id} have two canonical ids")

    # Which TML edition (and date) holds each TD edition's matches, so a fixture joins its edition's history.
    tml_edition_of, linked = {}, defaultdict(set)
    for (tour, tourney_id), td_keys in editions_of_tml.items():
        for td_key in td_keys:
            linked[td_key].add((tour, tourney_id))
    for td_key, targets in linked.items():
        if len(targets) == 1:
            tour, tourney_id = next(iter(targets))
            key = (tour, tourney_id)
            date = ymd(first_day[key]) if key in first_day else tml_editions[key]["start"]
            tml_edition_of[td_key] = (f"TML-{tourney_id}", date)
        else:
            report["TD editions linked to more than one TML edition (left unlinked)"] += 1

    # Sackmann before the start, provider matches after; a provider match Sackmann already holds is dropped.
    history = [m for m in sources.sackmann if m["tourney_date"] < start]
    recent = defaultdict(list)
    for m in history:
        if m["tourney_date"] >= start - 10000:
            recent[(m["tour"], frozenset((m["winner_id"], m["loser_id"])), m["round"])].append(m["tourney_date"])
    kept = []
    for m in matches:
        dates = recent.get((m["tour"], frozenset((m["winner_id"], m["loser_id"])), m["round"]), ())
        if any(abs((to_day(m["tourney_date"]) - to_day(d)).days) <= SACKMANN_REPEAT_DAYS for d in dates):
            report["provider matches dropped: already in Sackmann"] += 1
        else:
            kept.append(m)
    combined, merge_report = combine(history, [(m, None, None) for m in kept], last_sackmann_week=start - 1)
    for m in combined:
        m.setdefault("match_day", m["tourney_date"])
    report["history matches"] = len(combined)

    fixtures = build_fixtures(td_pending, td_editions, tml_edition_of, tml_window, tml_editions, identities, resolver,
                              sources, report)
    review = {"possible duplicates left out": [
        {"reason": item["reason"], "td_match_id": item["row"]["match_id"], "tournament": item["row"]["tournament"],
         "round": td_round(item["row"]), "home": item["row"]["home_name"], "away": item["row"]["away_name"]}
        for item in review_rows],
        "players": [dict(detail, kind=kind, tour=tour) for (kind, tour, _), detail in sorted(
            identities.review.items(), key=lambda item: tuple(map(str, item[0])))]}
    report = dict(report, merge=merge_report)
    ongoing = {(tour, f"TML-{tourney_id}") for (tour, tourney_id), e in tml_editions.items()
               if e["ongoing"] and e["start"] >= start}
    from matchup_dna.forecasting.providers import tennisdata_records
    from matchup_dna.forecasting.records import canonical_json
    alias_ids = {}
    for row in td_window:
        key = td_edition_key(row, td_editions)
        ids = {f"TD-{key[1]}-{key[2]}"} | ({tml_edition_of[key][0]} if key in tml_edition_of else set())
        alias_ids.setdefault((TD_PROVIDER, canonical_json(list(key))), set()).update(ids)
    people = FixtureIdentities(identities, resolver, sources)
    return Assembly(combined, fixtures, tml_edition_of, identities, resolver, report, review,
                    still_playing(combined, ongoing),
                    records=tennisdata_records(rows_td, sources.retrieved_at, main_draw_from=start),
                    alias_tourney_ids=alias_ids, resolvers={TD_PROVIDER: people.resolve})


# ---------------------------------------------------------------- identities of fixture players

def sackmann_candidates(resolver_names, active, tour, name):
    """Active Sackmann players (tour-level matches since 2015) whose name is compatible with `name`, for checking
    whether a provider-only player might really be an existing one (the split-identity error of erratum 1)."""
    tokens = set(name_tokens(name))
    found = []
    for (player_tour, player_id) in active:
        if player_tour != tour:
            continue
        person = resolver_names.get((tour, player_id))
        if person is None:
            continue
        full = f"{person['first']} {person['last']}"
        last = set(name_tokens(person["last"]))
        if last and last <= tokens or heldout.names_compatible(name, full) or (
                tokens and tokens <= set(name_tokens(full))):
            found.append(player_id)
    return sorted(found)


class FixtureIdentities:
    """Canonical id and identity status for a TD player on a fixture.

    status    verified      a Sackmann id through a validated crosswalk, the linked TML player, or a unique exact name
              new_player    a provider-only id, and no active Sackmann player has a compatible name
              ambiguous     a provider-only id, but some active Sackmann player has a compatible name: possibly an
                            existing player under another spelling (erratum 1's split identities). Not forecast.
              conflict      the identity evidence disagrees (the TD crosswalk names a different player than the
                            linked TML identity, the Vallejo case). Not forecast.
    """

    def __init__(self, identities, resolver, sources):
        self.identities, self.sources = identities, sources
        self.active = {(m["tour"], m[side]) for m in sources.sackmann if m["tourney_date"] >= heldout.NAME_HISTORY_START
                       for side in ("winner_id", "loser_id")}
        self.cache = {}

    def resolve(self, tour, td_id, name):
        key = (tour, td_id)
        if key in self.cache:
            return self.cache[key]
        saved = self.identities.report
        self.identities.report = Counter()
        try:
            player = self.identities.td(tour, td_id, name)
            routes = sorted(self.identities.report)
        finally:
            self.identities.report = saved
        flags = [kind for (kind, flag_tour, provider), _ in self.identities.review.items()
                 if flag_tour == tour and kind.startswith("conflict") and (
                     provider == td_id or (isinstance(provider, tuple) and td_id in provider)
                     or provider == self.identities.td_to_tml.get((tour, td_id)))]
        method = "; ".join(routes)
        if flags:
            status, method = "conflict", method + "; " + "; ".join(sorted(set(flags)))
        elif player >= 0:
            status = "verified"
        else:
            candidates = sackmann_candidates(self.sources.names, self.active, tour, name)
            if candidates:
                status, method = "ambiguous", method + f"; compatible Sackmann players {candidates[:5]}"
            else:
                status = "new_player"
        self.cache[key] = {"player_id": player, "status": status, "method": method}
        return self.cache[key]


# ---------------------------------------------------------------- fixtures

def build_fixtures(td_pending, td_editions, tml_edition_of, tml_window, tml_editions, identities, resolver, sources,
                   report):
    from matchup_dna.forecasting.records import canonical_json, iso
    from matchup_dna.load import normalize_surface
    from matchup_dna.audit_tennisismylife import tml_day
    people = FixtureIdentities(identities, resolver, sources)
    tml_by_round = defaultdict(list)
    for row in tml_window:
        tml_by_round[(row["tour"], row["round"])].append(row)

    fixtures, seen = [], {}
    for row in sorted(td_pending, key=lambda r: (r["tour"], int(r["match_id"]))):
        edition = td_editions[td.row_key(row)]
        td_key = td_edition_key(row, td_editions)
        round_name = td_round(row)
        home = people.resolve(row["tour"], row["home_id"], row["home_name"])
        away = people.resolve(row["tour"], row["away_id"], row["away_name"])
        tourney_id, tourney_date = tml_edition_of.get(td_key, (f"TD-{td.edition_name(row['tournament'])}-"
                                                                 f"{edition['tourney_date']}", edition["tourney_date"]))
        level = "G" if td.is_grand_slam(row) else None
        if td_key in tml_edition_of:
            tml_key = (row["tour"], tourney_id[len("TML-"):])
            from matchup_dna.merge import TML_LEVELS
            raw_level = tml_editions[tml_key]["level"]
            level = TML_LEVELS.get((row["tour"], raw_level), raw_level)
        fixture = {
            "provider": TD_PROVIDER, "provider_match_id": row["match_id"], "tour": row["tour"],
            "edition_uid": edition_uid(row["tour"], edition["tourney_date"], td.edition_name(row["tournament"])),
            "td_edition": list(td_key), "tml_edition": tourney_id if td_key in tml_edition_of else None,
            "edition_aliases": [[TD_PROVIDER, canonical_json(list(td_key))]] + (
                [["tml", f"{row['tour']}|{tourney_id}"]] if td_key in tml_edition_of else []),
            "tourney_id": tourney_id, "tourney_date": tourney_date, "tourney_name": td.edition_name(row["tournament"]),
            "tourney_level": level or "A", "surface": normalize_surface(row["surface"]), "best_of": td.best_of(row),
            "round": round_name, "scheduled_start": iso(int(float(row["date_timestamp"]))) if row["date_timestamp"] else None,
            "match_day": ymd(row["day"]), "status": "pending", "notes": [],
            "home": {"provider_id": row["home_id"], "name": row["home_name"],
                     "rank": None if td.number(row["home_rank"]) is None else int(td.number(row["home_rank"])), **home},
            "away": {"provider_id": row["away_id"], "name": row["away_name"],
                     "rank": None if td.number(row["away_rank"]) is None else int(td.number(row["away_rank"])), **away},
        }
        # Already played: TML holds this match with a result (TD lags), in the linked edition or within 3 days.
        for target in tml_by_round.get((row["tour"], round_name), ()):
            linked = td_key in tml_edition_of and tml_edition_of[td_key][0] == f"TML-{target['tourney_id']}"
            gap = (row["day"] - tml_day(target)).days
            if not linked and not FIXTURE_TML_WINDOW[0] <= gap <= FIXTURE_TML_WINDOW[1]:
                continue
            if heldout.orientation(row, target) is not None:
                fixture["status"] = "already_played"
                fixture["notes"].append(f"TML reports it played: {target['tourney_id']} {target['match_num']}")
                break
        if fixture["status"] == "pending":
            same = (row["tour"], fixture["edition_uid"], round_name,
                    frozenset((home["player_id"], away["player_id"])))
            if same in seen:
                fixture["status"] = "duplicate"
                fixture["notes"].append(f"same match as TD {seen[same]}")
            else:
                seen[same] = row["match_id"]
        report[f"fixtures: {fixture['status']}"] += 1
        fixtures.append(fixture)
    return fixtures


def still_playing(matches, ongoing_editions):
    """{(tour, player): [(tourney_date, tourney_id)]} for players who have not lost in an ongoing edition whose
    final is not yet recorded. A round-robin loss does not end a player's event, so it does not count as out."""
    by_edition = defaultdict(list)
    for match in matches:
        if (match["tour"], match["tourney_id"]) in ongoing_editions:
            by_edition[(match["tour"], match["tourney_id"])].append(match)
    found = defaultdict(list)
    for (tour, tourney_id), members in by_edition.items():
        if any(m["round"] == "F" for m in members):
            continue
        players, out = set(), set()
        for m in members:
            players |= {m["winner_id"], m["loser_id"]}
            if m["round"] != "RR":
                out.add(m["loser_id"])
        for player in players - out:
            found[(tour, player)].append((members[0]["tourney_date"], tourney_id))
    return dict(found)


def alive_elsewhere(assembly, fixture):
    """Players of `fixture` who may still be playing an earlier-dated edition: they have another pending fixture in
    an edition dated before this one, or they have not lost in an ongoing TML edition dated before this one whose
    final is not recorded. Their latest results are not known yet, so the tournament-start inputs are incomplete and
    the forecast is deferred. Returns {side: reason}."""
    found = {}
    for side in ("home", "away"):
        player = fixture[side]["player_id"]
        for other in assembly.fixtures:
            if other is fixture or other["status"] != "pending" or other["tour"] != fixture["tour"]:
                continue
            if other["tourney_date"] < fixture["tourney_date"] and player in (other["home"]["player_id"],
                                                                              other["away"]["player_id"]):
                found[side] = f"has a pending match in {other['tourney_name']} ({other['round']})"
        for date, tourney_id in assembly.still_playing.get((fixture["tour"], player), ()):
            if date < fixture["tourney_date"] and tourney_id != fixture["tourney_id"]:
                found.setdefault(side, f"still in the draw of ongoing edition {tourney_id}")
    return found


# ---------------------------------------------------------------- identity reviews (confirm only)

def load_identity_reviews(path):
    """{(tour, provider, provider_player_id): player_id} from a CSV of identities a person has checked
    (columns tour, provider, provider_player_id, player_id, reviewed_on, note). A review can only confirm the id the
    rules resolved; it never changes a player's identity, because the history was built with that id."""
    import csv
    from pathlib import Path
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as file:
        return {(r["tour"], r["provider"], r["provider_player_id"]): int(r["player_id"]) for r in csv.DictReader(file)}


def apply_reviews(fixtures, reviews):
    """Marks a fixture player as verified when a review confirms exactly the id the rules resolved."""
    for fixture in fixtures:
        for side in ("home", "away"):
            person = fixture[side]
            confirmed = reviews.get((fixture["tour"], fixture["provider"], str(person["provider_id"])))
            if confirmed is None or person["status"] == "verified":
                continue
            if confirmed == person["player_id"]:
                person["status"] = "verified"
                person["method"] += "; confirmed by identity review"
            else:
                person["method"] += f"; review names {confirmed}, rules resolved {person['player_id']}: not applied"
    return fixtures
