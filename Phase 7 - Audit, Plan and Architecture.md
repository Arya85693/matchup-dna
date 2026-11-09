# Matchup DNA — Phase 7 Audit, Plan and Architecture

**Date:** 8 November 2026 (US evening; 9 November UTC). **Branch:** `main` at `34be16b`, tracking `origin/main` (github.com/arya85693/matchup-dna).
**Scope:** Phase 7 builds the public website MVP on top of the Phase 6 forecasting system without changing it. This document is the planning stage only: **no website code exists yet, and nothing below is built until the visual direction and the plan are approved.**
**Design mockups:** three homepage directions, rendered from real forecasts read from the live store, are published as a private page (link given in the session). Section 4 summarizes them.

> **Progress, 8 November 2026 (evening):** direction B approved ("start with Design B"), with the note that the
> mockup felt cramped; design changes will follow. Milestones 7B and 7C started:
> - a read-only publisher (`web/publisher`, 19 tests);
> - a Next.js app with the Match Center, Match Detail and Status pages, reading real snapshots.
>
> Deviations from this plan, all reversible:
> 1. The new read functions live in `web/publisher/views.py`; `api.py` is unchanged.
> 2. The publisher's contract checks use the standard library (`web/publisher/contract.py`) instead of pydantic, so no
>    package is installed anywhere.
> 3. Frontend helpers are tested with Node's built-in test runner. Vitest's dependency tree crashed npm 10.9.
> 4. The homepage headline is the counted (first-issued) forecast, the recommended default for decision 2.
> 5. Spacing is more generous than in the mockup: taller rows, larger type, and secondary details (model version,
>    issue time) moved to the match page.
>
> **Later the same evening:** 7D–7F built.
> - **Pages:** Match Center, Match Detail, Research, Track record, Against the market, Models and ledger, Methodology, Status.
> - **Research export** (`python -m web.publisher.research`): it refuses to write unless every headline number equals
>   the published report.
> - **Tests:** 22 publisher tests, 7 unit tests, and 24 Playwright tests at desktop and phone sizes, with axe
>   accessibility checks.
> - **Unchanged:** all 323 existing tests pass, and the P1 code hash still matches.
>
> **Not yet done (7G, needs your approval):** hosting, the publisher's scheduled task, and the domain. Players and
> Explorer (7H, 7I) wait for the licensing review.

The document has ten parts:
1. the repository audit;
2. the product architecture;
3. a page-by-page specification;
4. the three homepage concepts and the recommendation;
5. the design system;
6. the technical architecture;
7. the hosting comparison;
8. the implementation roadmap;
9. risks and constraints;
10. the recommended approach and the decisions that are yours.

---

## 1. Repository audit

Every claim marked **checked** was verified in this session against the code or the live store, opened read-only. Nothing in the repository was modified apart from adding this document.

### 1.1 What exists and can be reused

| Component | State | Checked how |
|---|---|---|
| `matchup_dna/forecasting/api.py` | Five payload functions: `upcoming`, `match_detail`, `track_record`, `models`, `status`, plus `verify_store` and `MODEL_INFO` (the exact wording of what each model uses and does not use) | Read in full; all five called on the live store through a read-only connection (1.4) |
| Live store `data/store/live.sqlite` | Mode `live`, created 2026-11-09 00:36:55Z. **Snapshot at 03:03 UTC on 9 Nov:** 4 runs (all `ok`), 23 matches, 10 predictions (9 tournament-start, 1 round-aware), 90 eligibility decisions, 2 outcomes, 2 model versions, 959 source records | **Checked** (`mode=ro` URI; file SHA-256 identical before and after) |
| Prediction content | Each prediction stores players (id, name, rank, `rank_as_of`, seed, identity status and method), the full feature row (about 90 fields, both players), the model inputs, **per-feature log-odds contributions that sum exactly to the logit** (the models have no intercept), fixture details, the history digest, the code hash and the model hash | **Checked** on the stored rows and in `frozen_models.explain` |
| Eligibility reasons | Stored as text per match, model and run. Seen in the live store: *eligible*; *no confirmed start time yet*; *neither player has played earlier in this edition*; *round RR: R0 covers knockout rounds only*; *the match is already in progress*; *the match has already been played* | **Checked** |
| Model artifacts | `phase4-ts-v1` (9 features) and `phase4-r0-v1` (12: the same 9 plus `ra_elo_shift_logit`, `ra_surface_elo_shift_logit`, `ra_dominance_diff`), per tour, with fit window, provenance and sha256 | **Checked** |
| Ledger | `forecasts/ledger.jsonl`, 10 lines, hash-chained, committed in git (`56903a9` and later) | **Checked** |
| Prospective protocol | `experiments/phase6_prospective_protocol.json`, frozen 2026-11-09T00:29:15Z. Counting rule = the first stored forecast issued at least 30 minutes before the start; window to 2027-06-30; final evaluation not before 2027-07-15. **Monitoring rule: "the monitor may be run at any time; its output is labelled interim"** | **Checked**; the current code hash equals the protocol's `code_sha256` |
| Prospective metrics | `prospective.metrics`, `reliability` (ten 0.1 bins), `calibration_line`, `expected_calibration_error`, `paired`, slice helpers, `counted_predictions`, `outcome_rows` | Read |
| Freshness | `api.freshness` computes hours since the last forecast run, settlement run and ESPN download. It flags `ok` when all three are within 18 hours | Read; returned `ok: true` at 03:03 UTC |
| Scheduled job | Task Scheduler runs `scripts\run_daily.cmd` at 07:00 and 19:00 local time, from the project folder, with the first `python` on PATH. It appends to `data\logs\daily.log`; the last run exited 0 | Read |
| Research results | Phase 2–5 headline metrics with sample sizes and intervals in the reports. Machine-readable sources: `results/phase5/evaluation/evaluation.json`, `results/phase4/corrected/summary.json`, prediction-level CSVs (Phase 3 reserved, Phase 4 held-out original and corrected, Phase 4 long-run, Phase 5 dataset) | Inventoried. `results/` and `data/` are **gitignored**, so none of this exists on GitHub |
| Toolchain | Node 22.16, npm 10.9, Python 3.13.7. FastAPI 0.138, uvicorn 0.49 and pydantic 2.13 are already installed in the user-level Python that the scheduled job also uses | **Checked** |
| Tests | 323 tests pass per the Phase 6 report | **Not re-run** in this planning session; re-run before the first Phase 7 commit |

### 1.2 Feature map: existing, needs exposure, needs new queries, needs new computation, deferred

| Website need | Status | Source or work required |
|---|---|---|
| Upcoming matches with both models' forecasts or reasons | **Exists** | `api.upcoming` |
| Fixtures without a confirmed start time | **New read-only query** | `upcoming()` skips any match whose start is unknown (gap G1): 12 of the 21 pending matches at 03:03 UTC were invisible |
| Match status (scheduled, in progress, postponed, cancelled, completed) | **New read-only query** | The latest `source_records.status` and `payload.raw_status`; outcomes for settled matches |
| Tournament grouping, level, edition date | **New read-only query** | Join `editions` (level, `tourney_date`, `edition_uid`); `upcoming()` returns only the name and surface |
| Recently completed results with their forecasts | **New read-only query** | `store.settled()` joined with predictions and outcomes; `upcoming()` drops settled matches |
| Match detail: every forecast version, decisions, outcomes | **Exists, needs reshaping** | `api.match_detail` returns version rows without contributions or inputs, and raw decision rows with run ids (G4) |
| Feature contributions and model inputs per version | **Exists in storage** | `content_json.inputs.contributions` and `.row`; needs an allowlisted projection |
| Official counted forecast and supersession | **Exists** | `prospective.counted_predictions(rule="first")`; the `supersedes` column |
| Public track record (P1, interim) | **Exists, needs the right function** | `api.track_record` returns **every** settled prediction, including superseded ones, and applies neither the window, the 30-minute lead, nor the code-hash rule (G2). The site must use the same selection as `prospective.evaluate` |
| P1 metrics, reliability, intervals | **Exists** | `prospective.metrics`, `reliability`, `calibration_line`; week-clustered SEs via `uncertainty` |
| Historical results (Phases 2–5) | **New computation (export and verification)** | Curated from the reports and `results/*.json`. Reliability bins exist only as text tables, so they are recomputed from the prediction CSVs, and every recomputed headline number must equal the published one |
| Model metadata | **Exists** | `api.models` plus `MODEL_INFO` |
| Operational status and freshness | **Exists, needs allowlisting** | `api.status` includes identity-drift details and run ids not meant for the public (G7); `freshness()` reads the local ESPN archive (G8) |
| Ledger proof | **New, small** | The store head hash and count against the committed `forecasts/ledger.jsonl` on GitHub |
| Player profiles (Elo trend, surface strength, serve-return, results) | **New computation, deferred** | The history is rebuilt in memory on each run from Sackmann, TML and TD; no store table holds player state. Needs an export job and a licensing review (part 9) |
| Matchup Explorer (two players' statistics) | **New computation, deferred** | Same data as player profiles. **No hypothetical forecast exists or will be shown**; the engine forecasts real fixtures only |
| Live in-play probabilities | **Deferred** (brief Phase 9) | Not built; R0 is a between-rounds model |
| Market prices for current matches | **Deferred** | Not collected prospectively; a separate protocol is required (Phase 6 architecture, part 7) |

### 1.3 Gaps found on the real code and data

| # | Gap | Effect if ignored | Fix (all outside the protected files) |
|---|---|---|---|
| G1 | `api.upcoming` skips matches with no confirmed start | The Match Center would silently omit more than half of a typical day's draw | New function `fixtures(store, now)` returning those matches with `start: null` and the stored reason |
| G2 | `api.track_record` counts every version and ignores the protocol window, lead time and code hash | A published track record could differ from the P1 counting rule | New `prospective_record(store)` that applies exactly `evaluate()`'s selection; a test asserts it matches `evaluate --monitor` on a synthetic store |
| G3 | No match status in payloads | In-progress, postponed or cancelled matches would look "upcoming" | Expose the latest provider status and `raw_status`; map to a closed set |
| G4 | `match_detail` exposes run ids and lacks contributions | Internal noise is public, and the "why" panel has no data | A projection with allowlisted fields |
| **G5** | **`Store(path)` opens a read-write connection, runs schema DDL, and creates the file if the path is wrong** | **The website must never open the live store through `Store()`** | A read-only adapter: `Store.__new__(Store)` with an `sqlite3` connection on `file:…?mode=ro` (plus `PRAGMA query_only`). The existing read methods work unchanged on it. **Proven in this session:** all five payloads produced, live-store bytes unchanged, code hash unchanged |
| G6 | No edition or level fields in `upcoming` | No tournament hierarchy | Join `editions` |
| G7 | `status()` includes identity-drift details and failed run ids | Leaks internal operational detail | A public status projection: freshness, counts, `ok`, last run times |
| G8 | `freshness()` reads `data/raw/espn` | Works only on the PC | Computed at export time and shipped in the snapshot |
| G9 | Research inputs live in gitignored `results/` | A hosted site cannot read them | A curated research export, recomputed and asserted equal to published values, with source sha256s, committed under `web/` |
| G10 | No stored player state | Player pages need new work | Deferred milestone 7H |
| **G11** | **SQLite uses the default rollback journal.** A reader's shared lock held while the job commits can make the job wait, then fail with "database is locked" | A website read could break a scheduled forecast run | The publisher never reads during a run: it skips if any `runs.status = 'running'`, copies the store with SQLite's backup API in milliseconds, closes it, and works on the copy. It is scheduled 30–40 minutes after the job. **No hosted request ever touches the live store** |

### 1.4 Protected files: do not modify before 30 June 2027 without a committed amendment

From `prospective.CODE_FILES`: `matchup_dna/forecasting/{__init__, records, providers, espn, history, frozen_models, engine, store, pipeline, prospective}.py`; `matchup_dna/{features, phase4_features, phase4_model, model, profiles, round_aware, elo, load, workload, serve_stats, heldout, merge, crosswalk, tennisdata, tennisismylife, audit_tennisdata, audit_tennisismylife}.py`; `models/phase4_tournament_start.json`; `models/phase4_round_aware_r0.json`; `results/phase4/profile_settings.json`.

**May change:** `matchup_dna/forecasting/api.py`, `__main__.py`, `rehearsal.py`, scripts, documents, tests, and the CSV files in `forecasts/`. Phase 7 changes `api.py` **additively only**: new functions, with existing outputs unchanged and pinned by a snapshot test. Phase 7 never imports a write method from `store`, `pipeline` or `engine`; a test enforces this (part 6.7).

**Also binding (Phase 4 erratum and Phase 5 protocol):** they hash their own code files. No Phase 1–5 module is edited.

### 1.5 The brief compared with the current architecture

The Master Brief (v1.0, 29 Oct 2026) was read for this plan. Where it and the newer reports differ, this plan follows the newer verified architecture and records each difference.

| Brief | Now | Resolution |
|---|---|---|
| Phase 6 = database and backend (PostgreSQL, FastAPI) before the website (§62, §44) | Phase 6 became prospective forecasting with SQLite and a function-level API (`api.py`) | Phase 7 uses a static snapshot API generated from `api.py` (part 6). PostgreSQL and FastAPI are deferred until a feature needs live queries. This is consistent with §49 ("complexity follows need") |
| Phase 7 MVP includes the Matchup Explorer and selected player profiles (§63) | Your Phase 7 brief makes the four core pages the MVP and Players/Explorer later milestones | **Recorded as an explicit scope revision** (§77 requires one). 7H and 7I follow the MVP |
| Phase 8 = automatic updating | Already done locally in Phase 6 (Task Scheduler, twice daily) | The site shows freshness. Moving the job off the PC is a later decision |
| Homepage "Matchup DNA Live" (§42) | No live model; ESPN statuses only | Show the provider status (in progress) and **no live probability** |
| Quantitative Signal Laboratory (§42) | Phase 5: no edge; no betting recommendations | Not built. The Market page reports the research result only |
| Licences (§12–14, §48, §75) | Sackmann CC BY-NC-SA 4.0; Valuebetennis CC BY 4.0; TML terms unreviewed; ESPN is the live source | Part 9 sets the display rules; the site is non-commercial |

---

## 2. Product architecture

### 2.1 Navigation (MVP)

```
Matches   Research   Methodology                       ● Updated 07:12 · status
```

| Route | Page | In the MVP |
|---|---|---|
| `/` | Match Center: today's order of play, the next days, time-to-be-confirmed fixtures, recent results | Yes |
| `/matches/[matchUid]` | Match Detail | Yes |
| `/research` | Research overview: what has been tested, phase timeline, links | Yes |
| `/research/track-record` | Prospective P1 record (interim) and historical evaluations | Yes |
| `/research/market` | Phase 5: the model against the betting market | Yes |
| `/research/models` | Model versions, artifact hashes, what each uses, the forecast ledger | Yes |
| `/methodology` | How it works, limitations, data and attribution | Yes |
| `/status` | Freshness, last runs, counts, integrity check result | Yes (linked from the freshness light and the footer, not the main nav) |
| `/players`, `/players/[id]` | Player Intelligence | **7H**; absent from the nav until it ships |
| `/explorer` | Matchup Explorer | **7I**; absent until it ships |

Changes from the proposed routes:
- `/matches` is merged into `/`. Filters use query parameters (`?date=2026-11-09&tour=WTA&surface=Hard`), so a filtered board is a shareable URL.
- `/research/performance` becomes `/research/track-record`, the term used across the reports.
- `/research/models` is added: model versions are central to the integrity story.

The match URL uses the canonical `match_uid` (`/matches/M-915ecaa685ce…`). It never changes, because it is a hash of tour, edition, round and both canonical ids.

### 2.2 Journeys

**Tennis fan.**
1. Opens `/` and sees today's matches grouped by tournament, with the favourite and the percentage on every forecast row.
2. Taps a match and sees both players facing each other, the forecast, the round-aware update if one exists, and a plain-language "why" built from the stored contributions.
3. Follows "How often is it right?" to the track record, and learns that the market forecasts better and the model is not a betting tool.

**Researcher or recruiter.**
1. Opens `/research/track-record` and sees the prospective record (interim, with n and intervals), held-out results with their pre-registration status, and the erratum.
2. Opens `/research/market` for the Phase 5 negative result.
3. Opens `/research/models` and `/methodology` for artifact hashes, the counting rule, and the protocol file.
4. Opens a match page and expands "Integrity": prediction id, input hash, code hash, model hash, ledger position, and the command to reproduce the probability locally.
5. Checks `/status`, then the repository.

---

## 3. Page-by-page specification

Field names refer to the snapshot contract in part 6.4. "Reason text" means the stored eligibility reason mapped to user language (6.4.3). **No page computes a probability.**

### 3.1 Match Center (`/`)

| Block | Content | Data |
|---|---|---|
| Header | Wordmark, nav, freshness light: "Updated 07:12" (local time; UTC on hover). Amber "Forecasts may be out of date: last update 20 hours ago" past the stale threshold | `manifest.generated_at`, `status.last_forecast_run`, `status.ok` |
| Introduction (one screen-third at most) | One-line positioning and one featured match. Preference order: a match with both models issued; otherwise the highest-level event's next match. It shows both models side by side | `matches/index.json` |
| Controls | Day tabs (today, next days with fixtures, "Time to be confirmed", "Results"); tour (All/ATP/WTA); surface (only surfaces present). All filters are reflected in the URL | Index |
| Tournament group | Name, tour, level, surface chip (colour and text), rounds present, edition dates | `edition` |
| Match row | Start time (local), round, both players with rank (rank date on hover), the net-split probability bar with both percentages, the favourite in bold and highlighted, and a round-aware line (number, or reason). Issue time and model version in small type. A "Revised" marker when the latest forecast supersedes the counted one | `forecasts.tournament_start`, `.round_aware`, `players` |
| States | **No forecast:** reason text, never a number. **In progress:** "In progress", forecast kept, no live number. **Postponed/cancelled:** status shown, forecast kept and marked not scored. **Awaiting result** (start passed by more than 3 hours, not settled): shown under Results as "Result pending" | `status`, `decision`, `settlement` |
| Results | Completed matches from the last 7 days: score, winner, the counted forecast, and whether the favourite won. A walkover or retirement is labelled "not scored" | `recent_results` |
| Rail | Track record teaser: P1 forecasts issued, scored so far, link. Market disclosure: "Betting markets forecast better than this model" with the Phase 5 numbers and a link | `track_record.p1.summary`, `research.market.headline` |
| Empty, loading, error | **Empty day:** "No main-tour singles matches are scheduled for this day" plus the next day with matches. **Snapshot unreachable:** "Match data could not be loaded. The last good update was at 07:12" if a cached copy exists, else the error. **Skeletons** keep the row geometry | — |

### 3.2 Match Detail (`/matches/[matchUid]`)

| Block | Content | Data |
|---|---|---|
| Face-off header | Both players (name, rank with `rank_as_of`, seed if any, identity status if `new_player`), tournament, level, surface, round, best of, scheduled start, status | `match`, `players` |
| Forecast panel | **If both models issued:** side by side, "Before the tournament" and "After earlier rounds", each with a net bar, issue time and version. Caption: "The round-aware update uses everything the tournament-start forecast uses, plus the results of this tournament's completed earlier rounds" (`MODEL_INFO` wording). **If only A:** A, and a model B slot with the reason and no number. **If neither:** the reason, and when it will be issued if that is known | `forecasts` |
| Why (contributions) | A diverging bar chart in log-odds from a centre "net" line: bars toward each player's side. Labels in plain words. The note: "Each bar is that input's push on the model's log-odds; the bars add up to the forecast. Inputs are correlated (overall and surface Elo especially), so a single bar is not that input's independent effect." A toggle shows model A or model B terms | `versions[].contributions` |
| What the model saw | A two-column table of the stored inputs per player: overall Elo, surface Elo, rank and its date, days since the last match, recent form against Elo expectation, serve and return estimates (opponent-adjusted), and matches behind the serve-return estimates. For B, also this week's Elo change and share of games won. Values come from the stored row; nothing is recomputed | `versions[].inputs` |
| Forecast history | A timeline of every version per model: issued at, probability, `supersedes`, prediction id. The **counted (first) forecast** is labelled "Scored"; later ones "Revision, not scored". The decision log in plain words, deduplicated | `versions`, `decisions` |
| Result | When settled: winner, score, status, sources (and a conflict flag); a log-loss chip for each counted forecast | `settlement` |
| Integrity (collapsed) | Prediction id, input sha256, model artifact sha256, code sha256 (and whether it equals the P1 protocol), ledger position and the record hash, and the reproduction command: `python -m matchup_dna.forecasting verify` | `versions[].integrity` |
| Footnote | "A forecast is a probability, not a prediction of the score. A 70% favourite is expected to lose about 3 matches in 10." | — |

### 3.3 Track Record (`/research/track-record`)

Order on the page: definitions first, then the prospective record, then history.

1. **How to read this.** Accuracy (picks the winner; 0.5 counts half), log loss and Brier (probability quality; lower is better), calibration (do 70% forecasts win 70% of the time). Why a model can be better on log loss without being better at picking winners (Phase 4: "almost entirely" a gain in probability quality).
2. **Prospective record P1 (interim).**
   - Start: 2026-11-09 00:29 UTC; window to 30 June 2027; final evaluation on or after 15 July 2027.
   - Counts: forecasts issued, counted, scored, and excluded by reason (no result yet, walkover/retirement, conflict, other code).
   - Model A: log loss, Brier and accuracy with week-clustered 95% intervals, by tour and combined.
   - Model B minus A: the paired gap on identical matches.
   - Reliability: ten 0.1 bins, each drawn with its n; bins under 20 matches drawn hollow.
   - The surface Elo benchmark on the same matches.
   - Every number is labelled **"Interim. Not the P1 result. Decides nothing."** (the protocol's monitoring rule).
   - Slices are shown as descriptive only, never called findings.
   - **Until matches are scored:** "No forecasts have been scored yet", plus the counts. No placeholder metrics.
3. **Historical evaluations** (one table; each row carries its status: development, retrospective, pre-registered held-out, corrected after unblinding, post-hoc):

| Phase | Comparison | Window, n | Result | Status |
|---|---|---|---|---|
| 2 | Surface Elo vs Elo | 2021–2023, ATP 8,366 / WTA 7,673 | ATP −0.0031 (SE 0.0015), WTA −0.0004 (0.0017) | Development |
| 3 | Logistic vs calibrated surface Elo | Jan 2024–May 2026, 13,732 | 0.6128 vs 0.6207; −0.0078 (0.0015) | Reserved final evaluation |
| 4 | P4 (serve-return) vs P3 | Jun–Oct 2026, 2,518 | −0.0040 (SE 0.0021), 95% CI −0.0081 to +0.0001, p = 0.055: **"not a statistically supported improvement"** | Pre-registered held-out |
| 4 | Same, after erratum 1 | 2,453 | −0.0049 (0.0017), p = 0.005 | **Retrospective; the pre-registered verdict stands** |
| 4 | Round-aware R0 vs tournament start | Jun–Oct 2026, 1,286 (corrected 1,275) | −0.0072 (0.0023); corrected −0.0059 (0.0024) | Pre-registered; the most robust Phase 4 finding |
| 5 | Phase 4 vs opening market | Jan 2024–Oct 2026, 13,846 | Market better by 0.0236 (CI +0.0198 to +0.0274) | Frozen protocol |

   Charts:
   - log loss by phase, as dot-and-interval rows (not bars) with a reference line;
   - reliability diagrams for the Phase 3 reserved period and the Phase 4 held-out period, recomputed from the prediction CSVs;
   - the long-run per-year accuracy and log loss from `posthoc_longrun_predictions_corrected.csv`, labelled **post-hoc**.
4. **Limitations** (from the reports): validation reuse, ATP overconfidence, the held-out test's low power, rank-source differences, accuracy barely above the ranking, and every result being an association rather than a cause.

### 3.4 Market (`/research/market`)

**Headline:** "The betting market forecasts better than Matchup DNA."
- Opening prices (margin removed by the power method): log loss **0.5896**, Brier 0.2031, accuracy 68.07%. Phase 4: **0.6132**, 0.2130, 65.42%. Gap **+0.0236** (0.0019), 13,846 matches, Jan 2024–Oct 2026.
- The model added no information to the price: blend gap −0.0000 (p = 0.91); information slope −0.067 (p = 0.13).
- A paper value-betting rule: 8,721 bets, ROI **−8.9%** (−12.6% to −5.2%). Quarter-Kelly bankroll fell 100%.
- The gap by year, tour and ranking band (top 20: +0.0117; outside the top 100: +0.0434). The post-hoc round-aware comparison (+0.0132), labelled post-hoc.
- Disclosures, in the report's own words: the window is fresh only for the market question; the protocol was frozen and run in one session; prices carry no timestamps.
- "No economic outcome is claimed in either direction. This site makes no betting recommendations."

### 3.5 Models (`/research/models`)

- Each version: kind, label, what it uses and does not use (`MODEL_INFO`), the fit window (2010 to the week of 25 May 2026), the population, the features with their coefficients per tour (from the artifact), and the artifact sha256.
- The forecast ledger: count, head hash, the latest committed hash on GitHub, and how many forecasts are not yet in the committed copy. A table of the last 50 forecasts with prediction ids.

### 3.6 Methodology (`/methodology`)

The sections follow your list:
- what it is and why it was built;
- data to features (a chronological replay, no future information);
- Elo, explained with a worked example: expected score from the rating difference, then the update;
- surface Elo;
- ranking, inactivity, form and serve-return;
- the two models, illustrated with C's scale court drawing;
- probability generation (a logistic model; contributions sum to the log-odds);
- recording and immutability (append-only tables, hash chain, public ledger);
- calibration;
- historical against prospective evaluation;
- what works and what doesn't;
- data limitations (ESPN has no serve statistics; profiles update with file snapshots; ranks for players never seen in a crosswalked row);
- data sources and attribution;
- "Why no guarantees".

Diagrams are inline SVG.

### 3.7 Status (`/status`)

- Freshness: the last successful forecast, settlement and ESPN download, with hours since each; overall `ok` and the 18-hour rule.
- Snapshot generated at, and whether the last publish succeeded.
- Counts: predictions, matches, settled, conflicts (count only).
- `verify_store` result: "every stored probability recomputes exactly" or the number of problems.
- No paths, run ids, provider ids or identity-drift details.

---

## 4. Three homepage concepts and the recommendation

All three are rendered in the mockup page from the **real** 03:03 UTC live-store snapshot. Each is shown in a desktop frame and a 390 px phone frame, built from the same markup with container queries. They use the 9 forecasted matches, 12 fixtures without a start time, and one finished match that was never forecast. No data was invented. The full ten-point presentation for each is on that page; this is the summary.

| | A. Intelligence terminal | B. Centre court | C. Research studio |
|---|---|---|---|
| Thesis | The board as an instrument: a two-line scoreboard row per match, model columns where set scores go, a nine-bar contribution strip | Each match is two players facing each other across a net; the probability bar is split by a fixed centre "net" line | A printed order of play as a research publication; the hero is a scale court drawing with the forecasts as lines |
| Colour | About 85% deep navy, cream text; yellow only for the favourite's figure | The brief's 75/15/10: navy, grass-filled favourite side, yellow only for the favourite's percentage | Cream paper and navy ink; yellow as a highlighter |
| Type | Archivo (narrow widths) + Martian Mono for every figure | Big Shoulders Display (scoreboard voice) + Schibsted Grotesk | Newsreader + Geist / Geist Mono |
| Fans | Weak | **Excellent** | Good |
| Researchers | Excellent | Good on the board; excellent with the dense table variant on research pages | Good on methodology |
| Main risk | Reads as a spreadsheet; close to the generic dark-terminal look | Display face needs discipline | Close to the generic cream-and-serif look; inverts the 75% dark balance; static feel |

**Recommendation: B, Centre court.**
- It serves both audiences without a mode switch.
- Its signature, the net-split bar with the centre line as the neutral reference, becomes one visual grammar for the whole site:
  - the match board bar (50%);
  - the contribution chart (zero log-odds);
  - calibration (the diagonal);
  - interval rows (the reference model).
- From A, B takes the two-line scoreboard row and the mono figures as the **dense variant** of the same system for research tables and Status.
- From C, it takes the scale court drawing as a **Methodology illustration** only.
- These are components within one token set, not a second aesthetic.

---

## 5. Design system (for direction B)

### 5.1 Colour tokens

Contrast ratios were measured in this session (WCAG 2.x).

| Token | Hex | Role | Contrast |
|---|---|---|---|
| `--navy` | `#111C22` | Canvas (about 75%) | — |
| `--navy-raised` | `#16252D` | Featured panels, hover rows | — |
| `--line` | `#263A43` | Rules, table borders | Decorative |
| `--cream` | `#F5F1E6` | Primary text | 15.3 : 1 on navy |
| `--muted` | `#A3B1B3` | Secondary text | 7.8 : 1 |
| `--dim` | `#7E9096` (was `#6F8187`) | Tertiary text, versions | `#6F8187` measured **4.26 : 1**, below AA; raise to ≥ 4.5 : 1 (verify in 7B) |
| `--ball` | `#DFFF45` | **Only:** the favourite's percentage, the selected control's underline, focus rings | 15.3 : 1 on navy |
| `--grass` | `#176B4D` | Brand colour on light surfaces and large areas (logo plate, light-theme fills) | **2.68 : 1 on navy, too low for a fill on dark**, hence `--grass-fill` |
| `--grass-fill` | `#2A8A64` | The favourite's side of the bar, positive status | 4.05 : 1 on navy |
| `--underdog-fill` | `#33464F` → adjust | The other side of the bar | Only **2.31 : 1** against `--grass-fill`. Percentages are printed as text, so the bar is redundant, but 7B adjusts the pair to ≥ 3 : 1 |
| `--hard` | `#3278AD` | Hard-court chip and rule (text on it: white, 4.75 : 1) | Line 3.65 : 1 on navy |
| `--clay` | `#C96B3C` | Clay chip (text on it: **navy, 4.66 : 1**; white is only 3.72 : 1); the market warning rule | 4.66 : 1 |
| `--grass-surface` | `#2A8A64` + a court-line pattern | Grass chip | — (shares the fill colour, so the chip also carries the word "Grass") |
| `--warn` | amber, chosen in 7B | Stale data | ≥ 4.5 : 1 |
| `--error` | red-orange, distinct from clay | Load failures | ≥ 4.5 : 1 |
| `--unavailable` | dashed `--line` and `--muted` text | No forecast | — |

Rules:
- **Surface colours mean surfaces only.** Clay doubles only as the market-warning rule, which is labelled.
- **Probability series are never surface-coloured.** They are always "favourite" and "other", plus text.
- Colour is never the only carrier: the favourite also gets bold and the printed figure.
- Charts with two models: A is drawn as a dashed cream line or bar, B as a solid `--grass-fill` one, with a legend.

### 5.2 Typography

| Role | Family | Licence | Use |
|---|---|---|---|
| Display | **Big Shoulders Display** 600–800 | SIL OFL | Tournament names, page titles, key figures (a few per screen) |
| Interface and text | **Schibsted Grotesk** 400–700 | SIL OFL | Everything else; `font-variant-numeric: tabular-nums` for all figures |
| Technical | **Martian Mono** at 85–90% width, 400–500 | SIL OFL | Model versions, hashes, UTC timestamps, dense research tables only |

All three are self-hosted through `next/font` (no runtime Google request).

**Scale:**
- 12, 13, 14, 15 (body), 17, 20, 24, 30, 38, 48, 64;
- display at a line height of 0.95–1.05, text at 1.5;
- figures in the bar use 20 (favourite) and 14 (other);
- running text at most 68 characters wide;
- sentence case everywhere; no all-caps labels except the wordmark.

### 5.3 Layout

- Content maximum 1280 px; a 12-column grid with 24 px gutters; page padding 28 px on desktop, 16 px on phones (with safe-area insets).
- Match Center: board 8 columns, rail 4 (rail below 980 px).
- Match Detail: full-width face-off, then 7 columns (forecast, why) and 5 (inputs, history).
- Research: 12-column dense tables, horizontally scrollable inside their own container on phones.
- Section spacing 32 / 48 / 72. Board row height at least 64 px; touch targets at least 44 px.
- Corner radius: 2 px on controls, 0 on bars and rules (court lines are square).
- **No card shadows**; elevation is `--navy-raised` plus a 3 px top rule in the surface colour on featured panels only.

### 5.4 Components

| Component | Specification |
|---|---|
| Top nav | Logo (the court mark: rectangle, service lines, a yellow net), three links, freshness light (green `ok`, amber stale, red failed), "Updated hh:mm" |
| Tournament header | Display name, surface chip (colour and word), level, rounds; a 2 px rule in the surface colour |
| Match row | Time and round / left player (right-aligned) / net bar / right player. Sub-line: round-aware, issue time, version. On phones: names on one line, bar full width |
| Net bar | Two fills, a 2 px cream centre line extending 5 px beyond the bar, percentages above each end. `role="img"` with a full text alternative |
| Unavailable slot | A dashed outline with the reason text; **never a number, never greyed-out digits** |
| Model pair | Two labelled net bars ("Before the tournament", "After earlier rounds"), the nested-information caption |
| Contribution chart | Horizontal diverging bars from a centre line in log-odds; features sorted by \|value\|; a tooltip with the exact value and the input values for both players; an axis in log-odds with a secondary percentage-points hint near 50% |
| Reliability diagram | Square plot with the diagonal as the reference; points sized by n with 95% Wilson intervals; hollow points for n < 20; a histogram of forecasts underneath |
| Interval row | A dot with a whisker against a reference line (for metric gaps) |
| Dense table | A's two-line scoreboard row in Martian Mono for figures; a sticky header; zebra striping by match, not by line |
| Filters | Segmented controls, URL-synced; keyboard arrows within groups |
| Status pill | `ok` / stale / failed / interim / post-hoc / pre-registered: these labels encode evidence status everywhere |
| Tooltip | Opens on focus as well as hover; Escape closes it |
| Skeleton | Keeps the row geometry with a static fill (no shimmer) |
| Footer | Data sources and licences, "Not betting advice", repository link, last update |

### 5.5 Interaction and accessibility

- Hover: a row tint only. Focus: a 2 px `--ball` outline with 2 px offset everywhere.
- One orchestrated motion: bars grow from the net on first paint (200 ms). Disabled under `prefers-reduced-motion`.
- No page transitions beyond the browser default.
- Target WCAG 2.2 AA: semantic headings, `<table>` for tables, text alternatives for every chart (each chart has a "Show data" table), visible focus, 200% zoom without loss, 44 px targets.
- Times are shown in the viewer's time zone with an explicit UTC tooltip and a "Times in your time zone (Europe/London)" note.

---

## 6. Technical architecture

### 6.1 Decision: a static snapshot API, no hosted Python or database for the MVP

```
 PC (unchanged)                                 PC (new, separate task, :35 past the job)
 Task Scheduler 07:00 / 19:00                   web/publisher  (own venv, read-only)
 run_daily.cmd → forecasting daily              1. skip if any run is "running"
 → data/store/live.sqlite (writes)              2. sqlite backup API → temp copy (ms)
 → forecasts/ledger.jsonl                       3. api.py + new additive read functions
                                                4. validate every payload (pydantic)
                                                5. write /v1/*.json + manifest (sha256 of each file)
                                                6. upload to object storage (new prefix first, then manifest)
                                                7. POST revalidate webhook (secret)
                                                          │
                                                          ▼
                       Object storage (Cloudflare R2, private bucket, read-only token for the site)
                                                          │  server-side fetch, cached
                                                          ▼
                       Next.js (Vercel): server components, ISR (revalidate 300 s + on-demand)
                                                          │
                                                          ▼
                                                       visitors
```

Why this shape:
1. **Isolation.**
   - Visitors never reach the PC, the store or any Python code.
   - The only process touching the live store is a read-only publisher that runs between scheduled jobs.
   - A website bug cannot change, delay or invalidate a P1 forecast.
2. **It is what the data needs.** The data changes twice a day and is small (about 14 KB of payload today, a few MB after a season). A static, versioned JSON API serves that perfectly.
3. **No new always-on infrastructure.** There is no server to keep awake, no database to sync and no credentials on a public host beyond a read-only bucket token.
4. **The brief's architecture stays reachable.** The JSON paths are the HTTP contract. A FastAPI service can later serve the same paths from PostgreSQL without any frontend change (6.6).

### 6.2 Frontend

- **Next.js (App Router) + React + TypeScript, Tailwind CSS v4.** Tailwind is used as a utility layer over the token CSS variables of part 5, not a component kit. No shadcn defaults.
- **Server-side rendering: yes.**
  - Match and research pages are content that should be indexable and fast on phones.
  - Server components fetch the snapshot, so browsers never download the full index.
  - ISR keeps pages static between updates.
  - Client JavaScript only for filters, toggles and tooltips.
- **Charts: hand-built SVG components, not Recharts.**
  - There are five chart types: net bar, diverging contributions, reliability, interval rows, small trend lines.
  - Each needs exact geometry (the centre line) and server rendering with accessible data tables.
  - A library would add client weight and defaults to fight.
  - `d3-scale` and `d3-shape` may be used for maths only.
- **Testing:**
  - Vitest and Testing Library for components (states: available, unavailable with each reason, revised, stale);
  - Playwright end-to-end against a **fixture snapshot** (a frozen copy of a real export, plus synthetic edge cases clearly marked as test data), at desktop and phone sizes;
  - axe accessibility checks in Playwright.

### 6.3 Publisher (Python, read-only)

- Location: `web/publisher/` (new files). It imports `matchup_dna.forecasting.api` and the read functions of `prospective`.
- It runs in **its own virtual environment** (`web/publisher/.venv`, gitignored) with numpy pinned to `requirements.txt` and pydantic. The scheduled job's Python environment is not touched: **nothing is installed into it.**
- **Read-only adapter** (G5): connect with `file:<path>?mode=ro`, run `PRAGMA query_only = ON`, then hand the connection to `Store.__new__`. Copy with `sqlite3.Connection.backup` into a temporary file and close the live connection before any work.
- **Pre-flight checks:**
  - refuse if the store mode is not `live`;
  - refuse if a run is in progress;
  - refuse if `verify_store` reports problems (publish the status as failed, keep the previous snapshot);
  - record the store head hash and the protocol code-hash match.
- **Output:** a versioned directory `v1/<generated_at>/…`, then `v1/manifest.json` pointing to it, written last, so a reader never sees a half-written snapshot. Old snapshots are kept, giving the site its own audit trail.
- **Research export** (`web/publisher/research.py`, run by hand when the research changes, not twice daily):
  - reads `results/…` locally;
  - recomputes the reliability bins from the prediction CSVs;
  - **asserts that every recomputed headline value equals the published report value to its printed precision**;
  - writes `web/content/research/*.json` with each source file's sha256.
  
  Those aggregates are committed, so research pages are reviewable in git and do not depend on the PC.

### 6.4 The data contract

#### 6.4.1 Snapshot files (the read-only HTTP API)

| Path | Your proposed route | Content |
|---|---|---|
| `/v1/manifest.json` | — | `schema_version`, `generated_at`, snapshot directory, each file's sha256, store head hash, prediction count, publisher version |
| `/v1/matches/index.json` | `GET /api/v1/matches/upcoming` | Pending matches (scheduled and time-to-be-confirmed) and results from the last 7 days, compact: identity, edition, players, status, and per model `{available, p by player id, issued_at, model_version, prediction_id, counted, revised}` or `{available: false, decision, reason_code, reason_text}` |
| `/v1/matches/<uid>.json` | `GET /api/v1/matches/{id}` and `/{id}/forecasts` | Everything for one match: all versions with contributions, allowlisted inputs, integrity hashes, plain-language decision log, settlement and outcomes per source |
| `/v1/research/track-record.json` | `GET /api/v1/research/performance` | P1 interim: counts, exclusions, metrics with intervals, reliability bins, paired B−A, Elo benchmark, `interim: true`, protocol reference |
| `/v1/research/historical.json`, `/v1/research/market.json` | (static, from `web/content`) | Phase 2–5 curated aggregates with source hashes and status labels |
| `/v1/models.json` | `GET /api/v1/research/models` | `api.models` + `MODEL_INFO` + coefficients per tour, without `artifact_json` blobs |
| `/v1/status.json` | `GET /api/v1/status` | Public status projection (3.7) |
| `/v1/ledger/recent.json` | — | Last 200 ledger entries (id, match, model, issued, p, record hash) |

The future `/v1/players/<id>.json` and `/v1/compare?…` are reserved names; the latter needs a live API (6.6).

#### 6.4.2 Fields every forecast carries

`match_uid`, `prediction_id`, `model_version`, `model_kind`, `issued_at`, `scheduled_start_at_issue`, `probabilities` (by player id), `counted` (`true` for the first forecast that meets the protocol's rule), `supersedes`, `superseded_by`, `contributions`, `inputs` (allowlist), and `integrity` {`input_sha256`, `model_sha256`, `code_sha256`, `code_matches_p1_protocol`, `record_hash`, `ledger_index`}.

Every field comes from storage. **None is computed for display except** two things:
- `counted`, which is derived by `prospective.counted_predictions`;
- the reason text, which is a fixed mapping.

#### 6.4.3 Reason codes

A closed mapping from the stored decisions to user text. Anything unrecognized is shown verbatim, never hidden.

| Stored | Code | Shown |
|---|---|---|
| `deferred`: no confirmed start time | `start_unconfirmed` | "Start time not confirmed yet. The forecast is issued once it is published, at least 30 minutes before play." |
| `ineligible`: neither player has played earlier | `ra_first_match` | "Round-aware update: first match this week for both players." |
| `ineligible`: round RR | `ra_round_robin` | "Round-aware update: covers knockout rounds only." |
| `too_late`: in progress | `too_late_in_progress` | "No forecast: the match had already started when it was first seen." |
| `too_late`: already played | `too_late_played` | "No forecast: the match had already been played when it was first seen." |
| identity `ambiguous` / `conflict` (withheld) | `identity_review` | "No forecast: a player's identity is being checked." |
| No decision yet | `not_evaluated` | "Not evaluated yet." |

#### 6.4.4 Validation and types

- Pydantic v2 models in the publisher define the contract and export JSON Schema (`web/contract/schema/*.json`, committed).
- TypeScript types are generated from that schema.
- The frontend validates each fetched file at the boundary with generated zod schemas. A file that fails validation is treated as unavailable (error state), never partially rendered.
- `p` values must satisfy 0 < p < 1, and the two per match must sum to 1 within 1e-12.
- Every forecast's `model_version` must exist in `models.json`.

### 6.5 Caching and freshness

- **Publisher:** twice daily after the job.
- **Next.js:** fetch with `revalidate: 300` plus an on-demand revalidation webhook called by the publisher, so a new snapshot appears within seconds.
- **Freshness is judged from data, not cache age:**
  - the snapshot carries `status.last_forecast_run`;
  - the page shows amber "may be out of date" when that is more than 18 hours old (the same threshold as `api.STALE_AFTER_HOURS`), and red "updates have stopped" past 36 hours;
  - a match whose start is more than 3 hours past without a settled result moves to "Result pending";
  - a forecast is never shown as current for a match that has started.

### 6.6 What is deferred, and when it becomes worthwhile

| Item | Trigger | Shape |
|---|---|---|
| FastAPI service | Player search, Explorer comparisons over arbitrary pairs, or anything parametric that cannot be pre-rendered | A read-only FastAPI app serving the same `/v1` paths plus query routes, on a small always-on host |
| PostgreSQL | The above, or a hosted forecasting job | Neon (scale-to-zero) or similar; one-way sync from the PC (append-only tables map directly; triggers become revoked `UPDATE`/`DELETE` privileges) |
| Hosted scheduler | The PC being off becomes a measurable loss of forecasts | Moving the job is an operational change; the code hash is unchanged. It is documented as an operations note in the P1 record |
| Live intelligence | Brief Phase 9 | Needs a live source and a new model; push updates (SSE) from the API |

### 6.7 How official inference stays isolated (enforced, not promised)

1. The frontend has **no** probability code. A lint rule forbids `Math.exp`/`log` in `web/app` outside the chart scale helpers, and a test greps for logistic formulas.
2. The publisher imports only from an allowlist (`api`, `prospective.counted_predictions`, `outcome_rows`, `metrics`, `reliability`, `calibration_line`, `uncertainty`). A test fails if `web/` imports `engine`, `pipeline`, `frozen_models`, `history`, `espn`, or any `Store` write method.
3. A publisher test runs against a copy of a store and asserts that the file's sha256 is identical afterwards.
4. A Phase 7 CI check recomputes `prospective.code_sha256()` and fails if it differs from the protocol.
5. The full existing suite (323 tests) runs before every Phase 7 commit.

### 6.8 Working without disturbing the 07:00 / 19:00 job

- Development happens in `web/` in the **same working folder, on `main`**. A second worktree cannot check out `main` at the same time, and you want everything on `main`.
- **Branches are never switched** in this folder. `node_modules`, `.next`, the venv and build output are gitignored inside `web/`.
- No dev server, build or test touches `data/store/live.sqlite`. Development reads a **copied** snapshot store in `web/.dev-data/` (gitignored), refreshed by the publisher's `--copy-only` mode, which uses the same run-in-progress check.
- New Task Scheduler entries for the publisher are created **only with your approval**. `run_daily.cmd` is not edited.

---

## 7. Hosting comparison

Figures were checked on official pricing and documentation pages on 8 November 2026. "Unverified" means no official page confirmed it.

| Need | Option | Free tier (what matters) | Cheapest paid | Notes |
|---|---|---|---|---|
| Frontend | **Vercel Hobby** | 100 GB transfer, 1M function invocations, 4 active-CPU hours, 1M ISR reads; over-limit = paused 30 days, not billed. **Personal, non-commercial use only** | Pro $20/mo | Native Next.js (ISR, on-demand revalidation). Logs 1 hour on Hobby. Cron once a day on Hobby (we don't need it) |
| Frontend | Cloudflare Workers / Pages | 100k requests/day, static assets free and unlimited, 500 builds/month | Workers Paid $5/mo | Next.js runs through the OpenNext adapter: more configuration and occasional feature lag. Logs 3 days free |
| Frontend | Netlify | 300 credits/month, hard cap; **all sites pause when exhausted** | $9/mo | No Python functions; the credit model is less predictable |
| Snapshot storage | **Cloudflare R2** | 10 GB-month, 1M writes, 10M reads/month, **no egress fees** | $0.015/GB-month | Private bucket and scoped tokens; S3-compatible |
| Snapshot storage | Vercel Blob | 1 GB, 10k simple operations | Pro rates | The operations cap is tight for ISR reads |
| Python API (later) | Render | Free web service **sleeps after 15 min (about 1 min to wake)** | Starter $7/mo¹ | Free Postgres **deleted after 30 days** |
| Python API (later) | Railway | $1/mo credit; Hobby $5/mo including $5 of usage | — | Optional sleep; first request may return 502 |
| Python API (later) | Fly.io | **No free tier** for new organisations | About $2.19/mo + $2 IPv4 | Managed Postgres from $38/mo |
| Database (later) | Neon | 1 GB/project, scale to zero after 5 min | Pay as you go, no minimum | Short cold start |
| Database (later) | Supabase | 500 MB; **paused after 1 week inactive** | Pro $25/mo | — |
| Database (later) | Turso (hosted SQLite) | 5 GB, 500M row reads/month | $4.99/mo | Closest to the current schema |
| Scheduling | **The PC (existing)** + a second task for the publisher | — | — | GitHub Actions cron is free on public repositories but cannot see the live store |
| Monitoring | **UptimeRobot Free** | 50 monitors at 5 minutes, commercial use allowed | $144/yr | Monitors `/` and `/v1/status.json`, with a **keyword check that the status is `ok`** so stale data alerts too |
| Domain | Cloudflare Registrar | At cost, no markup | A .com is **unverified**: about $10/yr from old community figures | Free DNS and TLS |

¹ Render prices are partly verified (the pricing page did not render).

**Recommended for launch: about $0/month plus a domain.**
- Vercel Hobby for Next.js.
- Cloudflare R2 (private) for snapshots.
- The PC publisher.
- UptimeRobot Free.
- Cloudflare Registrar and DNS.

Two things make Hobby's non-commercial clause a fit rather than a risk:
- the Sackmann data licence (CC BY-NC-SA) already makes the site non-commercial;
- the site makes no money.

**Upgrade path:**
1. Traffic or any commercial intent: Vercel Pro ($20), and a commercial-use licence review first (part 9).
2. Player Intelligence and Explorer need queries: a FastAPI service on Railway Hobby (about $5) or Render Starter ($7), with Neon or Turso.
3. Moving the forecasting job off the PC: a small always-on VM or container, a separate decision after P1 operations are stable.

**Nothing will be provisioned without your approval.** You create the accounts; the plan lists the exact settings at 7G.

---

## 8. Implementation roadmap

Each milestone ends with tests passing, a short report, and **exact git commands for you to run** (verifying `git branch -vv` shows `main` tracking `origin/main`, ending with `git push origin main`). I never commit, stage or push.

| Milestone | Deliverables | Depends on | Tests | Acceptance criterion |
|---|---|---|---|---|
| **7A** Audit and specification | This document; the concept mockups | — | — | Every feature mapped to a source or marked as new work (part 1.2). **Awaiting approval** |
| **7B** Design system | `web/` scaffold (Next.js, TS, Tailwind v4 tokens, fonts via `next/font`); token file; component sheet route (`/design`, dev only) with the net bar, match row, unavailable slot, model pair, contribution chart, reliability diagram, dense table, filters, status pills, skeletons; contrast fixes (5.1) | Direction approved | Component tests for every state; axe on the sheet | You approve the component sheet at desktop and phone width |
| **7C** Read-only data layer | Additive `api.py` functions (`fixtures`, `match_view`, `prospective_record`, `public_status`); `web/publisher` (read-only adapter, pre-flight, backup copy, pydantic contract, JSON Schema, manifest, atomic layout, local output); generated TS types and zod validators; research export with published-value assertions | 7A | Existing outputs of `api.py` pinned by snapshot tests; store bytes unchanged after publishing; `prospective_record` = `evaluate --monitor` on synthetic stores; reason-code coverage; import allowlist; code hash = protocol; the full 323-test suite | A local snapshot from a copy of the live store validates. `git diff` touches no protected file |
| **7D** Match Center | `/` with grouping, day, tour and surface filters (URL state), time-to-be-confirmed and results views, freshness states, empty and error states | 7B, 7C | Playwright on fixture snapshots (normal, empty day, stale, error, only TBC); mobile | A visitor can browse genuine upcoming matches and see which have forecasts and why others do not |
| **7E** Match Detail | `/matches/[uid]`: face-off, model pair, contributions, inputs, history with counted/revision labels, result, integrity | 7D | States: A only, A+B, neither, revised, in progress, settled, walkover, conflict | A visitor can tell what was forecast, why, when, and by which version; the superseded forecasts are visible and labelled |
| **7F** Research and Methodology | Track record (P1 interim + historical + reliability), Market, Models (ledger), Methodology, Status | 7C (research export) | Every displayed number traced to a source field or report line by a test that loads the published files | All metrics verifiable and correctly labelled; the Phase 5 result is stated plainly |
| **7G** Deployment and launch | You create the Vercel, R2 and UptimeRobot accounts; a read-only token for the site and a write token on the PC; the revalidation secret; publisher Task Scheduler entries (07:35, 19:35, with your approval); domain; README section and launch runbook | 7D–7F | Playwright against the preview deployment; Lighthouse and axe; a failure drill (stop the publisher → stale banner; corrupt a file → error state) | The public URL serves real data and survives ordinary failures; the job's log shows no new errors over 3 days |
| **7H** Player Intelligence | Player export (Elo and surface Elo trend, serve-return estimates, recent results, activity), player pages, search | MVP live + licensing decision | Exported values reproduce the history's values for sampled players | Profiles show only reproducible statistics from licensed sources |
| **7I** Matchup Explorer | Compare two same-tour players' statistics | 7H | Same | Clearly labelled "comparison, not a forecast"; no hypothetical probability |

**Order and estimate:** 7B and 7C can run in parallel after approval; then 7D → 7E → 7F → 7G. The core MVP is the critical path; 7H and 7I start only after launch.

---

## 9. Risks and constraints

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| **P1 contamination**: a Phase 7 edit touches a hashed file | Low / severe (forecasts excluded from P1) | Protected list (1.4); a CI check of `code_sha256`; additive `api.py` only; review of `git diff --stat` at every milestone |
| **Job disruption**: the publisher locks the store during a write, or a new package changes the job's Python | Medium / high | Run-in-progress check; backup copy; offset schedule; separate venv; no installs into the user-level Python |
| **Accidental write** to the live store | Low / severe | `mode=ro` + `query_only`; never `Store()`; byte-hash test |
| **Misleading track record** (superseded forecasts counted; interim shown as final) | Medium / high | `prospective_record` mirrors `evaluate`; "Interim" labels; tests against `evaluate --monitor` |
| **Fixture freshness** (draw changes, ESPN placeholder times, PC off) | Medium / medium | Freshness rules (6.5); "Result pending" state; status light; UptimeRobot keyword check |
| **Player identity** (held-back results, `new_player` ranks missing, e.g. the wildcard Max Dahlin shown as rank 896 or unranked) | Medium / medium | Show `identity` and `rank_as_of`; never hide a withheld match; explain on Methodology |
| **Data licensing** (Sackmann NC-SA, TML unreviewed, ESPN display) | Medium / high | See the rules below |
| **Overstating the model** in copy | Medium / high | Copy review against the reports at 7F; the Phase 5 result on the homepage rail |
| **Design drift into a template look** | Medium / medium | One token set; the component sheet approved at 7B; no component-library defaults |
| **Small P1 sample for months** | Certain / low | Show counts and intervals; no metrics before scored matches exist; the protocol's power note |

**Licensing rules for the public site:**
- **Sackmann (CC BY-NC-SA 4.0):** the site is non-commercial, with attribution on every page footer and in Methodology. Derived aggregates are published under the same licence. No raw files are redistributed.
- **TennisIsMyLife:** its terms are still unreviewed. The site shows only model outputs and aggregates that pass through it (as the Phase 4 audit decided). Player pages (7H) **wait for that review**.
- **TennisData.app:** used under the terms you reported. Its rows are not redistributed.
- **Valuebetennis (CC BY 4.0):** attribution on the Market page.
- **ESPN:** the source of current fixtures, times and results. The attribution wording is to be confirmed with you before launch.
- **Kalshi:** never shown.

---

## 10. Recommended approach

**Design:** direction B, Centre court. It uses the brief's navy/grass/ball palette in a 75/15/10 balance, with Big Shoulders Display, Schibsted Grotesk and Martian Mono. The net-split bar is the signature. A's dense row is the research-table variant, and C's court drawing appears on Methodology only.

**Architecture:**
- a read-only Python publisher on the PC, in its own venv, run after each forecast job;
- versioned, validated JSON snapshots in a private R2 bucket;
- a Next.js site on Vercel Hobby with server rendering and on-demand revalidation;
- hand-built SVG charts.

There is no hosted Python, no database and no change to Phase 6.

**MVP scope:** Match Center, Match Detail, Track Record with Market and Models, Methodology and Status. Players and Explorer come after launch, behind a licensing gate.

**Order:** 7B and 7C → 7D → 7E → 7F → 7G.

### Decisions needed from you

1. **Visual direction:** approve B (or choose A or C, or ask for changes).
2. **The headline number on a match:** I recommend showing **the counted (first-issued) forecast** as the headline, with "Revised to X% at hh:mm (not scored)" when a later version exists. The scored number and the shown number are then always the same. The alternative is to headline the latest forecast.
3. **`api.py`:** add the new read functions there (additive, existing outputs pinned by tests), or keep them in `web/publisher`. I recommend `api.py`, since it is the documented contract.
4. **Research aggregates:** commit the curated, hash-referenced JSON under `web/content/research/`.
5. **Publisher schedule:** two new Task Scheduler entries at 07:35 and 19:35. They would be created only by you or with your explicit go-ahead.
6. **Hosting:** Vercel Hobby + Cloudflare R2 + UptimeRobot Free + a domain. Accounts are created at 7G, by you.
7. **Domain name and attribution wording** for the live data source.

### Assumptions to verify

- Big Shoulders Display and Martian Mono variable axes render as mocked in all target browsers (7B).
- R2 private-bucket reads from Vercel's server runtime stay within free limits at the chosen revalidation rate (7G).
- Whether the existing 323 tests still pass on this machine; they are re-run at 7C before any change.
