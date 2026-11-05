# Matchup DNA — Phase 2 Elo Report

**Date:** 4 November 2026, restructured 5 November 2026  
**Scored window:** tournament weeks from 1 January 1990 up to, but not including, 1 January 2024  
**Decision:** Surface-adjusted Elo is the baseline Phase 3 must beat on both tours. On the 2021–2023 validation years, where Phase 3 models will be compared, its log loss is 0.6245 on ATP matches and 0.6183 on WTA matches. On WTA validation matches it is not distinguishable from ordinary Elo, so Phase 3 should report both baselines for each tour.

The report follows the data in time order: warm-up, tuning, Phase 3 training years, Phase 3 validation years, and the reserved final period. ATP and WTA are shown separately at every stage. The two tours are separate rating pools, and no probability is given between an ATP player and a WTA player.

## Timeline

| Period | Tournament weeks | Use | ATP rated matches | WTA rated matches |
|---|---|---|---:|---:|
| Warm-up | 1968–1989 | Ratings start at 1500 and update. Not scored. | 80,956 | 60,226 |
| Tuning | 1990–2009 | K and surface weight chosen here | 67,503 | 55,064 |
| Phase 3 training | 2010–2020 | Training examples for Phase 3 models | 29,712 | 28,157 |
| Phase 3 validation | 2021–2023 | Model selection, feature experiments, hyperparameters, calibration | 8,366 | 7,673 |
| Reserved final evaluation | 1 January 2024–25 May 2026 | Scored once, after Phase 3's final model and protocol are frozen | 7,190 | 6,542 |

A period is set by `tourney_date`, so a tournament is never split between two periods. The 2024 season's first events, including Brisbane, Auckland, Hong Kong, and the United Cup, are dated 1 January 2024 and fall in the reserved period.

Ratings run through every period without stopping. A match in any year is predicted from the ratings at the start of its week, and the week's results are applied afterwards. The periods decide only which matches are scored, trained on, or used to make choices.

## How the ratings are built

- **Players.** A player is tour plus Sackmann id, as in Phase 1. ATP and WTA ids overlap and are rated separately.
- **Start.** Every player starts at 1500 overall and 1500 on each surface.
- **Probability.** The probability that A beats B is \(1 / (1 + 10^{(R_B - R_A)/400})\). A 400-point gap is 10-to-1 odds.
- **Update.** After a match, each player moves by \(K\) times the result minus the expected result. A heavy favorite who wins barely moves. An underdog who wins moves a lot.
- **Which matches count.** Completed best-of-3 and best-of-5 matches move ratings and are scored. Retirements, walkovers, defaults, abandoned matches, unknown scores, best-of-1 matches, and rows where winner and loser have the same id are skipped. A retirement or walkover says more about injury than about who is the stronger player.
- **Time.** Matches are replayed one `tourney_date` at a time, oldest first. Every match with that date is predicted with the ratings from before it, and the results are applied together afterwards. The cost is that a quarterfinal prediction does not use the earlier-round wins from the same tournament.
- **Surface Elo.** Each player also has a rating per surface, updated only by matches on that surface with the same rule. The prediction uses the average of the overall rating and the surface rating. A match with no recorded surface uses the overall rating only.

## 1968–1989: warm-up

| Tour | First week | Last week | Rows | Rated |
|---|---|---|---:|---:|
| ATP | 28 December 1967 | 15 December 1989 | 82,940 | 80,956 |
| WTA | 25 December 1967 | 11 December 1989 | 61,840 | 60,226 |

Nothing here is scored. Everyone starts at 1500, so the early predictions say little. These years exist to give players a rating history before tuning begins.

## 1990–2009: tuning

Every K rule and surface weight was scored on ATP and WTA matches together, and the lowest log loss was kept. One setting serves both tours.

| K rule | Elo | Surface weight 0.25 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|
| K = 16 | 0.6063 | 0.6050 | 0.6069 | 0.6124 | 0.6216 |
| K = 24 | 0.6030 | 0.5997 | 0.6004 | 0.6052 | 0.6145 |
| K = 32 | **0.6029** | 0.5979 | 0.5974 | 0.6019 | 0.6114 |
| K = 48 | 0.6069 | 0.5989 | **0.5967** | 0.6008 | 0.6112 |
| K = 64 | 0.6140 | 0.6034 | 0.5999 | 0.6039 | 0.6154 |
| K = 150 / (played + 5)^0.4 | 0.6045 | 0.5993 | 0.5988 | 0.6032 | 0.6126 |
| K = 250 / (played + 5)^0.4 | 0.6105 | 0.6022 | 0.6011 | 0.6073 | 0.6206 |
| K = 350 / (played + 5)^0.4 | 0.6220 | 0.6114 | 0.6105 | 0.6194 | 0.6375 |

The choice is **Elo with K = 32**, and **surface Elo with K = 48 and half overall, half surface**. A surface weight of 1.0 uses the surface rating alone, and it is worse than ordinary Elo for every K. A surface rating is built from far fewer matches, so it is noisier. Surface Elo prefers a larger K because a surface rating is updated less often and has to move further each time. The decaying K, which gives new players bigger moves, did not beat a fixed K in this setup.

With the chosen settings, on the tuning years:

| Tour | Matches | Elo log loss | Surface Elo log loss | Elo Brier | Surface Elo Brier | Elo accuracy | Surface Elo accuracy |
|---|---:|---|---|---|---|---|---|
| ATP | 67,503 | 0.6204 | 0.6127 | 0.2155 | 0.2121 | 65.69% | 66.35% |
| WTA | 55,064 | 0.5814 | 0.5772 | 0.1995 | 0.1977 | 68.74% | 69.16% |
| Both | 122,567 | 0.6029 | 0.5967 | 0.2083 | 0.2056 | 67.06% | 67.61% |

These numbers are in-sample, because the settings were chosen on these years. Surface Elo is better on both tours. In this era WTA matches were easier to predict than ATP matches.

## 2010–2020: Phase 3 training years

The settings are now fixed. Every number from here on is out of sample for Elo.

| Tour | Matches | Elo log loss | Surface Elo log loss | Elo Brier | Surface Elo Brier | Elo accuracy | Surface Elo accuracy |
|---|---:|---|---|---|---|---|---|
| ATP | 29,712 | 0.5986 | 0.5948 | 0.2062 | 0.2044 | 67.53% | 68.18% |
| WTA | 28,157 | 0.6179 | 0.6161 | 0.2146 | 0.2137 | 65.75% | 66.08% |
| Both | 57,869 | 0.6080 | 0.6051 | 0.2103 | 0.2089 | 66.66% | 67.16% |

Always predicting 0.5 gives a log loss of 0.6931, a Brier score of 0.2500, and 50% accuracy on every subset. The tours have switched places: after 2010, WTA matches are the harder ones to predict.

**Surface Elo minus Elo, log loss per match**

| Tour | Difference | Standard error, independent | Standard error, clustered by week | Weeks |
|---|---|---|---|---:|
| ATP | −0.0038 | 0.0007 | 0.0008 | 476 |
| WTA | −0.0018 | 0.0007 | 0.0008 | 521 |
| Both | −0.0028 | 0.0005 | 0.0006 | 697 |

The clustered error allows matches with the same `tourney_date` to be correlated, which covers what players share inside a tournament week. Neither error accounts for the same player's results being correlated across weeks, so both are rough guides rather than formal tests. The surface gain is about five standard errors on ATP matches and about two on WTA matches.

**Against the ranking,** on matches where both ranks are known and differ:

| Tour | Matches | Higher-ranked player | Elo | Surface Elo |
|---|---:|---|---|---|
| ATP | 29,064 | 66.81% | 67.57% | 68.23% |
| WTA | 26,964 | 65.65% | 65.87% | 66.15% |

Elo adds under a point of accuracy over the ranking on ATP matches and a fraction of a point on WTA matches. What Elo adds is a probability, not a better pick.

**By surface**

| Surface | ATP matches | ATP Elo | ATP surface Elo | WTA matches | WTA Elo | WTA surface Elo |
|---|---:|---|---|---:|---|---|
| Hard | 17,234 | 0.5920 | 0.5931 | 17,594 | 0.6126 | 0.6136 |
| Clay | 9,307 | 0.6108 | 0.6016 | 7,721 | 0.6257 | 0.6214 |
| Grass | 3,106 | 0.5969 | 0.5826 | 2,699 | 0.6276 | 0.6149 |
| Carpet | 65 | 0.6442 | 0.6452 | 143 | 0.6705 | 0.6529 |

The values are log loss. On both tours, surface Elo helps on clay and grass and is slightly worse on hard courts. Most matches are on hard courts, so a hard-court rating is close to the overall rating, and averaging in a noisier copy costs a little. Carpet has too few matches to read.

**Calibration.** Matches are grouped by the favorite's predicted probability, and each group compares that prediction with how often the favorite actually won.

ATP, 2010–2020:

| Favorite's probability | Elo matches | Elo predicted | Elo observed | Surface Elo matches | Surface Elo predicted | Surface Elo observed |
|---|---:|---|---|---:|---|---|
| 0.5 to 0.6 | 8,375 | 0.549 | 0.541 | 8,069 | 0.549 | 0.550 |
| 0.6 to 0.7 | 7,178 | 0.649 | 0.626 | 7,216 | 0.649 | 0.632 |
| 0.7 to 0.8 | 6,494 | 0.749 | 0.716 | 6,361 | 0.748 | 0.714 |
| 0.8 to 0.9 | 4,984 | 0.848 | 0.793 | 5,162 | 0.848 | 0.796 |
| 0.9 to 1.0 | 2,618 | 0.939 | 0.916 | 2,841 | 0.940 | 0.907 |

WTA, 2010–2020:

| Favorite's probability | Elo matches | Elo predicted | Elo observed | Surface Elo matches | Surface Elo predicted | Surface Elo observed |
|---|---:|---|---|---:|---|---|
| 0.5 to 0.6 | 9,058 | 0.548 | 0.548 | 8,790 | 0.549 | 0.548 |
| 0.6 to 0.7 | 7,270 | 0.648 | 0.623 | 7,264 | 0.648 | 0.628 |
| 0.7 to 0.8 | 5,897 | 0.748 | 0.707 | 5,843 | 0.748 | 0.705 |
| 0.8 to 0.9 | 4,206 | 0.846 | 0.786 | 4,357 | 0.846 | 0.783 |
| 0.9 to 1.0 | 1,661 | 0.935 | 0.910 | 1,838 | 0.936 | 0.910 |

Both models are overconfident on both tours, and the gap grows with confidence. A favorite given about 0.85 wins about 0.79 of the time on ATP matches and about 0.785 on WTA matches.

## 2021–2023: Phase 3 validation years

These are the numbers that Phase 3 models will be compared against during development.

| Tour | Matches | Elo log loss | Surface Elo log loss | Elo Brier | Surface Elo Brier | Elo accuracy | Surface Elo accuracy |
|---|---:|---|---|---|---|---|---|
| ATP | 8,366 | 0.6277 | 0.6245 | 0.2188 | 0.2174 | 64.18% | 64.94% |
| WTA | 7,673 | 0.6186 | 0.6183 | 0.2151 | 0.2147 | 65.15% | 65.61% |
| Both | 16,039 | 0.6233 | 0.6215 | 0.2170 | 0.2161 | 64.64% | 65.26% |

**Surface Elo minus Elo, log loss per match**

| Tour | Difference | Standard error, independent | Standard error, clustered by week | Weeks |
|---|---|---|---|---:|
| ATP | −0.0031 | 0.0015 | 0.0015 | 159 |
| WTA | −0.0004 | 0.0014 | 0.0017 | 137 |
| Both | −0.0018 | 0.0010 | 0.0012 | 201 |

On ATP matches, surface Elo is still better by about two standard errors. On WTA matches the difference is a quarter of one standard error, so the two models cannot be told apart on these three years. The validation set is about a quarter the size of the training set, so every error here is about twice as wide.

**Against the ranking**

| Tour | Matches | Higher-ranked player | Elo | Surface Elo |
|---|---:|---|---|---|
| ATP | 8,270 | 64.14% | 64.15% | 64.97% |
| WTA | 7,551 | 64.67% | 65.28% | 65.70% |

On ATP validation matches, ordinary Elo picks winners no better than the ranking does.

**By surface**

| Surface | ATP matches | ATP Elo | ATP surface Elo | WTA matches | WTA Elo | WTA surface Elo |
|---|---:|---|---|---:|---|---|
| Hard | 4,913 | 0.6192 | 0.6199 | 4,630 | 0.6130 | 0.6165 |
| Clay | 2,468 | 0.6491 | 0.6386 | 2,142 | 0.6299 | 0.6248 |
| Grass | 934 | 0.6130 | 0.6091 | 901 | 0.6205 | 0.6116 |
| Missing | 51 | 0.6684 | 0.6718 | — | — | — |

The values are log loss. The training-years pattern holds: surface Elo helps on clay and grass, and costs a little on hard courts. On WTA hard courts the cost is 0.0035 per match, larger than in the training years. Hard courts are 60% of WTA validation matches, which is why the WTA total gain nearly disappears. The 51 missing-surface matches are all ATP matches, and both models use the overall rating for them. No carpet matches were played in these years.

**Calibration**

ATP, 2021–2023:

| Favorite's probability | Elo matches | Elo predicted | Elo observed | Surface Elo matches | Surface Elo predicted | Surface Elo observed |
|---|---:|---|---|---:|---|---|
| 0.5 to 0.6 | 2,592 | 0.548 | 0.520 | 2,536 | 0.548 | 0.537 |
| 0.6 to 0.7 | 2,301 | 0.650 | 0.602 | 2,205 | 0.649 | 0.603 |
| 0.7 to 0.8 | 1,771 | 0.748 | 0.711 | 1,776 | 0.748 | 0.697 |
| 0.8 to 0.9 | 1,266 | 0.846 | 0.790 | 1,312 | 0.845 | 0.785 |
| 0.9 to 1.0 | 414 | 0.933 | 0.884 | 515 | 0.932 | 0.899 |

WTA, 2021–2023:

| Favorite's probability | Elo matches | Elo predicted | Elo observed | Surface Elo matches | Surface Elo predicted | Surface Elo observed |
|---|---:|---|---|---:|---|---|
| 0.5 to 0.6 | 2,529 | 0.549 | 0.537 | 2,437 | 0.549 | 0.540 |
| 0.6 to 0.7 | 2,068 | 0.648 | 0.610 | 2,093 | 0.650 | 0.622 |
| 0.7 to 0.8 | 1,675 | 0.749 | 0.733 | 1,654 | 0.748 | 0.727 |
| 0.8 to 0.9 | 1,109 | 0.844 | 0.805 | 1,138 | 0.845 | 0.793 |
| 0.9 to 1.0 | 282 | 0.927 | 0.908 | 341 | 0.928 | 0.894 |

The overconfidence is larger on ATP matches than in the training years. ATP favorites given 0.6 to 0.7 won only about 60% of the time. Recalibration is a Phase 3 job, and its first comparison. It must be fitted on training or validation years, and never on the reserved period.

## 2010–2023 together, by year

| Year | Period | ATP matches | ATP Elo | ATP surface Elo | WTA matches | WTA Elo | WTA surface Elo |
|---|---|---:|---|---|---:|---|---|
| 2010 | Training | 2,908 | 0.5943 | 0.5876 | 2,702 | 0.5949 | 0.5924 |
| 2011 | Training | 2,890 | 0.5833 | 0.5765 | 2,702 | 0.6061 | 0.6074 |
| 2012 | Training | 2,982 | 0.5696 | 0.5660 | 2,811 | 0.6016 | 0.5987 |
| 2013 | Training | 2,818 | 0.5873 | 0.5840 | 2,634 | 0.5942 | 0.5892 |
| 2014 | Training | 2,694 | 0.5898 | 0.5867 | 2,611 | 0.6230 | 0.6227 |
| 2015 | Training | 2,833 | 0.5762 | 0.5734 | 2,548 | 0.6246 | 0.6261 |
| 2016 | Training | 2,825 | 0.5894 | 0.5873 | 2,836 | 0.6326 | 0.6287 |
| 2017 | Training | 2,794 | 0.6142 | 0.6102 | 2,761 | 0.6313 | 0.6277 |
| 2018 | Training | 2,897 | 0.6326 | 0.6330 | 2,746 | 0.6358 | 0.6360 |
| 2019 | Training | 2,641 | 0.6356 | 0.6304 | 2,556 | 0.6301 | 0.6278 |
| 2020 | Training | 1,430 | 0.6313 | 0.6262 | 1,250 | 0.6286 | 0.6258 |
| 2021 | Validation | 2,650 | 0.6290 | 0.6281 | 2,485 | 0.6133 | 0.6101 |
| 2022 | Validation | 2,828 | 0.6168 | 0.6117 | 2,478 | 0.6256 | 0.6280 |
| 2023 | Validation | 2,888 | 0.6370 | 0.6338 | 2,710 | 0.6171 | 0.6168 |

The values are log loss. Surface Elo is better in 13 of 14 ATP years, all except 2018, and in 10 of 14 WTA years. The WTA exceptions are 2011, 2015, 2018, and 2022.

ATP log loss is about 0.57 to 0.59 through 2016 and rises to about 0.61 to 0.64 from 2017 on. WTA log loss rises earlier, from 2014. Past results alone predict the later tour less well on both sides. The reason was not investigated in this phase. 2020 has half the usual matches because the tours stopped from March to August.

Over the 14 years together:

| Tour | Matches | Elo log loss | Surface Elo log loss | Difference | Standard error, clustered by week |
|---|---:|---|---|---|---|
| ATP | 38,078 | 0.6049 | 0.6013 | −0.0037 | 0.0007 |
| WTA | 35,830 | 0.6181 | 0.6166 | −0.0015 | 0.0007 |
| Both | 73,908 | 0.6113 | 0.6087 | −0.0026 | 0.0005 |

## 2024–2026: reserved final evaluation

| Tour | First week | Last week | Rows | Rated |
|---|---|---|---:|---:|
| ATP | 1 January 2024 | 25 May 2026 | 7,469 | 7,190 |
| WTA | 1 January 2024 | 25 May 2026 | 6,779 | 6,542 |

No result for this period is shown here, and `python -m matchup_dna.evaluate` does not replay or score it. Ratings do keep updating through it when the Phase 3 dataset is built, so each reserved match has pre-match features. Its outcomes are left out of the dataset files.

**This period has already been seen.** Before this split existed, the first version of this report scored 2010 through May 2026 on both tours together. It published log loss, Brier score, accuracy, calibration, and results for 2024, 2025, and 2026. The per-match predictions for those years are also in `results/phase2_test_predictions.csv`. The Elo settings were chosen on 1990–2009 before any of that was seen, so the Elo results are not contaminated. What is lost is any claim that the reserved years were never looked at. From here the protection is procedural. Phase 3 development reads only the training and validation files, and the reserved period is scored once at the end.

## Matches left out, by period and tour

| Period | Tour | Rows | Rated | Retired | Walkover | Default | Abandoned | Unknown score | Best of 1 | Same id |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Warm-up | ATP | 82,940 | 80,956 | 935 | 756 | 129 | 23 | 103 | 35 | 3 |
| Warm-up | WTA | 61,840 | 60,226 | 558 | 782 | 1 | 2 | 178 | 92 | 1 |
| Tuning | ATP | 69,485 | 67,503 | 1,697 | 252 | 23 | 10 | 0 | 0 | 0 |
| Tuning | WTA | 56,418 | 55,064 | 1,125 | 217 | 5 | 6 | 1 | 0 | 0 |
| Training | ATP | 30,859 | 29,712 | 949 | 188 | 6 | 4 | 0 | 0 | 0 |
| Training | WTA | 29,144 | 28,157 | 820 | 145 | 22 | 0 | 0 | 0 | 0 |
| Validation | ATP | 8,636 | 8,366 | 209 | 57 | 4 | 0 | 0 | 0 | 0 |
| Validation | WTA | 8,001 | 7,673 | 252 | 76 | 0 | 0 | 0 | 0 | 0 |
| Reserved | ATP | 7,469 | 7,190 | 222 | 54 | 2 | 1 | 0 | 0 | 0 |
| Reserved | WTA | 6,779 | 6,542 | 192 | 45 | 0 | 0 | 0 | 0 | 0 |

The rows add up to all 361,571 tour-level matches. Excluded matches neither move ratings nor get scored.

## Limits

- The reserved period's results were published once before the split existed, as described above.
- A "week" is one `tourney_date` value, and some events don't start on a Monday. Among rated matches, that covers 7,335 ATP and 2,955 WTA training matches, and 763 ATP and 1,113 WTA validation matches. Examples are Davis Cup ties and the Antalya and Abu Dhabi events of January 2021. Two events dated a few days apart are replayed one after the other, so a match can be predicted with results from another event played during the same days. This is the Phase 1 rule, kept unchanged.
- One K and one surface weight serve both tours. They were tuned on ATP and WTA together, and a separate setting per tour was not tested.
- The weekly freeze ignores earlier-round wins in the same tournament.
- Only tour-level singles are rated. Players arriving from Challengers and ITF events start at 1500, as if unknown.
- Ratings never decay during long absences, so a player returning from injury keeps their old rating.
- Every standard error ignores that the same player's results are correlated across weeks.
- The validation years hold about 8,000 matches per tour. Differences smaller than about 0.003 in log loss cannot be separated there.

## Reproducing

```powershell
python -m matchup_dna.evaluate
```

This runs the tuning grid on 1990–2009, warns if it no longer picks K = 32, K = 48, and a surface weight of 0.5, and prints every number in this report. It also writes the 2010–2023 predictions to `results/phase2_development_predictions.csv`. It takes about a minute and a half and replays ratings only up to 1 January 2024. The chosen settings are `ELO_K`, `SURFACE_ELO_K`, and `SURFACE_WEIGHT` in `matchup_dna/elo.py`, and the period dates are in `matchup_dna/periods.py`.

The first version of this report, scored on 2010–May 2026, is kept in git at commit `2677c33`. The earlier file `results/phase2_test_predictions.csv` came from that version and is not overwritten.
