# Matchup DNA — Myth Check: Do Players Choke in Big Matches?

**Status:** Version 1 complete 14 November 2026; version 2 (robustness, power and sensitivity, at the end of this report) added the same day after a review. **Post-hoc and descriptive.** This analysis was not pre-registered. It was run after a question about "big-match players", and it was not used to choose, change or tune any model. No frozen protocol, live forecast or held-out result is affected. Every version 2 analysis was written after the version 1 results were known.

**Question:** Do some players win big matches (semi-finals, finals, late Slam and Masters rounds) more or less often than their strength says, and does that carry over from one part of a career to the next? If it does not persist, it cannot help a forecast.

**Answer:** No measurable trait. Across 26 years of tour-level matches:

- **Favourites as a group do not fall apart in big matches.** On the ATP tour Elo needs the same calibration in big matches as in regular ones (best of 3: slope 0.74 big, 0.75 regular). On the WTA tour Elo is a little more over-confident in big matches (0.75 against 0.82), so favourites' edges there are slightly smaller than in regular matches. That applies to every favourite alike and is removed before players are compared.
- **Players differ in big matches about as much as luck alone would make them differ.** The observed spread is 0.99 times the luck-only spread for ATP finals, and between 0.92 and 1.17 for every other big-match definition on either tour.
- **A player's big-match record does not predict their later one.** Split-half agreement is r = +0.094 (ATP) and +0.064 (WTA), both intervals including zero. Scores from 2012–2018 do not significantly improve forecasts of 2019 – May 2026 big matches (permutation p 0.250 ATP, 0.114 WTA). The part that does persist is ordinary form, which also persists in regular matches.

**Version 2 refines the answer:** the data rule out a *large* trait, not every trait.

- **What the data rule out.** At 95% confidence, a player one standard deviation above average gains at most 7.9 percentage points (ATP) and 5.0 points (WTA) at evens in big matches (clutch-spread bounds). A trait of a few points cannot be excluded.
- **A small ATP signal.** The ATP clutch spread, the test that removes general form, is nominally significant (exact p 0.044 with wins, permutation p 0.022 with game margins). It is not significant after correcting for the number of tests, it does not carry over from 2012–2018 to 2019 – May 2026, and it does not improve forecasts. The WTA shows nothing.
- **The WTA calibration difference is real** (p 0.006) but tour-wide: Elo overstates every WTA favourite a little more in big matches.

**Consequence for the model:** no player-specific big-match factor is added. A trait within the bounds would be too small to estimate player by player from a career's big matches.

`python -m matchup_dna.posthoc_big_match` writes `results/phase4/experiments/posthoc_big_match.txt` and `posthoc_big_match.json`. Tests: `tests/test_posthoc_big_match.py`. Version 2: `python -m matchup_dna.posthoc_big_match_robustness` writes `posthoc_big_match_robustness.txt` and `.json` (about 30 minutes); tests `tests/test_posthoc_big_match_robustness.py`.

---

## Data and definitions

All definitions below were written into the script before it was run.

- **Data:** Jeff Sackmann's ATP and WTA tour-level files to 25 May 2026. No outcome dated June 2026 or later is used. Window for tests 1 and 2: 2000 – May 2026, **131,649 main-tour matches, 14,071 of them big.**
- **Main-tour events only:** ATP levels G, M, A, F, O; WTA levels G, PM, P, I, W, T1–T5, F, O. Davis Cup, Billie Jean King Cup, other team events, exhibitions and bronze-medal matches are left out. Rated matches only (completed, best of 3 or 5), as everywhere in the project.
- **Big match:** any semi-final or final; a Slam fourth round or quarter-final; a Masters quarter-final (ATP Masters 1000, WTA Premier Mandatory and Tier I before 2009); any match at the season-ending Finals. Every other main-tour match is a **regular match**.
- **Strength:** the project's canonical surface-blended Elo (surface K 48, blended half and half), taken at the start of the tournament week. Nothing is refitted.
- **Recalibration:** plain Elo is too cautious in best-of-5 and too confident in best-of-3. Left alone, players who are usually favourites in Slams would look "clutch" for a reason unrelated to pressure. So Elo's log-odds are rescaled with one slope per (tour, big or regular, best of 3 or 5), fitted on the matches of the window being analysed.
- **Residual:** 1 if the player won, 0 if not, minus the calibrated probability.
- **Big-match score:** the sum of a player's big-match residuals divided by (matches + 20). This is heavy shrinkage: 20 big matches count as half signal, half "no effect".
- **Clutch score:** big-match score minus the same score on regular matches, so a player Elo underrates everywhere (a fast riser) is not counted as clutch.

### Calibration slopes (2000 – May 2026)

A slope of 1.00 means Elo's probabilities were already right; below 1, Elo is too confident; above 1, too cautious.

| Tour | Matches | Best of 3 | Best of 5 |
|---|---|---:|---:|
| ATP | Big | 0.74 | 1.01 |
| ATP | Regular | 0.75 | 1.06 |
| WTA | Big | 0.75 | — |
| WTA | Regular | 0.82 | — |

On the ATP tour, big and regular matches need nearly the same correction, in both formats. On the WTA tour the big-match slope is lower (0.75 against 0.82): Elo overstates favourites' edges a little more in big matches. This is a tour-wide effect on all favourites, not a trait of particular players, and the per-group calibration removes it before any player is scored. Its significance was not tested in version 1; version 2 tests it (z −2.74, p 0.006).

---

## Test 1: spread beyond luck

For players with at least 10 matches of each kind, 2000 – May 2026, the variance of their raw mean residuals is split into the part coin-flip luck would produce and the remainder, the variance of a true trait (an empirical Bayes split). **Ratio** is observed variance over luck variance; 1.00 means the differences between players are exactly what luck produces. **Implied k** is the shrinkage the data itself supports: the number of matches needed before half of a player's record is signal. Standard deviations are in win-probability points per match.

| Tour | Set | Players | Observed sd | Luck sd | Ratio | Trait sd | Implied k |
|---|---|---:|---:|---:|---:|---:|---:|
| ATP | Finals only | 108 | 11.4 | 11.4 | 0.99 | 0.0 | none |
| ATP | Semi-finals + finals | 222 | 9.9 | 9.7 | 1.04 | 1.8 | 652 |
| ATP | All big matches | 247 | 9.9 | 9.1 | 1.17 | 3.8 | 147 |
| ATP | Regular matches | 813 | 7.3 | 7.2 | 1.03 | 1.2 | 1514 |
| WTA | Finals only | 82 | 12.1 | 11.2 | 1.15 | 4.4 | 111 |
| WTA | Semi-finals + finals | 223 | 10.4 | 10.4 | 1.00 | 0.6 | 6361 |
| WTA | All big matches | 251 | 9.3 | 9.7 | 0.92 | 0.0 | none |
| WTA | Regular matches | 794 | 8.2 | 7.2 | 1.29 | 3.9 | 138 |

**Reading.** Where any excess appears, it is small and the implied shrinkage is above 100 big matches, more than almost any player plays in a career. The ratios do not rise as the matches get bigger: ATP finals, the "biggest" set, sit at 0.99.

## Test 2: split-half agreement

Big matches from 2000 – May 2026 are divided into two halves by tournament edition (CRC32 of the tour and tourney id, odd or even). For players with at least 10 big matches in each half, the two halves' raw mean residuals are correlated. This asks whether a trait exists at all, ignoring change over a career. Intervals are percentile bootstraps over players (2,000 draws).

| Tour | Players | r | 95% interval | Full-data reliability (Spearman–Brown) |
|---|---:|---:|---|---:|
| ATP | 149 | +0.094 | −0.051 to +0.238 | +0.171 |
| WTA | 132 | +0.064 | −0.125 to +0.245 | +0.120 |

## Test 3: period split, 2012–2018 against 2019 – May 2026

The persistence check. Scores are computed separately in each period, each with its own calibration.

**Correlation across players** with at least 10 big matches in both periods (bootstrap intervals over players):

| Tour | Players | Big-match score | Clutch score | Regular-match score (reference) |
|---|---:|---|---|---|
| ATP | 29 | +0.203 (−0.182 to +0.547) | +0.095 (−0.285 to +0.421) | +0.236 (−0.097 to +0.540) |
| WTA | 32 | +0.163 (−0.126 to +0.410) | +0.072 (−0.249 to +0.377) | +0.419 (+0.016 to +0.644) |

**Forecast test.** Do 2012–2018 scores improve the calibrated Elo forecast of every 2019 – May 2026 big match? Model: logit P = calibrated log-odds + beta × (score A − score B), one parameter fitted by maximum likelihood. The p-value comes from 1,000 permutations of the 2012–2018 scores among players, which respects that one player appears in many matches.

| Tour | Later big matches | With a 2012–2018 score | Score | Beta (se) | Log loss change per match | Permutation p |
|---|---:|---:|---|---|---:|---:|
| ATP | 2,013 | 1,580 | Big-match | +1.19 (0.99) | −0.00036 | 0.250 |
| ATP | 2,013 | 1,580 | Clutch | +1.20 (0.86) | −0.00049 | 0.164 |
| WTA | 1,672 | 1,345 | Big-match | +2.29 (1.26) | −0.00100 | 0.114 |
| WTA | 1,672 | 1,345 | Clutch | −0.03 (0.75) | −0.00000 | 0.967 |

**Reading.** The regular-match row is the key reference: an ordinary Elo residual persists at least as much as the big-match one (WTA +0.419 against +0.163). What carries over is general form that Elo is slow to catch, not something specific to pressure. Once that is subtracted, the clutch score does not persist on either tour, and no forecast gain reaches significance.

---

## Why the story feels true

- **Losing runs are common.** A player who wins 60% of their finals has a 98% chance of losing two in a row, and about a 71% chance of losing three in a row, somewhere in 29 finals (exact calculation, each final independent). Whenever such a run happens, it looks like a pattern.
- **Selection.** With hundreds of players on tour, some will have long losing runs in finals by chance, and those are the players who are written about. Players who beat expectations in finals rarely get the opposite article.
- **The opponent is stronger.** Players lose more finals than first rounds because finals are against stronger players. Raw finals records ignore that; this analysis measures results against each match's own expectation.

## Limits

- **Post-hoc and descriptive.** The definitions were fixed before the run, but the question arose after recent results had been seen.
- **Small samples in the period split:** 29 ATP and 32 WTA players. The test cannot rule out a small effect; it shows any effect is too small to measure or forecast with in tour-level data.
- **Start-of-week ratings.** Results from earlier rounds of the same tournament are not used. Both players in a late round have usually won several matches that week, so this affects both sides alike.
- **Pressure is not observed directly.** This tests results against expectation, not how players feel, and it cannot say that pressure has no effect on anyone.

---

## Version 2: robustness, power and sensitivity

Added 14 November 2026 after a review of version 1 asked what the data could have detected and whether the result survives other reasonable choices. **Everything in this section was written after the version 1 results were known.** The version 1 definitions (data, big matches, Elo baseline, calibration, scores) are imported unchanged, and the new array implementation reproduces every version 1 point estimate (largest difference 2.9e-15).

### Calibration slopes, tested

Wald test of the big-match slope against the regular-match slope, 2000 – May 2026.

| Tour and format | Big (se) | Regular (se) | z | p |
|---|---|---|---:|---:|
| ATP best of 3 | 0.735 (0.026) | 0.748 (0.010) | −0.43 | 0.67 |
| ATP best of 5 | 1.005 (0.053) | 1.064 (0.022) | −1.02 | 0.31 |
| WTA best of 3 | 0.748 (0.025) | 0.822 (0.009) | −2.74 | 0.006 |

The WTA difference is significant. It applies to every WTA favourite in a big match and is removed by the per-group calibration; it is not a player trait.

### Exact null tests

Each statistic against 2,000 simulated data sets with no trait: every result drawn from its calibrated probability, the calibration refitted, all tests rerun. One-sided p = share of simulations at least as large as observed. **Clutch spread** is new: the spread test on each player's mean big-match residual minus their mean regular-match residual, which removes general form.

| Statistic | ATP observed | ATP p | WTA observed | WTA p |
|---|---:|---:|---:|---:|
| Spread ratio, finals only | 0.99 | 0.501 | 1.15 | 0.172 |
| Spread ratio, semi-finals + finals | 1.04 | 0.358 | 1.00 | 0.462 |
| Spread ratio, all big matches | 1.17 | 0.062 | 0.92 | 0.760 |
| Spread ratio, regular matches | 1.03 | 0.365 | 1.29 | 0.000 |
| Clutch spread ratio | 1.20 | 0.044 | 0.98 | 0.543 |
| Split-half r | +0.094 | 0.147 | +0.064 | 0.245 |
| Carry-over r, big-match score | +0.203 | 0.148 | +0.163 | 0.193 |
| Carry-over r, clutch score | +0.095 | 0.314 | +0.072 | 0.340 |
| Forecast z, big-match score | +1.20 | 0.123 | +1.82 | 0.033 |
| Forecast z, clutch score | +1.40 | 0.082 | −0.05 | 0.498 |

Holm-adjusted across the eight spread sets: ATP all big matches 0.437, WTA regular matches 0.004, every other set 1.000. Two nominal results need care. The **WTA forecast z for the big-match score** (p 0.033) reflects general form: the simulation assumes no player differences of any kind, while the WTA regular-match spread (1.29, p < 0.001) shows form that Elo misses. The permutation test, which keeps form, gives p 0.114, and the clutch score gives p 0.498. The **ATP clutch spread** (p 0.044) is a pressure-specific test and is followed up below.

### Power and upper bounds

A clutch trait was injected: each player gets theta ~ N(0, tau²) on the log-odds scale, in big matches only, constant over the career (the easiest case to detect). 400 simulations at each tau. The edge at evens is 100 × (sigmoid(tau) − 0.5): the percentage points above 50% for a player one standard deviation above average against an equal opponent. Power = share of simulations beyond the no-trait 95th percentile. The 95% upper bound is the smallest tau at which the observed statistic would be in the lowest 5% of simulations.

| Tour | Test | Power at tau 0.2 (5.0 points) | 95% upper bound on tau | Edge at the bound |
|---|---|---:|---:|---:|
| ATP | Clutch spread | 0.43 | 0.320 | 7.9 points |
| ATP | Split-half r | 0.61 | 0.247 | 6.2 points |
| ATP | Forecast z, clutch score | 0.42 | 0.392 | 9.7 points |
| WTA | Clutch spread | 0.42 | 0.200 | 5.0 points |
| WTA | Split-half r | 0.55 | 0.241 | 6.0 points |
| WTA | Forecast z, clutch score | 0.37 | 0.279 | 6.9 points |

Every test detects tau = 0.4 (9.9 points) at least 80% of the time; below tau = 0.2 every test has less than even odds. The clutch spread is the headline bound because it is the only test that removes general form; its bounds are neither the tightest nor the loosest of the ten statistics (full grid in the output file). **The data rule out a large trait, not a small one.**

### Game margins

Each result replaced by the share of games won (a match tie-break counts as one game), against a fractional-logit expectation on the Elo log-odds per (tour, big or regular, best of). Null distributions: 1,000 permutations of residuals among matches within each group. All 131,649 matches have a readable score.

| Statistic | ATP | WTA |
|---|---|---|
| Residual sd per match | 12.7 points | 15.8 points |
| Spread ratio, finals only | 1.21 (p 0.098) | 1.48 (p 0.007) |
| Spread ratio, semi-finals + finals | 1.09 (p 0.231) | 0.98 (p 0.534) |
| Spread ratio, all big matches | 1.23 (p 0.038) | 1.06 (p 0.314) |
| Spread ratio, regular matches | 1.69 (p 0.001) | 1.97 (p 0.001) |
| Clutch spread ratio | 1.23 (p 0.022) | 1.02 (p 0.409) |
| Split-half r | +0.158 (−0.023 to +0.351) | +0.066 (−0.109 to +0.254) |
| Carry-over r, big-match score | +0.315 (+0.007 to +0.597) | +0.279 (+0.026 to +0.568) |
| Carry-over r, clutch score | +0.122 (−0.166 to +0.369) | +0.363 (+0.056 to +0.594) |
| Carry-over r, regular-match score | +0.278 (+0.014 to +0.497) | +0.265 (−0.135 to +0.576) |
| Forecast beta, big-match game score (p) | +4.44 (0.191) | +5.93 (0.075) |
| Forecast beta, clutch game score (p) | +3.83 (0.185) | −0.02 (0.990) |

Players differ a lot in game margins in every match (regular ratios 1.69 and 1.97): some win by wide margins and others narrowly, beyond what the win probability says. That style also lifts the big-match spreads, which is why the clutch spread is the one to read. It repeats the win-based pattern: an ATP excess (1.23, p 0.022), nothing on the WTA. The WTA clutch carry-over is the one clutch interval that excludes zero, but the forecast test with the same score finds nothing (p 0.990), and the win-based clutch carry-over is +0.072.

### Within-tournament ratings

Expectations recomputed with each player's rating updated through their earlier rounds of the same event (round-aware Elo shadow shifts). 94.3% of big matches on each tour have a complete earlier-round record; the rest keep the start-of-week rating.

| Statistic | ATP | WTA |
|---|---|---|
| Spread ratio, finals / SF+F / all big / regular | 0.98 / 1.02 / 1.15 / 0.99 | 1.14 / 0.99 / 0.91 / 1.25 |
| Clutch spread ratio | 1.17 | 0.97 |
| Split-half r | +0.102 (−0.047 to +0.250) | +0.064 (−0.117 to +0.244) |
| Forecast beta, big-match score (p) | +1.19 (0.237) | +2.34 (0.110) |
| Forecast beta, clutch score (p) | +1.08 (0.212) | −0.04 (0.962) |

Form shown earlier in the same week changes nothing material.

### Sensitivity of the carry-over test

One choice changed at a time; 1,000 fresh permutations each (so the first row's p-values differ slightly from version 1's).

| Tour | Variant | Players | Clutch r (95%) | Beta big (p) | Beta clutch (p) |
|---|---|---:|---|---|---|
| ATP | Version 1 settings | 29 | +0.095 (−0.27 to +0.44) | +1.19 (0.217) | +1.20 (0.186) |
| ATP | Shrinkage 10 | 29 | +0.108 (−0.35 to +0.47) | +0.82 (0.260) | +0.89 (0.175) |
| ATP | Shrinkage 50 | 29 | +0.099 (−0.22 to +0.40) | +2.28 (0.186) | +1.90 (0.132) |
| ATP | Shrinkage 100 | 29 | +0.108 (−0.19 to +0.38) | +3.94 (0.137) | +2.80 (0.101) |
| ATP | Minimum 5 | 51 | +0.087 (−0.19 to +0.35) | +1.19 (0.215) | +1.20 (0.168) |
| ATP | Minimum 20 | 15 | +0.028 (−0.54 to +0.55) | +1.19 (0.214) | +1.20 (0.179) |
| ATP | Semi-finals and finals only | 22 | +0.050 (−0.46 to +0.50) | +0.09 (0.955) | +0.31 (0.759) |
| ATP | Periods 2008–2015 / 2016–2026 | 34 | +0.336 (+0.09 to +0.54) | +1.30 (0.386) | +1.26 (0.231) |
| WTA | Version 1 settings | 32 | +0.072 (−0.24 to +0.38) | +2.29 (0.125) | −0.03 (0.963) |
| WTA | Shrinkage 10 | 32 | +0.080 (−0.22 to +0.39) | +1.66 (0.088) | +0.14 (0.832) |
| WTA | Shrinkage 50 | 32 | +0.070 (−0.25 to +0.34) | +3.53 (0.157) | −0.39 (0.745) |
| WTA | Shrinkage 100 | 32 | +0.079 (−0.23 to +0.32) | +5.02 (0.198) | −0.69 (0.683) |
| WTA | Minimum 5 | 52 | +0.156 (−0.09 to +0.39) | +2.29 (0.089) | −0.03 (0.968) |
| WTA | Minimum 20 | 16 | +0.287 (−0.07 to +0.60) | +2.29 (0.105) | −0.03 (0.964) |
| WTA | Semi-finals and finals only | 27 | −0.327 (−0.67 to +0.09) | +1.55 (0.326) | −0.05 (0.970) |
| WTA | Periods 2008–2015 / 2016–2026 | 33 | −0.006 (−0.34 to +0.38) | +0.38 (0.679) | +0.25 (0.695) |

No forecast p-value of the 32 falls below 0.088. One clutch correlation excludes zero (ATP, other periods, +0.336) and another is −0.327; the signs do not agree across choices.

### ATP clutch spread within one format

Added last, after the sections above showed the ATP clutch excess. ATP big matches are mostly best of 5 and regular matches mostly best of 3, so a player who is simply better over five sets would look clutch. Big against regular within each format; wins with 2,000 exact simulations, games with 1,000 permutations.

| Format | Big matches | Regular matches | Players | Clutch ratio, wins (exact p) | Clutch ratio, games (permutation p) |
|---|---:|---:|---:|---|---|
| ATP best of 3 | 5,868 | 50,517 | 231 | 1.19 (0.042) | 1.28 (0.010) |
| ATP best of 5 | 1,651 | 11,269 | 85 | 0.83 (0.849) | 1.26 (0.077) |

The excess remains within best-of-three matches alone, so five-set fitness does not explain it. Within best-of-five matches, wins show no excess and games a similar but non-significant one.

### Reading version 2

- The data rule out the large, persistent trait the choking story implies: at most 7.9 points (ATP) and 5.0 points (WTA) at evens for a player one standard deviation above average.
- On the ATP tour there is a small, nominally significant excess spread in big matches relative to regular ones, with wins and with game margins. It does not survive correction for the number of tests, does not carry over between periods, and does not improve forecasts. It is not explained by format: it remains within best-of-three matches alone (wins p 0.042, games p 0.010).
- On the WTA tour there is no sign of a trait.
- A trait within these bounds would be too small to estimate for an individual player: a record of 100 big matches has a luck sd of about 4.6 points per match. The forecasts therefore carry no player-specific big-match adjustment. A pre-registered test on matches played after this analysis could settle the ATP question.

### Version 2 limits

- **All post-hoc**, with many statistics per tour; one or two nominal p-values below 0.05 are expected by chance.
- **Simulation assumptions:** without a trait, results are independent given their calibrated probabilities. General form violates this, which inflates the big-match (not the clutch) statistics. The power analysis assumes a normal trait, constant over a career, in big matches only.
- **Game-share expectation** is a single slope per group; **within-tournament ratings** cover 94.3% of big matches.
