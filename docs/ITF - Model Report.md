# Matchup DNA — ITF Extension: Model Report (Stages I2–I3)

**Date:** 10 November 2026  
**Status:** complete. The protocol was frozen at 2026-11-11T04:34:31Z (`experiments/itf_frozen_protocol.json`, committed in d4ef8c8), and the held-out test ran once afterwards (section 6).  
**Question:** Can a model forecast ITF matches well, and do serve statistics help?  
**Answer:** yes on both counts, on matches nothing had seen.

On January–June 2026 (13,537 rated matches), the chosen model, **M2**, scores a log loss of 0.5505 with 71.4% accuracy. It beats:
- ranking alone, by 0.042;
- all-level Elo alone, by 0.012;
- the production main-tour model applied unchanged, by 0.085.

Serve and return profiles improve on the same model without them by 0.0011, with a 95% interval of 0.0006 to 0.0017. Every interval excludes zero. The improvements hold for both tours and in every tier.

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

## 5. The freeze (gates 2 and 3)

**Gate 2.** The user approved the choices above and committed the code (abf8a18):
- decaying-K Elo across every level;
- M2;
- L2 = 0 for both tours;
- the final fit: every model refitted on development and validation, meaning all ITF matches before 2026.

`freeze` then wrote `experiments/itf_frozen_protocol.json` at 2026-11-11T04:34:31Z. It records:
- those choices;
- the SHA-256 of all 18 code and model files the test depends on;
- the source commit;
- the fingerprints of the split record and of the development and validation results.

**Gate 3.** The user committed the protocol (d4ef8c8), which lifted the seal. `holdout --confirm` then ran once. It rebuilt the rows with 2026 included and refitted each model on all matches before 2026: 78,299 men's and 79,460 women's rows. It then scored the held-out half-year. It refuses to run again.

## 6. The held-out test: January–June 2026

13,537 rated matches (6,590 men's, 6,947 women's) from 458 editions. The other 581 scored matches in the split were retirements or walkovers, which aren't rated. 94.8% of these matches have serve history for both players.

| Model | Log loss | Brier | Accuracy | Calibration error |
|---|---:|---:|---:|---:|
| B0, rank only | 0.5921 | 0.2032 | 68.4% | 0.017 |
| B1, all-level Elo only | 0.5629 | 0.1911 | 70.4% | 0.011 |
| B2, production main-tour model, unchanged | 0.6351 | 0.2223 | 66.9% | 0.066 |
| M1, without serve | 0.5517 | 0.1866 | 71.3% | 0.011 |
| **M2, chosen** | **0.5505** | **0.1862** | **71.4%** | **0.012** |

**Paired comparisons** (bootstrap over the 458 editions):

| Comparison | Difference | 95% interval |
|---|---:|---|
| **M2 − B0** (rank only) | **−0.0416** | −0.0472 to −0.0362 |
| **M2 − B1** (Elo only) | **−0.0124** | −0.0150 to −0.0099 |
| **M2 − B2** (production model) | **−0.0846** | −0.0917 to −0.0773 |
| M2 − M1 (serve features) | −0.0011 | −0.0017 to −0.0006 |

**By tour:**

| | B0 | B1 | B2 | M1 | M2 | M2 accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Men (6,590) | 0.5789 | 0.5700 | 0.6267 | 0.5508 | 0.5495 | 71.7% |
| Women (6,947) | 0.6046 | 0.5562 | 0.6431 | 0.5525 | 0.5514 | 71.1% |

**By tier** (log loss):

| | Matches | B0 | B1 | B2 | M1 | M2 |
|---|---:|---:|---:|---:|---:|---:|
| M15 | 4,163 | 0.5934 | 0.5878 | 0.6359 | 0.5648 | 0.5635 |
| M25 | 2,427 | 0.5541 | 0.5394 | 0.6108 | 0.5267 | 0.5257 |
| W15 | 3,065 | 0.6076 | 0.5504 | 0.6482 | 0.5488 | 0.5475 |
| W35 | 2,050 | 0.5909 | 0.5455 | 0.6315 | 0.5407 | 0.5400 |
| W50 | 638 | 0.6079 | 0.5626 | 0.6570 | 0.5552 | 0.5551 |
| W75 | 867 | 0.6098 | 0.5752 | 0.6398 | 0.5690 | 0.5674 |
| W100 | 327 | 0.6429 | 0.6137 | 0.6496 | 0.6128 | 0.6102 |

M2 has the lowest log loss in every tier, including W100, where validation had it slightly behind Elo alone.

**Calibration (M2):**

| Forecast bin | Matches | Forecast | Observed |
|---|---:|---:|---:|
| 0.0–0.1 | 831 | 6.2% | 7.5% |
| 0.1–0.2 | 1,335 | 15.0% | 15.4% |
| 0.2–0.3 | 1,450 | 25.0% | 23.4% |
| 0.3–0.4 | 1,523 | 35.2% | 35.5% |
| 0.4–0.5 | 1,608 | 45.0% | 45.8% |
| 0.5–0.6 | 1,639 | 55.1% | 54.4% |
| 0.6–0.7 | 1,539 | 65.1% | 62.6% |
| 0.7–0.8 | 1,441 | 75.0% | 73.4% |
| 0.8–0.9 | 1,325 | 84.9% | 82.6% |
| 0.9–1.0 | 846 | 93.8% | 93.5% |

Most bins agree within 1–2 points. Strong favourites (60–90%) won about 2 points less often than forecast, so the model is slightly overconfident there in 2026, which it wasn't in 2025.

### Reading the result

- **The conclusions hold on unseen matches.** The ordering is the same as on validation, and every pre-declared comparison has an interval that excludes zero.
- **Every model scores worse in 2026 than in 2025**, including the simple baselines: Elo alone goes from 0.5438 to 0.5629. So January–June 2026 is a harder period, not a sign that M2 overfitted. The gaps between models are about the same size as before. M2's lead over Elo alone, for example, is 0.0124 against 0.0133 on validation.
- **The serve gain shrank** from 0.0020 to 0.0011, but it is still clearly above zero. It's small: about a tenth of what the all-level ratings add over ranking.
- **The production main-tour model is again the worst,** behind ranking alone. ITF forecasts need the ITF model.
- **Limits.** This is one half-year of one data snapshot. The slight overconfidence in 2026 is worth watching in any live use.

**Files:** `results/itf/holdout.json` holds the summary and `results/itf/holdout_predictions.csv` the per-match forecasts for every model. Both are in `results/`, which is not in git. The protocol's fingerprint is recorded in the summary.

## 7. What comes next

The model is finished and tested. Live ITF forecasts (stages I4–I6) use Flashscore for fixtures and results (see the I1 report, section 3).

**The live model is M1, not M2.** M2 needs serve counts that keep arriving. Sackmann's data ends in June 2026, and Flashscore's ITF matches carry no serve statistics. This was checked on 11 November 2026 on finished M15 and W35 matches, which have only "last 10 points" and "match points saved".

Live, M2 would face three problems:
- its serve profiles would stop following form;
- every player's profile would drift toward the ITF average;
- every player who began after June 2026 would be treated as having no serve history.

That is a set of inputs unlike anything it was tested on. M1 uses only Elo, rank, rest, form and tier, all of which stay current from results alone. On the held-out half-year it scored 0.5517, 0.0011 behind M2. So M1 is the better model for live use, and it is the one the live protocol (P2) registers.

## Reproducing

```powershell
python -m matchup_dna.itf_splits check
python -m matchup_dna.itf_experiment rows        # about 5 minutes; results/itf/rows/
python -m matchup_dna.itf_experiment develop     # results/itf/development.json
python -m unittest discover -s tests -p "test_itf_*.py"
```

`validate` and `holdout` have run, and both refuse to run again. Their outputs are `results/itf/validation.json` and `holdout.json`, with per-match forecasts in `validation_predictions.csv` and `holdout_predictions.csv`. `results/` is not in git.

## In ordinary language

The new ITF model rates every player using every match they've played at any level, from the smallest ITF events to the Grand Slams. The rating moves quickly while a player is new and settles as their record grows.

On top of that rating it uses ranking, recent form, rest, and, since 2025, how well each player serves and returns. On the second half of 2025, which it had never seen, it picks the winner 73% of the time, and its percentages are honest: when it says 75%, the player wins about 75% of the time.

The serve and return numbers help only a little, but reliably. The main-tour model, by contrast, does badly on ITF matches, because it doesn't know these players.

The real test was the first half of 2026, which stayed locked until every choice was frozen and committed. On those 13,537 matches the model picked the winner 71% of the time. It beat ranking alone, Elo alone and the main-tour model by clear margins, for men and women and at every level of event. Its percentages stayed close to reality, though strong favourites won a little less often than it said.
