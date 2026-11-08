"""Linking Valuebetennis odds rows to the model's matches (Phase 5).

Valuebetennis has its own player ids and full names ("Jannik Sinner"). The model's matches carry Sackmann ids
(and, from June 2026, the Phase 4 held-out identities) with full names. The integers never match, and a surname is
not enough (Sackmann has Martin and Jannik Sinner, and three Djokovics). Nothing here looks at prices or at who won,
so the join cannot favour the model or the market. The winner is used afterwards only as a data check.

Rules (the lessons of Phase 4 erratum 1 built in):

1. Name pass. A Valuebetennis row links to a model match on the same tour when both players' full names agree
   (accents, case, hyphens and word order ignored), the Valuebetennis match day is WINDOW days from the model
   match's tourney_date, and the rounds are consistent (quarterfinal, semifinal and final codes must agree).
2. Players become one person only through linked matches: a Valuebetennis id is mapped to a model id when every
   linked match pairs it with that id and no other Valuebetennis id claims the same model id (one-to-one).
   Conflicts are listed and never used.
   Name variants that exact names never verify ("Cori Gauff" for Coco Gauff, "Taylor Harry Fritz") are mapped from
   opponent evidence: in at least two rows the player's opponent is already mapped, exactly one model match of that
   opponent fits the window and the round, and the model player there shares a surname with this one; all the
   evidence must point to one model player, one-to-one (opponent_evidence). One row is enough when one name is the
   other with words added ("Aisam Qureshi" / "Aisam Ul Haq Qureshi").
   A player the model holds under two ids with one identical name (Martin Landaluce has two Sackmann ids) is
   mapped to both (same_name_ids); any other conflict stays out.
3. Id pass. A row the names missed links when both of its Valuebetennis ids are mapped and exactly one model match
   between those two players fits the window and the round.
4. One real match, one row. If several Valuebetennis rows claim one model match, a row with a real clock time is
   preferred to placeholders timed exactly 00:00:00; if that does not decide it, none is used and all are listed.
   A row that fits several model matches is never linked.
5. Data check. A linked pair whose two sources name different winners is reported and left out.
"""
import re
import unicodedata
from collections import Counter, defaultdict

from matchup_dna.crosswalk import build_links
from matchup_dna.valuebetennis import ROUND_NAMES, is_qualifying

WINDOW = (-3, 16)  # Valuebetennis match day minus the model match's tourney_date, in days
KNOCKOUT = ("QF", "SF", "F")


def linkable(row):
    """Every category is considered: Sackmann's tour-level files include WTA events that Valuebetennis files as
    Challenger or ITF, and a full-name, same-window, same-round match is the same match at any level. Tour-level
    qualifying rounds and "A/B" pairs are removed first."""
    return row["tour"] is not None and not is_qualifying(row) and not any("/" in n for n in row["names"])


def name_key(name):
    """Letter tokens, accent-free, in sorted order: "Carreño-Busta Pablo" == "Pablo Carreno Busta"."""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return tuple(sorted(token for token in re.split(r"[^a-z]+", text) if token))


def to_day(tourney_date):
    import datetime
    return datetime.date(tourney_date // 10000, tourney_date // 100 % 100, tourney_date % 100)


def in_window(vb_row, model_row):
    return WINDOW[0] <= (vb_row["day"] - to_day(model_row["tourney_date"])).days <= WINDOW[1]


TEAM_ROUND_CODES = 13  # codes from 13 up are team-event rubbers and say nothing about the round


def rounds_agree(vb_row, model_row):
    """False only when the two sources name clearly different rounds: a quarterfinal, semifinal or final in one
    source against a different round in the other. Earlier-round codes vary by draw size, and team-event codes
    (13 and up) carry no round, so neither is compared."""
    code = vb_row["round_code"]
    model_round = model_row["round"]
    if model_round in ("RR", "BR", "ER", "unknown") or code is None or code >= TEAM_ROUND_CODES:
        return True
    vb_round = ROUND_NAMES.get(code)
    if vb_round is not None or model_round in KNOCKOUT:
        return vb_round == model_round
    return True


def orientation(vb_row, model_row, by="names", crosswalk=None):
    """True if Valuebetennis player 1 is model player A, False if B, None if it cannot be told. With by="ids" the
    crosswalk maps each Valuebetennis id to a set of model ids (one person can hold several model ids)."""
    if by == "names":
        first, second = (name_key(n) for n in vb_row["names"])
        a, b = name_key(model_row["a_name"]), name_key(model_row["b_name"])
        if (first, second) == (a, b):
            return True
        if (first, second) == (b, a):
            return False
        return None
    first, second = (crosswalk.get((vb_row["tour"], i), frozenset()) for i in vb_row["ids"])
    straight = model_row["a_id"] in first and model_row["b_id"] in second
    crossed = model_row["b_id"] in first and model_row["a_id"] in second
    return None if straight == crossed else straight


def resolve_claims(found, report, label, editions=None):
    """found: [(vb_row, model_row, same_order)]. Keeps one row per model match (rule 4): the claimant from the
    Valuebetennis edition linked to that model tournament (a second meeting a week later at another event can fall
    in the same date window), else the one claimant with a real clock time, else none."""
    by_match = defaultdict(list)
    for item in found:
        by_match[item[1]["match_id"]].append(item)
    kept, review = [], []
    for items in by_match.values():
        if len(items) == 1:
            kept.append(items[0])
            continue
        if editions:
            own = [item for item in items
                   if editions.get((item[0]["tour"], item[0]["edition"])) == model_edition(item[1])]
            if len(own) == 1:
                kept.append(own[0])
                report[f"{label}: model match claimed by several rows, the one from the linked edition kept"] += 1
                continue
        timed = [item for item in items if not item[0]["midnight"]]
        if len(timed) == 1:
            kept.append(timed[0])
            report[f"{label}: model match claimed by several rows, one with a real time kept"] += 1
        else:
            report[f"{label}: model match claimed by several rows, none used"] += 1
            review.append({"reason": "several Valuebetennis rows claim one model match", "model_match": items[0][1]["match_id"],
                          "vb_ids": [item[0]["vb_id"] for item in items]})
    return kept, review


def model_edition(model_row):
    return model_row["match_id"].split("|")[1]


def edition_map(links):
    """{(tour, Valuebetennis edition): model tourney_id} where the unambiguous links of that edition point to one
    model tournament more often than to any other."""
    votes = defaultdict(Counter)
    for r, m, _ in links:
        votes[(r["tour"], r["edition"])][model_edition(m)] += 1
    found = {}
    for key, counts in votes.items():
        ranked = counts.most_common(2)
        if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
            found[key] = ranked[0][0]
    return found


def candidates_for(vb_row, pool, report, label, editions=None):
    fitting = [m for m in pool if in_window(vb_row, m) and rounds_agree(vb_row, m)]
    if len(fitting) > 1 and editions:
        mapped = editions.get((vb_row["tour"], vb_row["edition"]))
        same_edition = [m for m in fitting if model_edition(m) == mapped]
        if mapped is not None and len(same_edition) == 1:
            report[f"{label}: several fits, settled by the linked edition"] += 1
            fitting = same_edition
    if len(fitting) > 1:
        report[f"{label}: row fits several model matches, not linked"] += 1
        return None, {"reason": "row fits several model matches", "vb_id": vb_row["vb_id"],
                      "model_matches": [m["match_id"] for m in fitting]}
    return (fitting[0] if fitting else None), None


MIN_VARIANT_MATCHES = 2


def shares_surname(first, second):
    """The last word of either name is one of the other name's words: "Coco Gauff" / "Cori Gauff",
    "Paula Badosa" / "Paula Badosa Gibert", "Jaume Munar" / "Jaume Antoni Munar Clar". A shared given name alone
    ("Taylor Fritz" / "Taylor Townsend") is not enough."""
    a, b = name_key(first), name_key(second)
    last_a = re.split(r"[^a-z]+", unicodedata.normalize("NFKD", first).encode("ascii", "ignore").decode().lower().strip())[-1]
    last_b = re.split(r"[^a-z]+", unicodedata.normalize("NFKD", second).encode("ascii", "ignore").decode().lower().strip())[-1]
    return bool(a and b) and (last_a in b or last_b in a)


def extends(first, second):
    """One name is the other with words added: "Martin Landaluce" / "Martin Landaluce", "Aisam Qureshi" /
    "Aisam Ul Haq Qureshi", "Chak Lam Coleman Wong" / "Coleman Wong". Strong enough for one match of evidence."""
    a, b = set(name_key(first)), set(name_key(second))
    return bool(a and b) and (a <= b or b <= a) and shares_surname(first, second)


def opponent_evidence(rows, model_rows, crosswalk, taken_rows):
    """Name variants that exact names can never verify ("Cori Gauff" for Coco Gauff). An unmapped Valuebetennis
    player x gets a vote for model player y from a row where x's opponent is already mapped, exactly one model match
    of that opponent fits the window and the round, and y (the opponent's opponent there) shares a surname with x.
    x is mapped to y when all its votes are for y, no other x votes for y, y belongs to no other Valuebetennis id,
    and there are at least MIN_VARIANT_MATCHES votes, or one vote when one name extends the other (extends()).
    Returns ({(tour, x): frozenset({y})}, rejected candidates)."""
    by_player = defaultdict(list)
    for m in model_rows:
        by_player[(m["tour"], m["a_id"])].append((m, m["b_id"], m["b_name"]))
        by_player[(m["tour"], m["b_id"])].append((m, m["a_id"], m["a_name"]))
    owned = defaultdict(set)
    for (tour, _), model_ids in crosswalk.items():
        owned[tour] |= model_ids
    votes, x_names, y_names = defaultdict(Counter), {}, {}
    for r in rows:
        if r["vb_id"] in taken_rows:
            continue
        for side in (0, 1):
            x, opponent = r["ids"][side], r["ids"][1 - side]
            if (r["tour"], x) in crosswalk or (r["tour"], opponent) not in crosswalk:
                continue
            fits = [(m, y, y_name) for opponent_id in crosswalk[(r["tour"], opponent)]
                    for m, y, y_name in by_player.get((r["tour"], opponent_id), ())
                    if in_window(r, m) and rounds_agree(r, m) and shares_surname(r["names"][side], y_name)]
            if len(fits) == 1 and fits[0][1] not in owned[r["tour"]]:
                votes[(r["tour"], x)][fits[0][1]] += 1
                x_names[(r["tour"], x)], y_names[(r["tour"], fits[0][1])] = r["names"][side], fits[0][2]
    def one_person(tour, ids):
        """Several voted model ids count as one person only if they all carry the identical name."""
        return len({name_key(y_names[(tour, y)]) for y in ids}) == 1

    claimed = Counter((tour, y) for (tour, _), counts in votes.items() if one_person(tour, counts) for y in counts)
    found, rejected = {}, []
    for (tour, x), counts in votes.items():
        y, n = counts.most_common(1)[0]
        total = sum(counts.values())
        needed = 1 if extends(x_names[(tour, x)], y_names[(tour, y)]) else MIN_VARIANT_MATCHES
        if one_person(tour, counts) and total >= needed and all(claimed[(tour, i)] == 1 for i in counts):
            found[(tour, x)] = frozenset(counts)
        else:
            rejected.append({"tour": tour, "vb_id": x, "votes": dict(counts),
                             "reason": "one match only, and the names differ by more than added words"
                             if one_person(tour, counts) and total < needed
                             else "votes for several different model players" if not one_person(tour, counts)
                             else "another Valuebetennis id votes for the same model player"})
    return found, rejected


def same_name_ids(conflicts, model_names):
    """A Valuebetennis id that linked matches pair with several model ids is one person holding several model ids
    (Martin Landaluce has two Sackmann ids) only if all those model ids carry the identical name and no other
    Valuebetennis id pairs with them. Returns {(tour, Valuebetennis id): frozenset(model ids)}; the rest stay out."""
    found = {}
    for conflict in conflicts:
        tour, model_ids = conflict["tour"], set(conflict["sackmann_ids"])
        keys = {name_key(model_names.get((tour, i), "")) for i in model_ids}
        if len(model_ids) > 1 and len(keys) == 1 and not conflict["other_provider_ids"]:
            found[(tour, conflict["provider_id"])] = frozenset(model_ids)
    return found


def link(vb_rows, model_rows):
    """Returns {"links": [(vb_row, model_row, same_order)], "crosswalk": {(tour, vb id): model id},
    "conflicts": [...], "review": [...], "report": Counter, "winner_mismatches": [...]}."""
    report, review = Counter(), []
    rows = [r for r in vb_rows if linkable(r)]
    report["Valuebetennis rows"] = len(vb_rows)
    report["rows considered (tour-level qualifying and A/B pairs removed; any category)"] = len(rows)

    by_names, by_ids = defaultdict(list), defaultdict(list)
    for m in model_rows:
        by_names[(m["tour"], frozenset((name_key(m["a_name"]), name_key(m["b_name"]))))].append(m)
        by_ids[(m["tour"], frozenset((m["a_id"], m["b_id"])))].append(m)

    # Pass 1: names. Rows that fit one model match first; their editions then settle rows that fit several.
    def name_pass(candidate_rows, editions, counts):
        found, problems = [], []
        for r in candidate_rows:
            pool = by_names.get((r["tour"], frozenset(name_key(n) for n in r["names"])), ())
            match, problem = candidates_for(r, pool, counts, "names", editions)
            if problem:
                problems.append((r, problem))
            elif match is not None:
                same = orientation(r, match)
                if same is None:
                    counts["names: players share a name key, side unclear, not linked"] += 1
                else:
                    found.append((r, match, same))
        return found, problems

    found, problems = name_pass(rows, None, Counter())
    editions = edition_map(found)
    found, problems = name_pass(rows, editions, report)
    review += [problem for _, problem in problems]
    first_pass, problems = resolve_claims(found, report, "names", editions)
    review += problems
    report["linked by names"] = len(first_pass)

    # Players: one-to-one, from linked matches only.
    observations = []
    for r, m, same in first_pass:
        a, b = (m["a_id"], m["b_id"]) if same else (m["b_id"], m["a_id"])
        observations += [(r["tour"], r["ids"][0], a), (r["tour"], r["ids"][1], b)]
    players = build_links(observations)
    crosswalk = {key: frozenset({model_id}) for key, model_id in players["links"].items()}
    report["players mapped by exact names (one-to-one)"] = len(crosswalk)
    model_names = {}
    for m in model_rows:
        model_names[(m["tour"], m["a_id"])], model_names[(m["tour"], m["b_id"])] = m["a_name"], m["b_name"]
    several = same_name_ids(players["conflicts"], model_names)
    crosswalk.update(several)
    conflicts = [c for c in players["conflicts"] if (c["tour"], c["provider_id"]) not in several]
    report["players holding several model ids under one identical name (mapped to all)"] = len(several)
    report["player conflicts (not used)"] = len(conflicts)
    variants, rejected = opponent_evidence(rows, model_rows, crosswalk, {r["vb_id"] for r, _, _ in first_pass})
    crosswalk.update(variants)
    report["players mapped by verified opponents and a shared surname (name variants)"] = len(variants)
    report["name-variant candidates rejected (one match only, or conflicting evidence)"] = len(rejected)

    # Pass 2: verified ids.
    taken_rows = {r["vb_id"] for r, _, _ in first_pass}
    taken_matches = {m["match_id"] for _, m, _ in first_pass}
    found = []
    for r in rows:
        if r["vb_id"] in taken_rows:
            continue
        mapped = [crosswalk.get((r["tour"], i)) for i in r["ids"]]
        if None in mapped or mapped[0] & mapped[1]:
            continue
        pool = [m for x in mapped[0] for y in mapped[1] for m in by_ids.get((r["tour"], frozenset((x, y))), ())
                if m["match_id"] not in taken_matches]
        match, problem = candidates_for(r, pool, report, "ids", editions)
        if problem:
            review.append(problem)
        elif match is not None:
            found.append((r, match, orientation(r, match, "ids", crosswalk)))
    second_pass, problems = resolve_claims(found, report, "ids", editions)
    review += problems
    report["linked by verified player ids"] = len(second_pass)

    links, mismatches = [], []
    for r, m, same in first_pass + second_pass:
        if r["winner"] is None:
            links.append((r, m, same))
            continue
        vb_says_a_won = (r["winner"] == 0) == same
        if vb_says_a_won == bool(m["a_won"]):
            links.append((r, m, same))
        else:
            mismatches.append({"vb_id": r["vb_id"], "model_match": m["match_id"], "names": r["names"]})
    report["data check: linked pairs naming different winners (left out)"] = len(mismatches)
    report["links kept"] = len(links)
    return {"links": links, "crosswalk": crosswalk, "conflicts": conflicts, "review": review, "report": report,
            "winner_mismatches": mismatches, "variants": variants, "variants_rejected": rejected,
            "several_ids": several}
