# Matchup DNA — Phase 6 Audit, Plan and Architecture

**Date:** 8 November 2026. **Branch:** `phase4-data-correction`, at `4edca9d` (the Phase 5 results commit).
**Scope:** Phase 6 turns the research system into a forecasting system. It issues and stores both frozen Phase 4 models' forecasts before matches are played. It attaches results without altering those forecasts, and it evaluates them under a protocol fixed in advance.

This document has seven parts:
1. what the repository could and could not do at the start;
2. the plan and its acceptance criteria;
3. the architecture that was built;
4. the live-data provider decision;
5. how the website will expose the two models;
6. the research agenda for new features;
7. market research.

The results, verification and open issues are in [Phase 6 - Production Forecasting Report.md](Phase%206%20-%20Production%20Forecasting%20Report.md).

---

## 1. Repository audit

Every "works" below was checked in this session, not assumed from a report.

### What exists and works

| Component | State on 8 November 2026 | How it was checked |
|---|---|---|
| Sackmann history | 361,571 tour-level matches through the week of 25 May 2026 | Loaded (`phase4_features.backfilled_matches`, 28 s) |
| TennisIsMyLife (TML) | 2025–2026 season files plus the two "ongoing" files, snapshot of 5 November 2026; point counts | Loaded; 2,631 rows for editions from 1 June 2026, ongoing editions included |
| TennisData.app (TD) | 2025–2026 season files, snapshot of 5 November 2026 (file times 12:31 local). 49 rows still `SCHEDULED` (13 main-draw tour rows) | Status table read: `FINISHED` with `status_extra` FINISHED, RETIRED, WALKOVER, CANCELED, AWARDED; or `SCHEDULED` |
| Valuebetennis odds | 2021–October 2026, opening and closing prices, **no timestamps** | Phase 5 audit; not used here |
| Feature code | Phase 3 `features.build_rows`, Phase 4 `phase4_features.augment`, `profiles`, `round_aware` | Imported unchanged by the new engine; the engine tests compare against them |
| Identity and duplicate rules | `heldout.assemble` version 2 (erratum 1): three linking passes, one identity per person, build-stopping checks | 23 regression tests in `tests/test_heldout.py` pass |
| Frozen protocols | Phase 3, Phase 4 (+ amendment 1, erratum 1), Phase 5; `phase4_correction check` hashes its fix files | Untouched; no existing file was edited |
| Tests | **258 tests passed in 73 s** at the start of the session | `python -m unittest discover -s tests` |

### What was missing (the Phase 6 gaps)

| Gap | Why it mattered |
|---|---|
| **No saved model.** Every frozen command refitted P4-refit and R0 from code; no coefficients existed anywhere | Production inference would have meant refitting on every run, with no artifact to version or hash |
| **No path from an unplayed fixture to a feature row.** Every feature is built by a batch replay of *completed* matches | Nothing could produce a forecast for a match that has not happened |
| **The provider assembly covered only finished editions.** `heldout.window_rows` dropped ongoing editions by design | A live system must forecast while tournaments are running, and R0 needs the edition's completed rounds |
| **No canonical match or player record across runs**, and no store | Re-running a job could not be shown to be idempotent, and a forecast could not be shown to predate its match |
| **No prediction archive**, no immutability, no timestamps beyond file dates | The brief's §34 archive did not exist |
| **No prospective protocol or evaluation code** | Future outcomes could not be scored without the risk of choosing the rules afterwards |
| **No live provider tested.** Phase 0 recorded HTTP 401s from both candidates without credentials; none are present in this environment either | The provider decision cannot be closed (part 4) |
| `predict.py` is an empty placeholder; README's build order still says Phase 6 = "PostgreSQL storage and a Python API" | This brief re-scopes Phase 6 to production forecasting. A database is introduced (SQLite), and the API is a function layer. A hosted PostgreSQL and HTTP server come later |

### Readiness verdict

The research code was ready to be **reused** but not to be **run forward**. Its definitions are exact and tested, and the frozen models can be reproduced. But it could not:
- issue a forecast for an unplayed match;
- store one immutably;
- tell which forecasts were made in time.

Phase 6 builds those missing pieces around the research code without changing it.

---

## 2. Plan and acceptance criteria

The plan was prioritized for a complete vertical slice (fixture → forecast → stored → result → evaluation) before any breadth. Status as of the end of this session:

| # | Priority | Deliverable | Acceptance criterion | Status |
|---|---|---|---|---|
| 1 | P0 | Frozen model artifacts | Model A reproduces all 2,453 saved corrected held-out predictions (≤ the file's 5×10⁻⁷ rounding). Model B reproduces the published R0 log loss 0.5993 on 1,275 matches, and its reference 0.6052. Serialized = fitted, exactly | **Met** (largest difference 5×10⁻⁷; R0 0.5993 / 0.6052; serialized difference 0.0) |
| 2 | P0 | Fixture → feature row | For a match forecast before it is played, every model input equals the research dataset's row for that match. Proven on synthetic data, and on real replayed days once the rank source is controlled | **Met**: tests to 12 decimals; real rehearsal in the report |
| 3 | P0 | No leakage | The placeholder's result, later matches, other editions in the same week, and other fixtures in the same round each leave a fixture's row unchanged | **Met** (tests) |
| 4 | P0 | One real match, one player | Erratum 1's failure modes are refused in production: a cross-provider duplicate, a split identity, a crosswalk naming the wrong man (Vallejo), and a fixture tied to last week's meeting | **Met** (tests). Flagged identities are withheld, not forecast |
| 5 | P0 | Immutable, timestamped storage | Predictions and results cannot be updated or deleted. Each prediction carries its issue time, model version and artifact hash, full input snapshot and code hash. A hash chain plus a prefix-checked ledger detects tampering | **Met** (tests) |
| 6 | P0 | Idempotent jobs | Re-running a forecast or settlement with the same data writes nothing new. Changed inputs append a superseding forecast and keep the original | **Met** (tests) |
| 7 | P0 | Eligibility | Model B is issued only when its earlier-round information exists. It is never filled in from Model A. Late, deferred and identity-flagged fixtures get a recorded reason and no number | **Met** (tests; real run) |
| 8 | P0 | Settlement and evaluation | Results come from each source separately. A disagreement is a conflict, and that match is not scored. Only completed best-of-3/5 matches are scored | **Met** (tests) |
| 9 | P0 | Prospective protocol | Frozen before any counted forecast. It fixes models, code hash, window, counting rule, metrics, slices, clusters, reporting rule and forbidden decisions | **Ready, not yet frozen**: the contents are fixed in `prospective.protocol_contents`; `protocol freeze` writes `experiments/phase6_prospective_protocol.json` after you commit the code, so it records a clean commit |
| 10 | P1 | End-to-end on real data | A live run on the 5 November snapshot issues genuine pre-match forecasts and refuses late ones. A replay of past days matches the research path | **Met** (report) |
| 11 | P1 | Website interface | JSON payloads for upcoming forecasts (both models, with reasons), match history, track record, models and status. No forecasting logic in the payload layer | **Met** (`forecasting/api.py`) |
| 12 | P1 | Automatic data source | Real responses read and parsed; results and fixtures linked to the canonical history without duplicates; identities checked | **Met with ESPN scoreboards** (part 4). The two paid-tier APIs were not tested (no credentials); a probe command is ready |
| 13 | P2 | Scheduled operation | The daily job runs without manual steps (fetch, forecast, settle, ledger) | **Job ready, scheduler not set up**: `python -m matchup_dna.forecasting daily` does all four steps; a scheduler (Windows Task Scheduler or GitHub Actions) still has to call it |
| 14 | P2 | Hosted database and HTTP API | PostgreSQL schema migration, FastAPI wrapper of `api.py` | **Not started** (deliberately: part 3 explains why SQLite comes first) |
| 15 | P3 | Market price capture | Prospective prices with their own collection timestamps, under a separate protocol | **Designed only** (part 7) |

---

## 3. Architecture

### Layers

```
 provider snapshot or response
        │  providers.py    → MatchRecord (provider-neutral; event / published / retrieved / ingested times)
        ▼
 source_records (store, append-only, content-hashed)
        │
        ▼  history.py      Sackmann (< 1 Jun 2026) + TML + TD, Phase 4 erratum 1 rules
 canonical history ───────────── one record per real match, one identity per real person
 + pending fixtures ──────────── identity status, edition, "already played" and duplicate checks
        │
        ▼  engine.py       placeholder replay → the research feature row (features.py, phase4_features.py)
 feature row per fixture
        │                  eligibility: Model A rules; Model B adds round-aware rules
        ▼  frozen_models.py (artifacts in models/, hashed)
 probability + input snapshot + contributions
        │
        ▼  store.py / pipeline.py
 predictions (append-only, hash-chained) ── ledger forecasts/ledger.jsonl
        │
        ▼  pipeline.settle  (later snapshot)          ▼  api.py
 outcomes (append-only, per source)              website payloads (read-only)
        │
        ▼  prospective.py, under experiments/phase6_prospective_protocol.json
 evaluation (interim monitor; one final P1 run)
```

| Module | Responsibility | Reuses |
|---|---|---|
| `forecasting/records.py` | `MatchRecord`, UTC-only time handling, canonical JSON and hashing | — |
| `forecasting/providers.py` | TD snapshot adapter, recorded-JSON adapter, authenticated HTTP probe (archives raw responses, does not parse) | `tennisdata`, `heldout.td_score` |
| `forecasting/espn.py` | ESPN scoreboards: archived fetch, parse, linking to the history, evidence (player ids, editions, main-tour events), gap results, fixtures | `heldout.names_compatible`, `merge.assert_unique` |
| `forecasting/history.py` | Canonical history and fixtures as of a snapshot, identity status, edition mapping, "still playing elsewhere" | `heldout` v2 linking and identity functions, `merge.combine`, `tml_match`, `td_match` |
| `forecasting/frozen_models.py` | One-time export and byte-for-byte check of the two models; `FrozenModel` inference | `phase4_experiment.provider_period`, `fit_final_models`, `phase4_model.design` |
| `forecasting/engine.py` | Placeholder replay, eligibility, prediction content, reproduction | `features.build_rows`, `phase4_features.augment`, `round_aware` |
| `forecasting/store.py` | SQLite schema, append-only triggers, hash chain, ledger | — |
| `forecasting/pipeline.py` | `forecast`, `settle`, `replay_sources` | all of the above |
| `forecasting/prospective.py` | Protocol freeze, counting rules, metrics, paired comparison, slices | `uncertainty`, `model.fit_logistic` |
| `forecasting/api.py` | Website payloads, `verify_store` | — |
| `forecasting/rehearsal.py` | Replays past days into a replay store and compares with the research path | `phase4_experiment.provider_period` |

The rule throughout: **the production path imports the research code; it never re-implements a feature.** The engine computes a fixture's features by running the unchanged Phase 3 and 4 replays, so there is no second definition that could drift.

### How an unplayed fixture gets its features

Every feature is computed in a chronological replay, from strictly earlier information:

| Feature | Uses |
|---|---|
| Elo, surface Elo | Start-of-week ratings: matches dated before the edition's date |
| Form, days since last match | Earlier tournament dates only |
| Serve-return profiles | Replayed one date at a time; a date's matches are added after its rows |
| Round-aware Elo shifts, earlier-round share of games (R0 only) | Strictly earlier rounds of the same edition |
| Rank | The rank on the match record (here: TD's pre-match rank) |

So the fixture is appended to the history as a placeholder match with an arbitrary result, and the replay produces its row:
- Player A is chosen by a hash of the match id and the two player ids, never by the result.
- The placeholder's result could only reach matches dated later. Each replay therefore holds the history up to one edition date, plus that date's fixtures, and nothing after.

Tests prove the claims: swapping the placeholder's result changes nothing, and neither do later matches, other same-week editions, or the other fixtures of the round. A semifinal's production row equals the research row computed after the whole tournament.

### Identity, editions and matches

- **Players.** A fixture player's canonical id comes from the version-2 identity rules. Each player also gets an identity status:

  | Status | Meaning | Forecast? |
  |---|---|---|
  | `verified` | Crosswalk, the linked TML player, or a unique exact full name | Yes |
  | `new_player` | Provider-only id, and no active Sackmann player's name is compatible | Yes |
  | `ambiguous` | Provider-only id, but an existing player's name is compatible: erratum 1's split-identity risk | No |
  | `conflict` | The evidence disagrees: the Vallejo case | No |

  `ambiguous` and `conflict` players are listed, not forecast. `forecasts/identity_reviews.csv` lets a person **confirm** an identity the rules resolved; a review can never change it, because the history was built with that id.
- **Editions.** An edition's stable id is tour, first main-draw day and event name, the way TD lists it. `edition_aliases` maps provider edition keys (TD's key, the TML tourney id) to it.
- **Matches.** `match_uid` is a hash of tour, edition, round and the two canonical ids, ordered. It is unique in the database. `match_aliases` binds each provider match id to one `match_uid`, so a re-listed fixture keeps its match. If a provider id later resolves to different players, the fixture is not forecast, and the change shows up in `identity_drift`.
- **Already played.** A TD fixture that TML already reports as played is never forecast. Scheduled rows are **not** linked by the research name-and-19-day window, because that window can tie a fixture to last week's meeting of the same players (tested).

### Time

Every record carries four times (brief §17):
- **event time:** the scheduled start;
- **provider publication time:** if the provider states one; TD's files do not;
- **retrieval time:** the snapshot's file time, or an HTTP response's;
- **ingestion time:** the run's time. That is when the record became eligible for use.

All times are UTC ISO 8601 with a `Z`; a time without a timezone is refused.

A forecast is issued only if both hold:
- it is at least **30 minutes before the scheduled start**;
- the issue time is within five minutes of the real clock in a **live** store. A past or future issue time is a replay, and only a replay store accepts one.

### Immutability and reproduction

| Guarantee | Mechanism |
|---|---|
| A forecast cannot change | SQLite triggers abort any `UPDATE` or `DELETE` on predictions, results, records, decisions, identity observations, editions, matches and model versions |
| Tampering is detectable | `prediction_id` = SHA-256 of the full canonical content. `record_hash` chains every prediction to the one before. `verify` recomputes all of it |
| Outside evidence | `forecasts/ledger.jsonl` is rewritten only if the existing file is an exact prefix of the new chain. A committed ledger is therefore a public timestamp |
| A forecast can be reproduced | Each prediction stores its full feature row, the model inputs and contributions, the model artifact hash, the history digest (SHA-256 over every match the replay read) and the code hash. `verify` recomputes every probability from its own snapshot with the stored artifact and requires exact equality |
| Idempotency | Unique keys on records, editions, matches, aliases, decisions and outcomes. A prediction is unique on (match, model, input hash) |
| Model versions cannot drift | A version name can be registered with only one artifact hash. A changed model needs a new name |
| Live vs replay | A store's mode is fixed at creation. Rehearsals can never enter the live record |

### Why SQLite now and PostgreSQL later

The brief (§39, §49) asks for a relational store and for complexity to follow need. One writer runs a daily job, and the site updates periodically. SQLite is a standard-library file with real constraints and triggers, and it needs no server or credentials. The schema uses only portable SQL: keys, foreign keys, uniqueness, `ON CONFLICT DO NOTHING`. Two pieces change when the site is hosted:
- the triggers become PostgreSQL rules or revoked `UPDATE`/`DELETE` privileges;
- `api.py` is wrapped by FastAPI.

---

## 4. The automatic data source

**Decision: ESPN's public scoreboards supply fixtures and recent results; TML and TennisData.app file snapshots remain the history up to their snapshot date.** ESPN was checked on real responses (8 November 2026; 2025 and 2026 archived), not on documentation.

| Criterion | ESPN scoreboards | TennisData.app (file snapshots) | TennisIsMyLife (files) | Live Tennis API / SportsAPI365 |
|---|---|---|---|---|
| ATP and WTA main tour | **Verified**; WTA 125 and ITF events appear too and are filtered by evidence (below) | **Verified** | **Verified** | Not tested (no credentials) |
| Upcoming fixtures | **Verified**: about 1–3 days ahead, UTC start times; a placeholder time when `timeValid` is false | **Verified**, about a day ahead | No | Not tested |
| Completed results | **Verified**: set scores with each player's tiebreak points, winner flag, retirements and walkovers | **Verified** | **Verified**, with point counts | Not tested |
| Statistics | None in the scoreboard | Percentages only | Point counts | Not tested |
| Ids | Competition id per match (stable from scheduled to final), athlete ids, event id per season, tournament id across seasons | Tour + match id; player ids | Tourney id, player ids | Not tested |
| Rounds | "Round 1…n", Quarterfinal, Semifinal, Final, "Group Stage"; mapped by counting back from the quarterfinal | Mapped labels; blank for team events | Sackmann labels | Not tested |
| Ranking | **Not given**: the per-player number is the tournament seed (see below) | Pre-match rank | Rank at the match | Not tested |
| Freshness | Updated during play. On 8 November it already showed the WTA Finals draw change (Noskova–Kostyuk at 20:10 UTC) that the 5 November TD snapshot still listed as Rybakina–Noskova | Snapshot date | Snapshot date | Not tested |
| Cost and limits | One request per tour per day; the archive refreshes the last 14 days and the next 3 (about 36 requests a day), one per second | Manual download | Manual download | 50–100 calls/day free |

**What was found on the real responses, and how it is handled:**

1. **The seed is not the ranking.** ESPN's per-player "curatedRank" is the tournament seed (Stockholm 2026: Michelsen 6, unseeded players blank). A first trial read it as a rank, and unseeded players became "unranked", which pushed several forecasts above 90%. ESPN records now carry the seed separately and never a rank. A fixture takes each player's **latest rank printed on a history match** (Sackmann, TML or TD) before the match day, at most a year old, with that date stored in the forecast. Phase 4's rehearsal measured the rank-source effect at about 0.001 in probability.
2. **Placeholder times.** Matches without a confirmed time carry midnight US Eastern with `timeValid: false`. They get no start time and are deferred until ESPN publishes one, because a forecast must provably precede the start.
3. **Joint events.** The ATP feed also carries the women's draw at combined events, so tour is taken from the draw ("mens-singles", "womens-singles") and each competition is read once.
4. **Which events count.** ESPN has no tour-tier field. An event counts as main tour only with evidence:
   - its matches link to TML, TD or Sackmann main-draw matches; or
   - its ESPN tournament id did in an earlier edition, so the 2025 archive covers events whose 2026 edition has not yet produced a result (the WTA Finals, Stockholm).

   Level and surface come from the same evidence. On 8 November, 1,225 ESPN records (125s, ITF events) had no such evidence and were left out.
5. **One record per real match.** An ESPN result is linked to a history match when tour and round agree, the day is within −3 to +16 days of the history match's tournament date, and both players' names fit in exactly one orientation, with a unique candidate in both directions. On 8 November, 9,658 of 13,780 ESPN records linked. ESPN results are added only for matches the history lacks:
   - a result whose canonical players already meet in the same round within three days counts as already present (29 cases);
   - a result whose names fit a history match without linking uniquely is held back for review;
   - the build stops if an addition still duplicates a history match. That stop fired once during development and exposed the case the second rule now handles.

   On 8 November, 23 results from 5–8 November were added (Paris 8, Hong Kong 7, Chennai 6, Stockholm first round 2), filling the gap after the file snapshot.
6. **Identities.** An ESPN player is:
   - `verified` when linked ESPN matches always point to one history player, or when the full name is a unique exact name in the history;
   - `new_player` or `ambiguous` otherwise, by the same compatible-name check as TD players;
   - `conflict` when the evidence disagrees.

   `forecasts/identity_aliases.csv` lets a person record a checked ESPN-id → player mapping (for example "Catherine McNally", whose ESPN name never matches the history's spelling). On 8 November, 25 ESPN results were held back for an unverified identity.
7. **Traceability.** Every response is archived under `data/raw/espn/` with its retrieval time and SHA-256 before parsing. Parses are cached beside it, keyed by that hash and the parser version, and a run reads only responses retrieved at or before its own time.

**The paid APIs** (Live Tennis API, SportsAPI365) remain untested, for lack of credentials. `python -m matchup_dna.forecasting probe` is kept for them.

## 5. How the website will expose both models

`forecasting/api.py` is the contract; a future FastAPI app wraps its functions one-to-one, and the website never calls a data provider.

**`upcoming(store, now)`.** One entry per pending match:

```json
{
  "match_uid": "M-…", "tour": "WTA", "tournament": "Finals - Indian Wells WTA", "round": "unknown",
  "surface": "Hard", "scheduled_start": "2026-11-08T21:30:00Z", "best_of": 3,
  "players": [{"player_id": 221103, "name": "Gauff C.", "rank": 4, "identity": "verified"}, {...}],
  "forecasts": {
    "tournament_start": {"available": true, "model_version": "phase4-ts-v1", "issued_at": "…Z",
                         "prediction_id": "…", "probabilities": {"221103": 0.5187, "202468": 0.4813},
                         "explanation": {"terms": [{"feature": "surface_elo_logit", "log_odds": 0.115}, …]},
                         "earlier_versions": 0},
    "round_aware": {"available": false, "model_version": "phase4-r0-v1",
                    "reason": "round unknown: R0 covers knockout rounds only", "decision": "ineligible"}
  },
  "data": {"fixture_retrieved_at": "2026-11-05T17:31:00Z", "provider": "tennisdata_app"}
}
```

Rules the payload enforces, and the page must keep:

1. **Tournament-start probability for every eligible match.** For a fixture that cannot be forecast, the reason is shown: identity under review, inputs incomplete (deferred), or too late.
2. **Round-aware probability only when R0 issued one.** When it did not, the toggle shows the reason (first match of both players, round robin, earlier rounds incomplete) and **no number**. Model A's number is never shown under Model B's label.
3. **The toggle compares two forecasts of the same match, made from nested information.** The page should say: "The round-aware update uses everything the tournament-start forecast uses, plus the results of this tournament's completed earlier rounds." `MODEL_INFO` in `api.py` holds the exact wording of what each model does and does not use. The two are never presented as independent models.
4. **Every number shows its model version and issue time.** Superseded versions are counted (`earlier_versions`) and are reachable through `match_detail`.
5. **History cannot be rewritten.** The track record and calibration pages read `track_record(store)`: the first counted forecast for each match, joined to the settled result. A page should link the ledger file and its latest committed hash.
6. **Freshness.** `status(store)` gives the last successful forecast and settlement runs, failed runs, conflicts and identity changes. The site must show "last updated", and must say so when the feed is stale (brief §15, §47).
7. **Forecast availability is not live-score availability.** R0 is a between-round model. The site may show a live score from a provider, but no live probability exists until Phase 9.

---

## 6. Model-improvement research agenda

The frozen models stay the production baselines. A new feature enters only through a new, pre-registered experiment. It must beat Phase 4 or R0 on development data, then be confirmed on a window that **starts after its own freeze**: never on P1, which is reserved for the frozen models. LightGBM stays a research benchmark; Phase 4 found it no better than the logistic model with the same inputs.

For each candidate, the six questions the brief asks:

| Candidate | 1. Information added | 2. Why Elo, rank and serve-return may miss it | 3. Available before the match? | 4. Enough reliable data? | 5. Test | 6. Negative result |
|---|---|---|---|---|---|---|
| **Challenger and ITF history** | Results and serve-return for players with few tour-level matches | Phase 4: players with under 10 matches of statistics gain only −0.0012 (n.s.). Their profiles are mostly the tour average, and Elo starts at 1500 | Yes, if dated by match | TD has Challenger and WTA 125 main draws for 2025–2026 (13,863 / 3,576 rows), without point totals. Sackmann's Challenger files are not loaded. **Not yet audited** | Pre-registered: Phase 4 model + a Challenger-informed Elo and profile prior. Development on 2025 to May 2026; score only on matches where a player has under 20 tour-level matches | No gain on the low-history slice beyond two clustered SEs, or worse calibration there |
| **Better shrinkage for short histories** | A prior centred on a player's level (rank band, Challenger record) instead of the tour mean | The Phase 4 prior is the tour average for everyone | Yes | Yes (existing data) | Prior means by rank band, chosen without outcomes (next-match serve-points loss, as Phase 4 did), then the keep rule | Serve-points loss not better than the tour-mean prior |
| **Withdrawals and fitness** | Recent retirements, walkovers, medical time-outs | Elo ignores retirements and walkovers by design (not rated) | Only if time-stamped. A retirement is known after its match; a withdrawal announcement often only hours before | TD has statuses with timestamps; announcements have no source yet | "Retired or gave a walkover in the last 30 days" indicator, tournament-start track | Coefficient interval includes 0, or the keep rule fails |
| **Rest and travel** | Days since last match day, time-zone shifts | "Days since last match" is by tournament date. Phase 4 could not study rest because no source had match days before 2025 | Yes (TD timestamps, TML round dates) | Only from 2025: about 2 seasons | Rest days in the round-aware track (A5 deferred it for lack of data); development 2025, evaluation after its freeze | No gain, or a gain confined to one tour without replication |
| **Court and conditions** | Indoor/outdoor, altitude, court pace | Surface is coarse. TML has `indoor`; pace is not in any source | Indoor yes; pace not reliably | Indoor yes; pace no | Indoor × serve-return interaction against the Phase 4 model | Phase 4's surface interactions (C3) already failed; failing again ends the line |
| **Tactical matchup detail** | Style interactions (e.g. return depth against serve patterns) | Phase 4's interactions (C1–C4) added nothing | Only for charted matches | Match Charting Project covers a minority of matches, non-randomly chosen | Only as a descriptive study unless coverage is adequate | Not proposed as a model feature at present |

The two with the clearest gap and data are **Challenger history** and **level-aware shrinkage**. Both target the low-history players where Phase 4 adds least. The other candidates wait on data that is either time-stamped too poorly or too sparse.

---

## 7. Market research

Phase 5 stands. The opening market beats Phase 4 by 0.024 log loss per match; the model adds no information to the price; and the paper rule loses money. Phase 6 adds no betting recommendation and makes no claim of positive expected value. The market remains the benchmark any future model is compared with.

If prices are collected prospectively:
- **Store each price as its own record:** provider, bookmaker, market, the two prices, the provider's quote time if given, and our retrieval time. Use an append-only table like `source_records`.
- **Classify each price by its retrieval time** relative to the forecast's issue time and the match start:
  - "latest before issue" is the only price a decision at issue time could have used;
  - "opening" is the earliest price retrieved;
  - "closing" is the last retrieved before the start.
- **Never treat a historical opening price without a timestamp as executable** at a given decision time. That was Phase 5's stated limit.
- **Use a separate protocol.** Any market comparison on P1 forecasts gets its own frozen protocol, written before it is run, with the frozen blend weights and margin method of Phase 5. It is never folded into P1.
