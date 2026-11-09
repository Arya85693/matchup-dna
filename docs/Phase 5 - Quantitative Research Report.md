# Matchup DNA — Phase 5 Quantitative Research Report

**Status:** Complete, 8 November 2026. The data were audited, the method was developed on 2021–2023, and the protocol was frozen. The one-time evaluation on January 2024–October 2026 then ran once.
**Question:** Do the frozen models' probabilities contain information that the betting market's prices do not? And does a gap between model and market say anything about results?
**Answer, on 13,846 evaluation matches:**

- **The market is the better forecaster.** The margin-free opening price beats Phase 4 by **0.024 log loss per match**, with a 95% interval of 0.020 to 0.027. It beats Phase 3, Elo and surface Elo by more. It picks the winner 68.1% of the time, against 65.4% for Phase 4.
- **The model adds nothing to the price.** A blend of market and model, with weights fixed on 2021–2023, is indistinguishable from the market alone: −0.0000, interval −0.0004 to +0.0003.
- **Disagreement does not predict results.** When Phase 4 and the market disagree, the outcome follows the market. The slope of the result on the disagreement is −0.07 (interval −0.15 to +0.02). It was −0.08 (p = 0.03) in development.
- **A paper rule that backs Phase 4's value loses money.** It returns **−8.9% per unit staked** (interval −12.6% to −5.2%), which is worse than the −7.5% a bettor would lose if the market's own probabilities were exactly right.
- **The gap narrows over time and is smallest where information is richest.** It was 0.031 in 2024, 0.021 in 2025 and 0.019 in 2026. It is 0.012 for matches with a top-20 player, against 0.043 when the better-ranked player is outside the top 100.

A post-hoc check of Phase 4's round-aware model, which also uses earlier rounds of the same tournament, narrows the market's lead on later-round matches by about 30%, from 0.019 to 0.013. The market is still clearly ahead.

In the brief's terms (section 31): market efficiency was treated as a hypothesis, and on these data the market wins. That is a rigorous negative result, not a failed experiment.

The data and the join are audited in [Phase 5 - Market Data Audit.md](Phase%205%20-%20Market%20Data%20Audit.md). The last section, "What Phase 5 did", says all this in ordinary language.

## Data

**Market prices.** Valuebetennis records an opening and a closing decimal price for each player (CC BY 4.0). The two prices are kept apart:
- **the opening price** is the decision price, the only one a forecaster could have used;
- **the closing price** is a benchmark only.

**Model probabilities.** Nothing was refitted. Each probability is the saved, chronological prediction of a model fitted only on earlier matches:

| Period | Phase 3 and Phase 4 fitted on | Source |
|---|---|---|
| 2021–2023 | 2010–2020 | Phase 3 and 4 development fits |
| Jan 2024–May 2026 | 2010–2023 | Phase 3 final run; Phase 4 retrospective fit |
| Jun–Oct 2026 | 2010–May 2026 | Phase 4 erratum 1's corrected held-out rebuild |

Elo and surface Elo are the Phase 2 ratings. The probabilities are **tournament-start** probabilities: they use no result from the same tournament.

**Population.** Every model match linked to an odds row with usable opening prices, at every level the model was built on:
- Grand Slams and Masters;
- the other ATP and WTA events;
- Davis Cup and Billie Jean King Cup;
- the Finals and Olympics;
- the WTA ITF-level events Sackmann includes.

Main-draw rounds only, as in every earlier phase.

| Split | Period | Matches | With closing prices |
|---|---|---:|---:|
| Development | 2021–2023 | 15,164 | 8,924 |
| Evaluation | Jan 2024–May 2026 | 11,540 | 11,367 |
| Evaluation | Jun–Oct 2026 | 2,306 | 2,263 |

## Method

**Margin.** 1 / price is a raw probability, and the two sides sum to the overround, about 1.034 here. The excess is the bookmaker's margin, so the fair probabilities have to be estimated. Four methods were implemented: multiplicative, additive, power and Shin.

**The questions,** fixed before any evaluation row was opened:

| | Question | Test |
|---|---|---|
| Q1 | Do Phase 4's probabilities beat the opening market? | Log loss and Brier per match, paired, standard errors clustered by tournament date |
| Q2 | Does the model add information to the price? | A blend, logit P = w_m·logit(market) + w_x·logit(model), with weights fitted on 2021–2023, scored against the market alone |
| Q3 | Does the model–market discrepancy predict what the market misses? | The slope b of (result − market) on (model − market). b = 0: no information; b = 1: the model is right where it disagrees |
| Q4 | Is any gap concentrated somewhere? | The Q1 gap by year, tour, surface, level, the favourite's price, and ranking. 23 slices, descriptive only |
| Q5 | Does a simulated decision rule survive costs, risk and uncertainty? | Paper rules at opening prices, below |

**The paper rules** were written into the code before the development run, and were not tuned on it:

| Rule | Decision probability | Back a side when | Stake |
|---|---|---|---|
| Primary | Phase 4 | expected value p·o − 1 ≥ 5% | 1 unit |
| Primary, 2% haircut | Phase 4 | same, at prices 2% worse | 1 unit |
| Primary, quarter Kelly | Phase 4 | same | ¼ of the Kelly fraction of the bankroll, at most 2% |
| Secondary | the frozen blend | expected value ≥ 2% | 1 unit |

Every rule uses opening prices, at most one side per match, and settles in order of start time. Return intervals come from 2,000 bootstrap draws of whole tournament dates.

**Closing line value** asks whether the price a rule took was better than the closing price on the same side (opening ÷ closing − 1). It is a way to judge decisions that does not wait for results.

**Development and evaluation.**
- **Development, 2021–2023,** could choose only two things: the margin method (the one with the lowest opening-market log loss) and the blend weights.
- **The protocol was then frozen** (`experiments/phase5_frozen_protocol.json`, sha256 `df243323af3655e7…`). It records the choices, the questions, the rules, the slices, the reporting rule, and the sha256 of all eight Phase 5 code files and all nine inputs.
- **The evaluation command** checks every hash, opens the evaluation rows only with that protocol, and refuses to run twice.

**Disclosures:**
1. **The development result was already known.** The 2021–2023 model–market comparison had been seen on 6 November by an earlier draft that was later removed.
2. **The evaluation window is fresh for the market question, not for the models.** The models' outcomes there were seen in Phases 3 and 4, but the models had never been compared with the market there.
3. **The protocol was not committed before the run.** Unlike Phase 4, it was frozen and evaluated in one session, under a minute apart (12:49:42 and 12:50:09 on 8 November), and committed afterwards. Its integrity rests on the recorded hashes and timestamps.

## Development, 2021–2023

| Forecast | Log loss | Brier | Accuracy | Calibration a, b |
|---|---:|---:|---:|---|
| Opening market (power method) | **0.5831** | **0.2004** | **68.36%** | +0.012, 1.021 |
| Phase 4 | 0.6088 | 0.2110 | 66.35% | +0.018, 0.945 |
| Phase 3 | 0.6115 | 0.2122 | 65.93% | +0.017, 0.987 |
| Elo | 0.6231 | 0.2169 | 64.77% | +0.015, 0.798 |
| Surface Elo | 0.6214 | 0.2161 | 65.34% | +0.016, 0.785 |

**What development chose:**
- **The margin method.** Opening-market log loss was 0.58392 multiplicative, 0.58334 additive, 0.58310 power and 0.58334 Shin. **Power** was chosen.
- **The blend weights.** For Phase 4: market 1.099, model −0.093 (model weight 95% −0.182 to +0.004). For Phase 3: 1.114 and −0.120. The model gets no positive weight. The market weight above 1 means the opening price is slightly too cautious, and the model's small negative weight trims it.

**What the development rows already showed:**
- Phase 4 minus market: +0.0257 (se 0.0017).
- Information slope: −0.084 (p = 0.03).
- Primary rule: −10.0% per unit staked (interval −12.8% to −7.1%). The quarter-Kelly version ended at a bankroll of zero.
- Closing beat opening by 0.0039.

## Evaluation, January 2024 – October 2026 (run once)

13,846 matches.

| Forecast | Log loss | Brier | Accuracy | Calibration a, b |
|---|---:|---:|---:|---|
| Opening market (power) | **0.5896** | **0.2031** | **68.07%** | +0.032, 0.972 |
| Blend, Phase 4 (frozen weights) | 0.5896 | 0.2030 | 68.16% | +0.032, 0.951 |
| Blend, Phase 3 (frozen weights) | 0.5895 | 0.2030 | 67.97% | +0.032, 0.951 |
| Phase 4 | 0.6132 | 0.2130 | 65.42% | +0.029, 0.920 |
| Phase 3 | 0.6156 | 0.2140 | 65.27% | +0.030, 0.953 |
| Elo | 0.6267 | 0.2186 | 64.44% | +0.031, 0.766 |
| Surface Elo | 0.6266 | 0.2184 | 64.53% | +0.030, 0.756 |

### Q1 and Q2: forecast against the opening market

Log loss per match minus the market's; positive means worse than the market. Standard errors are clustered by tournament date.

| | Gap (se) | 95% interval | p | Brier gap |
|---|---|---|---:|---|
| **Q1 Phase 4** | **+0.0236 (0.0019)** | +0.0198 to +0.0274 | <0.001 | +0.0099 |
| Phase 3 | +0.0260 (0.0020) | +0.0220 to +0.0299 | <0.001 | +0.0109 |
| Elo | +0.0371 (0.0025) | +0.0322 to +0.0421 | <0.001 | +0.0155 |
| Surface Elo | +0.0370 (0.0023) | +0.0324 to +0.0415 | <0.001 | +0.0153 |
| **Q2 Phase 4 blend (frozen)** | **−0.0000 (0.0002)** | −0.0004 to +0.0003 | 0.91 | −0.0000 |
| Phase 3 blend (frozen) | −0.0001 (0.0002) | −0.0005 to +0.0003 | 0.67 | −0.0001 |

- **By period:** Phase 4 minus market is +0.0252 (se 0.0021) for January 2024–May 2026 and +0.0157 (se 0.0046) for June–October 2026.
- **By tour:** ATP +0.0221, WTA +0.0252.

**Q1: not supported.** The market is clearly better. **Q2: not supported.** The blend's interval includes zero, so the model's probabilities carry no information the opening price lacks.

### Q3: does the disagreement carry information?

| Model | Slope b (se) | 95% interval | p |
|---|---|---|---:|
| **Phase 4** | **−0.067 (0.044)** | −0.152 to +0.019 | 0.13 |
| Phase 3 | −0.069 (0.041) | −0.150 to +0.012 | 0.09 |
| Elo | −0.076 (0.036) | −0.146 to −0.006 | 0.03 |
| Surface Elo | −0.081 (0.035) | −0.148 to −0.013 | 0.02 |

**Q3: not supported.** No model's disagreement predicts results the market misses. The point estimates are all slightly *negative*: where a model disagrees, the result tends to land even a little beyond the market's view. The bucket table shows it.

| Phase 4 − market (player A's side) | Matches | Market | Phase 4 | Observed |
|---|---:|---:|---:|---:|
| below −0.15 | 712 | 0.652 | 0.449 | **0.662** |
| −0.15 to −0.10 | 1,003 | 0.612 | 0.490 | 0.622 |
| −0.10 to −0.05 | 2,061 | 0.582 | 0.510 | 0.589 |
| −0.05 to −0.02 | 1,797 | 0.551 | 0.516 | 0.573 |
| −0.02 to +0.02 | 2,674 | 0.500 | 0.500 | 0.513 |
| +0.02 to +0.05 | 1,808 | 0.433 | 0.468 | 0.447 |
| +0.05 to +0.10 | 2,073 | 0.413 | 0.485 | 0.403 |
| +0.10 to +0.15 | 1,025 | 0.395 | 0.517 | 0.373 |
| above +0.15 | 693 | 0.352 | 0.559 | **0.355** |

In every bucket the observed win rate sits next to the market's probability, not the model's. Phase 4 mostly disagrees by rating the market's favourite lower, and the favourite wins as often as the market said.

### The closing line (a benchmark only)

| 13,630 matches with closing prices | Gap (se) | 95% interval |
|---|---|---|
| Closing minus opening | −0.0043 (0.0006) | −0.0055 to −0.0030 |
| Phase 4 minus closing | +0.0282 (0.0021) | +0.0242 to +0.0323 |

**The market learns between the opening and the start.** The closing price is better again, by 0.004. Measured against the closing price, Phase 4 trails by 0.028.

### Q4: where the gap is (descriptive)

| Slice | Matches | Phase 4 − market (se) |
|---|---:|---|
| 2024 | 4,297 | +0.0309 (0.0039) |
| 2025 | 5,052 | +0.0209 (0.0029) |
| 2026 | 4,467 | +0.0194 (0.0028) |
| ATP / WTA | 7,034 / 6,812 | +0.0221 / +0.0252 |
| Hard / clay / grass | 8,298 / 3,761 / 1,736 | +0.0224 / +0.0276 / +0.0214 |
| Grand Slam | 2,809 | +0.0274 (0.0059) |
| Masters / WTA 1000 | 4,000 | **+0.0164** (0.0028) |
| Other tour events | 6,420 | +0.0249 (0.0027) |
| Davis / BJK Cup | 218 | +0.0131 (0.0113) |
| Finals, Olympics, ITF-level | 399 | +0.0552 (0.0206) |
| Market favourite 50–60% | 4,153 | +0.0245 |
| 60–75% | 5,693 | +0.0205 |
| 75–90% | 3,079 | +0.0238 |
| 90% or more | 921 | +0.0387 |
| Better-ranked player in the top 20 | 5,096 | **+0.0117** (0.0023) |
| … ranked 21–100 | 7,721 | +0.0281 |
| … outside the top 100 | 979 | +0.0434 |

The year slices count by match start. 30 evaluation matches started on 29–31 December 2023, ahead of tournaments Sackmann dates in 2024, and they form a small "2023" slice.

- **The market leads in every slice with enough matches.** The only slices whose intervals include zero are the smallest: Davis Cup, missing ranks and unknown surface.
- **The gap is smallest where the most is known about the players:** top-20 matches and the biggest events.
- **It is largest for lower-ranked players and heavy favourites.** There, the model's sparse data and its pull toward 50% cost the most.
- **The gap shrinks from 2024 to 2026,** in line with the models being refitted on more recent data.

With 23 slices, about one would look notable by chance. None of these is a finding on its own.

### Q5: paper decisions (simulated; no real bet)

| Rule | Bets | ROI per unit (95%) | If the market were right | Hit rate @ mean odds | Max drawdown | Closing line value |
|---|---:|---|---:|---|---|---|
| **Primary** | 8,721 | **−8.9%** (−12.6% to −5.2%) | −7.5% | 37.1% @ 3.85 | 821 units | +0.6%; 48.2% beat the close |
| Primary, 2% haircut | 8,721 | −10.0% (−13.7% to −6.3%) | −8.6% | 37.1% @ 3.85 | 911 units | same |
| Primary, quarter Kelly (2% cap) | 8,721 | −16.6% | −6.4% | 37.1% @ 3.85 | 100% of bankroll | same |
| Secondary, frozen blend | 66 | +12.9% (−9.1% to +35.6%) | −3.1% | 62.1% @ 1.95 | 3.7 units | −1.6%; 35.4% beat the close |

**Q5: not supported.**
- **The primary rule bets on most matches** (8,721 of 13,846), mostly underdogs at a mean price of 3.85. That's because Phase 4 rates favourites lower than the market does.
- **It loses more than the margin alone would cost.** The market-right benchmark is −7.5%, and the rule returns −8.9%. The bucket table suggests a higher threshold would not help, because it would select the biggest disagreements, where the market is most clearly right. That was not tested, since only the pre-registered threshold was run.
- **Its picks beat the closing price half the time,** which is what a rule with no information would do.
- **Kelly sizing compounds the losses.** It stakes a share of a shrinking bankroll on 8,721 bets with negative expected value, and the bankroll falls to zero. Sizing cannot rescue a probability that is worse than the price.
- **The secondary rule's +12.9% is not evidence of anything.** It rests on 66 bets, its interval runs from −9% to +36%, the same rule lost 10.8% on 101 development bets, and its picks mostly lost to the closing price.

## What it means

- **Prediction against a strong benchmark.** Phases 3 and 4 beat Elo and the rankings, with better probabilities, and the market is a much stronger benchmark again.
  - **The scale:** Phase 4's gain over Phase 3 was 0.005 log loss per match, and the market's lead over Phase 4 is about five times that.
  - **Why the market has more information:** prices absorb injuries, withdrawals, motivation, conditions, form inside the tournament, and many other people's models, none of which this project's features see.
- **No information beyond the price.** A blend that gives the model zero or negative weight, and a disagreement slope at or below zero, say the same thing: what Phase 4 knows, the opening price already knows.
- **Calibration explains the losing rule.** Phase 4 is somewhat overconfident on its own scale (calibration slope 0.92) and disagrees with the market mainly by doubting favourites. A rule built on those disagreements backs the wrong side more often than the price implies.
- **The negative result is the rigorous one.** The brief anticipated it (section 31): "Finding that market prices outperform the independent model would still constitute a meaningful research result if the methodology is rigorous." The methodology here has six safeguards:
  - point-in-time probabilities;
  - an audited join;
  - a decision price kept apart from the benchmark;
  - choices fixed on development data;
  - a hash-checked, one-time evaluation;
  - intervals on every claim.
- **Separating the five things** from brief section 28:
  - **The predictions are real.**
  - **The discrepancies are measured.**
  - **The hypothesis that they carry information is rejected.**
  - **The simulated decisions lose.**
  - **No economic outcome is claimed in either direction.**

## Post-hoc: the round-aware model against the market (not pre-registered)

*Added after the evaluation. Descriptive only; it does not change the frozen result.*

**Why check it.** The frozen comparison used tournament-start probabilities, which ignore results from the same tournament, while the market sees every earlier round. Phase 4's round-aware model R0 adds those earlier rounds, so it is the fairer model to put next to the market.

**How.** Its per-match predictions had not been saved for these years. They were reproduced by re-running the frozen R0 fits on earlier matches only:
- 2010–2020 for 2021–2023;
- 2010–2023 for January 2024–May 2026;
- 2010–May 2026 for June–October 2026, the corrected rebuild.

All three reproduced Phase 4's published scores exactly:
- R0 minus reference −0.0054 on 7,829 validation rows;
- R0 log loss 0.5994 on 6,959 retrospective rows;
- R0 log loss 0.5993 on 1,275 held-out rows.

R0 applies only to later-round matches, so the market, R0 and the tournament-start model are all scored on those matches.

| Later-round matches with opening prices | Market log loss | R0 | Phase 4 (tournament start) | R0 − market (95%) | Phase 4 − market |
|---|---:|---:|---:|---|---:|
| 2021–2023 (7,792) | 0.5888 | 0.6047 | 0.6101 | +0.0159 (+0.0123 to +0.0195) | +0.0213 |
| Jan 2024–Oct 2026 (7,462) | **0.5857** | 0.5988 | 0.6044 | **+0.0132** (+0.0088 to +0.0175) | +0.0187 |

**Accuracy** in January 2024–October 2026: market 68.5%, R0 67.1%, Phase 4 66.9%.

**The information slope** for R0 is +0.068 in the evaluation window (interval −0.066 to +0.202). It was −0.036 in 2021–2023. Neither is distinguishable from zero.

**What it shows:**
- **Earlier-round results narrow the gap but do not close it.** R0 cuts the market's lead on later-round matches from 0.019 to 0.013 per match, about 30% of it. That is the same 0.0056 gain R0 showed over the tournament-start model in Phase 4.
- **The market is still clearly better.** Its lead's interval excludes zero in both periods.
- **R0's disagreements with the price carry no reliable information.**
- **So part of the market's advantage is information from inside the tournament.** Much of the rest is information the project's data does not contain, such as injuries, withdrawals, conditions and other bettors' models.

`python -m matchup_dna.posthoc_round_aware_market` writes `results/phase5/experiments/posthoc_round_aware_market.txt` and `.json`. It stops unless all three reproductions match.

## Limits

- **Not a fully fresh window.** The models' outcomes in the evaluation window had been seen before, so this is a fresh test of the model-against-market question only.
- **Unsealed protocol timing.** The protocol was frozen and evaluated in one session, before your commit. Integrity rests on the recorded hashes and timestamps.
- **Prices without timestamps.** The two Valuebetennis prices carry no timestamp, so the opening price is assumed to be available when a forecaster would act.
  - The frozen comparison used tournament-start probabilities, which ignore results from the same tournament that the market can see. The post-hoc round-aware check above shows that this explains about 30% of the market's lead on later-round matches, not all of it.
- **Gaps in the window.** The evaluation loses the matches inside the source's outages, January–March 2024, October 2024 and May 2026, and the 8% of model matches that could not be linked, mostly Davis Cup rubbers.
- **Untested sizing and pricing.** Only flat and capped quarter-Kelly sizing were tried, and only one price haircut. Nothing here models liquidity, limits or the price a real account could get.

## Reproducing

```powershell
python -m matchup_dna.audit_valuebetennis          # market data audit and the join (no comparison)
python -m matchup_dna.phase5_experiment dataset    # linked matches with opening prices -> results/phase5/dataset.csv
python -m matchup_dna.phase5_experiment develop    # 2021-2023 only: margin method, blend weights, all analyses
python -m matchup_dna.phase5_experiment freeze     # experiments/phase5_frozen_protocol.json (never overwritten)
python -m matchup_dna.phase5_experiment evaluate   # once; checks every hash; results/phase5/evaluation/
python -m unittest discover -s tests
```

The evaluation refuses to run again while `results/phase5/evaluation/` exists. Each run appends to `experiments/phase5_log.md`.

## Concepts used in Phase 5

- **Implied probability and overround.** A decimal price o pays o per unit if it wins, so 1/o is the probability that would make the bet fair. Prices of 1.90 on both players give 0.526 + 0.526 = 1.053. The extra 5.3% is the bookmaker's margin, and treating 1/o as fair would invent an "edge" that is only that margin.
- **Removing the margin:**
  - multiplicative divides both raw probabilities by the overround;
  - additive subtracts half the margin from each;
  - power raises both to a power chosen so they sum to 1, which puts more of the margin on the longshot, as bookmakers tend to;
  - Shin models a market with a share of informed bettors; for two players it equals additive.

  Power fitted these markets best, and it was chosen on development data only.
- **Opening against closing.** The opening price is what a forecaster could have used. The close has seen more information, so it is usually more accurate (by 0.004 here). Using it as if it were available earlier is a timing leak.
- **Log loss, not accuracy.** The market and the model pick the same winner most of the time. What separates them is how well their probabilities are calibrated to outcomes, which log loss and the Brier score measure and accuracy ignores.
- **The blend (encompassing) test.** If a model knows something the market does not, a regression of results on both forecasts gives the model a positive weight, and the blend scores better out of sample. Here the weight was slightly negative, and the blend scored the same as the market.
- **The information slope.** Regress what the market got wrong (result − market) on the disagreement (model − market):
  - b = 0 means disagreements are noise;
  - b = 1 means the model is right whenever it disagrees.

  Subtracting two probabilities magnifies calibration errors, which is why an overconfident model can show a slightly negative b.
- **Expected value.** p × o − 1 is the expected net return per unit, and it is only as good as p. A probability that is too high on underdogs turns into a "positive expected value" that is really a loss.
- **Kelly sizing.** Kelly stakes the share of bankroll that maximizes long-run growth, *if p is right*. With a p that is worse than the price, it bets more on the worst disagreements and drives the bankroll to zero. Capping the stake slows that, but does not stop it.
- **Drawdown and losing runs.** These are the worst peak-to-trough fall and the longest streak of losses. A return figure without them hides the risk.
- **Closing line value.** If a rule's prices are regularly better than the closing price, it was acting on information before the market. Here the picks beat the close about half the time: no information.
- **Clustered errors and the cluster bootstrap.** Matches in one tournament week share players and news, so they are not independent. Standard errors treat a tournament date as one cluster, and return intervals resample whole tournament dates.
- **Multiple testing.** 23 slices at the 5% level will produce about one false "finding" by chance. Slices are reported, never selected from.

## What Phase 5 did

Phases 3 and 4 built models that predict tennis matches better than Elo ratings or rankings. Phase 5 asked the harder question: are they better than the betting market? Bookmakers' prices are the strongest public forecast there is, because they absorb the opinions and information of everyone betting.

**The data.** The odds came from Valuebetennis, which records an opening and a closing price for each player. First, every odds row had to be matched to the right match in the project's data. That was harder than it sounds: the two sources spell many players differently. "Cori Gauff" is Coco Gauff, and "Taylor Harry Fritz" is Taylor Fritz. Without care, every Gauff and Fritz match would have been dropped. The matching checks players through the opponents they faced, never by name alone, and it linked 92% of the model's matches.

**The method.** Everything was decided on 2021–2023: how to strip the bookmaker's cut out of the prices, how to blend model and market, and which simple betting rule to test. The decisions were then locked in a file with fingerprints of every input and line of code. The test on January 2024–October 2026 ran once.

**The result: the market wins clearly.** Its probabilities were better than Phase 4's by about 0.024 log loss per match, five times the gain Phase 4 made over Phase 3. Adding the model to the market's price improved nothing. When the model disagreed with the market, the result followed the market. A paper strategy that bet whenever the model saw value lost about 9% of every unit staked, more than the bookmaker's margin alone would explain. Betting a share of the bankroll each time lost all of it, on paper.

The gap is smallest for matches with top-20 players and at the biggest events, and it shrank from 2024 to 2026, but it never closed.

That is a real answer to a real research question. A model built on results, ratings, rankings and serve-return statistics knows less than the betting market, and its disagreements with the market are not an edge. It is better to establish that with a careful method than to claim a profit that would not survive one.
