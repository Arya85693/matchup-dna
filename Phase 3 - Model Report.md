# Matchup DNA — Phase 3 Model Report

**Status:** Stages 0–5 complete, protocol frozen 5 November 2026. **Stage 6, the final evaluation on 2024–May 2026, has not been run.**  
**Question:** Does pre-match information beyond Elo give better win probabilities than Elo, on ATP and WTA matches separately?  
**Answer so far, on validation only:** Yes. A logistic regression that adds ranking, inactivity, and recent form beats calibrated surface Elo by 0.0084 log loss per match (clustered standard error 0.0013), on both tours and in every validation year. A gradient-boosted model is a further 0.0015 better (standard error 0.0007), which narrowly passes the keep rule. The logistic model is still frozen as the primary model, and LightGBM is scored as secondary. The Experiment D section explains why. Validation numbers are optimistic because about two dozen comparisons were made on these three years. The reserved test is the unbiased estimate.

## Data and splits

The model input is one row per completed best-of-3 or best-of-5 tour-level match, built by `python -m matchup_dna.features`.

| Split | Tournament weeks | ATP | WTA | Use |
|---|---|---:|---:|---|
| Training | 2010–2020 | 29,712 | 28,157 | Fitting models, calibration, and everything chosen inside the training years |
| Validation | 2021–2023 | 8,366 | 7,673 | Choosing feature groups and models with the keep rule |
| Reserved | 1 January 2024–25 May 2026 | 7,190 | 6,542 | One final test, not yet run |

Each row compares player A with player B. A is chosen by a hash of the match id and the two player ids, so it never depends on who won. A won 49.93% of training rows and 50.54% of validation rows. Ratings and player histories are replayed one tournament date at a time, so every feature uses only earlier dates. The same rule is applied in Phase 2 and is described in the [Phase 2 report](Phase%202%20-%20Elo%20Report.md).

Every model is fitted separately for ATP and WTA. The combined score pools the two tours' predictions.

## Stage 0: safeguards

- `results/phase2_test_predictions.csv` holds the 2024–2026 outcomes from the first Phase 2 run. It was moved to `results/archive_do_not_use/`.
- Development code reads data only through `load_split`, which refuses anything except the training and validation files. The reserved file has no outcome column.
- Reserved outcomes are rebuilt from the raw files only inside `python -m matchup_dna.experiment final`. That command needs `--confirm`, checks the rebuilt rows against the saved reserved features, and refuses to run if its output folder already exists.
- Every run writes its output and a manifest to `results/phase3/experiments/`. The manifest holds input hashes, the git commit, and package versions. Every run also appends an entry to `experiments/log.md`.
- Player A is random, so every model has to give P(B wins) = 1 − P(A wins). Every logistic feature is an A-minus-B difference, or a difference times something symmetric, and the logistic models have no intercept. LightGBM is trained on both orderings of each match, and its prediction is averaged with one minus the prediction for the swapped match. Tests check this for every model type.
- Learned preprocessing is fitted on the fitting rows only: the rank given to unranked players, the mean experience used to center an interaction, and feature scaling. A test checks that predicting on other rows doesn't change them.

**Keep rule, fixed before Experiment C.** A change is kept only if all three of these hold:

1. Combined validation log loss falls by more than two clustered standard errors.
2. Neither tour gets worse by more than one of its own standard errors.
3. At least two of the three validation years improve.

Standard errors are clustered by tournament date. They allow matches in the same week to be correlated, but they ignore that the same player's results are correlated across weeks. So they are rough guides, not formal tests.

## Experiment A: recalibrating Elo

**Temperature scaling** keeps the sign of Elo's log-odds and multiplies their size: \(p' = \sigma(b \cdot \text{logit}(p))\). A value of \(b < 1\) pulls every probability toward 0.5, which is the fix for an overconfident model. The parameter is fitted on 2010–2020, separately per tour.

| Tour | Elo \(b\) | Surface Elo \(b\) | Platt intercept, surface Elo |
|---|---|---|---|
| ATP | 0.824 | 0.822 | −0.005 |
| WTA | 0.807 | 0.798 | −0.012 |

The Platt intercept comes out near zero, as expected when player A is random. So the one-parameter temperature form is used.

On 2021–2023 validation:

| Model | ATP log loss | WTA log loss | Combined | Combined Brier | Change vs raw surface Elo (se) |
|---|---|---|---|---|---|
| Elo | 0.6277 | 0.6186 | 0.6233 | 0.2170 | +0.0018 (0.0012) |
| Surface Elo | 0.6245 | 0.6183 | 0.6215 | 0.2161 | — |
| Elo, temperature | 0.6232 | 0.6171 | 0.6203 | 0.2160 | −0.0013 (0.0012) |
| **Surface Elo, temperature** | **0.6196** | **0.6161** | **0.6179** | **0.2150** | **−0.0036 (0.0008)** |

Calibration alone is worth twice the whole surface-Elo gain over ordinary Elo. It helps on both tours: by 0.0049 on ATP matches (standard error 0.0010) and by 0.0022 on WTA matches (0.0010). Accuracy doesn't change, because a monotone rescaling never changes who the favorite is.

ATP favorites that raw surface Elo gives 0.8–0.9 won 78.5% of the time. After scaling, favorites in that bucket are predicted at 0.842 and win 83.2%.

Two variants were checked and did not do better:
- one \(b\) shared by both tours (combined 0.6178);
- \(b\) fitted on 2016–2020 only (combined 0.6178).

**Calibrated surface Elo is the benchmark that additional features have to beat:** 0.6196 on ATP matches, 0.6161 on WTA matches, and 0.6179 combined.

## Experiment B: logistic regression on the two Elo ratings

The model is \(\text{logit}\,P(A) = \beta_1 \cdot \text{logit}(p_{\text{Elo}}) + \beta_2 \cdot \text{logit}(p_{\text{surface Elo}})\), with no intercept.

A coefficient of 1 on a feature reproduces that Elo model exactly. Temperature scaling is the special case with only one of the two features. So this model adds exactly one freedom: it learns how much weight each rating gets. The L2 penalty was chosen inside the training years, by fitting on 2010–2017 and scoring on 2018–2020. It came out at 1000 for ATP and 100 for WTA.

| Tour | \(\beta_1\), ordinary Elo | \(\beta_2\), surface Elo | Sum | Surface share |
|---|---|---|---|---|
| ATP | 0.339 | 0.401 | 0.740 | 0.54 |
| WTA | 0.289 | 0.513 | 0.802 | 0.64 |

**How to read the coefficients:**
- The sum, about 0.74–0.80, is the overconfidence correction, similar to the temperature found in Experiment A.
- The split shows that WTA predictions should lean more on surface Elo than ATP predictions do.

On validation, the change against calibrated surface Elo is +0.0000 on ATP matches (standard error 0.0007), −0.0008 on WTA matches (0.0005), and −0.0003 combined (0.0004). That fails the keep rule. **Re-weighting the two ratings adds nothing beyond rescaling them.**

Two numbers separate rescaling from information:
- Moving from raw surface Elo to Experiment B is worth 0.0039 per match.
- 0.0036 of that comes from temperature scaling alone, so the rest is within noise.

## Experiment C: adding pre-match information

Feature groups were added to Experiment B one at a time, in an order fixed beforehand. Each group was kept or dropped by the keep rule.

| Group | Features (each as A minus B) | Missing data handling |
|---|---|---|
| Rank | log rank; missing-rank indicator | Missing rank (1–4% of rows) set to the 99th percentile of training ranks, plus the indicator |
| Experience | log(1 + rated matches); surface log-odds × centered log(1 + fewer player's matches) | None needed |
| Surface experience | log(1 + matches on this surface) | No recorded surface counts as 0 |
| Inactivity | log(1 + days since last played match), capped at 365 | No previous match counts as 365 (about 3% of rows) |
| Form | mean of (result − Elo expected) over the last 10 rated matches | 0 with no history |

"Played" means completed or retired. Walkovers and defaults are not time on court.

**Forward selection on validation.** Each row compares the model with the new group against the model without it.

| Step | ATP change (se) | WTA change (se) | Combined (se) | Years better | Decision |
|---|---|---|---|---|---|
| + rank | −0.0061 (0.0013) | −0.0047 (0.0017) | −0.0054 (0.0011) | 3 of 3 | Keep |
| + experience | +0.0020 (0.0004) | −0.0001 (0.0001) | +0.0010 (0.0002) | 0 of 3 | Reject |
| + surface experience | +0.0035 (0.0009) | −0.0001 (0.0002) | +0.0018 (0.0005) | 0 of 3 | Reject |
| + inactivity | −0.0012 (0.0008) | −0.0031 (0.0008) | −0.0021 (0.0006) | 3 of 3 | Keep |
| + form | −0.0004 (0.0002) | −0.0006 (0.0004) | −0.0005 (0.0002) | 3 of 3 | Keep |

**Ablation.** Each group was also tried alone on Experiment B, and each kept group was removed again from the selected model. Rank alone gives −0.0054, and inactivity alone gives −0.0040. Removing rank costs 0.0037, inactivity 0.0021, and form 0.0005. The two experience groups make ATP predictions worse in every form tried, even though their penalty was tuned. The likely reason is that their relationship shifted between the training and validation years, but this was not investigated.

**Selected model:** Elo, rank, inactivity, and form.

| Model, 2021–2023 | ATP log loss | WTA log loss | Combined | Brier | Accuracy |
|---|---|---|---|---|---|
| Surface Elo, temperature | 0.6196 | 0.6161 | 0.6179 | 0.2150 | 65.26% |
| Logistic, Elo only (B) | 0.6196 | 0.6153 | 0.6176 | 0.2148 | 65.01% |
| **Logistic, selected** | **0.6119** | **0.6070** | **0.6095** | **0.2113** | **66.10%** |

Against calibrated surface Elo, the change is −0.0076 on ATP matches (standard error 0.0017), −0.0091 on WTA matches (0.0019), and −0.0084 combined (0.0013).

**Where the gain holds:**
- every validation year on both tours: ATP 2021, 2022, and 2023 by 0.004–0.011, and WTA 2021, 2022, and 2023 by 0.006–0.012;
- every surface: ATP clay 0.6323 → 0.6220, and WTA hard courts 0.6126 → 0.6046;
- after removing the 967 overlap-flagged matches, where the combined change is still −0.0084.

The model is also well calibrated. ATP favorites predicted at 0.747 won 75.0% of the time, and WTA favorites predicted at 0.746 won 75.5%.

**Coefficients, fitted on 2010–2020** (feature units):

| Feature | ATP | WTA |
|---|---|---|
| Ordinary Elo log-odds | +0.228 | +0.144 |
| Surface Elo log-odds | +0.315 | +0.434 |
| log rank, A minus B | −0.201 | −0.186 |
| A unranked minus B unranked | −0.884 | −1.565 |
| log(1 + days since last match), A minus B | −0.124 | −0.117 |
| Form, A minus B | +0.135 | +0.284 |

**What the coefficients mean, near even odds:**
- **Rank.** A player whose rank number is twice the opponent's, for example 40 against 20, loses about 0.14 log-odds, roughly 3.5 points of win probability, beyond what Elo says.
- **Inactivity.** Coming back after 60 days against an opponent who played a week ago costs about 0.25 log-odds, roughly 6 points.
- **Form.** Form adds little.
- **Elo shares strength with rank.** With rank in the model, the Elo coefficients add up to only 0.54 on ATP and 0.58 on WTA.

**Why rank helps.** Elo here rates tour-level matches only. The ranking also counts Challenger and ITF results, and how much a player has been playing. Missing rank is a strong negative signal. These are associations: rank and layoffs predict outcomes, but they are not causes.

## Experiment D: gradient-boosted trees

LightGBM was trained on the same feature groups. It also got symmetric context that the logistic model doesn't use: the less experienced player's log match count, whether the match is best-of-5, and the surface.

The number of leaves (7, 15, or 31) and the tree count were chosen inside the training years, by fitting on 2010–2017 and stopping early on 2018–2020:

| Tour | Leaves | Trees |
|---|---:|---:|
| ATP | 31 | 68 |
| WTA | 15 | 138 |

For ATP, 31 leaves is the edge of the grid.

| Model, 2021–2023 | ATP log loss | WTA log loss | Combined | Brier | Accuracy |
|---|---|---|---|---|---|
| Logistic, selected | 0.6119 | 0.6070 | 0.6095 | 0.2113 | 66.10% |
| LightGBM | 0.6099 | 0.6060 | 0.6080 | 0.2107 | 66.34% |

Against the selected logistic model, the change is −0.0020 on ATP matches (standard error 0.0011), −0.0010 on WTA matches (0.0009), and −0.0015 combined (0.0007). It is better in two of the three years.

That is 2.1 standard errors, so it **passes the keep rule narrowly**.

**Decision: the logistic model stays primary, and LightGBM is scored as secondary.** The keep rule is a filter, not the only input to this choice. Four reasons:
- The margin is small compared with how many comparisons have been made on validation.
- LightGBM's gain mixes two effects: non-linear structure, and the extra context features the logistic model doesn't have.
- Phase 4 tests matchup features and asks for interpretable reports, and that is much easier with a logistic model.
- A logistic model is simpler to serve in the later API phases.

The final test reports both models on the same matches. LightGBM is also compared directly with the logistic model.

## Diagnostic: K and surface blending

The official baselines stay Elo with K = 32 and surface Elo with K = 48, at a weight of 0.5. Comparing them mixes two changes at once: a different K, and blending in the surface rating. So the same-K comparison below holds K fixed and isolates the blending effect.

| Split, tour | Elo K=32 | Surface K=32 | Elo K=48 | Surface K=48 | Surface gain at K=32 (se) | Surface gain at K=48 (se) |
|---|---|---|---|---|---|---|
| Training ATP | 0.5986 | 0.5926 | 0.6040 | 0.5948 | −0.0059 (0.0007) | −0.0093 (0.0009) |
| Training WTA | 0.6179 | 0.6148 | 0.6221 | 0.6161 | −0.0031 (0.0007) | −0.0061 (0.0009) |
| Validation ATP | 0.6277 | 0.6229 | 0.6328 | 0.6245 | −0.0048 (0.0018) | −0.0083 (0.0020) |
| Validation WTA | 0.6186 | 0.6190 | 0.6220 | 0.6183 | +0.0004 (0.0017) | −0.0038 (0.0021) |

**What it shows:**
- At the same K, blending in a surface rating helps clearly on ATP matches.
- On WTA validation at K = 32 it doesn't help.
- At K = 48 blending looks better partly because K = 48 is too large for an overall-only rating, and averaging with the surface rating damps that.

**What it doesn't justify:**
- Changing the baseline. K was fixed on 1990–2009, and choosing it again now would mean tuning on validation.
- Reading these gaps as the pure value of surface information. The surface rating is updated less often, so its effective K is different.

## Frozen protocol

The frozen protocol is `experiments/frozen_protocol.json`, frozen on 5 November 2026. It was written from code at commit `6fd2495` plus uncommitted changes. It also records the hashes of the training and validation files.

| Item | Frozen choice |
|---|---|
| Selected model | Logistic regression per tour, with L2 1000 for ATP and 100 for WTA |
| Secondary model | LightGBM per tour, compared with calibrated surface Elo and with the selected model |
| LightGBM settings | ATP 31 leaves and 68 trees; WTA 15 leaves and 138 trees. Learning rate 0.05, at least 400 rows per leaf, seed 0, and single thread are constants in `experiment.py`, pinned by the commit. |
| Feature groups | Elo, rank, inactivity, and form. LightGBM also gets symmetric context: the less experienced player's log match count, best-of-5, clay, and grass. |
| Missing data | As in Experiment C. Imputation values are refitted on the fitting rows. |
| Refit | Both models and both temperature scalings refitted on 2010–2023, with no setting re-chosen |
| Comparisons | The selected model against Elo, surface Elo, Elo with temperature, and surface Elo with temperature |
| Primary metric | Log loss per tour and combined, paired against each comparison on the same 13,732 matches, with standard errors clustered by tournament date |
| Secondary | Brier score, accuracy, reliability buckets, and results by surface and by year |
| Robustness | The paired comparisons repeated without overlap-flagged matches |
| Final command | `python -m matchup_dna.experiment final --protocol experiments/frozen_protocol.json --confirm` |

Before running the final command, the code and the protocol should be committed, so the run records a clean commit.

## Final evaluation, 2024–May 2026

**Not yet run.**

## Limits

- The reserved period's Elo-only results were published once, in the first Phase 2 report, before this split existed. The Elo settings were chosen before then. No Phase 3 model or choice has used reserved outcomes.
- About two dozen model comparisons were made on the 2021–2023 validation years: seven calibration variants, the logistic regression on Elo, five forward-selection steps, eight ablations, and LightGBM. The selected model's validation numbers are therefore optimistic.
- Standard errors ignore that the same player's results are correlated across weeks.
- The LightGBM tree counts were tuned on 2010–2017 and are reused unchanged on 2010–2023, which is more data. The ATP leaf count sits at the edge of its grid.
- Serve and return statistics were not used. WTA coverage is 74–80% from 2010 to 2015, and serve-return style is Phase 4 matchup work.
- Inactivity counts tour-level matches only. A player coming from Challengers looks inactive.
- Dates are tournament start dates, so features are as of the start of each tournament, not each match.

## Reproducing

```powershell
pip install -r requirements.txt
python -m matchup_dna.features
python -m matchup_dna.experiment calibration
python -m matchup_dna.experiment elo-lr
python -m matchup_dna.experiment features
python -m matchup_dna.experiment gbm
python -m matchup_dna.experiment same-k
python -m unittest discover -s tests
```

Each command prints the numbers in its section. Each also writes `results/phase3/experiments/<name>.txt` and a manifest, and appends to `experiments/log.md`. `freeze` writes the protocol and refuses to overwrite an existing one.
