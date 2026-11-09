"""Writes the website snapshot from a forecast store, without ever writing to the store.

    python -m web.publisher.publish                       live store -> web/.data/snapshot (local files)
    python -m web.publisher.publish --store PATH --out DIR

Steps, each of which can stop the publish (the previous snapshot then stays as it was):
1. open the store read-only; refuse a store that is not "live" (unless --allow-replay, for development only);
2. skip if a forecasting or settlement run is in progress, so a scheduled run is never held up by a read lock;
3. copy the store with SQLite's backup API and close the live file; everything below reads the copy;
4. build the public views; check every file against the contract (web/publisher/contract.py);
5. write the files into a new directory v1/<generated-at>/, then replace v1/manifest.json, which names that
   directory and every file's sha256. A reader following the manifest never sees a half-written snapshot;
6. delete all but the newest KEEP_SNAPSHOTS snapshot directories (scheduled every two hours: two days' worth).

Uploading the directory to hosting is a separate step (Phase 7G), not done here.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from matchup_dna.forecasting import prospective
from matchup_dna.forecasting.records import iso, utc
from web.publisher import contract, views
from web.publisher.readonly import copy_store, open_readonly, runs_in_progress

ROOT = Path(__file__).resolve().parents[2]
LIVE_STORE = ROOT / "data" / "store" / "live.sqlite"
DEFAULT_OUT = ROOT / "web" / ".data" / "snapshot"
PUBLISHER_VERSION = "1"
KEEP_SNAPSHOTS = 24
STAMP = re.compile(r"\d{8}T\d{6}Z")


class Skipped(Exception):
    pass


def prune(directory, current, keep=KEEP_SNAPSHOTS):
    """Deletes all but the newest `keep` snapshot directories, never `current`. Only directories named like a
    snapshot stamp are touched."""
    stamps = sorted(p for p in Path(directory).iterdir() if p.is_dir() and STAMP.fullmatch(p.name))
    for old in stamps[:-keep] if keep > 0 else stamps:
        if old.name != current:
            shutil.rmtree(old, ignore_errors=True)


def _dump(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(store, now, protocol):
    """{relative path: document} for every snapshot file, all checked against the contract."""
    snap = views._Snapshot(store, protocol)
    model_versions = set(snap.kinds)
    files = {}
    index = views.match_index(snap, now)
    contract.check_index(index, model_versions)
    files["matches/index.json"] = index
    for uid in snap.matches:
        page = views.match_page(snap, uid, now)
        contract.check_match_page(page, model_versions)
        files[f"matches/{uid}.json"] = page
    for name, document in (("research/track-record.json", views.track_record(snap, now)),
                           ("models.json", views.models_view(snap)), ("status.json", views.status_view(snap, now)),
                           ("ledger/recent.json", views.ledger_recent(snap)),
                           ("archive.json", views.archive(snap, now)), ("players.json", views.players_view(snap, now))):
        contract.check_any(document)
        files[name] = document
    return files


def publish(store_path=LIVE_STORE, out=DEFAULT_OUT, now=None, allow_replay=False, protocol=None):
    now = utc(now) if now else datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    protocol = protocol or prospective.load_protocol()
    live = open_readonly(store_path)
    try:
        if live.mode != "live" and not allow_replay:
            raise SystemExit(f"{Path(store_path).name} is a {live.mode} store; the website publishes live stores only")
        running = runs_in_progress(live)
        if running:
            raise Skipped(f"{len(running)} run(s) in progress; nothing published (the next publish will catch up)")
    finally:
        live.close()
    work = Path(tempfile.mkdtemp(prefix="matchup-dna-publish-"))
    try:
        copy = copy_store(store_path, work / "copy.sqlite")
        store = open_readonly(copy)
        try:
            if runs_in_progress(store):
                raise Skipped("a run started while the store was being copied; nothing published")
            files = build(store, now, protocol)
            head = store.last_hash()
            count = len(store.predictions())
        finally:
            store.close()
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        version_dir = Path(out) / "v1" / stamp
        if version_dir.exists():
            raise SystemExit(f"{version_dir.name} already exists; publish again in a second")
        hashes = {name: _dump(version_dir / name, document) for name, document in sorted(files.items())}
        manifest = {"schema_version": views.SCHEMA_VERSION, "publisher_version": PUBLISHER_VERSION,
                    "generated_at": iso(now), "snapshot": stamp, "files": hashes,
                    "ledger": {"count": count, "head": head},
                    "code_matches_protocol": prospective.code_sha256() == protocol["code_sha256"]}
        contract.check_any(manifest)
        staging = Path(out) / "v1" / "manifest.json.tmp"
        _dump(staging, manifest)
        os.replace(staging, Path(out) / "v1" / "manifest.json")
        prune(Path(out) / "v1", stamp)
        return manifest
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, default=LIVE_STORE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--allow-replay", action="store_true", help="development only: publish a replay store")
    args = parser.parse_args(argv)
    try:
        manifest = publish(args.store, args.out, allow_replay=args.allow_replay)
    except Skipped as skipped:
        print(f"skipped: {skipped}")
        return 0
    print(f"published snapshot {manifest['snapshot']}: {len(manifest['files'])} files, "
          f"{manifest['ledger']['count']} forecasts in the ledger, code matches P1 protocol: "
          f"{manifest['code_matches_protocol']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
