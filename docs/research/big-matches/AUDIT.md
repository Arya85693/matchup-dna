# Research audit — working paper 1, version 2.2 → 3.0

Carried out on 16 November 2026. Scope: the three version 2 analysis scripts, the Elo and data-loading code they
depend on, the publisher and the paper. Method: reading the code, running checks against the data, rerunning the
analyses, and checking the references against bibliographic records. Section numbers refer to the version 2.2 paper unless marked v3.

Severity: **E** error that changed results or made a statement false; **M** methodological weakness or
misdescription; **V** verified, no change needed.

## Errors

| # | Sev. | Finding | Cause | Fix | Effect |
|---|---|---|---|---|---|
| 1 | E | Roland Garros 2026 was in the sample, including its later rounds played in June 2026, although the paper said "no result from June 2026 onward is used" and the project seals that period. | The window was defined by `tourney_date ≤ 20260531`; Sackmann dates an edition by its start (25 May). | `LAST_DAY = 20260524` in `posthoc_big_match.py`; window and later period end there. | 241 matches removed (28 big). |
| 2 | E | Team events and exhibitions coded as ordinary tour events were analysed as main-tour matches, although Data said team events were excluded: ATP Cup and United Cup (both tours), World Team Cup (Düsseldorf round robin 2000–2012), Laver Cup. | Classification used Sackmann's level code (A, I) only. | `excluded_event()` by name. | ATP Cup/United Cup 532 matches (46 ATP big), World Team Cup 307, Laver Cup 58. |
| 3 | E | The Next Gen ATP Finals (under-21, sets to four games) were counted as "season-ending Finals", so every match was big; 2024–25 editions were coded best of five and entered the best-of-five calibration. | Level code F. | Excluded by name. | 118 matches (94 big). |
| 4 | E | Second-tier WTA year-end events (Tournament of Champions 2009–14, Elite Trophy 2015–19) were "Finals" (all matches big); the 2015 WTA Finals (code W) and 2023 ATP Finals (code A) were not. | Level code F used as the Finals rule. | `is_finals()` by event name; second-tier events treated as ordinary events. | WTA: 111 big → regular, among others; ATP 2023 Finals: 11 regular → big. |
| 5 | E | The WTA "Masters-level" tier was inconsistent across years: Premier Mandatory events are coded P in 2016 and 2020–2022 (their QFs were regular), from 2023 the PM code covers all WTA 1000 events, and Premier 5 events were never included, unlike ATP Masters. | Sackmann's level codes. | `WTA_TOP_TIER` by event and year (Tier I to 2008; Premier Mandatory + Premier 5 2009–20; WTA 1000 from 2021), verified against season records. | 311 WTA regular → big, together with item 4. |
| 6 | E | WTA 125 events (below the main tour) were included. | Level W covers some 125s. | Excluded by name. | 31 matches. |
| 7 | E | Holm's correction was applied only to the eight spread ratios, yet the abstract and discussion said the ATP clutch result (p = 0.044) "did not survive correction for multiple tests"; no adjusted p for it existed. | Code computed Holm on spread sets only. | Defined family: 9 trait statistics per tour × 2 tours = 18; Holm across all 18 (primary) and within tour; disclosed as chosen post hoc. | v3 ATP clutch spread p = 0.108, Holm 1.000. Smallest adjusted p 0.108. |
| 8 | E | Section 5.4 / discussion: "our forecasts calibrate big and regular matches separately". The live model (`models/phase4_tournament_start.json`, a logistic regression on Elo, form, rest and ranking features) has no big-match calibration or adjustment. Introduced in v2.1. | Drafting error. | Corrected; v3 §5.4 states what the live model does. | Statement only. |
| 9 | M | The "forecast test" fitted β, and the period calibration, on the same 2019–2026 matches it scored. Its permutation p-value is a valid association test, but it is not an out-of-sample forecast evaluation. | Design. | Relabelled "retrospective association"; added `posthoc_big_match_forecast.py` (chronological, every quantity fitted on earlier years). | New OOS results; no player score helps. |
| 10 | M | "Spread ratio", Figure 3's axis ("observed spread ÷ spread from luck") and the abstract ("varied 0.92 to 1.17 times as much as luck") described a **variance** ratio as a ratio of spreads. | Wording. | Called variance ratios throughout; Table 3 shows both sds and the ratio. | Wording. |
| 11 | M | "The implied reliability of a big-match record is below 0.2" / "at most 0.17" presented a Spearman–Brown point estimate as a maximum. | Wording. | v3 §4.3 calls it a point estimate with wide uncertainty and notes the equal-halves assumption. | Wording. |
| 12 | M | "Detected … in at least 100% of simulations" (v2.2 p. 13). | Template text. | Text switches to "essentially every simulation" when power ≥ 99.5%. | Wording. |
| 13 | M | The fixed shrinkage constant (k = 20) was described as empirical Bayes. | Terminology. | Described as fixed shrinkage chosen before the v1 run; an actual empirical Bayes variant added to the OOS test; sensitivity k = 10, 50, 100 kept. | EB variant gives no gain. |
| 14 | M | The calibration-slope Wald test assumed independent matches. | Model-based SE. | Edition-cluster bootstrap (2,000) and slopes by period. | WTA difference p 0.014 (Wald) → 0.016 (cluster); grows from −0.004 (2000–08) to −0.177 (2018–26). |
| 15 | M | Upper bounds came from linear interpolation on a coarse τ grid with 400 simulations per point, with no estimate of simulation error, and were interpreted as if unconditional. | Design. | τ = 0.35 added; Monte Carlo range from 1,000 resamples of the simulations; text states the model assumptions and that a bound is a population sd, not a per-player maximum. | ATP 7.1 (6.9–7.3), WTA 4.8 (4.6–5.0) points. |
| 16 | M | Game-margin permutations shuffled residuals across close and lopsided matches within a group, although their variances differ. | Design. | Stratified by decile of |Elo log-odds|, with stratum-level noise variance. | ATP game clutch p 0.022 (v2) → 0.027 (v3). |
| 17 | M | Several cited works were described inaccurately: Baumeister (1984) — choking was linked to pressure raising attention to one's own performance, and was more common among people *low* in dispositional self-consciousness; Efron & Morris (1975) — all 18 records had 45 at-bats, so "especially short records" was unsupported; Elo (1978) — the system predates the book; Miller & Sanjurjo (2018) — correcting the bias reverses the original conclusion; Cohen-Zada et al. (2017) — direction not stated (men choke more consistently). | Written from memory in v2. | Checked against Crossref, publisher and archive records; descriptions corrected or the citation dropped; DOIs added. | References now 18 (penalty-shoot-out and hot-hand papers removed as not directly relevant; Harris et al. 2021, Jetter & Walker 2015 and Paserman 2023 added). |
| 18 | M | The Sackmann repositories cited as the source return 404; the data were read from a mirror snapshot. | Upstream change. | Citation states the snapshot and mirror; README records SHA-256 of each input file. | Provenance. |
| 19 | M | Published results were produced from uncommitted code (on top of commit 4882aa0), so they could not be tied to a commit. | Workflow. | The forecast output now records whether the analysis files were committed; the paper says so when they were not. | Provenance. |

## Verified, no change needed

| # | Check | How |
|---|---|---|
| V1 | Elo uses only earlier information: ratings are frozen per tournament week, so no match sees its own result or any other result from that week. | `matchup_dna/elo.py::run_elo` (groups by `tourney_date`, applies the week's updates afterwards). |
| V2 | Each match is one observation; player-level statistics use the match twice with opposite-signed residuals. | `totals()` in the robustness script; match counts equal row counts. |
| V3 | Simulations draw one outcome per match, so the two players' results are complementary, and refit the calibration on every simulated data set. | `simulate()`, `window_tests()`, `period_tests()`. |
| V4 | The robustness implementation reproduces the main analysis to 1.8 × 10⁻¹⁵. | Section A of the robustness output. |
| V5 | The out-of-sample evaluation has no look-ahead. | Unit test flipping all results from 2013 on leaves 2012–2013 forecasts unchanged. |
| V6 | Every reported figure in the paper is rendered from the publisher's export; headline figures are asserted against outputs; prose claims are asserted at build time. | `web/publisher/research.py` (`HEADLINES`), `ensure()` in the page. |
| V7 | Licence of the source data (CC BY-NC-SA 4.0); data are not redistributed. | Archived README of the Sackmann repositories; repository contents. |
| V8 | The frozen live model and the prospective protocol are untouched; no file in `prospective.CODE_FILES` was edited. | `git status` on those paths. |

## Known limitations not fixed

- The bootstraps resample players or tournament editions, not both; dependence through shared players across editions
  is only partly captured.
- The simulation null holds the observed draw fixed and assumes no form or other player effects beyond Elo.
- Split-half halves have unequal length; Spearman–Brown is approximate.
- Players selected into big matches are in form that week; within-tournament ratings address this only for the 95%
  of big matches with complete earlier rounds.
- The multiple-testing family and the out-of-sample design were chosen after earlier results were known.
- WTA tier lists were verified against secondary season records (Wikipedia season pages and WTA tier articles), not
  official WTA documents.
