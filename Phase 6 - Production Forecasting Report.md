# Matchup DNA — Phase 6 Production Forecasting Report

**Status, 8 November 2026:** the forecasting engine is built, tested and verified on real data. One step remains before the prospective record starts: committing the code, then freezing the prospective protocol (see [Starting the prospective record](#starting-the-prospective-record)).
**Design:** [Phase 6 - Audit, Plan and Architecture.md](Phase%206%20-%20Audit%2C%20Plan%20and%20Architecture.md) has the repository audit, the plan with acceptance criteria, the architecture, the data source, the website interface, and the research agendas.

## Summary

- **Both frozen Phase 4 models now run forward.** The tournament-start model (P4-refit) and the round-aware model (R0) were exported once from the frozen procedure, and reproduce Phase 4's published held-out results exactly.
- **The production path computes what the research path computed.** Ten past days were replayed as if live. Every forecast matches Phase 4's research prediction for the same match to 9 decimal places, once the one intended input difference (the rank source) is controlled: 182 tournament-start and 113 round-aware forecasts.
- **Forecasts are stored before matches and cannot be changed afterwards.** Database triggers forbid edits, a hash chain detects tampering, and every forecast keeps its inputs, so it can be recomputed exactly.
- **Fixtures and recent results update without a manual download.** ESPN's scoreboards were parsed and linked to the canonical history under Phase 4 erratum 1's duplicate and identity rules. On 8 November they supplied 22 upcoming main-tour fixtures, and 23 results the file snapshots did not yet have.
- **Real data caught three problems before any official forecast existed:**
  - a stale fixture list in the file snapshot;
  - ESPN's seed being mistaken for a ranking;
  - one cross-source duplicate, stopped by the build check.
- **This is infrastructure, not a new finding about the models.** The models are unchanged, and no new accuracy claim is made. The prospective evaluation (P1) will produce the first genuinely out-of-sample results once forecasts accumulate.

## What was built

All new code is in `matchup_dna/forecasting/`. **No Phase 1–5 file, result or protocol was changed**: the Phase 4 erratum and Phase 5 protocol hash their code files, and those hashes still hold.

| Piece | What it does |
|---|---|
| `frozen_models.py`, `models/*.json` | The two models as stored numbers (coefficients, scales, preprocessing), exported once after three reproduction checks. Inference never refits |
| `engine.py` | A fixture's features computed by the unchanged Phase 3/4 replay, with the fixture as a placeholder match; eligibility for each model; the stored input snapshot |
| `history.py` | The canonical history (Sackmann, TML, TennisData.app) with ongoing tournaments, one identity per player, and pending fixtures. Checks for "already played", duplicate listings, and players still in an earlier event |
| `espn.py` | ESPN scoreboards, archived with hashes; parsing; linking to the history; evidence for events and players; gap results; fixtures |
| `store.py` | SQLite with append-only tables, hash chain, ledger |
| `pipeline.py` | `forecast`, `settle`, replay; the live-store clock rule |
| `prospective.py` | The prospective protocol, counting rules, metrics, paired comparison, slices |
| `api.py` | The website's read-only payloads; `verify_store` |
| `rehearsal.py` | Past days replayed into a replay store and compared with the research predictions |

Commands are listed in the README under Phase 6.

## Verification

### 1. The frozen models are reproduced

`models export` refits exactly as `experiments/phase4_frozen_protocol.json` specifies. That means 87,640 rated matches from 2010 to the week of 25 May 2026, with the erratum's corrected rows; the fitting rows are identical in both versions. It writes the artifacts only if all of these hold (`results/phase6/frozen_model_verification.txt`):

| Check | Result |
|---|---|
| Serialized model against the fitted model | Identical (largest difference 0.0) on 2,453 and 1,275 held-out rows |
| `phase4-ts-v1` against the 2,453 saved corrected held-out predictions | Largest difference 5×10⁻⁷, the file's 6-decimal rounding |
| `phase4-r0-v1` on 1,275 later-round held-out matches | Log loss 0.5993 (published 0.5993); reference 0.6052 (published 0.6052) |

The artifact hashes are `a34233a3…` (tournament start) and `1121f09c…` (R0). `models check` refits and requires the stored files to be reproduced byte for byte.

### 2. The production path equals the research path

**Synthetic tests:**
- A semifinal forecast before it is played gets exactly the input row the research dataset gives it after the whole tournament. Both models' probabilities agree to 12 decimals.
- Neither the placeholder's result, later results, other same-week events, nor the other fixtures of the round change a fixture's row.

**Real replay** (`python -m matchup_dna.forecasting rehearse`). Ten days from June to October 2026 were cut as a snapshot at 00:00 UTC would have held them: earlier results kept, that day's matches turned into fixtures, later rows dropped. TML rows are cut by the day of their linked TennisData.app match, because TML dates a whole round by its first day. The replay issued 217 tournament-start and 121 round-aware forecasts, which were then compared with Phase 4's corrected research predictions for the same matches:

| | Matched | Identical as issued | Identical with the research rank | Mean difference as issued |
|---|---:|---:|---:|---:|
| Tournament start | 182 | 22% | **100%** | 0.0067 (largest 0.086) |
| Round-aware R0 | 113 | 30% | **100%** | 0.0018 (largest 0.013) |

The only difference is intended:
- **What it is:** a fixture carries the rank shown before the match (TennisData.app), while the research rows used the rank TML printed on the completed match.
- **Every other input agrees:** Elo, surface Elo, rest, form, serve and return estimates, and the round-aware values are identical in every matched row.
- **The largest gap:** Merida Aguilar's two sources disagree on his rank.
- **The unpaired forecasts:** 35 forecasts did not pair with a research row (8 for R0), because the edition or player identity differs between the cut snapshot and the research assembly, or the match was not rated.

The replayed forecasts were also scored. This is **descriptive only**: Phase 4 had already seen these outcomes.
- **Tournament start:** log loss 0.6055 on 203 matches.
- **R0 against tournament start, same 113 later-round matches:** 0.5342 against 0.5461, a gap of −0.012 (95% interval −0.027 to +0.004).
- **Excluded:** 22 retirements, walkovers and cancellations.

### 3. Real-data runs on 8 November 2026

**File-snapshot run (19:23 UTC).** The 5 November TennisData.app snapshot had 13 main-draw fixtures still pending:

| Outcome | Fixtures |
|---|---:|
| Refused as too late (5–6 November starts) | 10 |
| Refused as already played: Fils–Fritz, still "scheduled" in TennisData.app, already reported by TML | 1 |
| Forecast: the two WTA Finals matches that evening | 2 |

The two forecasts are kept as a **pilot**: issued by uncommitted code before any protocol, and never pooled with P1. They are stored in `data/store/pilot_2026-11-08.sqlite`, with their ledger in `forecasts/pilot_2026-11-08_ledger.jsonl`; both reproduce exactly.

ESPN showed that the first of them (Rybakina–Noskova) was not on that evening's schedule: the draw had changed after the snapshot, and the 20:10 UTC match was Noskova–Kostyuk. That forecast will probably never be settled. It is the clearest evidence that a file snapshot goes stale within days.

**ESPN run.** The archive holds the 2025 and 2026 scoreboards, every third day (one response lists every match of every event running that day), plus every day from 25 October to 11 November: 13,780 main-draw singles records.

| Step | Count |
|---|---:|
| Linked to a history match (tour, round, date window, both names, unique in both directions) | 9,658 |
| Results already in the history | 2,479 |
| … by the same canonical players, round and edition when names did not link | 29 |
| **Results added** (5–8 November: Paris 8, Hong Kong 7, Chennai 6, Stockholm 2) | **23** |
| Results held back: identity not verified (mostly "Catherine McNally", whose ESPN spelling never matches) | 25 |
| Records outside the main tour (WTA 125, ITF; no evidence) | 1,225 |
| Pending fixtures (WTA Finals, Chennai final, Stockholm), every player verified | 22 |

A trial forecast run on these, into a scratch store, gave the following. Every stored probability reproduced from its snapshot.

| Model | Issued | Deferred (no confirmed start time yet) | Refused as too late (in progress or played) | No R0 information |
|---|---:|---:|---:|---:|
| Tournament start | 10 | 12 | 2 | – |
| Round-aware R0 | 1 (the Chennai final) | 12 | 2 | 9 (first matches and round robins) |

### 4. Problems found on real data, and their fixes

| Problem | How it was found | Fix and guard |
|---|---|---|
| **ESPN's per-player number is the tournament seed, not the ranking.** Unseeded players looked unranked, pushing several first trial forecasts above 90% (Michelsen 92.6% over Hanfmann) | Contributions of the first ESPN trial | Seeds are kept apart and never read as ranks. A fixture uses each player's latest official rank printed on a history match (Sackmann, TML, or any TennisData.app row, Challengers included, through the validated crosswalk), at most a year old, with its date stored. After the fix: Michelsen 64.7% (ranks 35 vs 59). Tests |
| **An ESPN result whose names did not link would have been added twice** | The build-stopping uniqueness check fired on a WTA R16 | Same canonical players, round and edition within three days count as already present (the erratum 1 rule); the uniqueness check stays as the last guard. Test |
| **A result row could be silently dropped.** `INSERT OR IGNORE` also discards rows that break NOT NULL | End-to-end test: a TML result without a retrieval time vanished | Every insert now skips only true duplicates; a result without a retrieval time is refused. Tests |
| **A replay could see results not yet played.** TML dates a round by its first day | First rehearsal: 20 fixtures wrongly "already played" | Replay cuts TML rows by the linked TennisData.app match day |
| **A fixture could be tied to last week's meeting** by the research name-and-window linking | Design review; confirmed by a test showing the research pass would link it | Scheduled rows are never linked that way; only same-round played matches in the same edition (or within three days) mark a fixture as played |
| **A live store accepted a backdated issue time** | Code review | A live forecast must be issued within five minutes of the clock; any other time belongs in a replay store. Test |
| **ESPN placeholder times** (midnight US Eastern, `timeValid: false`) | Real response | No start time until ESPN publishes one; such fixtures are deferred, never forecast on a guessed time |

### 5. Tests

**323 tests pass**: the 258 that existed at the start of the phase, plus 65 new ones in `tests/test_forecast_*.py`.

| File | Covers |
|---|---|
| `test_forecast_store.py` | Append-only tables, idempotency, supersession, chain and ledger tampering, live/replay separation, result conflicts |
| `test_forecast_engine.py` | Production row equals research row; no leakage; eligibility for both models; identity and timing guards; exact reproduction |
| `test_forecast_history.py` | Same output as the corrected research assembly; ongoing editions; already-played fixtures and repeat meetings; duplicate listings; the Vallejo conflict; possible split identities; confirm-only reviews |
| `test_forecast_espn.py` | Parsing (rounds, tiebreaks, walkovers, placeholder times, joint events, seed ≠ rank); linking; added versus held-back results; fixtures; non-main-tour events; aliases; the archive's hash and newest-response rules; ranks from Challenger rows |
| `test_forecast_pipeline.py` | End to end on synthetic provider rows: forecast, idempotent re-run, ledger, website payload (no R0 number when R0 did not forecast), settlement, conflicts, the live clock |
| `test_forecast_prospective.py` | First-counted rule, scoring only completed matches, hand-checked metrics, paired gap, protocol and final-run guards, code-hash exclusion |
| `test_forecast_records.py` | UTC-only times, impossible records refused, TennisData.app status mapping |

## The prospective evaluation (P1)

The protocol's contents are fixed in `prospective.protocol_contents`; `protocol freeze` writes them to `experiments/phase6_prospective_protocol.json` and refuses to overwrite it.

| Item | Rule |
|---|---|
| Models | `phase4-ts-v1`, `phase4-r0-v1`, by artifact hash |
| Code | One SHA-256 over every file the inference path reads. A forecast from different code counts only under a committed amendment stating that features, models and eligibility are unchanged |
| Window | Forecasts issued from the freeze; matches scheduled up to 30 June 2027. The one final evaluation runs on or after 15 July 2027 and refuses to run twice |
| Counted forecast | The first stored forecast for each match and model, issued at least 30 minutes before the start known at the time. The last forecast before the start is a sensitivity check |
| Counted matches | Settled with no disagreement between sources; completed; best of 3 or 5. Retirements, walkovers, defaults and cancellations are counted and excluded, as in every earlier phase |
| Primary | Model A: log loss by tour and combined. Model B minus Model A: the paired log-loss gap on identical later-round matches |
| Secondary | Brier score, accuracy, reliability, calibration line, ECE (descriptive), uncalibrated surface Elo as a benchmark |
| Slices | Tour, surface, level, ranking band, history coverage, identity status, round. All descriptive |
| Uncertainty | Standard errors clustered by tournament week (both tours together), plus a week-level cluster bootstrap (2,000 draws). Limitation: a player's results are correlated across weeks, which this clustering does not capture, so intervals may be somewhat too narrow |
| Reporting | An improvement is claimed only if its 95% interval excludes zero |
| Forbidden | Choosing any model, feature, rule, threshold or calibration from P1 outcomes while calling P1 untouched. A changed model is a new version, evaluated on a window after its own freeze |
| Expected size | At most about 3,000 tournament-start matches and 1,500 later-round pairs, and only with daily runs. The R0 gap's minimum detectable value is about 0.007, against Phase 4's 0.005–0.007: **P1 alone may be inconclusive for R0**, and the report will say so |

## Starting the prospective record

1. Review and commit the Phase 6 files:
   - `matchup_dna/forecasting/`
   - `models/`
   - `tests/test_forecast_*.py`
   - `forecasts/`
   - the two Phase 6 documents and the README
2. `python -m matchup_dna.forecasting protocol freeze`, then commit `experiments/phase6_prospective_protocol.json`. P1 starts at that moment.
3. Schedule `python -m matchup_dna.forecasting daily` at least once a day (twice is better: order-of-play times are often published the evening before). Each run:
   - refreshes ESPN for the last 14 and next 3 days, about 36 requests;
   - forecasts every eligible fixture;
   - settles finished matches;
   - extends `forecasts/ledger.jsonl`.

   Use Windows Task Scheduler on this machine, or GitHub Actions with the history files available.
4. Commit `forecasts/ledger.jsonl` regularly. The commit history is the outside timestamp that no forecast was added after its match.
5. Every few weeks, save fresh TML and TennisData.app files. ESPN carries no serve statistics, so between file snapshots the serve-return profiles stop updating, although Elo, form and rest keep updating from ESPN results.

## Open issues

| Issue | Effect | Next step |
|---|---|---|
| Protocol not frozen | No forecast counts yet | Steps 1–2 above |
| No scheduler | Forecasts exist only when someone runs the job | Step 3 above |
| The ESPN path has not been rehearsed against the research path | ESPN's archive was retrieved now, so it cannot show what was known before past matches. The replay that matched the research exactly used the TennisData.app fixture path; the ESPN path shares the same engine and history but adds its own linking and ranks | Compare ESPN-added results with the next TML snapshot (agreement of winners, scores and identities), and replay ESPN days once the archive has been collected live |
| Ranks for players never seen in a crosswalked row | Treated as unranked (e.g. the Swedish wildcard Max Dahlin), which the ATP model penalizes heavily | An official ranking source; until then the input snapshot shows each rank's source date for review |
| Serve-return profiles between file snapshots | ESPN-added matches move Elo and form only, like the TennisData.app-only matches in Phase 4's held-out period | Periodic TML files (step 5) |
| 25 ESPN results held back for identity | Those results are missing from the history | Check them and add reviewed rows to `forecasts/identity_aliases.csv` |
| R0 in early rounds of draws with byes | When a round is only partly scheduled, `has_byes` can fail to see byes, so R0 declines a few second-round matches the research sample included. It declines; it never guesses | Read the draw size where a source gives it |
| ESPN's format can change | A changed response would stop parsing or drop records | Raw responses are archived and parses versioned; a run that finds no fixtures for an active week should be treated as a failure (monitoring, next phase) |
| Davis Cup in TennisData.app | All ties of a week form one TD edition while TML files each tie separately, so they stay unlinked | Harmless: team rounds are blank, so only tournament-start forecasts apply |
| Run time | About 5–10 minutes per run (one feature replay per edition date and tour, plus about 2 minutes reading the history) | Acceptable for a daily job; cache player state if runs become frequent |
| Paid live APIs untested | No credentials | `probe` command kept |
| Local storage | The live store is a local SQLite file | The committed ledger is the durable record; back up `data/store/`; PostgreSQL when hosted |

## Next milestones

1. **Start P1** (steps 1–3 above) and run the daily job for two weeks. Each week, check that the job ran, that ESPN-added results agree with the next TML snapshot, and that no conflicts or identity changes appear (`status`).
2. **Website MVP (Phase 7)** on top of `api.py`:
   - an upcoming-matches page with the tournament-start / round-aware toggle;
   - match pages with forecast history;
   - a track-record page reading the ledger;
   - a methodology page using the `MODEL_INFO` wording.

   A FastAPI wrapper and a hosted PostgreSQL come with it.
3. **Monitoring:** freshness and failure alerts; "last updated" on every page; a run that finds no fixtures in an active week counts as a failure.
4. **Research, on development data only** (agenda in the architecture document): Challenger history and level-aware shrinkage for players with short histories. Each must beat the frozen models on development data, then be confirmed on a window after its own freeze, never on P1.
5. **Market research**, if prices are collected prospectively: stored with their own retrieval times and evaluated under a separate protocol. The opening market remains the benchmark the models trail by 0.024 log loss.
