# Research summary (website / portfolio)

**Do Players Choke in Big Matches? Evidence from 26 Years of Professional Tennis**
Aryamaan Roy Choudhury · Independent research · Matchup DNA · Working paper v4.0, November 2026 (not peer reviewed)

**Question.** Matchup DNA forecasts ATP and WTA matches with an Elo-based model. Does a player's past record in big
matches (semi-finals, finals, late Grand Slam rounds) carry information the ratings miss, enough to justify a
player-specific "clutch" adjustment in the forecasts?

**Data.** 130,460 main-tour matches from 2000 to May 2026, 14,086 of them big matches (Jeff Sackmann's public
tennis data).

**Methods.** Calibrated Elo expectations; shrinkage-based player scores; variance-components and split-half
reliability tests; parametric-bootstrap null distributions with Holm correction; power simulations and upper bounds on
the size of a trait; and a chronological out-of-sample evaluation in which every forecast uses only earlier data,
with a cluster bootstrap over tournaments.

**Findings.**
- Players' big-match results vary about as much as chance predicts, and no trait test is significant after
  correcting for 18 tests.
- Adding a player's past big-match or clutch score did not improve out-of-sample forecasts of 7,476 later big matches
  (log-loss changes of +0.00003 and +0.00007, with intervals including zero).
- One tour-level pattern holds up: Elo is more overconfident in WTA big matches than in regular WTA matches, and
  calibrating them separately slightly improved out-of-sample WTA forecasts.

**Decision.** No player-specific big-match adjustment in the forecasting model. The WTA calibration pattern is a
candidate for a future, pre-specified model version.

**Limitations.** Post-hoc analysis; a modest trait (up to about 7 percentage points at even odds on the ATP tour,
under the simulation model) cannot be ruled out; pressure itself is not observed.

**Links.** Full paper: `/research/big-matches` (PDF: `/research/big-matches.pdf`) · Code and reproduction steps:
`docs/research/big-matches/README.md` in the repository *(add the public repository URL here)*.

---

## Resume bullet

Led an independent statistical study of "clutch" performance across 130,460 professional tennis matches
(Python, NumPy): calibrated Elo baselines, shrinkage estimators, simulation-based hypothesis tests with multiple-testing
correction and power analysis, and a leakage-tested out-of-sample evaluation, which showed that player-specific
big-match adjustments do not improve forecasts. Published as a reproducible working paper.

*(Shorter: Built a reproducible Python/NumPy analysis of 130K tennis matches testing whether "clutch" performance
predicts results; simulation tests, power analysis and out-of-sample evaluation showed no forecasting gain, so the
adjustment was kept out of the production model.)*
