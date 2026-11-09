"""Provider adapters. Each turns one source's rows or responses into records.MatchRecord objects.

    TennisDataSnapshot   TennisData.app season CSV files saved at one moment (the fixtures and results source
                         used by this phase; verified on real files)
    RecordedJson         MatchRecords saved as JSON: tests, and fixtures typed in by hand from an official order of play
    HttpProbe            one authenticated GET to a live provider, archiving the raw response with its hash and
                         retrieval time. It does not parse: no live provider's response has been seen yet (no
                         credentials were available, Phase 0 and Phase 6 reports), and a parser written from
                         documentation alone would claim a verification that has not happened.

Adding a provider means writing one adapter that yields MatchRecords, plus a validated player and edition mapping
(canonical.py). The prediction engine never changes for a new provider.
"""
import datetime
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from matchup_dna.forecasting import records as rec
from matchup_dna.forecasting.records import MatchRecord, iso

TD_STATUS = {"FINISHED": rec.COMPLETED, "RETIRED": rec.RETIRED, "WALKOVER": rec.WALKOVER, "CANCELED": rec.CANCELLED,
             "AWARDED": rec.CANCELLED, "SCHEDULED": rec.SCHEDULED}


def td_record(row, retrieved_at):
    """A TennisData.app row (as tennisdata.load_provider returns it, unsealed) as a MatchRecord."""
    from matchup_dna import tennisdata as td
    from matchup_dna.heldout import td_round, td_score
    from matchup_dna.load import normalize_surface
    raw = {k: v for k, v in row.items() if isinstance(v, str)}
    if row["status"] == "SCHEDULED":
        status = rec.SCHEDULED
    else:
        status = TD_STATUS.get(row.get("status_extra", ""), rec.UNKNOWN)
    winner_side, score = None, None
    if status in (rec.COMPLETED, rec.RETIRED, rec.WALKOVER):
        score, winner_side = td_score(row)
        if winner_side is None:
            status = rec.UNKNOWN
    rank = lambda value: None if td.number(value) is None else int(td.number(value))
    return MatchRecord(
        provider="tennisdata_app", provider_match_id=row["match_id"], tour=row["tour"], circuit=row["circuit"],
        tournament=row["tournament"], round=td_round(row), home_id=row["home_id"], home_name=row["home_name"],
        away_id=row["away_id"], away_name=row["away_name"], status=status, retrieved_at=retrieved_at,
        event_time=iso(int(float(row["date_timestamp"]))) if row["date_timestamp"] else None,
        surface=normalize_surface(row["surface"]), best_of=td.best_of(row), qualifying=row["qualifying"],
        wheelchair=row["wheelchair"], home_rank=rank(row["home_rank"]), away_rank=rank(row["away_rank"]),
        winner_side=winner_side if status in (rec.COMPLETED, rec.RETIRED, rec.WALKOVER) else None, score=score,
        raw_status=f"{row['status']}/{row.get('status_extra', '')}",
        raw_sha256=hashlib.sha256(rec.canonical_json(raw).encode()).hexdigest())


def tennisdata_records(td_rows, retrieved_at, main_draw_from=None):
    """MatchRecords for main-draw tour rows (optionally only from a date), each with its file's retrieval time."""
    from matchup_dna import tennisdata as td
    found = []
    for row in td_rows:
        if not td.is_main_draw(row):
            continue
        if main_draw_from is not None and int(row["day"].strftime("%Y%m%d")) < main_draw_from:
            continue
        found.append(td_record(row, retrieved_at[row["source_file"]]))
    return found


class RecordedJson:
    """MatchRecords stored as a JSON list of their fields."""

    def __init__(self, path):
        self.path = Path(path)

    def records(self):
        return [MatchRecord(**item) for item in json.loads(self.path.read_text(encoding="utf-8"))]

    @staticmethod
    def save(path, records):
        Path(path).write_text(json.dumps([r.payload() for r in records], indent=2, sort_keys=True), encoding="utf-8")


class HttpProbe:
    """One authenticated GET, saved raw. The key is read from an environment variable and never written anywhere.

        python -m matchup_dna.forecasting probe --name sportsapi365 --url URL --header X-RapidAPI-Key \
            --key-env SPORTSAPI365_KEY [--extra-header X-RapidAPI-Host=HOST]

    The response body, status, headers and retrieval time are archived under data/raw/<name>/ (gitignored: provider
    terms limit redistribution) with the body's sha256, for the provider audit."""

    def __init__(self, name, url, header, key_env, extra_headers=None, directory=None):
        from matchup_dna.load import DATA_DIR
        self.name, self.url, self.header, self.key_env = name, url, header, key_env
        self.extra_headers = dict(extra_headers or {})
        self.directory = Path(directory) if directory else DATA_DIR / "raw" / name

    def fetch(self, timeout=30):
        key = os.environ.get(self.key_env)
        if not key:
            raise SystemExit(f"No credential: environment variable {self.key_env} is not set. Nothing was requested.")
        request = urllib.request.Request(self.url, headers={self.header: key, **self.extra_headers,
                                                            "User-Agent": "matchup-dna-research/0.6"})
        retrieved = datetime.datetime.now(datetime.timezone.utc)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, headers, body = response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as error:
            status, headers, body = error.code, dict(error.headers), error.read()
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = retrieved.strftime("%Y%m%dT%H%M%SZ")
        digest = hashlib.sha256(body).hexdigest()
        (self.directory / f"{stamp}.body").write_bytes(body)
        safe_headers = {k: v for k, v in headers.items() if k.lower() not in ("set-cookie", "authorization")}
        meta = {"url": self.url, "status": status, "retrieved_at": iso(retrieved), "body_sha256": digest,
                "bytes": len(body), "headers": safe_headers}
        (self.directory / f"{stamp}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return meta
