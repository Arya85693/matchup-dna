# Matchup DNA — ITF Extension: Model Report (Stages I2–I3)

**Date:** 10 November 2026  
**Status:** development and validation are done, and the held-out test has not run. This report stops at gate 2: the user approves the choices below before the protocol is frozen.  
**Question:** Can a model forecast ITF matches well, and do serve statistics help?  
**Answer, so far:** yes on both counts, on the validation half-year.

The chosen model, **M2**, scores a log loss of 0.5305 on July–December 2025 (18,535 matches, accuracy 73.2%). It beats:
- ranking alone, by 0.055;
- all-level Elo alone, by 0.013;
- the production main-tour model applied unchanged, by 0.093.

Adding serve and return profiles improves on the same model without them by 0.0020, with a 95% interval of 0.0016 to 0.0025.

The one-time test on January–June 2026 (14,118 matches) decides whether this holds.

## 1. What was built

| File | Role |
|---|---|
| `matchup_dna/itf_data.py` | Reads every Sackmann singles file through the seal: ITF, Challenger and qualifying, and main tour, from 2010. Applies the unmarked-retirement rule, the level tiers, and the repeated-row rule |
| `matchup_dna/itf_ratings.py` | One Elo pool across every level: Phase 2's replay plus three options (first rating, which matches move ratings, which predictions are kept) |
| `matchup_dna/itf_features.py` | Feature rows: Phase 3's row builder and Phase 4's serve-return profiles, imported unchanged |
| `matchup_dna/itf_model.py` | The five models, the scoring and the paired bootstrap |
| `matchup_dna/itf_experiment.py` | `rows`, `develop`, `validate`, and, behind the gates, `freeze` and `holdout --confirm` |
| `tests/test_itf_data.py`, `test_itf_ratings.py`, `test_itf_features.py`, `test_itf_experiment.py`, plus fixtures in `tests/itf_fixtures.py` | 36 tests, all on synthetic data |

**No locked file changed.** Where the ITF code needed an option that Phase 2–4 code lacks, it uses a copy, and a test checks the copy against the original:
- the Elo replay reproduces `elo.run_elo`'s predictions and ratings exactly;
- the history builder reproduces `features.player_history`;
- the profile replay reproduces `profiles.replay`.

The memory limits of the laptop shaped two choices: rating history starts in 2010, an 11-year warm-up, and serve lines are kept from 2015.

## 2. Data rules added in I2

1. **Unmarked retirements.** A "completed" ITF match whose winner did not win a majority of *finished* sets is a retirement, so it doesn't move the ratings. A set counts only when it is finished: 6 games with a 2-game lead, 7-5, 7-6, or a match tiebreak to 10 by 2.
   - The first version counted "3-0" as a set won, so "6-2 3-0" slipped through. Fixed and tested.
   - The rule catches 448 men's and 390 women's matches in 2025, as the audit predicted.
   - It applies to the ITF files only. The main-tour files hold short-set events (first to 4 games, such as the Next Gen Finals), whose finished matches it would misread.
2. **Exact repeats.** The women's ITF file repeats 1,138 rows exactly, all unscored WTA 125 and qualifying matches (all of 2014 Nanchang qualifying, for one). Each repeat is dropped so the match counts once. Two *different* rows with one key stop the load; none exist.
3. **Serve averages.** Profiles shrink toward ITF's own averages, from scored ITF matches in January–June 2025:

   | | Men | Women |
   |---|---:|---:|
   | Service points won, ITF | 59.0% | 53.4% |
   | Service points won, main tour (Phase 4) | 63.5% | 56.3% |

## 3. Development: the Elo variant

The variants were scored by the log loss of the plain Elo probability on development matches: 2021 to June 2025, 140,151 rated matches.

| Variant | Men | Women | Pooled |
|---|---:|---:|---:|
| Phase 2 (K 32, surface 48) | 0.5798 | 0.5746 | 0.5772 |
| **Decaying K (250 / (matches + 5)^0.4)** | **0.5725** | **0.5613** | **0.5668** |
| First rating from first rank | 0.5782 | 0.5736 | 0.5759 |

Decaying K wins clearly. ITF fields are full of players with short histories, and their ratings need to move fast. The L2 penalty, chosen inside development (fit before July 2024, scored on the year after), is 0 for both tours, so the models are unpenalised.

A dry run inside development (fit before July 2024, scored July 2024 to June 2025) checked every model end to end before validation was opened. It found no missing values and coefficients with the expected signs.

## 4. Validation: July–December 2025

Each model was fitted on development and scored on validation, once. About 90% of validation matches have serve history for both players.

| Model | Log loss | Brier | Accuracy | Calibration error |
|---|---:|---:|---:|---:|
| B0, rank only | 0.5852 | 0.2000 | 69.1% | 0.024 |
| B1, all-level Elo only | 0.5438 | 0.1833 | 72.0% | 0.009 |
| B2, production main-tour model, unchanged | 0.6240 | 0.2172 | 68.0% | 0.069 |
| M1, Elo + rank + rest + form + tier | 0.5326 | 0.1787 | 73.1% | 0.007 |
| **M2, M1 + serve and return** | **0.5305** | **0.1779** | **73.2%** | **0.004** |

The log loss of a coin flip is 0.693. Calibration error is the average gap between forecast and outcome, over ten probability bins.

**Paired comparisons** (log loss difference per match; the bootstrap resamples the 610 editions):

| Comparison | Difference | 95% interval |
|---|---:|---|
| **M2 − M1** (the pre-declared choice) | **−0.0020** | −0.0025 to −0.0016 |
| M2 − B0 | −0.0546 | −0.0600 to −0.0493 |
| M2 − B1 | −0.0133 | −0.0157 to −0.0109 |
| M2 − B2 | −0.0934 | −0.0999 to −0.0869 |

The rule declared in the I1 plan was to choose M2 only if its interval lies entirely below zero. It does, so **M2 is chosen**.

**By tour:**

| | B0 | B1 | B2 | M1 | M2 |
|---|---:|---:|---:|---:|---:|
| Men (8,788) | 0.5720 | 0.5517 | 0.6193 | 0.5343 | 0.5315 |
| Women (8,820) | 0.5983 | 0.5360 | 0.6286 | 0.5309 | 0.5296 |

**By tier** (log loss):

| | Matches | B0 | B1 | M1 | M2 |
|---|---:|---:|---:|---:|---:|
| M15 | 5,434 | 0.5864 | 0.5690 | 0.5476 | 0.5445 |
| M25 | 3,354 | 0.5486 | 0.5236 | 0.5126 | 0.5103 |
| W15 | 4,560 | 0.5955 | 0.5235 | 0.5170 | 0.5150 |
| W35 | 2,484 | 0.6002 | 0.5445 | 0.5407 | 0.5401 |
| W50 | 754 | 0.5945 | 0.5437 | 0.5386 | 0.5381 |
| W75 | 685 | 0.6157 | 0.5731 | 0.5690 | 0.5682 |
| W100 | 337 | 0.5961 | 0.5512 | 0.5525 | 0.5529 |

M2 is best in every tier except W100, the smallest at 337 matches, where Elo alone is slightly better.

**Calibration (M2, pooled):** forecasts and outcomes agree within about 1 percentage point in every bin. For example, 0.0–0.1 forecast 6.1% against 5.7% observed, 0.7–0.8 forecast 75.0% against 76.2%, and 0.9–1.0 forecast 93.7% against 93.9%.

### What the models learned

Coefficients per unit, fitted on development:

| | Men | Women |
|---|---:|---:|
| Elo log-odds | 0.359 | 0.574 |
| Surface Elo log-odds | 0.396 | 0.508 |
| log rank difference | −0.147 | −0.088 |
| Unranked difference | −0.312 | −0.072 |
| log days since last match | −0.167 | −0.078 |
| Form | 0.260 | 0.167 |
| Elo × tier | 0.027 | −0.064 |
| Serve (adjusted, logit) | 0.333 | 0.323 |
| Return (adjusted, logit) | 0.688 | 0.270 |
| No serve history | −0.229 | −0.186 |

**What stands out:**
- **Rank still matters next to Elo,** and being unranked costs a man much more than a woman.
- **Rating matters about equally at every tier.** The Elo × tier term is small.
- **Return counts for more than serve in the men's game.** In the men's model, the return coefficient is twice the serve one.

### Why the production model fails on ITF (B2)

Applied unchanged, the main-tour model is worse than ranking alone (0.6240 against 0.5852), and it is overconfident (calibration error 0.069). It sees ITF players through main-tour history, which almost none of them have. So most players sit at a 1500 rating, and its large coefficient on "no serve history" pushes forecasts around without information. This is the audit's finding, measured: ITF needs its own ratings and its own fit.

## 5. What happens next (the gates)

**Gate 2 (now): approve these choices.**
- Decaying-K Elo across every level.
- M2.
- L2 = 0 for both tours.
- The final fit: every model refitted on development and validation, meaning all ITF matches before 2026.

Then:
1. The user commits the code. `python -m matchup_dna.itf_experiment freeze` writes `experiments/itf_frozen_protocol.json`, which records the choices, the SHA-256 of every code file, and the split record's fingerprint. Freeze refuses if the code isn't committed.
2. The user commits the protocol. That lifts the seal: `itf_splits.unsealed()` checks the protocol is committed and names this split record.
3. **Gate 3:** `python -m matchup_dna.itf_experiment holdout --confirm` scores January–June 2026, once. It refuses to run twice, or if any code file differs from the protocol.

The held-out result will be added to this report as section 6, whatever it shows.

## Reproducing

```powershell
python -m matchup_dna.itf_splits check
python -m matchup_dna.itf_experiment rows        # about 5 minutes; results/itf/rows/
python -m matchup_dna.itf_experiment develop     # results/itf/development.json
python -m unittest discover -s tests -p "test_itf_*.py"
```

`validate` has run, and it refuses to run again. Its output is `results/itf/validation.json`, with per-match forecasts in `validation_predictions.csv`. `results/` is not in git.

## In ordinary language

The new ITF model rates every player using every match they've played at any level, from the smallest ITF events to the Grand Slams. The rating moves quickly while a player is new and settles as their record grows.

On top of that rating it uses ranking, recent form, rest, and, since 2025, how well each player serves and returns. On the second half of 2025, which it had never seen, it picks the winner 73% of the time, and its percentages are honest: when it says 75%, the player wins about 75% of the time.

The serve and return numbers help only a little, but reliably. The main-tour model, by contrast, does badly on ITF matches, because it doesn't know these players.

The real test, on the first half of 2026, is still locked. It runs once, after you approve.
