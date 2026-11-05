"""Linking TennisData.app players and matches to Sackmann's.

The two sources use different player ids, and the provider writes names as "Surname I.". Players are never
matched by surname alone. A player link is accepted only through a match:

1. A provider match and a Sackmann match are the same match when they are on the same tour, both players'
   name keys (normalized full surname plus first initial) agree, and the provider's match day falls between
   WINDOW[0] and WINDOW[1] days after the Sackmann tourney_date. If more than one Sackmann match fits, or one
   Sackmann match fits more than one provider row, nothing is linked.
2. Each uniquely linked match pairs two provider ids with two Sackmann ids. A provider id enters the crosswalk
   only if every linked match pairs it with the same Sackmann id and no other provider id is paired with that
   Sackmann id. Anything else is a conflict, reported and left out.
"""
import csv
import datetime
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from matchup_dna.load import DATA_DIR, TOURS

# Provider match day minus Sackmann tourney_date, in days. Grand Slams run 15 days from a Sunday start, and a few
# events (United Cup) start before their Sackmann date.
WINDOW = (-3, 16)


def normalize(text):
    """Accents removed, lower case, letters only: "Carreño-Busta" -> "carrenobusta"."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", ascii_text.lower())


def provider_name_key(name):
    """("surname", "i") from "Surname I." or "Surname I. J.". None if the name has no initial."""
    tokens = name.replace(",", " ").split()
    initials = [token for token in tokens if token.endswith(".")]
    surname = normalize(" ".join(token for token in tokens if token not in initials))
    initial = normalize(initials[0])[:1] if initials else ""
    if not surname or not initial:
        return None
    return surname, initial


def sackmann_name_keys(first, last):
    """The direct key (last name, first initial) and the reversed key (first name, last initial).

    The reversed key exists because some players' names are stored in the other order in one of the sources,
    for example Sackmann's "Bu Yunchaokete" is the provider's "Bu Y.".
    """
    first, last = normalize(first), normalize(last)
    return {"direct": (last, first[:1]), "reversed": (first, last[:1])}


def load_player_names(tours=TOURS, data_dir=DATA_DIR):
    """{(tour, player_id): {"first", "last", "keys"}} from the Sackmann player files."""
    names = {}
    for tour in tours:
        path = Path(data_dir) / tour.lower() / f"{tour.lower()}_players.csv"
        with open(path, encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                names[(tour, int(row["player_id"]))] = {
                    "first": row["name_first"], "last": row["name_last"],
                    "keys": sackmann_name_keys(row["name_first"], row["name_last"]),
                }
    return names


def to_day(date):
    return datetime.date(date // 10000, date // 100 % 100, date % 100)


def sackmann_index(matches, names):
    """{(tour, frozenset of two name keys): [(match, used_reversed)]} using every key combination."""
    index = defaultdict(list)
    for match in matches:
        winner = names[(match["tour"], match["winner_id"])]["keys"]
        loser = names[(match["tour"], match["loser_id"])]["keys"]
        for winner_kind, winner_key in winner.items():
            for loser_kind, loser_key in loser.items():
                if winner_key == loser_key:
                    continue
                reversed_used = "reversed" in (winner_kind, loser_kind)
                index[(match["tour"], frozenset((winner_key, loser_key)))].append((match, reversed_used))
    return index


def in_window(row, match, window=WINDOW):
    return window[0] <= (row["day"] - to_day(match["tourney_date"])).days <= window[1]


def home_side(row, match, names):
    """"winner" if the provider's home player is Sackmann's winner, "loser" if the loser, None if unclear."""
    home, away = provider_name_key(row["home_name"]), provider_name_key(row["away_name"])
    winner = set(names[(match["tour"], match["winner_id"])]["keys"].values())
    loser = set(names[(match["tour"], match["loser_id"])]["keys"].values())
    as_winner = home in winner and away in loser
    as_loser = home in loser and away in winner
    if as_winner and not as_loser:
        return "winner"
    if as_loser and not as_winner:
        return "loser"
    return None


def link_matches(rows, matches, names, window=WINDOW):
    """One result per provider row: {"row", "status", "match", "reversed", "home"}.

    status is "linked", "ambiguous" (several Sackmann candidates, or a Sackmann match claimed by several rows),
    "no candidate", "unparseable name", or "same name key" (both players share a key, so sides are unclear).
    """
    index = sackmann_index(matches, names)
    results = []
    for row in rows:
        home, away = provider_name_key(row["home_name"]), provider_name_key(row["away_name"])
        result = {"row": row, "status": None, "match": None, "reversed": False, "home": None}
        results.append(result)
        if home is None or away is None:
            result["status"] = "unparseable name"
            continue
        if home == away:
            result["status"] = "same name key"
            continue
        candidates = {}
        for match, reversed_used in index.get((row["tour"], frozenset((home, away))), ()):
            if in_window(row, match, window):
                previous = candidates.get(id(match))
                # A match found through a direct key is not "reversed" even if a reversed key also finds it.
                candidates[id(match)] = (match, reversed_used and (previous is None or previous[1]))
        if not candidates:
            result["status"] = "no candidate"
        elif len(candidates) > 1:
            result["status"] = "ambiguous"
        else:
            match, reversed_used = next(iter(candidates.values()))
            side = home_side(row, match, names)
            if side is None:
                result["status"] = "same name key"
                continue
            result.update(status="linked", match=match, reversed=reversed_used, home=side)

    claims = Counter(id(result["match"]) for result in results if result["status"] == "linked")
    for result in results:
        if result["status"] == "linked" and claims[id(result["match"])] > 1:
            result.update(status="ambiguous", match=None, home=None)
    return results


def pair_ids(result):
    """((provider home id, Sackmann id), (provider away id, Sackmann id)) for a linked result."""
    row, match = result["row"], result["match"]
    home_id, away_id = (match["winner_id"], match["loser_id"]) if result["home"] == "winner" else (
        match["loser_id"], match["winner_id"])
    return (row["home_id"], home_id), (row["away_id"], away_id)


def build_crosswalk(results):
    """The validated one-to-one TennisData.app crosswalk from linked results. See build_links."""
    pairs = []
    for result in results:
        if result["status"] == "linked":
            pairs.extend((result["row"]["tour"], provider_id, sackmann_id) for provider_id, sackmann_id in pair_ids(result))
    return build_links(pairs)


def build_links(pairs):
    """A one-to-one crosswalk from (tour, foreign id, Sackmann id) observations, one per player per linked match.

    A foreign id is accepted only if every observation pairs it with the same Sackmann id and no other foreign id
    is paired with that Sackmann id. Returns {"links": {(tour, foreign_id): sackmann_id},
    "support": {(tour, foreign_id): Counter}, "conflicts": [description dicts]}.
    """
    support = defaultdict(Counter)
    for tour, provider_id, sackmann_id in pairs:
        support[(tour, provider_id)][sackmann_id] += 1
    providers_of = defaultdict(set)
    for (tour, provider_id), counts in support.items():
        for sackmann_id in counts:
            providers_of[(tour, sackmann_id)].add(provider_id)

    links, conflicts = {}, []
    for (tour, provider_id), counts in sorted(support.items()):
        rivals = {other for sackmann_id in counts for other in providers_of[(tour, sackmann_id)]} - {provider_id}
        if len(counts) == 1 and not rivals:
            links[(tour, provider_id)] = next(iter(counts))
        else:
            conflicts.append({"tour": tour, "provider_id": provider_id, "sackmann_ids": dict(counts),
                              "other_provider_ids": sorted(rivals)})
    return {"links": links, "support": dict(support), "conflicts": conflicts}


def link_by_ids(rows, matches, links, window=WINDOW, taken=()):
    """Second pass for rows the name keys missed: both provider ids already in the crosswalk, and exactly one
    Sackmann match between those two Sackmann ids inside the window that no other row has taken."""
    by_pair = defaultdict(list)
    for match in matches:
        by_pair[(match["tour"], frozenset((match["winner_id"], match["loser_id"])))].append(match)
    taken = set(taken)
    results = []
    for row in rows:
        home, away = links.get((row["tour"], row["home_id"])), links.get((row["tour"], row["away_id"]))
        if home is None or away is None or home == away:
            continue
        candidates = [match for match in by_pair.get((row["tour"], frozenset((home, away))), ())
                      if in_window(row, match, window) and id(match) not in taken]
        if len(candidates) == 1:
            match = candidates[0]
            results.append({"row": row, "status": "linked by ids", "match": match, "reversed": False,
                            "home": "winner" if match["winner_id"] == home else "loser"})
    claims = Counter(id(result["match"]) for result in results)
    return [result for result in results if claims[id(result["match"])] == 1]


# ---------------------------------------------------------------- general pair linking (TennisIsMyLife)

def full_name_key(name):
    """A full name as one normalized string: "Pablo Carreño Busta" -> "pablocarrenobusta"."""
    return normalize(name)


def sackmann_full_keys(first, last):
    """Full-name keys for a Sackmann player in both orders, tagged "direct" and "reversed"."""
    return {"direct": normalize(first + last), "reversed": normalize(last + first)}


def initial_keys(full_name):
    """Every TennisData.app-style ("surname", "i") key a full name could produce: each split of the name into
    given names and surname, with the surname last or first. "Bu Yunchaokete" gives ("yunchaokete", "b") and
    ("bu", "y"); "Pablo Carreno Busta" gives ("carrenobusta", "p") among others."""
    tokens = full_name.split()
    keys = set()
    for k in range(1, len(tokens)):
        keys.add((normalize("".join(tokens[k:])), normalize(tokens[0])[:1]))
        keys.add((normalize("".join(tokens[:k])), normalize(tokens[k])[:1]))
    return {key for key in keys if key[0] and key[1]}


def link_pairs(items, targets, item_keys, target_keys, in_window):
    """Links each item to at most one target describing the same match.

    item_keys(item) gives the item's two players' keys as an ordered pair (or None). target_keys(target) gives
    alternatives as (ordered pair of keys, tag). An item links when its two keys equal one alternative's two
    keys, in_window(item, target) holds, exactly one target fits, and no other item links to that target.

    Returns one result per item: {"item", "status", "target", "tag", "same_order"}, where same_order says whether
    the item's first player is the target's first player. Status is "linked", "ambiguous", "no candidate",
    "no usable names", or "same name key".
    """
    index = defaultdict(list)
    for position, target in enumerate(targets):
        for ordered, tag in target_keys(target):
            if ordered[0] != ordered[1]:
                index[frozenset(ordered)].append((position, ordered, tag))
    results = []
    for item in items:
        keys = item_keys(item)
        result = {"item": item, "status": None, "target": None, "tag": None, "same_order": None}
        results.append(result)
        if keys is None or None in keys or keys[0] == keys[1]:
            result["status"] = "no usable names"
            continue
        found = defaultdict(list)
        for position, ordered, tag in index.get(frozenset(keys), ()):
            if in_window(item, targets[position]):
                found[position].append((ordered, tag))
        if not found:
            result["status"] = "no candidate"
        elif len(found) > 1:
            result["status"] = "ambiguous"
        else:
            position, options = next(iter(found.items()))
            orders = {ordered[0] == keys[0] for ordered, _ in options}
            if len(orders) != 1:
                result["status"] = "same name key"
                continue
            tags = {tag for _, tag in options}
            result.update(status="linked", target=targets[position], same_order=orders.pop(),
                          tag="direct" if "direct" in tags else sorted(tags)[0])
    claims = Counter(id(result["target"]) for result in results if result["status"] == "linked")
    for result in results:
        if result["status"] == "linked" and claims[id(result["target"])] > 1:
            result.update(status="ambiguous", target=None, same_order=None)
    return results


def sackmann_pair_keys(names, key_function=sackmann_full_keys):
    """target_keys for Sackmann matches: every combination of the winner's and loser's keys, in winner-loser
    order, tagged "direct" only when both keys are direct."""
    def keys(match):
        winner = names[(match["tour"], match["winner_id"])]
        loser = names[(match["tour"], match["loser_id"])]
        options = []
        for winner_tag, winner_key in key_function(winner["first"], winner["last"]).items():
            for loser_tag, loser_key in key_function(loser["first"], loser["last"]).items():
                tag = "direct" if winner_tag == loser_tag == "direct" else "reversed"
                options.append(((winner_key, loser_key), tag))
        return options
    return keys


def save_crosswalk(path, crosswalk, names, provider_names):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["tour", "provider_id", "sackmann_id", "sackmann_name", "provider_names", "linked_matches"])
        for (tour, provider_id), sackmann_id in sorted(crosswalk["links"].items()):
            person = names[(tour, sackmann_id)]
            writer.writerow([tour, provider_id, sackmann_id, f"{person['first']} {person['last']}",
                             "; ".join(sorted(provider_names.get((tour, provider_id), ()))),
                             crosswalk["support"][(tour, provider_id)][sackmann_id]])


def load_crosswalk(path):
    """{(tour, provider_id): sackmann_id} from a saved crosswalk file."""
    with open(path, encoding="utf-8", newline="") as file:
        return {(row["tour"], row["provider_id"]): int(row["sackmann_id"]) for row in csv.DictReader(file)}
