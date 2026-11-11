"""Decides, at the start of a GitHub Actions run, whether there is work to do and whether it is safe to do it (Phase 8).

    python scripts/cloud/gate.py preflight     --store PATH   the store's hash chain and every stored probability
                                                             verify, and the code matches the P1 protocol's fingerprint
                                                             (or a committed amendment's)
    python scripts/cloud/gate.py forecast-due  --store PATH   a 07:00 or 19:00 US Eastern slot has begun (within the last
                                                             3 hours) and no forecasting run has started since
    python scripts/cloud/gate.py results-due   --store PATH   a match started between 45 minutes and 6 hours ago and has
                                                             no result, or no results check has run for 2 hours

Each prints its answer and, on GitHub, writes `due=true|false` to $GITHUB_OUTPUT. preflight exits 1 on any problem, so
the run stops before it writes anything. The store is opened read-only (web/publisher/readonly.py).

GitHub schedules run in UTC and may start late, so each forecasting slot has two triggers an hour apart (for daylight
saving) and the second finds the slot already done. US Eastern time is computed here (second Sunday of March to first
Sunday of November), so no time-zone package is needed.
"""
import argparse
import datetime
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SLOTS = (7, 19)                       # forecasting runs, US Eastern hours
SLOT_WINDOW_HOURS = 3
RESULTS_FROM_MINUTES, RESULTS_TO_HOURS = 45, 6
RESULTS_FALLBACK_HOURS = 2
UTC = datetime.timezone.utc


def eastern_offset(moment):
    """US Eastern UTC offset at a UTC moment: -4 h in daylight saving time, else -5 h."""
    year = moment.year

    def sunday(month, nth):
        first = datetime.datetime(year, month, 1, tzinfo=UTC)
        return first + datetime.timedelta(days=(6 - first.weekday()) % 7 + 7 * (nth - 1))
    starts = sunday(3, 2) + datetime.timedelta(hours=7)        # 02:00 EST = 07:00 UTC
    ends = sunday(11, 1) + datetime.timedelta(hours=6)         # 02:00 EDT = 06:00 UTC
    return datetime.timedelta(hours=-4 if starts <= moment < ends else -5)


def latest_slot(now):
    """The most recent forecasting slot (07:00 or 19:00 Eastern) at or before `now`, as a UTC time."""
    local = now + eastern_offset(now)
    candidates = []
    for days in (0, 1):
        day = (local - datetime.timedelta(days=days)).date()
        for hour in SLOTS:
            slot_local = datetime.datetime(day.year, day.month, day.day, hour, tzinfo=UTC)   # wall time, as if UTC
            slot = slot_local - eastern_offset(slot_local + datetime.timedelta(hours=5))    # offset at ~that moment
            if slot <= now:
                candidates.append(slot)
    return max(candidates)


def runs(store):
    return [dict(r) for r in store.db.execute("SELECT kind, started_at, status FROM runs ORDER BY started_at")]


def parse(text):
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def forecast_due(store, now):
    slot = latest_slot(now)
    if now - slot > datetime.timedelta(hours=SLOT_WINDOW_HOURS):
        return False, f"no slot in progress (last slot {slot:%Y-%m-%d %H:%M} UTC)"
    done = [r for r in runs(store) if r["kind"] == "forecast" and parse(r["started_at"]) >= slot]
    if done:
        return False, f"slot {slot:%H:%M} UTC already ran at {done[-1]['started_at']}"
    return True, f"slot {slot:%Y-%m-%d %H:%M} UTC is due"


def results_due(store, now, protocol=None):
    from matchup_dna.forecasting import prospective
    from web.publisher import views
    snap = views._Snapshot(store, protocol or prospective.load_protocol())
    due = []
    for uid in snap.matches:
        start = snap.start(uid)
        if uid in snap.settled or not start or snap.state(uid, now) in ("cancelled", "postponed"):
            continue
        if datetime.timedelta(minutes=RESULTS_FROM_MINUTES) <= now - start <= datetime.timedelta(hours=RESULTS_TO_HOURS):
            due.append(uid)
    checks = [parse(r["started_at"]) for r in runs(store) if r["kind"] in ("settle", "forecast")]
    stale = not checks or now - max(checks) >= datetime.timedelta(hours=RESULTS_FALLBACK_HOURS)
    if due:
        return True, f"{len(due)} result(s) due"
    if stale:
        return True, f"no results check for {RESULTS_FALLBACK_HOURS} hours"
    return False, "no result due"


def preflight(store_path):
    """([problems], [notes]). Problems stop the run. A probability that recomputes within the processor-rounding
    tolerance of its stored value is a note, by the rule in web/publisher/integrity.py that the website's status page
    applies too. The hash chain, the content hashes and the code fingerprint are still checked exactly."""
    from matchup_dna.forecasting import prospective
    from web.publisher import integrity
    from web.publisher.readonly import open_readonly
    problems, notes = [], []
    if prospective.code_sha256() not in prospective.accepted_code(prospective.load_protocol()):
        problems.append("the code does not match the P1 protocol's fingerprint (or a committed amendment's)")
    store = open_readonly(store_path)
    try:
        if store.mode != "live":
            problems.append(f"the store is in {store.mode} mode, not live")
        found, notes = integrity.check(store)
        problems += found
    finally:
        store.close()
    return problems, notes


def output(due, why):
    print(f"{'due' if due else 'not due'}: {why}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"due={'true' if due else 'false'}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("check", choices=("preflight", "forecast-due", "results-due"))
    parser.add_argument("--store", required=True)
    args = parser.parse_args(argv)
    now = datetime.datetime.now(UTC).replace(microsecond=0)
    if args.check == "preflight":
        problems, notes = preflight(args.store)
        print("preflight: " + ("ok (hash chain intact, probabilities recomputed, code matches P1)" if not problems
                               else "FAILED\n  " + "\n  ".join(problems)))
        for note in notes:
            print(f"  note: {note}")
        return 1 if problems else 0
    from web.publisher.readonly import open_readonly
    store = open_readonly(args.store)
    try:
        due, why = (forecast_due if args.check == "forecast-due" else results_due)(store, now)
    finally:
        store.close()
    output(due, why)
    return 0


if __name__ == "__main__":
    sys.exit(main())
