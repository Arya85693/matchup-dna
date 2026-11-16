# Do Players Choke in Big Matches? — research materials

Working paper 1 of Matchup DNA, version 4.0 (16 November 2026). Author: Aryamaan Roy Choudhury. Post-hoc, not peer
reviewed. The paper is on the website's Research tab (`/research/big-matches`, source
`web/app/research/big-matches/page.tsx`) and as a PDF (`web/public/research/big-matches.pdf`).

This folder:

| File | What it is |
|---|---|
| `README.md` | This file: question, method, findings, limitations, and how to reproduce everything. |
| `AUDIT.md` | The version 3 audit: what was checked, what was wrong, what was fixed. |
| `CHANGELOG.md` | What changed from version 2.2 to 3.0 (statistical, editorial, numerical) and from 3.0 to 3.1 (attribution) and 3.1 to 4.0 (corrections). |
| `ORIGINALITY_AUDIT.md` | The originality, citation and attribution audit of version 3.0. |
| `ATTRIBUTION.md` | How version 3.1 acts on that audit: citations added, established methods, contributions, open items. |
| `SUMMARY.md` | A short summary for the website and a portfolio, and a resume bullet. |
| `AUTHOR_CHECKLIST.md` | What the author should understand and check personally before publishing. |

## The question

Matchup DNA forecasts ATP and WTA matches with a frozen model built on Elo ratings. Does a player's past record in big
matches (semi-finals, finals, Grand Slam fourth rounds and quarter-finals, quarter-finals at the top non-Slam tier, and
the season-ending Finals) carry information the ratings miss, enough to justify a player-specific adjustment?

## What was done

1. **Expectation.** Surface-blended Elo, frozen per tournament week, rescaled by one calibration slope per (tour, big
   or regular, best of three or five).
2. **Scores.** Residual = result − calibrated probability. Big-match score = residual sum / (n + 20) (fixed shrinkage);
   clutch score = big-match score − regular-match score.
3. **Trait tests.** Variance of players' mean residuals against binomial chance (variance ratios); split-half
   agreement; carry-over from 2012–2018 to 2019 – May 2026; a retrospective association test.
4. **Inference.** Parametric-bootstrap null (2,000 simulations, calibration refitted), Holm's correction across 18
   trait statistics, power curves and 95% upper bounds from simulations with an injected trait (400 per trait size,
   with a Monte Carlo range on each bound).
5. **Out-of-sample forecasts.** Every big match from 2012 to May 2026 predicted from earlier calendar years only:
   calibration, scores and the coefficient β all fitted on the past. Baselines with and without the big-match
   calibration, and player-score models (fixed shrinkage, empirical Bayes, last five years). Paired log-loss and Brier
   differences with a tournament-edition cluster bootstrap.
6. **Calibration.** Big- vs regular-match slopes with Wald and edition-cluster bootstrap tests, and by period.
7. **Robustness.** Game margins, within-tournament ratings, the ATP format split, and sensitivity to shrinkage,
   minimum matches, big-match definition and period split.

## Findings (version 3)

- 130,460 main-tour matches from 2000 to 24 May 2026, 14,086 of them big.
- Big-match variance ratios 0.93–1.16 (1 = chance); split-half r = 0.12 (ATP) and 0.04 (WTA), both intervals include 0.
- No trait statistic is significant after Holm's correction (smallest adjusted p 0.108: the WTA big-match association,
  which disappears once regular-match form is removed).
- Out of sample (7,476 big matches): the big-match score changed log loss by +0.00003 and the clutch score by +0.00007
  versus the baseline; every player-score interval includes zero.
- 95% upper bounds on the trait's standard deviation, under the simulation model: 7.1 points (ATP) and 4.8 points
  (WTA) at even odds. A modest trait is not ruled out.
- Elo is more overconfident in WTA big matches (slope 0.755 vs 0.821; cluster bootstrap p = 0.016), the gap is largest
  in 2018–2026, and separate WTA big-match calibration improved out-of-sample WTA big-match log loss by 0.00089 (95%
  interval 0.00030 to 0.00148).
- Decision: no player-specific big-match adjustment for the forecasting model. The live model is frozen and unchanged;
  a tour-level WTA adjustment would have to be pre-specified and tested prospectively as a new version.

## Limitations

Post-hoc (the multiple-testing family and several checks were chosen after earlier results were known). The bounds
assume a normal, career-constant trait confined to the defined big matches. Few players have long records in both
periods (26 ATP, 32 WTA). The simulation null holds the observed draw fixed and assumes no player differences beyond
Elo, including form. Bootstraps resample players or editions, not both. Pressure itself is never observed.

## Reproducing the analysis

### Data

Jeff Sackmann's `tennis_atp` and `tennis_wta` match files, licensed CC BY-NC-SA 4.0 (non-commercial, attribution,
share-alike). The original repositories at github.com/JeffSackmann returned 404 on 16 November 2026; this analysis read
a June 2026 snapshot from the archive mirror github.com/Aneeshers/tennis-sackmann-archive. Place the files as the
project README describes (`data/atp/atp_matches_YYYY.csv`, `data/wta/wta_matches_YYYY.csv`). The data are not in this
repository and must not be redistributed outside the licence.

The SHA-256 of every input file used (118 files, 1968–2026) is recorded in
`results/phase4/experiments/posthoc_big_match_forecast.json` under `provenance.data_files`; their combined
fingerprint is `3910dc824f72926f464dfabc0932a1757a16c9ede186d142ca77a8a1ab0c64fe`. A rerun on different files will
produce different numbers, and the publisher check below will then refuse.

Matches from tournaments starting on or after 25 May 2026 (Roland Garros 2026 onwards) are not used: they overlap the
project's sealed June 2026+ period.

### Environment

- Python 3.13.7, numpy 2.3.0 (`pip install -r requirements.txt`; the analysis needs only numpy).
- For the website and the PDF: Node and the packages in `web/package.json` (`npm ci` in `web/`), and Google Chrome
  (Playwright drives the installed Chrome; pass `--channel chromium` after `npx playwright install chromium` if Chrome is
  not installed).

### Commands (from the repository root)

| Step | Command | Time | Seed |
|---|---|---|---|
| Main analysis (definitions, trait tests, named players) | `python -m matchup_dna.posthoc_big_match` | ~30 s | 20261114 |
| Simulations, power and bounds, game margins, within-tournament, sensitivity, format | `python -m matchup_dna.posthoc_big_match_robustness` | ~40 min | 20261115 (format: 20261116) |
| Extreme-record player tables | `python -m matchup_dna.posthoc_big_match_players` | ~30 s | none |
| Calibration tests and out-of-sample evaluation | `python -m matchup_dna.posthoc_big_match_forecast` | ~1 min | 20261116 |
| Export the figures for the paper | `python -m web.publisher.research` | seconds | — |
| Tests | `python -m pytest tests/test_posthoc_big_match*.py` | seconds | — |

Run the main analysis first: the robustness script checks that it reproduces the main analysis's point estimates.
Outputs go to `results/phase4/experiments/posthoc_big_match*.{json,txt}` (local, not committed). The publisher writes
`web/content/research/big-match.json` (committed), which is the only file the paper reads.

### What is checked automatically

- The robustness script must reproduce the main analysis's point estimates (largest difference in the version 3 run:
  1.8 × 10⁻¹⁵) or the publisher refuses.
- The publisher asserts the headline figures quoted in the abstract, this README and the summary (`HEADLINES` in
  `web/publisher/research.py`) against the analysis outputs, and refuses to export if any differ.
- Every other number in the paper is rendered from `big-match.json`; nothing is typed by hand.
- The paper's page asserts its qualitative claims at build time (`ensure(...)` in the page source, for example "every
  player-score interval includes zero"); the website build fails if a rerun breaks one.
- `tests/test_posthoc_big_match_forecast.py` checks that flipping every result from a given year on leaves the
  out-of-sample forecasts for earlier years unchanged (no look-ahead), and that every model scores the same matches.
- `tests/test_posthoc_big_match.py` checks the match classification rules (WTA tiers by year, Finals by name, excluded
  events).

### The website and the PDF

```
cd web
npm run build
npx next start -p 3123          # leave running
npm run paper:pdf               # in a second terminal: writes public/research/big-matches.pdf
```

## Status

Exploratory and post-hoc. Not pre-registered and not peer reviewed. It does not touch the frozen live model or the
prospective forecast record.
