# Matchup DNA — Myth Check: Do Players Choke in Big Matches?

**Status:** Complete, 14 November 2026. **Post-hoc and descriptive.** This analysis was not pre-registered. It was run after a question about "big-match players", and it was not used to choose, change or tune any model. No frozen protocol, live forecast or held-out result is affected.

**Question:** Do some players win big matches (semi-finals, finals, late Slam and Masters rounds) more or less often than their strength says, and does that carry over from one part of a career to the next? If it does not persist, it cannot help a forecast.

**Answer:** No measurable trait. Across 26 years of tour-level matches:

- **Favourites as a group do not fall apart in big matches.** On the ATP tour Elo needs the same calibration in big matches as in regular ones (best of 3: slope 0.74 big, 0.75 regular). On the WTA tour Elo is a little more over-confident in big matches (0.75 against 0.82), so favourites' edges there are slightly smaller than in regular matches. That applies to every favourite alike and is removed before players are compared.
- **Players differ in big matches about as much as luck alone would make them differ.** The observed spread is 0.99 times the luck-only spread for ATP finals, and between 0.92 and 1.17 for every other big-match definition on either tour.
- **A player's big-match record does not predict their later one.** Split-half agreement is r = +0.094 (ATP) and +0.064 (WTA), both intervals including zero. Scores from 2012–2018 do not significantly improve forecasts of 2019 – May 2026 big matches (permutation p 0.250 ATP, 0.114 WTA). The part that does persist is ordinary form, which also persists in regular matches.

**Consequence for the model:** no big-match factor is added. On this evidence it would add noise, not accuracy.

`python -m matchup_dna.posthoc_big_match` writes `results/phase4/experiments/posthoc_big_match.txt` and `posthoc_big_match.json`. Tests: `tests/test_posthoc_big_match.py`.

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

On the ATP tour, big and regular matches need nearly the same correction, in both formats. On the WTA tour the big-match slope is lower (0.75 against 0.82): Elo overstates favourites' edges a little more in big matches. This is a tour-wide effect on all favourites, not a trait of particular players, and the per-group calibration removes it before any player is scored. Its significance was not tested.

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
