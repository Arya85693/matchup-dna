"""ITF extension: the data splits, fixed before any ITF model work so the final test never waits for new matches.

    python -m matchup_dna.itf_splits write    record the splits, the scope and every input file's SHA-256
                                               in experiments/itf_splits.json (refuses if it exists)
    python -m matchup_dna.itf_splits check    the input files and the split counts still match that record

Every ITF match is assigned by its edition's `tourney_date` (Sackmann's date for the whole edition), so an edition
never straddles two splits:

    burn-in      before 2021-01-01         ratings warm up on it; never scored
    development  2021-01-01 - 2023-12-31   fitting and model choice, chronologically
    validation   2024-01-01 - 2024-12-31   final choice among a few declared candidates
    held-out     from 2025-01-01           sealed; scored once, after the ITF protocol is frozen and committed

The held-out split ends where the data snapshot ends (early June 2026), so it is complete today. Live ITF forecasts
are a later, separate prospective test.

Scope (the matches that are scored): ITF main-draw singles. Men: `atp_matches_futures_YYYY.csv`, levels 15 and 25
(and "S", the code for men's ITF events up to 2019). Women: `wta_matches_qual_itf_YYYY.csv`, ITF levels 10 to 100;
that file's WTA 125 events ("C"), tour qualifying (G/PM/P/I/W) and ITF qualifying rounds are left out. Women's ITF
qualifying coverage falls from about 20,000 rows in 2024 to about 2,300 in 2025, so scoring qualifying would make the
held-out split a different population; main draws are steady (about 16,000 a year).

The women's levels were renamed in 2024 (W25/W40/W60/W80 before, W35/W50/W75 after), so development and the later
splits use different level codes: a model must map them onto one scale rather than use the code itself.

The seal: until the protocol is committed, `rows()` drops every row dated in the held-out period from every file
(ITF, Challenger, main tour, rankings), so nothing about 2025 onward can shape a model choice. Main-tour 2025-2026
outcomes were seen in Phases 4-6; that is disclosed, and they still stay out of ITF development.
"""
import argparse
import csv
import datetime
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from matchup_dna.load import DATA_DIR

ROOT = Path(__file__).resolve().parent.parent
SPLITS_PATH = ROOT / "experiments" / "itf_splits.json"
PROTOCOL_PATH = ROOT / "experiments" / "itf_frozen_protocol.json"

SPLITS = (("burn_in", None, 20201231),
          ("development", 20210101, 20231231),
          ("validation", 20240101, 20241231),
          ("held_out", 20250101, None))
HELD_OUT_START = 20250101

ITF_FILES = {"ATP": re.compile(r"atp_matches_futures_\d{4}\.csv"), "WTA": re.compile(r"wta_matches_qual_itf_\d{4}\.csv")}
ITF_LEVELS = {"ATP": {"S", "15", "25"}, "WTA": {"10", "15", "25", "35", "40", "50", "60", "75", "80", "100"}}
DATE_COLUMNS = ("tourney_date", "ranking_date")      # match files, rankings files


def split_of(tourney_date):
    day = int(tourney_date)
    for name, first, last in SPLITS:
        if (first is None or day >= first) and (last is None or day <= last):
            return name
    raise ValueError(tourney_date)


def in_scope(row, tour):
    """An ITF main-draw singles match."""
    return row["tourney_level"].strip() in ITF_LEVELS[tour] and not row["round"].strip().upper().startswith("Q")


def itf_files(tour, data_dir=DATA_DIR):
    folder = Path(data_dir) / tour.lower()
    return sorted(p for p in folder.iterdir() if ITF_FILES[tour].fullmatch(p.name))


def input_files(data_dir=DATA_DIR):
    """Every Sackmann CSV the ITF work may read: ITF, Challenger and qualifying, main tour, players, rankings."""
    return sorted(p for tour in ("atp", "wta") for p in (Path(data_dir) / tour).glob("*.csv"))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


def committed(path):
    """Tracked by git and identical to HEAD."""
    rel = str(Path(path).resolve().relative_to(ROOT))
    return git("ls-files", "--error-unmatch", rel).returncode == 0 and git("diff", "--quiet", "HEAD", "--", rel).returncode == 0


def unsealed(protocol_path=PROTOCOL_PATH, splits_path=SPLITS_PATH, is_committed=None):
    """The held-out rows may be read only once a frozen ITF protocol that names these splits is committed."""
    is_committed = is_committed or committed
    if not (Path(protocol_path).exists() and Path(splits_path).exists()):
        return False
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    return protocol.get("splits_sha256") == sha256(splits_path) and is_committed(protocol_path) and is_committed(splits_path)


def rows(path, allow_held_out=None):
    """A Sackmann CSV's rows, without held-out-period rows unless the seal is lifted."""
    if allow_held_out is None:
        allow_held_out = unsealed()
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        column = next((c for c in DATE_COLUMNS if c in (reader.fieldnames or ())), None)
        for row in reader:
            if allow_held_out or column is None or int(row[column]) < HELD_OUT_START:
                yield row


def counts(data_dir=DATA_DIR):
    """In-scope rows and editions per tour and split. Counts only: no winner, score or statistic is read."""
    out = {}
    for tour in ("ATP", "WTA"):
        matches, editions, levels = Counter(), {}, {}
        for path in itf_files(tour, data_dir):
            for row in rows(path, allow_held_out=True):      # counted, never inspected
                if in_scope(row, tour):
                    split = split_of(row["tourney_date"])
                    matches[split] += 1
                    editions.setdefault(split, set()).add(row["tourney_id"])
                    levels.setdefault(split, Counter())[row["tourney_level"].strip()] += 1
        out[tour] = {name: {"matches": matches[name], "editions": len(editions.get(name, ())),
                            "levels": dict(sorted(levels.get(name, Counter()).items()))} for name, _, _ in SPLITS}
    return out


def last_held_out_date(data_dir=DATA_DIR):
    days = [int(r["tourney_date"]) for tour in ("ATP", "WTA") for p in itf_files(tour, data_dir)
            for r in rows(p, allow_held_out=True) if in_scope(r, tour)]
    return max(days)


def record(data_dir=DATA_DIR, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    files = {str(p.relative_to(Path(data_dir))).replace("\\", "/"): sha256(p) for p in input_files(data_dir)}
    return {
        "name": "ITF extension data splits",
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "assigned_by": "tourney_date (the edition's date), so an edition is never split",
        "splits": [{"name": n, "first": f, "last": l} for n, f, l in SPLITS],
        "held_out_data_ends": last_held_out_date(data_dir),
        "scope": {"ATP": {"files": "atp_matches_futures_YYYY.csv", "levels": sorted(ITF_LEVELS["ATP"])},
                  "WTA": {"files": "wta_matches_qual_itf_YYYY.csv", "levels": sorted(ITF_LEVELS["WTA"], key=int)},
                  "rounds": "main draw only (no round starting with Q)"},
        "seal": "rows dated 2025-01-01 or later are dropped from every file until experiments/itf_frozen_protocol.json"
                " is committed and names this file's SHA-256",
        "seen_before": ["Phases 4-6 saw main-tour outcomes from 2025-2026 (not ITF).",
                        "Phase 5 compared the model with the market on a few hundred WTA W35/W50 matches from 2024-2026"
                        " in aggregate (its 'ITF-level' group).",
                        "Phases 0 and 5 summarised ITF betting odds (coverage and margins only).",
                        "Before this record: per-year row counts by level and round, and how many rows carry serve"
                        " statistics and ranks. No ITF winner, score or statistic was looked at."],
        "counts": counts(data_dir),
        "input_files": files,
    }


def write(path=SPLITS_PATH, data_dir=DATA_DIR):
    path = Path(path)
    if path.exists():
        raise SystemExit(f"{path.name} already exists: the splits are fixed. Use `check`.")
    text = json.dumps(record(data_dir), indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256(path)


def check(path=SPLITS_PATH, data_dir=DATA_DIR):
    """[problems]: input files changed, added or missing, or the split counts differ."""
    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = []
    now = {str(p.relative_to(Path(data_dir))).replace("\\", "/"): p for p in input_files(data_dir)}
    for name, digest in saved["input_files"].items():
        if name not in now:
            problems.append(f"missing: {name}")
        elif sha256(now[name]) != digest:
            problems.append(f"changed: {name}")
    problems += [f"added: {name}" for name in sorted(set(now) - set(saved["input_files"]))]
    if not problems and counts(data_dir) != saved["counts"]:
        problems.append("split counts differ")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("write", "check"))
    args = parser.parse_args(argv)
    if args.command == "write":
        digest = write()
        saved = json.loads(SPLITS_PATH.read_text(encoding="utf-8"))
        for tour, splits in saved["counts"].items():
            print(tour, ", ".join(f"{n} {s['matches']:,} matches / {s['editions']:,} editions" for n, s in splits.items()))
        print(f"held-out data ends {saved['held_out_data_ends']}; wrote {SPLITS_PATH.name} (sha256 {digest[:16]}...)")
        return 0
    problems = check()
    print("check: ok" if not problems else "check: FAILED\n  " + "\n  ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
