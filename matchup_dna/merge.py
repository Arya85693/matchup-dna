"""One match stream from Sackmann, TennisIsMyLife (TML), and TennisData.app, with every match counted once.

Precedence (Phase 4 Data Audit, Part 3):

1. Tournament weeks up to and including SACKMANN_LAST_WEEK come from Sackmann only. A TML match linked to a
   Sackmann match is never added; it may only fill that Sackmann match's blank statistics or minutes
   ("backfill"), and only when both sources name the same winner.
2. Editions starting after SACKMANN_LAST_WEEK come from TML, plus TennisData.app rows that match no TML row.
   (Assembling the held-out period happens only inside the frozen held-out command.)
3. Player ids from TML and TennisData.app are mapped to Sackmann ids through validated crosswalks. A player
   with no validated link gets a provider-only id: a fixed negative integer derived from the source and the
   provider id, so it can never collide with a Sackmann id.

assert_unique() stops the build if a match appears twice within a source, or if two sources hold the same
two players in the same round within MAX_EDITION_GAP_DAYS of each other.
"""
import hashlib
from collections import defaultdict

from matchup_dna.load import match_outcome, normalize_surface, to_int
from matchup_dna.workload import to_day

SACKMANN_LAST_WEEK = 20260525
MAX_EDITION_GAP_DAYS = 3

# TML level codes -> Sackmann's.
TML_LEVELS = {("ATP", "250"): "A", ("ATP", "500"): "A", ("WTA", "1000"): "PM", ("WTA", "500"): "P",
              ("WTA", "250"): "I"}
BACKFILL_FIELDS = ("minutes", "w_ace", "w_svpt", "w_first_in", "l_ace", "l_svpt", "l_first_in")


def provider_only_id(source, tour, provider_id):
    """A negative integer that identifies a player known only to one provider."""
    digest = hashlib.sha256(f"{source}|{tour}|{provider_id}".encode()).digest()
    return -(int.from_bytes(digest[:6], "big") + 1)


def resolve(source, tour, provider_id, links):
    """The Sackmann id for a provider id through a validated crosswalk, else its provider-only id."""
    found = links.get((tour, provider_id))
    return found if found is not None else provider_only_id(source, tour, provider_id)


def tml_match(row, links, tourney_date):
    """An open TML row as a Sackmann-shaped match. Sealed rows carry no result and are refused."""
    if row.get("sealed") or "winner_id" not in row:
        raise PermissionError("sealed TML rows have no result; they open only inside the frozen held-out command")
    tour = row["tour"]
    match = {
        "tour": tour,
        "key": (tour, f"TML-{row['tourney_id']}", row["match_num"], row["round"]),
        "tourney_id": f"TML-{row['tourney_id']}",
        "tourney_name": row["tourney_name"],
        "tourney_level": TML_LEVELS.get((tour, row["tourney_level"]), row["tourney_level"]),
        "tourney_date": tourney_date,
        "match_num": row["match_num"],
        "surface": normalize_surface(row["surface"]),
        "round": row["round"],
        "best_of": to_int(row["best_of"]),
        "score": row["score"].strip(),
        "outcome": match_outcome(row["score"]),
        "winner_id": resolve("tml", tour, row["winner_id"], links),
        "winner_name": row["winner_name"],
        "winner_rank": to_int(row["winner_rank"]),
        "loser_id": resolve("tml", tour, row["loser_id"], links),
        "loser_name": row["loser_name"],
        "loser_rank": to_int(row["loser_rank"]),
        "minutes": to_int(row["minutes"]),
        "draw_size": row["draw_size"].strip(),
        "winner_entry": row["winner_entry"].strip().upper(),
        "loser_entry": row["loser_entry"].strip().upper(),
        "source": "tml",
    }
    for prefix in ("w", "l"):
        match[f"{prefix}_ace"] = to_int(row[f"{prefix}_ace"])
        match[f"{prefix}_svpt"] = to_int(row[f"{prefix}_svpt"])
        match[f"{prefix}_first_in"] = to_int(row[f"{prefix}_1stIn"])
    return match


def combine(sackmann, additions):
    """Sackmann matches plus additions under the precedence rules.

    `additions` is a list of (match, linked Sackmann match or None, same_winner) from another source. A linked
    addition is never added: when it names the same winner it fills the Sackmann match's blank fields. An unlinked
    addition dated on or before SACKMANN_LAST_WEEK is dropped (Sackmann is the record for those weeks).

    Returns (matches, report). Sackmann's own match dicts are never modified: a backfilled match is a copy with a
    "backfilled" list of the fields filled.
    """
    replaced, report = {}, defaultdict(int)
    added = []
    for match, linked, same_winner in additions:
        if linked is not None:
            if not same_winner:
                report["linked, winners differ: not used"] += 1
                continue
            target = replaced.get(id(linked)) or dict(linked, backfilled=[])
            for field in BACKFILL_FIELDS:
                if target.get(field) is None and match.get(field) is not None:
                    target[field] = match[field]
                    target["backfilled"].append(field)
            replaced[id(linked)] = target
            report["linked to Sackmann"] += 1
        elif match["tourney_date"] <= SACKMANN_LAST_WEEK:
            report["unlinked, in Sackmann's weeks: dropped"] += 1
        else:
            added.append(match)
            report["added"] += 1
    merged = [replaced.get(id(match), match) for match in sackmann] + added
    report["backfilled matches"] = sum(1 for match in replaced.values() if match["backfilled"])
    assert_unique(merged)
    return merged, dict(report)


def assert_unique(matches):
    """Raises ValueError if a match key repeats, or if two sources hold the same pair in the same round within
    MAX_EDITION_GAP_DAYS of each other."""
    keys = defaultdict(int)
    for match in matches:
        keys[match["key"]] += 1
    repeated = [key for key, count in keys.items() if count > 1]
    if repeated:
        raise ValueError(f"match keys repeat: {repeated[:5]}")
    by_pair = defaultdict(list)
    for match in matches:
        by_pair[(match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"])].append(match)
    for group in by_pair.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda match: match["tourney_date"])
        for earlier, later in zip(group, group[1:]):
            gap = (to_day(later["tourney_date"]) - to_day(earlier["tourney_date"])).days
            if earlier.get("source") != later.get("source") and gap <= MAX_EDITION_GAP_DAYS:
                raise ValueError(f"the same match appears in {earlier.get('source')} and {later.get('source')}: "
                                 f"{earlier['key']} and {later['key']}")
