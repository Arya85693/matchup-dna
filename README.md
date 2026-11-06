# Matchup DNA

**Status: Phases 0–4 complete — local Python program**

Matchup DNA is a long-term machine-learning and quantitative research project on professional tennis. It will start as a small local Python program and grow into a public site that serves match probabilities, player profiles, historical model evaluations, and, later, live match analysis.

The repository holds the project brief, the Phase 0 feasibility report, the Phase 1 program, and the Phase 2 rating engine. Phase 1 loads the Sackmann tour-level singles files, validates them, and compares two players using only matches from earlier tournament weeks. Phase 2 replays those matches in date order to build Elo and surface-adjusted Elo ratings, and scores their win probabilities on matches held out from tuning. The results are in [Phase 2 - Elo Report.md](Phase%202%20-%20Elo%20Report.md), in time order from the 1968 warm-up to 2023, with ATP and WTA shown separately at each stage. Phase 3 builds a pre-match feature dataset split into training (2010–2020), validation (2021–2023), and reserved (2024–May 2026) rows, chooses a model on validation, and scores that frozen model once on the reserved rows. The results are in [Phase 3 - Model Report.md](Phase%203%20-%20Model%20Report.md). Phase 4 adds point-in-time serve and return profiles, matchup interactions, and a round-aware track for workload and route difficulty. It tests them with the same keep rule, and prepares a one-time test on June–October 2026 matches from two newer sources. The sources are audited in [Phase 4 - Data Audit.md](Phase%204%20-%20Data%20Audit.md), and the results are in [Phase 4 - Matchup Intelligence Report.md](Phase%204%20-%20Matchup%20Intelligence%20Report.md).

## Purpose

The work follows one path:

**Raw data → validated information → statistical features → predictive models → probabilities → quantitative signals → historical evaluation → decision support**

Three capabilities are meant to stay connected as the project grows:

- **Machine learning.** Estimate the probability that one player beats another from information available before the match, including surface and matchup-specific features.
- **Quantitative research.** Compare those probabilities with market-implied probabilities, test them in chronological backtests, and report uncertainty.
- **Software engineering.** Ingest data, store it, serve predictions, and publish them on a site that updates without manual work.

The planning document in this repository is [Matchup DNA - Resume Project.pdf](Matchup%20DNA%20-%20Resume%20Project.pdf) (version 1.0, October 29, 2026). The Phase 0 audit is [Phase 0 - Feasibility Report.md](Phase%200%20-%20Feasibility%20Report.md) (3 November 2026).

## What a finished version should let someone do

A visitor should be able to open the site, see upcoming matches with model probabilities, compare two players, read a player profile, and inspect how past predictions performed. Later phases add market-discrepancy research and in-play probabilities that update from real score states.

Predictions are research outputs. The project records them before a match starts and keeps that record after the result is known.

## Build order

Each phase is finished only when its completion standard in the brief is met. Later phases wait on the ones they depend on.

| Phase | Focus |
|---|---|
| 0 | Audit historical and live sources: fields, coverage, licenses, cost, and player-identity matching |
| 1 | Local Python program for basic match statistics and data handling |
| 2 | Chronological Elo ratings, then surface-adjusted Elo if it beats the baseline |
| 3 | Point-in-time features and a supervised model compared with that baseline |
| 4 | Matchup features, tested for whether they improve predictions, plus interpretable reports |
| 5 | Market-odds comparison, signals, and paper backtests |
| 6 | PostgreSQL storage and a Python API |
| 7 | Public website MVP |
| 8 | Scheduled updates for fixtures, results, and new predictions |
| 9 | In-play win probabilities from incoming match states |
| 10 | Deeper research and product work justified by data, cost, and results |

Near-term progress through the end of 2026 is Phases 0–3: verified data, a clean Python pipeline, a baseline rating system, and a first predictive experiment. The public site is later work.

## Candidate data sources

These sources were identified in October 2026 and audited on 3 November 2026. The feasibility report records fields, coverage, licenses, cost, and the player-identity result. Phase 1 uses the Sackmann tour-level singles files.

| Role | Source | Notes |
|---|---|---|
| Historical ATP/WTA results | [Jeff Sackmann archive mirror](https://github.com/Aneeshers/tennis-sackmann-archive) | CC BY-NC-SA 4.0. Results through a June 2026 snapshot. Grand Slam point-by-point data for 2011–2024. |
| Shot-level research | [Tennis Abstract Match Charting Project](https://github.com/JeffSackmann/tennis_MatchChartingProject) | CC BY-NC-SA 4.0. Later research, not required to start. |
| Historical odds | [Valuebetennis open data](https://www.valuebetennis.com/en/donnees.htm) | CC BY 4.0. ATP and WTA matches from January 2021, with opening and closing odds. |
| Live fixtures and scores | [Live Tennis API](https://livetennisapi.com/) and [SportsAPI365](https://docs.tennis-api.com/getting-started) | Candidates only. Provider choice waits on real API responses and usage terms. |

Sackmann-derived datasets need an attribution and licensing review before they appear in a public deployment. Opening odds and closing odds are separate timestamps and will be treated that way.

## Working rules

- A historical prediction may use only information that existed at that prediction time.
- Models are trained on earlier matches and evaluated on later ones.
- Elo and other simple baselines come before more complex models, and a more complex model stays only if it improves on them.
- Probabilities are checked for calibration. A high winner-pick rate is not enough.
- Every feature, score, and model version needs a definition that can be explained and reproduced.
- The first versions stay on free, local tools. Paid data is added only after the core model works and the cost solves a specific gap.

## Running the project

Phases 1 and 2 and the Phase 3 dataset need Python 3.10 or newer and no installed packages. The Phase 3 experiments need the pinned packages in `requirements.txt`: numpy and LightGBM, plus scikit-learn, which only the tests use. Install them with `pip install -r requirements.txt`.

### Data

The match data is compiled by [Jeff Sackmann](https://github.com/JeffSackmann) ([tennis_atp](https://github.com/JeffSackmann/tennis_atp), [tennis_wta](https://github.com/JeffSackmann/tennis_wta)) and used under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). It is not stored in this repository.

1. Download the [archive mirror](https://github.com/Aneeshers/tennis-sackmann-archive) as a ZIP (green **Code** button, then **Download ZIP**) and extract it.
2. Copy its `atp` and `wta` folders into `data/`, so that `data/atp/atp_matches_2024.csv` and `data/wta/wta_players.csv` exist.

The program reads only `atp_matches_YYYY.csv`, `wta_matches_YYYY.csv`, `atp_players.csv`, and `wta_players.csv`. Futures, qualifying, ITF, doubles, amateur, and rankings files are left unread.

### Commands

Run these from the project folder.

```powershell
python compare.py ATP 206173 ATP 104925 20240115
```

Compares Jannik Sinner and Novak Djokovic using every match from tournament weeks before 15 January 2024. The arguments are two tour-and-id pairs and a date as `YYYYMMDD`. Add `--list Clay` (or `Hard`, `Grass`, `Carpet`, `All`) to print the completed matches behind each surface record.

```powershell
python -m matchup_dna.validate
```

Prints the data-quality report: duplicate match keys, player ids missing from the player files, rows where winner and loser are the same id, surfaces, outcomes, and best-of counts.

```powershell
python rate.py ATP 206173 ATP 104925 20240115
```

Elo and surface Elo ratings for Sinner and Djokovic from tournament weeks before 15 January 2024, and the probability that the first player wins on each surface. Both players must be on the same tour.

```powershell
python -m matchup_dna.elo
```

Writes every rated player's final Elo and surface Elo ratings to `results/final_ratings.csv` and prints the top 10 active players on each tour.

```powershell
python -m matchup_dna.evaluate
```

Runs the Phase 2 experiment: tunes K and the surface weight on 1990–2009, then scores the chosen models on each period up to 2023 for ATP, WTA, and both tours. It writes the 2010–2023 predictions to `results/phase2_development_predictions.csv`. It does not replay or score weeks from 1 January 2024 on. Takes about a minute and a half.

```powershell
python -m matchup_dna.features
```

Builds the Phase 3 dataset in `results/phase3/`: `train.csv`, `validation.csv`, and `reserved_features.csv`. It checks the date boundaries and the label rule before writing, and stops if either fails. Takes about half a minute.

```powershell
python -m matchup_dna.experiment calibration
python -m matchup_dna.experiment elo-lr
python -m matchup_dna.experiment features
python -m matchup_dna.experiment gbm
python -m matchup_dna.experiment same-k
```

These are the Phase 3 experiments, run in this order:
- temperature scaling;
- logistic regression on Elo;
- feature selection;
- LightGBM;
- the same-K diagnostic.

They read only the training and validation files. Each writes its output and a manifest to `results/phase3/experiments/` and appends to `experiments/log.md`.

`python -m matchup_dna.experiment freeze` writes `experiments/frozen_protocol.json` and refuses to overwrite an existing one.

`python -m matchup_dna.experiment final --protocol experiments/frozen_protocol.json --confirm` runs the one reserved-period evaluation into `results/phase3/final/`. It refuses to run a second time.

#### Phase 4

Phase 4 also reads TennisData.app season files from `data/external/tennisdata_app/` and TennisIsMyLife files from `data/external/tennisismylife/`. Both are private, gitignored, and read only through sealed readers that hide every result from 1 June 2026 on.

```powershell
python -m matchup_dna.audit_tennisdata          # TennisData.app audit
python -m matchup_dna.audit_tennisismylife      # TennisIsMyLife audit and overlap
python -m matchup_dna.audit_workload            # workload and route-difficulty feasibility
python -m matchup_dna.phase4_experiment profiles      # tune serve-return profiles (no outcomes)
python -m matchup_dna.phase4_experiment dataset       # Phase 4 rows; checks Phase 3's frozen hashes
python -m matchup_dna.phase4_experiment tournament    # tournament-start forward selection
python -m matchup_dna.phase4_experiment gbm           # LightGBM comparison
python -m matchup_dna.phase4_experiment round-aware   # workload and route-difficulty track
python -m matchup_dna.phase4_experiment rehearse      # held-out pipeline rehearsed on open 2026 data
python -m matchup_dna.phase4_experiment verify        # reproducibility and leakage checks before the freeze
python -m matchup_dna.phase4_experiment freeze --dry-run
python explain.py ATP 206173 ATP 104925 20260525 --surface Clay --best-of 5
```

`freeze` writes `experiments/phase4_frozen_protocol.json`, never overwrites it, and refuses while code has uncommitted changes. `retrospective` and `holdout --confirm` each run once, and only after three conditions hold:
- the protocol is committed;
- every input it hashed is unchanged;
- the code is identical to the commit it recorded.

```powershell
python -m unittest discover -s tests
```

Runs the tests. The test that counts every match is skipped when `data/` is missing.

### Code

| File | What it does |
|---|---|
| `matchup_dna/load.py` | Reads the CSVs into match records and a player lookup, normalizes surfaces, and classifies each score |
| `matchup_dna/validate.py` | Builds and prints the data-quality report |
| `matchup_dna/stats.py` | Builds a player's record from matches before a date |
| `matchup_dna/elo.py` | Elo probability and update, the week-by-week replay, the chosen K and surface weight, and the final-ratings export |
| `matchup_dna/periods.py` | The warm-up, tuning, training, validation, and reserved date boundaries |
| `matchup_dna/evaluate.py` | Log loss, Brier score, accuracy, calibration, standard errors, exclusions, and the tuning and 2010–2023 experiment |
| `matchup_dna/features.py` | Pre-match feature rows, player history (days since last match, form, overlap flag), the three Phase 3 splits, the split checks, and the loader that refuses reserved rows |
| `matchup_dna/model.py` | Model features, missing-value handling, and the no-intercept logistic regression fitted by Newton's method with L2 |
| `matchup_dna/calibrate.py` | Temperature and Platt scaling |
| `matchup_dna/experiment.py` | Experiments A–D, the keep rule, LightGBM, the same-K diagnostic, the protocol freeze, and the final evaluation |
| `requirements.txt` | Pinned numpy, LightGBM, and scikit-learn versions |
| `experiments/` | Run log and the frozen protocol |
| `results/archive_do_not_use/` | First Phase 2 run's predictions, which include 2024–2026 outcomes, kept out of all Phase 3 code |
| `matchup_dna/tennisdata.py`, `matchup_dna/tennisismylife.py` | Sealed readers for the two newer sources |
| `matchup_dna/crosswalk.py`, `matchup_dna/merge.py`, `matchup_dna/heldout.py` | Player and match linking, source precedence, and the held-out period |
| `matchup_dna/serve_stats.py`, `matchup_dna/profiles.py` | Statistic validity rules and point-in-time serve-return profiles |
| `matchup_dna/workload.py`, `matchup_dna/round_aware.py` | Match workload, round chronology, route difficulty, round-aware Elo |
| `matchup_dna/phase4_features.py`, `matchup_dna/phase4_model.py`, `matchup_dna/selection.py`, `matchup_dna/phase4_experiment.py` | Phase 4 dataset, features, model, selection, and commands |
| `matchup_dna/audit_*.py` | The three Phase 4 audits |
| `matchup_dna/matchup.py`, `matchup_dna/interpret.py`, `explain.py` | The matchup report |
| `compare.py` | Command-line comparison of two players |
| `rate.py` | Command-line ratings and win probability for two players |
| `tests/test_stats.py` | Hand-countable cases for the date rule, outcomes, and serve rates |
| `tests/test_elo.py` | Hand-computed Elo updates, the weekly freeze, skipped outcomes, tours, and surfaces |
| `tests/test_evaluate.py` | Hand-computed metric values, standard errors, exclusion reasons, and the ranking baseline |
| `tests/test_periods.py` | Period boundaries, with no gaps or overlaps |
| `tests/test_features.py` | No same-week or future information in features, outcome-blind player order, player history, split boundaries, the reserved label rule, and the loader |
| `tests/test_model.py` | Logistic fit against scikit-learn, antisymmetry, and preprocessing fitted on fitting rows only |
| `tests/test_calibrate.py` | Temperature and Platt scaling |
| `tests/test_experiment.py` | Keep rule, scoring, and the final command's guard |

`predict.py` is an empty placeholder.

### Definitions

- **Player key:** tour plus Sackmann `player_id`. ATP and WTA ids overlap and refer to different people.
- **Match key:** tour, `tourney_id`, `match_num`, and `round`. A few older WTA events reuse a `match_num` in two rounds, so `round` is needed for the key to be unique.
- **Time:** `tourney_date` is the Monday of the tournament week. A record as of a date uses only matches whose `tourney_date` is strictly earlier, so matches from that same week are excluded.
- **Outcome:** read from the score text. `RET` is a retirement. `W/O` or `Walkover` is a walkover. `DEF`, `Def.`, or `Default` is a default. `ABD`, `ab`, `Played and abandoned`, or `Played and unfinished` is abandoned. An empty score, `UNK`, `NA`, or `&nbsp;` is unknown. Anything else is completed.
- **Win-loss:** the main record and the surface splits count completed matches only. Retirements, walkovers, defaults, abandoned matches, unknown scores, and best-of-1 matches are counted separately, as wins and losses for that player.
- **Serve rates:** summed over completed and retired matches where the player's serve points are present and above zero. First serve in is first serves made divided by serve points; ace rate is aces divided by serve points. A rate with no serve points is shown as `n/a`.
- **Last rank:** the player's rank on their most recent earlier match that has one, with that match's tournament date.
- Rows where the winner id equals the loser id (4 rows, mostly placeholder "Unknown" players) are reported by validation and left out of player records.
- **Elo:** every player starts at 1500 overall and on each surface. Only completed best-of-3 and best-of-5 matches move ratings. A tournament week is predicted with start-of-week ratings, and its results are applied together afterwards. Surface Elo predicts from the average of the overall and surface ratings. The full definitions are in the Phase 2 report.
- **Periods:** by `tourney_date`. Warm-up before 1990, tuning 1990–2009, Phase 3 training 2010–2020, Phase 3 validation 2021–2023, and reserved from 1 January 2024. Ratings update through every period with the fixed Phase 2 settings. The reserved period's outcomes are not used to train, calibrate, tune, or choose a Phase 3 model, and are scored once at the end.
- **Phase 3 rows:** one per rated match from 2010 on. Player A is chosen by a hash of the match key and both player ids, so the choice does not depend on who won, and `a_won` is the label. Each row has `match_id` (tour, `tourney_id`, `match_num`, round), the week, period, tour, level, surface, round, and best-of. It also has both players' ids and names, start-of-week Elo, surface Elo overall, surface and blended ratings, matches played, the A-minus-B differences, both models' probabilities for A, and both ranks as of the tournament date. It also has each player's days since their last played match, their form (mean result minus Elo expectation over the last 10 rated matches), and an overlap flag for a previous event that may still have been running. Reserved rows have no `a_won` column.

### Validation results

Run on the June 2026 snapshot: 361,571 matches (199,389 ATP, 162,182 WTA), 137,483 players, no duplicate match keys, no missing player ids, and 4 rows with the same winner and loser id. Outcomes: 351,517 completed, 6,960 retired, 2,572 walkovers, 192 defaults, 46 abandoned, and 284 with an unknown score.

The walkover and abandoned counts are higher than the Phase 0 report's 2,566 and 23. That report counted only the `W/O` and `ABD` spellings. Six Davis Cup walkovers are written `Walkover`, and 23 further rows are written `Played and abandoned`, `Played and unfinished`, or `ab`.
