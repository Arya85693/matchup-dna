"""Assembling matches after Sackmann's last week from TennisIsMyLife (TML) and TennisData.app.

Used twice, by the same code:

- the one-time held-out evaluation (editions starting 1 June 2026 or later, complete before the 5 November 2026
  file snapshot), which unseals the provider rows with the frozen Phase 4 protocol; and
- a rehearsal on January to mid-May 2026, where the provider rows are open and Sackmann has the same matches, so the
  provider-built features can be compared with Sackmann-built ones without looking at any held-out outcome.

Rules (Phase 4 Data Audit, Part 3):

1. TML rows are the record. A TennisData.app row is added only if it matches no TML row (names in the date window,
   then validated ids), is not from one of the event families Sackmann omits, and is not the same pair in the same
   round within 3 days of a TML row.
2. Players: validated crosswalk, else a unique full-name (TML) or surname-and-initial (TennisData.app) match to a
   Sackmann player with tour-level matches since 2015, else a provider-only id.
3. An edition's tourney_date is TennisData.app's first main-draw day when the edition is in TennisData.app, else
   TML's earliest date. Best-of comes from the tournament. Ratings move only on completed matches.

Two versions of the assembly exist (Phase 4 erratum 1):

- Version 1 is the code the frozen held-out evaluation ran (commit 4f6076e, amendment 1). It is kept unchanged so
  the original, affected evaluation can be reproduced.
- Version 2 is the correction. Version 1 linked a TennisData.app row to a TML row only when both players' names
  produced the same surname-and-initial key, or both players were in both validated crosswalks. A player whose two
  providers write the name differently ("Merida Aguilar D." and "Daniel Merida", "Ruse G." and "Elena Gabriela
  Ruse", "Tam Sin Hang" and "Sin Hang Tam") failed both, so the match was added twice: its last guard compared
  resolved player ids, and those players had been resolved to different ids on the two sides. Version 2:

  a. adds a third match-linking pass: same tour, same round (TennisData.app's blank round allowed), inside the
     day window, the same tournament edition when the edition is already linked, and both players name-compatible
     (a shared surname token, and every initial matching a given name). A row with more than one such TML
     candidate (after setting aside candidates other rows claim alone), or a TML row claimed twice, is never
     merged: the TennisData.app row is left out and listed for review (TML is the record);
  b. learns which TennisData.app and TML ids are one person from every linked match. Ids joined by linked matches
     count as one person only if all their TML records carry the same full name, every TennisData.app name fits
     it, and their TML crosswalk entries agree (TML gives some WTA players two ids); otherwise nothing is merged
     and the group is listed. A TML player resolves by the TML crosswalk, else a unique exact full name, else the
     validated crosswalk entry of the linked TennisData.app id; a TennisData.app player resolves to its TML
     person's id. When the TennisData.app crosswalk names a different Sackmann player than the TML-linked
     identity, the conflict is listed and the TML identity is used (TML carries ATP's official player codes);
  c. drops the unverified "unique surname and initial" guess for TennisData.app players: an unresolved player gets
     a provider-only id and is listed for review; and
  d. stops the build if any TennisData.app addition is still name-compatible with a TML match in the same round,
     day window and edition, or if a linked person has two canonical ids. Neither rule looks at a result.
"""
import datetime
import re
import unicodedata
from collections import Counter, defaultdict

from matchup_dna import tennisdata as td
from matchup_dna import tennisismylife as tml
from matchup_dna.crosswalk import (
    build_links, full_name_key, provider_name_key, sackmann_full_keys, sackmann_name_keys,
)
from matchup_dna.load import match_outcome, normalize_surface
from matchup_dna.merge import MAX_EDITION_GAP_DAYS, provider_only_id, tml_match
from matchup_dna.workload import to_day

NAME_HISTORY_START = 20150101


def ymd(day):
    return int(day.strftime("%Y%m%d"))


class NameResolver:
    """Unique name matches to Sackmann players who have tour-level matches since NAME_HISTORY_START."""

    def __init__(self, sackmann_matches, names):
        active = {(m["tour"], m[side]) for m in sackmann_matches if m["tourney_date"] >= NAME_HISTORY_START
                  for side in ("winner_id", "loser_id")}
        self.full, self.initial = defaultdict(set), defaultdict(set)
        for key in active:
            person = names.get(key)
            if person is None:
                continue
            for value in sackmann_full_keys(person["first"], person["last"]).values():
                self.full[(key[0], value)].add(key[1])
            for value in sackmann_name_keys(person["first"], person["last"]).values():
                self.initial[(key[0], value)].add(key[1])

    def by_full_name(self, tour, name):
        found = self.full.get((tour, full_name_key(name)), set())
        return next(iter(found)) if len(found) == 1 else None

    def by_initial(self, tour, name):
        key = provider_name_key(name)
        found = self.initial.get((tour, key), set()) if key else set()
        return next(iter(found)) if len(found) == 1 else None


def resolve_tml(tour, provider_id, name, links, resolver, report):
    if (tour, provider_id) in links:
        report["TML ids by crosswalk"] += 1
        return links[(tour, provider_id)]
    found = resolver.by_full_name(tour, name)
    if found is not None:
        report["TML ids by unique full name"] += 1
        return found
    report["TML ids new to Sackmann"] += 1
    return provider_only_id("tml", tour, provider_id)


def resolve_td(tour, provider_id, name, links, resolver, report):
    if (tour, provider_id) in links:
        report["TennisData.app ids by crosswalk"] += 1
        return links[(tour, provider_id)]
    found = resolver.by_initial(tour, name)
    if found is not None:
        report["TennisData.app ids by unique surname and initial"] += 1
        return found
    report["TennisData.app ids new to Sackmann"] += 1
    return provider_only_id("tennisdata", tour, provider_id)


def td_score(row):
    """A Sackmann-style score from the winner's side, the winner's side ("home" or "away"), and an outcome."""
    if row["status_extra"] == "WALKOVER":
        return "W/O", "home" if row["winner_code"] == "1" else "away"
    if row["status_extra"] not in ("FINISHED", "RETIRED") or row["winner_code"] not in ("1", "2"):
        return None, None
    winner = "home" if row["winner_code"] == "1" else "away"
    loser = "away" if winner == "home" else "home"
    sets = []
    for number in range(1, 6):
        won, lost = td.number(row[f"{winner}_set_{number}_score"]), td.number(row[f"{loser}_set_{number}_score"])
        if won is not None and lost is not None:
            sets.append(f"{int(won)}-{int(lost)}")
    if not sets:
        return None, None
    return " ".join(sets) + (" RET" if row["status_extra"] == "RETIRED" else ""), winner


def td_match(row, tourney_date, links, resolver, report, resolve_player=None):
    """A TennisData.app row as a Sackmann-shaped match. Players resolve through resolve_td (version 1) unless
    resolve_player(tour, provider_id, name) is given (version 2)."""
    score, winner = td_score(row)
    if score is None:
        report["TennisData.app rows without a usable result (canceled, awarded, blank)"] += 1
        return None
    loser = "away" if winner == "home" else "home"
    tour = row["tour"]
    if resolve_player is None:
        def resolve_player(tour, provider_id, name):
            return resolve_td(tour, provider_id, name, links, resolver, report)
    match = {
        "tour": tour, "key": (tour, f"TD-{td.edition_name(row['tournament'])}-{tourney_date}", row["match_id"],
                              td.ROUNDS.get(row["round"]) or "unknown"),
        "tourney_id": f"TD-{td.edition_name(row['tournament'])}-{tourney_date}", "tourney_name": row["tournament"],
        "tourney_level": "G" if td.is_grand_slam(row) else "A", "tourney_date": tourney_date,
        "match_num": row["match_id"], "surface": normalize_surface(row["surface"]),
        "round": td.ROUNDS.get(row["round"]) or "unknown", "best_of": td.best_of(row), "score": score,
        "outcome": match_outcome(score),
        "winner_id": resolve_player(tour, row[f"{winner}_id"], row[f"{winner}_name"]),
        "winner_name": row[f"{winner}_name"], "winner_rank": None if td.number(row[f"{winner}_rank"]) is None else int(td.number(row[f"{winner}_rank"])),
        "loser_id": resolve_player(tour, row[f"{loser}_id"], row[f"{loser}_name"]),
        "loser_name": row[f"{loser}_name"], "loser_rank": None if td.number(row[f"{loser}_rank"]) is None else int(td.number(row[f"{loser}_rank"])),
        "minutes": None, "draw_size": "", "winner_entry": "", "loser_entry": "", "source": "tennisdata",
        "w_ace": None, "w_svpt": None, "w_first_in": None, "l_ace": None, "l_svpt": None, "l_first_in": None,
        "stats": {prefix: {field: None for field in ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms",
                                                      "bpSaved", "bpFaced")} for prefix in ("w", "l")},
    }
    return match


def assemble(tml_rows, td_rows, sackmann_matches, names, tml_links, td_links, excluded_names, start, end, snapshot,
             version=2):
    """Provider matches for editions starting in [start, end) and finished before `snapshot`, under the rules in
    the module notes. Rows must be open (unsealed) for this window. Returns (matches, held-out keys, report).
    version=1 is the original, affected assembly; version=2 the correction (module notes)."""
    if version == 1:
        return assemble_v1(tml_rows, td_rows, sackmann_matches, names, tml_links, td_links, excluded_names, start,
                           end, snapshot)
    if version == 2:
        return assemble_v2(tml_rows, td_rows, sackmann_matches, names, tml_links, td_links, excluded_names, start,
                           end, snapshot)
    raise ValueError(f"unknown assembly version {version!r}")


# ---------------------------------------------------------------- version 2 (erratum 1)

# TennisData.app round labels that may stand for any TML round: team events give no round.
OPEN_ROUND = "unknown"


def name_tokens(name):
    """Lower-case ASCII letter tokens: "Tung-Lin Wu" -> ["tung", "lin", "wu"]."""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return [token for token in re.split(r"[^a-z]+", text) if token]


def td_name_parts(name):
    """(surname tokens, initials) from a TennisData.app name. "Merida Aguilar D." -> ({"merida", "aguilar"}, ["d"]);
    "Choi W. F." -> ({"choi"}, ["w", "f"]); "Struff J-L." -> ({"struff"}, ["j", "l"]); "Tam Sin Hang" (no
    initials) -> ({"tam", "sin", "hang"}, [])."""
    surname, initials = set(), []
    for token in (name or "").replace(",", " ").split():
        if token.endswith("."):
            initials += [part[0] for part in name_tokens(token)]
        else:
            surname.update(name_tokens(token))
    return surname, initials


def names_compatible(td_name, full_name):
    """Could this TennisData.app name and this full name be the same person? A surname token is shared and every
    initial starts one of the full name's other tokens; with no initials, every token must appear. Used only to
    decide whether two records describe the same match (with round, dates, edition and opponent), never to decide
    a player's identity on its own."""
    surname, initials = td_name_parts(td_name)
    tokens = set(name_tokens(full_name))
    if not surname or not tokens:
        return False
    if not initials:
        return surname <= tokens
    shared = {token for token in surname & tokens if len(token) >= 2}
    if not shared:
        return False
    rest = tokens - shared
    return all(any(token.startswith(letter) for token in rest) for letter in initials)


def tml_people(row):
    """[(TML id, name), (TML id, name)] in the order tml_initial_options uses: player A and B in the sealed view,
    winner and loser in the open view."""
    if "a_name" in row:
        return [(row["a_id"], row["a_name"]), (row["b_id"], row["b_name"])]
    return [(row["winner_id"], row["winner_name"]), (row["loser_id"], row["loser_name"])]


def td_round(row):
    return td.ROUNDS.get(row["round"]) or OPEN_ROUND


def td_edition_key(row, td_editions):
    return row["tour"], td.edition_name(row["tournament"]), td_editions[td.row_key(row)]["tourney_date"]


def orientation(row, target):
    """True if the TennisData.app home player is the TML row's first person, False if the second, None if the
    names fit neither way or both ways."""
    (_, first), (_, second) = tml_people(target)
    straight = names_compatible(row["home_name"], first) and names_compatible(row["away_name"], second)
    crossed = names_compatible(row["home_name"], second) and names_compatible(row["away_name"], first)
    if straight == crossed:
        return None
    return straight


def link_remaining(td_rows, tml_rows, taken, editions_of_tml, td_editions):
    """Third linking pass for TennisData.app rows the first two passes missed. A TML row is a candidate when it is
    on the same tour, in the same round (a blank TennisData.app round fits any), inside the day window, not taken,
    not part of a TML edition already linked to a different TennisData.app edition, and both players are
    name-compatible in exactly one orientation. Results never depend on who won.

    Returns (links, review): links are [(TennisData.app row, TML row, same_order)], unique in both directions;
    review lists rows with several candidates, or whose candidate another row also claims."""
    from matchup_dna.audit_tennisismylife import WINDOW, tml_day
    by_tour = defaultdict(list)
    for target in tml_rows:
        if id(target) not in taken:
            by_tour[target["tour"]].append(target)
    found, review, several = [], [], []
    for row in td_rows:
        edition = td_edition_key(row, td_editions)
        round_name = td_round(row)
        candidates = []
        for target in by_tour.get(row["tour"], ()):
            if round_name != OPEN_ROUND and target["round"] != round_name:
                continue
            if not WINDOW[0] <= (row["day"] - tml_day(target)).days <= WINDOW[1]:
                continue
            linked_editions = editions_of_tml.get((target["tour"], target["tourney_id"]))
            if linked_editions and edition not in linked_editions:
                continue
            same_order = orientation(row, target)
            if same_order is not None:
                candidates.append((target, same_order))
        if len(candidates) == 1:
            found.append((row, *candidates[0]))
        elif len(candidates) > 1:
            several.append((row, candidates))
    # A TML row is one match: a candidate another row has already claimed alone cannot also be this row's match
    # (a blank-round team-event row that fits both a round-robin and a final between the same two players).
    single_claims = Counter(id(target) for _, target, _ in found)
    claimed = {id(target) for _, target, _ in found if single_claims[id(target)] == 1}
    for row, candidates in several:
        rest = [c for c in candidates if id(c[0]) not in claimed]
        if len(rest) == 1:
            found.append((row, *rest[0]))
        else:
            review.append({"reason": "several TML rows fit", "row": row, "candidates": [c[0] for c in candidates]})
    claims = Counter(id(target) for _, target, _ in found)
    links = []
    for row, target, same_order in found:
        if claims[id(target)] == 1:
            links.append((row, target, same_order))
        else:
            review.append({"reason": "TML row claimed by several rows", "row": row, "candidates": [target]})
    return links, review


def player_links(pairs, tml_links):
    """Which TennisData.app and TML ids are one person, from linked matches [(TennisData.app row, TML row,
    same_order)].

    Ids joined by linked matches form groups (a provider sometimes gives one person two ids: TML has two ids for
    some WTA players). A group is one person only if every TML id in it carries the same full name, every
    TennisData.app name in it is compatible with that name, and its TML crosswalk entries (if any) agree.
    Returns {"links": {(tour, TennisData.app id): TML id}, "aliases": {(tour, TML id): TML id},
    "conflicts": [...]}: links and aliases point to the group's representative TML id (the one in the TML
    crosswalk, else the smallest)."""
    edges, td_names, tml_names = defaultdict(set), defaultdict(set), defaultdict(set)
    for row, target, same_order in pairs:
        people = tml_people(target)
        if not same_order:
            people = people[::-1]
        tour = row["tour"]
        for side, (tml_id, tml_name) in zip(("home", "away"), people):
            td_node, tml_node = (tour, "td", row[f"{side}_id"]), (tour, "tml", tml_id)
            edges[td_node].add(tml_node)
            edges[tml_node].add(td_node)
            td_names[td_node].add(row[f"{side}_name"])
            tml_names[tml_node].add(tml_name)
    links, aliases, conflicts, seen = {}, {}, [], set()
    for start in edges:
        if start in seen:
            continue
        group, stack = set(), [start]
        while stack:
            node = stack.pop()
            if node in group:
                continue
            group.add(node)
            stack.extend(edges[node] - group)
        seen |= group
        tour = start[0]
        td_ids = sorted(node[2] for node in group if node[1] == "td")
        tml_ids = sorted(node[2] for node in group if node[1] == "tml")
        full_names = {"".join(name_tokens(name)) for node in group if node[1] == "tml" for name in tml_names[node]}
        shown = sorted(name for node in group if node[1] == "tml" for name in tml_names[node])
        crosswalked = {tml_links[(tour, tml_id)] for tml_id in tml_ids if (tour, tml_id) in tml_links}
        names_fit = len(full_names) == 1 and all(
            names_compatible(name, shown[0]) for node in group if node[1] == "td" for name in td_names[node])
        if not names_fit or len(crosswalked) > 1:
            conflicts.append({"tour": tour, "td_ids": td_ids, "tml_ids": tml_ids, "tml_names": sorted(set(shown)),
                              "td_names": sorted(n for node in group if node[1] == "td" for n in td_names[node]),
                              "reason": "names differ" if not names_fit else "TML crosswalk entries differ"})
            continue
        representative = next((i for i in tml_ids if (tour, i) in tml_links), tml_ids[0])
        for td_id in td_ids:
            links[(tour, td_id)] = representative
        for tml_id in tml_ids:
            if tml_id != representative:
                aliases[(tour, tml_id)] = representative
    return {"links": links, "aliases": aliases, "conflicts": conflicts}


class IdentityResolver:
    """Canonical player ids for the version 2 assembly. Every resolution is counted by route, and every case a
    person should check is kept in `review`."""

    def __init__(self, tml_links, td_links, people, tml_names, name_resolver, report):
        self.tml_links, self.td_links = tml_links, td_links
        self.td_to_tml, self.aliases = people["links"], people["aliases"]
        self.tml_to_td = defaultdict(set)
        for (tour, td_id), tml_id in self.td_to_tml.items():
            self.tml_to_td[(tour, tml_id)].add(td_id)
        self.tml_names, self.names = tml_names, name_resolver
        self.report = report
        self.review = {}
        self.claimed = defaultdict(set)  # (tour, Sackmann id) -> TML ids the TML crosswalk resolves to it
        for (tour, tml_id), sackmann_id in tml_links.items():
            self.claimed[(tour, sackmann_id)].add(tml_id)

    def flag(self, kind, tour, provider, detail):
        self.review.setdefault((kind, tour, provider), detail)

    def tml(self, tour, tml_id, name=None):
        """TML crosswalk, else a unique exact full name, else the validated crosswalk entry of the TennisData.app
        id linked to this person, else a provider-only id. Ids TML gives one person are resolved together."""
        if (tour, tml_id) in self.aliases:
            self.report["TML ids merged with another TML id of the same person"] += 1
            self.flag("TML gives one person several ids (resolved together)", tour, tml_id,
                      {"tml_id": tml_id, "same_person_as": self.aliases[(tour, tml_id)],
                       "name": self.tml_names.get((tour, tml_id), name)})
            tml_id = self.aliases[(tour, tml_id)]
            name = None
        name = name or self.tml_names.get((tour, tml_id), "")
        if (tour, tml_id) in self.tml_links:
            self.report["TML ids by crosswalk"] += 1
            return self.tml_links[(tour, tml_id)]
        found = self.names.by_full_name(tour, name)
        if found is not None:
            self.report["TML ids by unique full name"] += 1
            return found
        targets = {self.td_links[(tour, td_id)] for td_id in self.tml_to_td.get((tour, tml_id), ())
                   if (tour, td_id) in self.td_links}
        if len(targets) == 1:
            sackmann_id = targets.pop()
            others = self.claimed[(tour, sackmann_id)] - {tml_id}
            if others:
                self.flag("conflict: TennisData.app crosswalk target already held by another TML id", tour, tml_id,
                          {"tml_id": tml_id, "name": name, "sackmann_id": sackmann_id, "other_tml_ids": sorted(others)})
            else:
                self.report["TML ids through a linked TennisData.app crosswalk entry"] += 1
                self.flag("resolved through TennisData.app crosswalk", tour, tml_id,
                          {"tml_id": tml_id, "name": name, "td_ids": sorted(self.tml_to_td[(tour, tml_id)]),
                           "sackmann_id": sackmann_id})
                return sackmann_id
        elif len(targets) > 1:
            self.flag("conflict: linked TennisData.app ids have different crosswalk entries", tour, tml_id,
                      {"tml_id": tml_id, "name": name, "sackmann_ids": sorted(targets)})
        self.report["TML ids new to Sackmann"] += 1
        return provider_only_id("tml", tour, tml_id)

    def td(self, tour, td_id, name):
        tml_id = self.td_to_tml.get((tour, td_id))
        crosswalk = self.td_links.get((tour, td_id))
        if tml_id is not None:
            canonical = self.tml(tour, tml_id)
            self.report["TennisData.app ids through the linked TML player"] += 1
            if crosswalk is not None and crosswalk != canonical:
                self.flag("conflict: TennisData.app crosswalk disagrees with the TML-linked identity", tour, td_id,
                          {"td_id": td_id, "name": name, "tml_id": tml_id, "crosswalk_sackmann_id": crosswalk,
                           "used_id": canonical})
            return canonical
        if crosswalk is not None:
            self.report["TennisData.app ids by crosswalk"] += 1
            return crosswalk
        self.report["TennisData.app ids new to Sackmann"] += 1
        self.flag("unresolved TennisData.app player (provider-only id)", tour, td_id, {"td_id": td_id, "name": name})
        return provider_only_id("tennisdata", tour, td_id)


def cross_source_duplicates(matches, editions_of_tml, td_edition_of_match):
    """TennisData.app additions that still look like a TML match: same tour and round (or a blank round), match
    days within the window, a compatible edition, and both players name-compatible, or the same canonical pair."""
    from matchup_dna.audit_tennisismylife import WINDOW
    tml_matches = [m for m in matches if m.get("source") == "tml"]
    found = []
    for match in (m for m in matches if m.get("source") == "tennisdata"):
        edition = td_edition_of_match[match["key"]]
        for other in tml_matches:
            if other["tour"] != match["tour"]:
                continue
            if match["round"] != OPEN_ROUND and other["round"] != match["round"]:
                continue
            gap = (to_day(match["match_day"]) - to_day(other["match_day"])).days
            if not WINDOW[0] <= gap <= WINDOW[1]:
                continue
            linked_editions = editions_of_tml.get((other["tour"], other["tourney_id"][len("TML-"):]))
            if linked_editions and edition not in linked_editions:
                continue
            same_pair = {match["winner_id"], match["loser_id"]} == {other["winner_id"], other["loser_id"]}
            names_fit = any(
                names_compatible(match[f"{a}_name"], other["winner_name"])
                and names_compatible(match[f"{b}_name"], other["loser_name"])
                for a, b in (("winner", "loser"), ("loser", "winner")))
            if same_pair or names_fit:
                found.append((match["key"], other["key"]))
    return found


def window_rows(tml_rows, td_rows, excluded_names, start, end, snapshot):
    """The population rules, as version 1: (TML rows, TennisData.app main-draw rows, TML editions, TennisData.app
    editions) for editions starting in [start, end) and complete before the snapshot. Works on sealed rows too."""
    snapshot_date = ymd(snapshot)
    editions = tml.editions(tml_rows)
    tml_window = [r for r in tml_rows if start <= editions[(r["tour"], r["tourney_id"])]["start"] < end
                  and not editions[(r["tour"], r["tourney_id"])]["ongoing"]
                  and editions[(r["tour"], r["tourney_id"])]["end"] < snapshot_date]
    td_main = [r for r in td_rows if td.is_main_draw(r)]
    td_editions = td.editions(td_main)
    td_window = [r for r in td_main if start <= td_editions[td.row_key(r)]["tourney_date"] < end
                 and td_editions[td.row_key(r)]["last_day"] < snapshot
                 and r["tournament"] not in excluded_names]
    return tml_window, td_window, editions, td_editions


def link_rows(td_window, tml_window, td_links, tml_links, td_editions):
    """Version 2's three match-linking passes. Uses names, ids, rounds and dates only, so it runs on sealed rows too.
    Returns (pairs [(TennisData.app row, TML row, same_order)], the third pass's pairs, rows left for review,
    {(tour, TML tourney_id): TennisData.app editions}, counts)."""
    from matchup_dna.audit_tennisismylife import td_to_tml, td_to_tml_by_ids
    # Passes 1 and 2, exactly as version 1.
    direct = td_to_tml(td_window, tml_window)
    pairs = [(r["item"], r["target"], r["same_order"]) for r in direct if r["status"] == "linked"]
    taken = {id(target) for _, target, _ in pairs}
    second = td_to_tml_by_ids([r["item"] for r in direct if r["status"] != "linked"], tml_window, td_links,
                              tml_links, taken)
    for row, target in second:
        first_tml = tml_links.get((target["tour"], tml_people(target)[0][0]))
        pairs.append((row, target, td_links.get((row["tour"], row["home_id"])) == first_tml))
    counts = {"TennisData.app rows matched to TML rows by name keys": len(pairs) - len(second),
              "TennisData.app rows matched to TML rows by validated ids": len(second)}
    # Pass 3: name-compatible players, same round and edition.
    editions_of_tml = defaultdict(set)
    for row, target, _ in pairs:
        editions_of_tml[(target["tour"], target["tourney_id"])].add(td_edition_key(row, td_editions))
    linked_rows = {id(row) for row, _, _ in pairs}
    taken = {id(target) for _, target, _ in pairs}
    third, review_rows = link_remaining([r for r in td_window if id(r) not in linked_rows], tml_window, taken,
                                        editions_of_tml, td_editions)
    pairs += third
    for row, target, _ in third:
        editions_of_tml[(target["tour"], target["tourney_id"])].add(td_edition_key(row, td_editions))
    counts["TennisData.app rows matched to TML rows by compatible names, round and edition"] = len(third)
    counts["TennisData.app rows matched to TML rows"] = len(pairs)
    return pairs, third, review_rows, editions_of_tml, counts


def assemble_v2(tml_rows, td_rows, sackmann_matches, names, tml_links, td_links, excluded_names, start, end,
                snapshot):
    """Version 2 of assemble (module notes, a-d). Same inputs, outputs, and population rules as version 1; the
    report also carries "review": the cases left for a person to check."""
    report = Counter()
    resolver = NameResolver(sackmann_matches, names)
    tml_window, td_window, editions, td_editions = window_rows(tml_rows, td_rows, excluded_names, start, end, snapshot)
    report["TML rows in the window"] = len(tml_window)
    report["TennisData.app main-draw rows in the window"] = len(td_window)

    pairs, third, review_rows, editions_of_tml, counts = link_rows(td_window, tml_window, td_links, tml_links,
                                                                   td_editions)
    report.update(counts)
    pair_of = {id(row): target for row, target, _ in pairs}
    held_back = {id(item["row"]) for item in review_rows}
    report["TennisData.app rows left out for review (possible duplicates, not merged)"] = len(held_back)

    # Player links from every linked match, then one identity per person.
    people = player_links(pairs, tml_links)
    tml_names = {}
    for row in tml_window:
        for tml_id, name in tml_people(row):
            tml_names[(row["tour"], tml_id)] = name
    identities = IdentityResolver(tml_links, td_links, people, tml_names, resolver, report)
    for conflict in people["conflicts"]:
        identities.flag("conflict: linked ids do not describe one person (not merged)", conflict["tour"],
                        tuple(conflict["td_ids"] + conflict["tml_ids"]), conflict)

    for row in td_window:
        target = pair_of.get(id(row))
        if target is None or "winner_code" not in row or "winner_name" not in target:
            continue
        if row["winner_code"] in ("1", "2"):
            td_winner = row["home_name" if row["winner_code"] == "1" else "away_name"]
            report["data check: TML and TennisData.app name the same winner"] += names_compatible(td_winner, target["winner_name"])
            report["data check: matched pairs with a winner in both"] += 1

    first_day = {}
    for row in td_window:
        target = pair_of.get(id(row))
        if target is not None:
            key = (target["tour"], target["tourney_id"])
            day = td_editions[td.row_key(row)]["first_day"]
            first_day[key] = min(day, first_day.get(key, day))

    matches, by_pair = [], defaultdict(list)
    for row in tml_window:
        key = (row["tour"], row["tourney_id"])
        date = ymd(first_day[key]) if key in first_day else editions[key]["start"]
        match = tml_match(row, {}, date)
        for side in ("winner", "loser"):
            match[f"{side}_id"] = identities.tml(row["tour"], row[f"{side}_id"], row[f"{side}_name"])
        match["match_day"] = int(row["tourney_date"])
        matches.append(match)
        by_pair[(match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"])].append(match)

    td_edition_of_match = {}
    for row in td_window:
        if id(row) in pair_of or id(row) in held_back:
            continue
        date = td_editions[td.row_key(row)]["tourney_date"]
        match = td_match(row, date, td_links, resolver, report, resolve_player=identities.td)
        if match is None:
            continue
        near = [m for m in by_pair.get((match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"]), ())
                if abs((to_day(m["tourney_date"]) - to_day(date)).days) <= MAX_EDITION_GAP_DAYS]
        if near:
            report["TennisData.app rows dropped as duplicates of TML rows by player ids"] += 1
            continue
        match["match_day"] = ymd(row["day"])
        td_edition_of_match[match["key"]] = td_edition_key(row, td_editions)
        matches.append(match)
        report["TennisData.app rows added (no TML row)"] += 1

    problems = cross_source_duplicates(matches, {(t, i): e for (t, i), e in editions_of_tml.items()}, td_edition_of_match)
    if problems:
        raise ValueError(f"{len(problems)} TennisData.app additions still match TML rows: {problems[:5]}")
    checker = IdentityResolver(tml_links, td_links, people, tml_names, resolver, Counter())
    for (tour, td_id), tml_id in people["links"].items():
        if checker.td(tour, td_id, "") != checker.tml(tour, tml_id):
            raise ValueError(f"linked players {td_id} and {tml_id} have two canonical ids")
    for match in matches:
        del match["match_day"]
    report = dict(report)
    report["review"] = {
        "possible duplicates left out": [
            {"reason": item["reason"], "td_match_id": item["row"]["match_id"], "tournament": item["row"]["tournament"],
             "round": td_round(item["row"]), "home": item["row"]["home_name"], "away": item["row"]["away_name"],
             "tml_candidates": [f"{c['tourney_id']}|{c['match_num']}|{c['round']}" for c in item["candidates"]]}
            for item in review_rows],
        "players": [dict(detail, kind=kind, tour=tour) for (kind, tour, _), detail in sorted(
            identities.review.items(), key=lambda item: tuple(map(str, item[0])))],
    }
    report["linked TennisData.app-TML player pairs"] = len(people["links"])
    report["details"] = {"third_pass": third, "player_links": people}  # in memory only, for the diagnostics
    return matches, {m["key"] for m in matches}, report


# ---------------------------------------------------------------- version 1 (the original, affected assembly)

def assemble_v1(tml_rows, td_rows, sackmann_matches, names, tml_links, td_links, excluded_names, start, end, snapshot):
    """The assembly the frozen held-out evaluation ran, unchanged. See the module notes for its defect."""
    from matchup_dna.audit_tennisismylife import td_to_tml, td_to_tml_by_ids

    report = Counter()
    resolver = NameResolver(sackmann_matches, names)
    snapshot_date = ymd(snapshot)
    editions = tml.editions(tml_rows)
    tml_window = [r for r in tml_rows if start <= editions[(r["tour"], r["tourney_id"])]["start"] < end
                  and not editions[(r["tour"], r["tourney_id"])]["ongoing"]
                  and editions[(r["tour"], r["tourney_id"])]["end"] < snapshot_date]
    td_main = [r for r in td_rows if td.is_main_draw(r)]
    td_editions = td.editions(td_main)
    td_window = [r for r in td_main if start <= td_editions[td.row_key(r)]["tourney_date"] < end
                 and td_editions[td.row_key(r)]["last_day"] < snapshot
                 and r["tournament"] not in excluded_names]
    report["TML rows in the window"] = len(tml_window)
    report["TennisData.app main-draw rows in the window"] = len(td_window)

    direct = td_to_tml(td_window, tml_window)
    taken = {id(r["target"]) for r in direct if r["status"] == "linked"}
    second = td_to_tml_by_ids([r["item"] for r in direct if r["status"] != "linked"], tml_window, td_links, tml_links, taken)
    pair_of = {id(r["item"]): r["target"] for r in direct if r["status"] == "linked"}
    pair_of.update({id(row): target for row, target in second})
    report["TennisData.app rows matched to TML rows"] = len(pair_of)
    from matchup_dna.crosswalk import initial_keys
    for row in td_window:
        target = pair_of.get(id(row))
        if target is None or "winner_code" not in row or "winner_name" not in target:
            continue
        if row["winner_code"] in ("1", "2"):
            td_winner = provider_name_key(row["home_name" if row["winner_code"] == "1" else "away_name"])
            report["data check: TML and TennisData.app name the same winner"] += td_winner in initial_keys(target["winner_name"])
            report["data check: matched pairs with a winner in both"] += 1

    first_day = {}
    for row in td_window:
        target = pair_of.get(id(row))
        if target is not None:
            key = (target["tour"], target["tourney_id"])
            day = td_editions[td.row_key(row)]["first_day"]
            first_day[key] = min(day, first_day.get(key, day))

    matches, by_pair = [], defaultdict(list)
    for row in tml_window:
        key = (row["tour"], row["tourney_id"])
        date = ymd(first_day[key]) if key in first_day else editions[key]["start"]
        match = tml_match(row, {}, date)
        for side in ("winner", "loser"):
            match[f"{side}_id"] = resolve_tml(row["tour"], row[f"{side}_id"], row[f"{side}_name"], tml_links, resolver, report)
        matches.append(match)
        by_pair[(match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"])].append(match)

    for row in td_window:
        if id(row) in pair_of:
            continue
        date = td_editions[td.row_key(row)]["tourney_date"]
        match = td_match(row, date, td_links, resolver, report)
        if match is None:
            continue
        near = [m for m in by_pair.get((match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"]), ())
                if abs((to_day(m["tourney_date"]) - to_day(date)).days) <= MAX_EDITION_GAP_DAYS]
        if near:
            report["TennisData.app rows dropped as duplicates of TML rows by player ids"] += 1
            continue
        matches.append(match)
        report["TennisData.app rows added (no TML row)"] += 1
    keys = {m["key"] for m in matches}
    return matches, keys, dict(report)


def crosswalks(sackmann_overlap_matches, names):
    """The validated TML and TennisData.app crosswalks, rebuilt exactly as the audits build them (open rows only)."""
    from matchup_dna.audit_tennisdata import link_population
    from matchup_dna.audit_tennisismylife import to_sackmann

    tml_open = [r for r in tml.load_tml() if not r["sealed"]]
    pairs = []
    for result in to_sackmann(tml_open, sackmann_overlap_matches, names):
        if result["status"] != "linked":
            continue
        row, target = result["item"], result["target"]
        winner, loser = (target["winner_id"], target["loser_id"]) if result["same_order"] else (
            target["loser_id"], target["winner_id"])
        pairs += [(row["tour"], row["winner_id"], winner), (row["tour"], row["loser_id"], loser)]
    td_open = [r for r in td.load_provider() if not r["sealed"] and td.is_main_draw(r)]
    _, td_crosswalk, _ = link_population(td_open, sackmann_overlap_matches, names)
    return build_links(pairs)["links"], td_crosswalk["links"]


def excluded_tournaments(sackmann_overlap_matches, names):
    """TennisData.app tournament names whose open main-draw rows link to Sackmann less than half the time (the
    event families Sackmann omits). Names never seen in the open period are kept, as decided in the audit."""
    from matchup_dna.audit_tennisdata import ELIGIBLE_SHARE, link_population, tournament_mapping
    td_open = [r for r in td.load_provider() if not r["sealed"]]
    linked, _, by_ids = link_population([r for r in td_open if td.is_main_draw(r)], sackmann_overlap_matches, names)
    mapping = tournament_mapping(td_open, linked, by_ids)
    return sorted(name for (_, name), entry in mapping.items() if entry["share"] < ELIGIBLE_SHARE)


def snapshot_day():
    return datetime.date(2026, 11, 5)
