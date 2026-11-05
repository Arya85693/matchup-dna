# Matchup DNA — Phase 2 Elo Report

**Date:** 4 November 2026  
**Decision:** Surface-adjusted Elo is the baseline Phase 3 must beat. It improves on ordinary Elo by a small, consistent margin on matches it never saw during tuning.

## Result

On 87,640 ATP and WTA tour-level matches from January 2010 to May 2026, scored once after all choices were fixed:

| Model | Log loss | Brier score | Accuracy |
|---|---|---|---|
| Always 0.5 | 0.6931 | 0.2500 | 50.00% |
| Elo, K = 32 | 0.6135 | 0.2127 | 65.95% |
| Surface Elo, K = 48, half overall and half surface | 0.6113 | 0.2117 | 66.37% |

Lower log loss and Brier score are better. Surface Elo's log loss is 0.0022 lower per match, with a standard error of 0.0004. That standard error treats matches as independent, which they are not quite, because the same players appear many times. The gap is still about five standard errors, and surface Elo is better on both tours and in 14 of the 17 test years.

Picking the higher-ranked player is right 65.52% of the time on the 85,389 test matches where both ranks are known and differ. Elo is right 66.03% and surface Elo 66.44% on those same matches. Elo beats the ranking by about half a point of accuracy, so most of what Elo knows the ranking already knows. The advantage Elo has is that it gives a probability, not just a pick.

## How the ratings are built

- **Players.** A player is tour plus Sackmann id, as in Phase 1. ATP and WTA are separate rating pools, so no probability is given between an ATP player and a WTA player.
- **Start.** Every player starts at 1500 overall and 1500 on each surface.
- **Probability.** The probability that A beats B is \(1 / (1 + 10^{(R_B - R_A)/400})\). A 400-point gap is 10-to-1 odds.
- **Update.** After a match each player moves by \(K\) times the result minus the expected result. A heavy favorite who wins barely moves. An underdog who wins moves a lot.
- **Which matches count.** Completed best-of-3 and best-of-5 matches move ratings and are scored. Retirements, walkovers, defaults, abandoned matches, unknown scores, best-of-1 matches, and the 4 rows where winner and loser have the same id are skipped. A retirement or walkover says more about injury than about who is the stronger player.
- **Time.** Matches are replayed one tournament week at a time, oldest first. Every match in a week is predicted with the ratings from the start of that week, and the week's results are applied together afterwards. This is the Phase 1 rule that `tourney_date` is the tournament Monday and a week sees only earlier weeks. The cost is that a player's quarterfinal prediction does not use their earlier-round wins that same week.
- **Surface Elo.** Each player also has a rating per surface, updated only by matches on that surface with the same update rule. The prediction uses the average of the overall rating and the surface rating. A match with no surface recorded uses the overall rating only.

## How the choices were made

The data runs from 1968. Ratings are computed over all of it, but the scoring periods are:

- **Warm-up, 1968 to 1989.** Not scored. Everyone starts at 1500, so early predictions say little.
- **Tuning, 1990 to 2009.** Every K rule and surface weight was scored here, and the lowest log loss was kept.
- **Test, 2010 to May 2026.** Scored once with the chosen settings.

Tuning-period log loss:

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

A surface weight of 1.0 uses the surface rating alone, and it is worse than ordinary Elo for every K. A player's surface rating is built from far fewer matches, so it is noisier. The best blend puts half the weight on each. Surface Elo prefers a larger K than ordinary Elo, which fits: a surface rating is updated less often and has to move further each time.

The decaying K, which gives a new player bigger moves than an established one, did not beat a fixed K here. That is a result of this setup, where every match from 1968 is used and only tour-level matches are rated. It may change once lower-level matches give new players a history before they reach the tour.

## Where it works and where it does not

| Test subset | Matches | Elo log loss | Surface Elo log loss |
|---|---|---|---|
| ATP | 45,268 | 0.6084 | 0.6054 |
| WTA | 42,372 | 0.6190 | 0.6177 |
| Hard | 52,495 | 0.6084 | 0.6100 |
| Clay | 25,945 | 0.6232 | 0.6162 |
| Grass | 8,828 | 0.6146 | 0.6040 |
| Carpet | 208 | 0.6623 | 0.6505 |

Surface Elo helps most on grass and clay and is slightly worse on hard courts. Hard courts are the majority of matches, so a hard-court rating is close to the overall rating anyway, and averaging in a noisier copy of it costs a little. WTA matches are harder to predict than ATP matches under both models.

Log loss rises from about 0.59 in 2010 to 2013 to about 0.62 to 0.63 from 2017 on, for both models. The later tour is harder to predict from past results alone. The reason was not investigated in this phase.

## Calibration

Elo is overconfident. When it makes a player a favorite, the favorite wins less often than predicted:

| Favorite's probability | Matches | Predicted | Observed |
|---|---|---|---|
| 0.5 to 0.6 | 26,899 | 0.548 | 0.539 |
| 0.6 to 0.7 | 22,512 | 0.649 | 0.618 |
| 0.7 to 0.8 | 18,785 | 0.748 | 0.712 |
| 0.8 to 0.9 | 13,526 | 0.846 | 0.792 |
| 0.9 to 1.0 | 5,695 | 0.936 | 0.909 |

Surface Elo has the same pattern. The probabilities rank matches well but are too far from 0.5. Calibration is a Phase 3 job. Phase 3's model has to beat these numbers, and recalibrating Elo itself is the obvious first comparison.

## Limits

- Only tour-level singles are rated. Players arriving from Challengers and ITF events start at 1500, as if unknown.
- The weekly freeze ignores wins earlier in the same tournament.
- Ratings never decay during long absences, so a player returning from injury keeps their old rating.
- The standard error ignores that matches share players. It is a rough guide, not a test.
- The test period ends with the June 2026 snapshot, whose last tournament week is 25 May 2026.

## Reproducing

```powershell
python -m matchup_dna.evaluate
```

Prints every number in this report and writes the test-period predictions to `results/phase2_test_predictions.csv`. That folder is not committed, because it is derived from the Sackmann data. The chosen settings are `ELO_K`, `SURFACE_ELO_K`, and `SURFACE_WEIGHT` in `matchup_dna/elo.py`, and the script warns if tuning would now pick something different.
