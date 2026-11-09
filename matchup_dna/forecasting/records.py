"""Provider-neutral match records.

Every provider adapter turns its rows or responses into MatchRecord objects, so nothing downstream depends on one
vendor's field names. A record carries four separate times (brief, section 17):

    event_time      when the match is scheduled to start, or started (the provider's value; UTC)
    published_at    when the provider says it last changed the record, if it says so (often unknown)
    retrieved_at    when this system received the provider's data (a file snapshot's time, or an HTTP response's)
    ingested_at     when the record was stored; set by the store, and the earliest moment the record may be used
                    by a forecast ("eligible for prediction")

A forecast issued at time t may use a record only if its ingested_at is at or before t. A result is never used
before it was retrieved.
"""
import datetime
import hashlib
import json
from dataclasses import asdict, dataclass, field

UTC = datetime.timezone.utc

# Canonical statuses. A provider's own labels are mapped to these by its adapter, and the raw label is kept.
SCHEDULED = "scheduled"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"      # played to the end
RETIRED = "retired"          # one player retired during the match
WALKOVER = "walkover"        # never started; one player advanced
CANCELLED = "cancelled"      # cancelled, postponed without a result, or awarded without play
UNKNOWN = "unknown"
STATUSES = (SCHEDULED, IN_PROGRESS, COMPLETED, RETIRED, WALKOVER, CANCELLED, UNKNOWN)
FINAL_STATUSES = (COMPLETED, RETIRED, WALKOVER, CANCELLED)

ROUNDS = ("R128", "R64", "R32", "R16", "QF", "SF", "F", "RR", "unknown")


def utc(value):
    """A timezone-aware UTC datetime from a datetime, an ISO string, or seconds since 1970; None stays None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            raise ValueError(f"naive datetime {value!r}: every time must carry a timezone")
        return value.astimezone(UTC)
    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(value, UTC)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"time {value!r} has no timezone")
    return parsed.astimezone(UTC)


def iso(value):
    """ISO 8601 in UTC with a Z, to the second; None stays None."""
    value = utc(value)
    return None if value is None else value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value):
    """The one JSON spelling used for every hash: sorted keys, no spaces, floats as Python writes them (exact)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MatchRecord:
    """One provider's view of one singles match at one moment.

    Players are the provider's ids and names: identity is decided later, by the canonical layer, never here.
    `home` and `away` are the provider's sides, not a prediction order. Results (winner_side, score) are present
    only when the status says the match is over.
    """
    provider: str
    provider_match_id: str
    tour: str                      # "ATP" or "WTA"
    circuit: str                   # "tour", "challenger", "itf"
    tournament: str                # the provider's tournament name
    round: str                     # one of ROUNDS
    home_id: str
    home_name: str
    away_id: str
    away_name: str
    status: str                    # one of STATUSES
    retrieved_at: str              # ISO UTC
    event_time: str = None         # ISO UTC
    published_at: str = None       # ISO UTC, if the provider gives it
    surface: str = None            # "Hard", "Clay", "Grass", "Carpet" or None
    best_of: int = None
    indoor: bool = None
    qualifying: bool = False
    wheelchair: bool = False
    home_rank: int = None
    away_rank: int = None
    winner_side: str = None        # "home" or "away", only for final statuses with a winner
    score: str = None              # Sackmann-style score from the winner's side, e.g. "6-4 3-6 7-5" or "6-2 2-1 RET"
    raw_status: str = ""
    raw_sha256: str = ""           # hash of the provider's raw row or payload item
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.tour not in ("ATP", "WTA"):
            raise ValueError(f"tour must be ATP or WTA, not {self.tour!r}")
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}")
        if self.round not in ROUNDS:
            raise ValueError(f"unknown round {self.round!r}")
        if self.home_id == self.away_id:
            raise ValueError(f"{self.provider} {self.provider_match_id}: both sides are the same player")
        for name in ("retrieved_at", "event_time", "published_at"):
            value = getattr(self, name)
            if value is not None and iso(value) != value:
                raise ValueError(f"{name} must be ISO UTC with a Z, got {value!r}")
        if self.winner_side is not None and self.status not in (COMPLETED, RETIRED, WALKOVER):
            raise ValueError(f"{self.provider_match_id}: a winner on a match with status {self.status}")
        if self.status in (COMPLETED, RETIRED, WALKOVER) and self.winner_side not in ("home", "away"):
            raise ValueError(f"{self.provider_match_id}: status {self.status} needs a winner side")

    @property
    def key(self):
        """A provider record is identified by provider, tour and the provider's match id (TennisData.app reuses a
        match id across its ATP and WTA files)."""
        return self.provider, self.tour, self.provider_match_id

    def payload(self):
        return asdict(self)

    def content_sha256(self):
        """Hash of everything except the retrieval time: two snapshots that say the same thing hash the same."""
        content = {k: v for k, v in asdict(self).items() if k != "retrieved_at"}
        return sha256_text(canonical_json(content))
