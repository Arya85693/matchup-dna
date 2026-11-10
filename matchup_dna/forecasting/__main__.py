"""Commands for the forecasting engine.

    python -m matchup_dna.forecasting models export          write the frozen model artifacts (once)
    python -m matchup_dna.forecasting models check           refit and confirm the artifacts byte for byte
    python -m matchup_dna.forecasting espn sync              archive ESPN scoreboards (every third day from --first,
                                                             daily for the last 14 days and next 3)
    python -m matchup_dna.forecasting forecast               refresh ESPN, then forecast every eligible fixture now
    python -m matchup_dna.forecasting settle                 refresh ESPN, then attach results to stored matches
    python -m matchup_dna.forecasting daily                  refresh, forecast, settle, ledger: the scheduled job
                                                             (--no-espn: TennisData.app snapshot fixtures only)
    python -m matchup_dna.forecasting status                 runs, decisions, predictions, integrity, identity drift
    python -m matchup_dna.forecasting verify                 recompute every hash, and every stored probability from
                                                             its own input snapshot and model artifact
    python -m matchup_dna.forecasting export-ledger          write forecasts/ledger.jsonl (append-only check)
    python -m matchup_dna.forecasting rehearse [--days ...]  replay past days into a replay store, compare with research
    python -m matchup_dna.forecasting protocol freeze        write the prospective protocol (once)
    python -m matchup_dna.forecasting protocol amend --details FILE   write the next protocol amendment (code change)
    python -m matchup_dna.forecasting evaluate --monitor     interim monitor (decides nothing)
    python -m matchup_dna.forecasting evaluate --final       the one P1 evaluation, after the window closes
    python -m matchup_dna.forecasting api upcoming           print the website's upcoming-forecasts payload
    python -m matchup_dna.forecasting probe ...              one authenticated GET to a live provider, archived raw

Stores: data/store/live.sqlite (live forecasts) unless --store is given. Provider files are read from data/external/.
"""
import argparse
import datetime
import json
import sys

from matchup_dna.elo import RESULTS_DIR

ROOT = RESULTS_DIR.parent
LIVE_STORE = ROOT / "data" / "store" / "live.sqlite"


def open_store(path, mode):
    from matchup_dna.forecasting.store import Store
    return Store(path, mode=mode)


def sources():
    from matchup_dna.forecasting.history import load_sources
    from matchup_dna.phase4_experiment import PROTOCOL_PATH
    return load_sources(PROTOCOL_PATH)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m matchup_dna.forecasting")
    parser.add_argument("command")
    parser.add_argument("sub", nargs="?")
    parser.add_argument("--store", default=str(LIVE_STORE))
    parser.add_argument("--days", nargs="*")
    parser.add_argument("--monitor", action="store_true")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--details", help="protocol amend: JSON file with the amendment's reason, fix and statements")
    parser.add_argument("--name")
    parser.add_argument("--url")
    parser.add_argument("--header")
    parser.add_argument("--key-env")
    parser.add_argument("--extra-header", action="append", default=[])
    parser.add_argument("--no-espn", action="store_true", help="use the TennisData.app snapshot's fixtures only")
    parser.add_argument("--first", help="espn sync: first day to archive (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    from matchup_dna.forecasting.records import UTC
    now = datetime.datetime.now(UTC)

    if args.command == "models":
        from matchup_dna.forecasting import frozen_models
        {"export": frozen_models.export, "check": frozen_models.check}[args.sub]()
    elif args.command in ("forecast", "settle", "daily"):
        from matchup_dna.forecasting import pipeline
        if not args.no_espn:
            print(f"ESPN requests: {pipeline.refresh_espn(now.date())}")
            now = datetime.datetime.now(UTC)
        data = sources()
        now = datetime.datetime.now(UTC)
        assembly = pipeline.live_assembly(data, now, use_espn=not args.no_espn)
        now = datetime.datetime.now(UTC)
        store = open_store(args.store, "live" if args.command != "settle" else None)
        if args.command in ("forecast", "daily"):
            run, counts = pipeline.forecast(store, data, now, assembly=assembly, ledger_path=pipeline.LEDGER)
            print(run)
            print(json.dumps({k: v for k, v in counts.items() if not k.startswith("assembly")}, indent=2,
                             sort_keys=True))
        if args.command in ("settle", "daily"):
            run, counts = pipeline.settle(store, data, now, assembly=assembly)
            print(run, json.dumps(counts, indent=2, sort_keys=True))
    elif args.command == "espn" and args.sub == "sync":
        from matchup_dna.forecasting import espn
        first = datetime.date.fromisoformat(args.first or "2026-01-01")
        print(f"ESPN requests: {espn.sync(first, now.date() + datetime.timedelta(days=3), step=3, refresh_from=now.date() - datetime.timedelta(days=14))}")
    elif args.command == "status":
        from matchup_dna.forecasting.api import status
        print(json.dumps(status(open_store(args.store, None)), indent=2, sort_keys=True))
    elif args.command == "verify":
        from matchup_dna.forecasting.api import verify_store
        problems = verify_store(open_store(args.store, None))
        print("intact" if not problems else "\n".join(problems))
        sys.exit(1 if problems else 0)
    elif args.command == "export-ledger":
        from matchup_dna.forecasting import pipeline
        count = open_store(args.store, None).export_ledger(pipeline.LEDGER)
        print(f"{count} predictions in {pipeline.LEDGER}")
    elif args.command == "rehearse":
        from matchup_dna.forecasting import rehearsal
        rehearsal.rehearse(args.days or rehearsal.DEFAULT_DAYS)
    elif args.command == "protocol" and args.sub == "freeze":
        from matchup_dna.forecasting import prospective
        prospective.freeze()
    elif args.command == "protocol" and args.sub == "amend":
        from pathlib import Path
        from matchup_dna.forecasting import prospective
        if not args.details:
            raise SystemExit("protocol amend needs --details FILE (a JSON object with "
                             f"{', '.join(prospective.AMENDMENT_DETAILS)})")
        prospective.amend(json.loads(Path(args.details).read_text(encoding="utf-8")))
    elif args.command == "evaluate":
        from matchup_dna.forecasting import prospective
        print("\n".join(prospective.evaluate(open_store(args.store, "live"), final=args.final)))
    elif args.command == "api":
        from matchup_dna.forecasting import api
        store = open_store(args.store, None)
        payloads = {"upcoming": lambda: api.upcoming(store, now), "models": lambda: api.models(store),
                    "track-record": lambda: api.track_record(store)}
        print(json.dumps(payloads[args.sub](), indent=2, sort_keys=True))
    elif args.command == "probe":
        from matchup_dna.forecasting.providers import HttpProbe
        extra = dict(item.split("=", 1) for item in args.extra_header)
        print(json.dumps(HttpProbe(args.name, args.url, args.header, args.key_env, extra).fetch(), indent=2))
    else:
        parser.error(f"unknown command {args.command} {args.sub or ''}")


if __name__ == "__main__":
    main()
