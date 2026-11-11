"""Whether an ITF run is due: the store has no ITF run that started in the last 50 minutes (about hourly on the
15-minute job's clock). Exit 0 if due, 1 if not. Read-only.

    python scripts/cloud/itf_due.py --store data/store/itf.sqlite

This replaces `python -m matchup_dna.itf_live due` (about every two hours) in the workflow. The pace is the
workflow's choice, not part of the frozen P2 code: P2 fixes how a forecast is made and counted, not how often runs
happen.
"""
import argparse
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

EVERY = datetime.timedelta(minutes=50)
UTC = datetime.timezone.utc


def due(store_path, now=None):
    from web.publisher.readonly import open_readonly
    now = now or datetime.datetime.now(UTC)
    if not Path(store_path).exists():
        return True, "no ITF store yet"
    store = open_readonly(store_path)
    try:
        starts = [r["started_at"] for r in store.runs("itf_forecast") if r["status"] != "running"]
    finally:
        store.close()
    if not starts:
        return True, "no ITF run yet"
    last = datetime.datetime.strptime(max(starts), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return now - last >= EVERY, f"last ITF run started {last:%Y-%m-%dT%H:%M:%SZ}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", default=str(ROOT / "data" / "store" / "itf.sqlite"))
    args = parser.parse_args(argv)
    is_due, why = due(args.store)
    print(f"{'due' if is_due else 'not due'}: {why}")
    return 0 if is_due else 1


if __name__ == "__main__":
    sys.exit(main())
