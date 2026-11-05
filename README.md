# Matchup DNA

**Status: Phase 0 complete · Phase 1 next — local Python program**

Matchup DNA is a long-term machine-learning and quantitative research project on professional tennis. It will start as a small local Python program and grow into a public site that serves match probabilities, player profiles, historical model evaluations, and, later, live match analysis.

The repository holds the project brief, the Phase 0 feasibility report, and this README. There is no program to install or run yet.

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

Nothing to run yet. When Phase 1 exists, this section will say how to install dependencies, which data file to use, and what command starts the program.
