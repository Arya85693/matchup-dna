"""ITF extension, stage I1: the data audit behind "ITF - Data Audit and Plan.md".

    python -m matchup_dna.audit_itf      writes results/itf/audit.json and prints a summary

Every file is read through `itf_splits.rows`, so the held-out period (itf_splits.HELD_OUT_START on) is sealed: nothing here sees a
match, a rank or a ranking dated in it. Outcome-based numbers (the rank baseline) use the development split only;
validation contributes coverage and quality counts, never results.
"""
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from matchup_dna import itf_splits as splits
from matchup_dna.elo import is_rated
from matchup_dna.load import DATA_DIR, parse_match

OUT = Path(__file__).resolve().parent.parent / "results" / "itf" / "audit.json"
FAMILIES = {   # file family -> what it holds
    "itf": re.compile(r"(atp_matches_futures|wta_matches_qual_itf)_\d{4}\.csv"),
    "challenger_qualifying": re.compile(r"atp_matches_qual_chall_\d{4}\.csv"),
    "main": re.compile(r"(atp|wta)_matches_\d{4}\.csv"),
}
FIRST_YEAR = 2015
STATS = ("w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms", "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon", "l_SvGms")


def family(name):
    return next((f for f, p in FAMILIES.items() if p.fullmatch(name)), None)


def load(data_dir=DATA_DIR):
    """Every singles match before the held-out period from the three families: [(family, raw row, parsed match)]."""
    out = []
    for tour in ("ATP", "WTA"):
        for path in sorted((Path(data_dir) / tour.lower()).glob("*.csv")):
            fam = family(path.name)
            if fam is None:
                continue
            for row in splits.rows(path, allow_held_out=False):
                out.append((fam, row, parse_match(row, tour)))
    return out


def num(value):
    value = (value or "").strip()
    return None if value == "" else float(value)


def stats_state(row):
    """'none', 'partial', 'inconsistent' or 'ok' for one row's serve counts."""
    values = [num(row.get(c)) for c in STATS]
    if all(v is None for v in values):
        return "none"
    if any(v is None for v in values):
        return "partial"
    for side in ("w", "l"):
        svpt, first_in, first_won, second_won, games = (num(row[f"{side}_{c}"]) for c in ("svpt", "1stIn", "1stWon", "2ndWon", "SvGms"))
        if svpt <= 0 or first_in > svpt or first_won > first_in or second_won > svpt - first_in or games <= 0:
            return "inconsistent"
    return "ok"


def in_scope(fam, row, match):
    return fam == "itf" and splits.in_scope(row, match["tour"])


def coverage(data):
    table = defaultdict(lambda: {"matches": 0, "editions": set()})
    surfaces, best_of, draws = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for fam, row, m in data:
        if in_scope(fam, row, m) and m["tourney_date"] // 10000 >= FIRST_YEAR:
            year = m["tourney_date"] // 10000
            key = (m["tour"], year, m["tourney_level"])
            table[key]["matches"] += 1
            table[key]["editions"].add(m["tourney_id"])
            surfaces[m["tour"]][m["surface"] or "missing"] += 1
            best_of[m["tour"]][str(m["best_of"])] += 1
            draws[m["tour"]][row["draw_size"].strip() or "missing"] += 1
    return {"by_year_level": [{"tour": t, "year": y, "level": lv, "matches": v["matches"], "editions": len(v["editions"])}
                              for (t, y, lv), v in sorted(table.items())],
            "surfaces": {t: dict(c.most_common()) for t, c in surfaces.items()},
            "best_of": {t: dict(c) for t, c in best_of.items()},
            "draw_sizes": {t: dict(c.most_common()) for t, c in draws.items()}}


def quality(data, players):
    out = {}
    keys = Counter((m["key"]) for fam, row, m in data if fam == "itf")
    for fam, row, m in data:
        if not in_scope(fam, row, m):
            continue
        split = splits.split_of(m["tourney_date"])
        if split == "burn_in" and m["tourney_date"] // 10000 < FIRST_YEAR:
            continue
        name = split if split != "burn_in" else "2015-2020"
        q = out.setdefault((m["tour"], name), Counter())
        q["matches"] += 1
        q[f"outcome_{m['outcome']}"] += 1
        q["rated"] += is_rated(m)
        q["surface_missing"] += m["surface"] is None
        ranked = (m["winner_rank"] is not None) + (m["loser_rank"] is not None)
        q[f"ranked_{ranked}_of_2"] += 1
        q[f"stats_{stats_state(row)}"] += 1
        q["player_not_in_players_file"] += sum((m["tour"], pid) not in players for pid in (m["winner_id"], m["loser_id"]))
        q["same_player_both_sides"] += m["winner_id"] == m["loser_id"]
        q["duplicate_key"] += keys[m["key"]] > 1
    return [{"tour": t, "split": s, **dict(c)} for (t, s), c in sorted(out.items())]


def players_file(data_dir=DATA_DIR):
    import csv
    ids = set()
    for tour in ("ATP", "WTA"):
        with open(Path(data_dir) / tour.lower() / f"{tour.lower()}_players.csv", encoding="utf-8", errors="replace") as f:
            ids |= {(tour, int(r["player_id"])) for r in csv.DictReader(f) if r["player_id"].strip()}
    return ids


def overlaps(data):
    """Matches that appear in the ITF files and in another family: same tourney_id, or same date, players and round."""
    itf_ids, other_ids = defaultdict(set), defaultdict(set)
    itf_sig, other_sig = set(), set()
    for fam, row, m in data:
        sig = (m["tour"], m["tourney_date"], frozenset((m["winner_id"], m["loser_id"])), m["round"])
        if fam == "itf":
            itf_ids[m["tour"]].add(m["tourney_id"])
            if splits.in_scope(row, m["tour"]):
                itf_sig.add(sig)
        else:
            other_ids[m["tour"]].add(m["tourney_id"])
            other_sig.add(sig)
    return {"shared_tourney_ids": {t: len(itf_ids[t] & other_ids[t]) for t in ("ATP", "WTA")},
            "scope_matches_also_in_other_files": len(itf_sig & other_sig)}


def history_depth(data):
    """For development and validation scope matches: prior rated matches of the less-experienced player, counting
    (a) every family and (b) the main tour only. Earlier tourney_dates only, as the ratings replay sees them."""
    by_date = defaultdict(list)
    for fam, row, m in data:
        if is_rated(m):
            by_date[m["tourney_date"]].append((fam, row, m))
    every, main = Counter(), Counter()
    out = defaultdict(Counter)

    def bucket(n):
        return "0" if n == 0 else "1-9" if n < 10 else "10-49" if n < 50 else "50+"
    for date in sorted(by_date):
        for fam, row, m in by_date[date]:
            split = splits.split_of(date)
            if in_scope(fam, row, m) and split in ("development", "validation"):
                pair = [(m["tour"], m["winner_id"]), (m["tour"], m["loser_id"])]
                out[(m["tour"], split, "every_level")][bucket(min(every[p] for p in pair))] += 1
                out[(m["tour"], split, "main_tour_only")][bucket(min(main[p] for p in pair))] += 1
        for fam, row, m in by_date[date]:
            for pid in (m["winner_id"], m["loser_id"]):
                every[(m["tour"], pid)] += 1
                main[(m["tour"], pid)] += fam == "main"
    return [{"tour": t, "split": s, "history": h, **dict(c)} for (t, s, h), c in sorted(out.items())]


def entrant_ranks(data):
    """Median and quartiles of entrants' ranks per level and year (2021-2025): how strong each level's field is, so the
    2024 renaming of the women's levels can be mapped by field strength. Ranks only, no outcomes."""
    ranks = defaultdict(list)
    for fam, row, m in data:
        year = m["tourney_date"] // 10000
        if in_scope(fam, row, m) and 2021 <= year <= 2025 and m["round"] in ("R32", "R64"):
            for side in ("winner", "loser"):
                if m[f"{side}_rank"] is not None:
                    ranks[(m["tour"], year, m["tourney_level"])].append(m[f"{side}_rank"])
    out = []
    for (t, y, lv), r in sorted(ranks.items()):
        q = statistics.quantiles(r, n=4) if len(r) > 3 else [None, None, None]
        out.append({"tour": t, "year": y, "level": lv, "entrants_ranked": len(r), "q1": q[0], "median": q[1], "q3": q[2]})
    return out


def rank_baseline(data):
    """Development split only: how often the better-ranked player won, by tour and level, among rated scope matches."""
    out = defaultdict(Counter)
    for fam, row, m in data:
        if in_scope(fam, row, m) and is_rated(m) and splits.split_of(m["tourney_date"]) == "development":
            c = out[(m["tour"], m["tourney_level"])]
            w, l = m["winner_rank"], m["loser_rank"]
            if w is not None and l is not None:
                c["both_ranked"] += 1
                c["better_ranked_won"] += w < l
            elif w is None and l is None:
                c["neither_ranked"] += 1
            else:
                c["one_ranked"] += 1
                c["ranked_player_won"] += w is not None
    return [{"tour": t, "level": lv, **dict(c)} for (t, lv), c in sorted(out.items())]


def history_composition(data):
    c = Counter()
    for fam, row, m in data:
        if is_rated(m) and m["tourney_date"] // 10000 >= 2015:  # 2015 to the seal
            c[(m["tour"], fam if fam != "itf" or splits.in_scope(row, m["tour"]) else "itf_qualifying_or_other")] += 1
    return [{"tour": t, "family": f, "rated_matches_since_2015": n} for (t, f), n in sorted(c.items())]


def players(data):
    seen = defaultdict(set)
    for fam, row, m in data:
        if splits.split_of(m["tourney_date"]) in ("development", "validation") or fam == "main":
            for pid in (m["winner_id"], m["loser_id"]):
                tag = "itf" if in_scope(fam, row, m) else fam
                seen[(m["tour"], tag)].add(pid)
    out = {}
    for tour in ("ATP", "WTA"):
        itf = seen[(tour, "itf")]
        out[tour] = {"itf_players_2021_2025": len(itf),
                     "of_whom_ever_played_main_tour_before_2026": len(itf & seen[(tour, "main")])}
    return out


def audit(data_dir=DATA_DIR):
    data = load(data_dir)
    if any(m["tourney_date"] >= splits.HELD_OUT_START for _, _, m in data):
        raise SystemExit("the seal failed: a held-out-period row was read")
    return {"coverage": coverage(data), "quality": quality(data, players_file(data_dir)), "overlaps": overlaps(data),
            "history_composition": history_composition(data), "history_depth": history_depth(data),
            "players": players(data), "entrant_ranks": entrant_ranks(data), "rank_baseline_development": rank_baseline(data)}


def main():
    result = audit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for row in result["quality"]:
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
