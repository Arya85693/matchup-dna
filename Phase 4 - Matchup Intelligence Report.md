# Matchup DNA — Phase 4 Matchup Intelligence Report

**Status:** Development complete, 6 November 2026. The protocol is ready to freeze. The one-time held-out evaluation (June to October 2026) has **not** been run, and its outcomes are still sealed.  
**Question:** Do serve-return abilities and genuine matchup interactions improve pre-match win probabilities beyond the Phase 3 model? And do physical workload and the difficulty of a player's route through a tournament add anything once a tournament is under way?  
**Answer, on the 2021–2023 validation years:**

- **Serving and returning ability adds information.** Adding opponent-adjusted serve and return estimates to the Phase 3 model lowers log loss by 0.0027 per match (clustered standard error 0.0007), on both tours (ATP 0.0036, WTA 0.0016) and in all three years. It is not a regularization artifact.
- **The other groups add nothing measurable:** surface-specific and recent serve-return, first- and second-serve detail, break points, all four matchup interactions, head-to-head, and recent workload. All of them fail the pre-registered keep rule.
- **LightGBM** with the same features is no better than the logistic model.
- **Once a tournament is under way, knowing its earlier results helps clearly:** 0.0054 per match (0.0011) on later-round matches. Neither the workload a player carried through earlier rounds nor the strength of the opponents they beat adds anything beyond those results.

The last section, "What Phase 4 did," says this in ordinary language. The data behind every number here is audited in [Phase 4 - Data Audit.md](Phase%204%20-%20Data%20Audit.md).

## Data and splits

The rows are Phase 3's: one per rated tour-level match, rebuilt by `python -m matchup_dna.phase4_experiment dataset`. The rebuilt training and validation files hash **byte for byte** to the values recorded in Phase 3's frozen protocol (`28bc190f…` and `37d1b1e4…`), so Phase 3 is reproduced, not changed. The build stops if they differ.

| Split | Tournament weeks | ATP | WTA | Use in Phase 4 |
|---|---|---:|---:|---|
| Training | 2010–2020 | 29,712 | 28,157 | Fitting, and every setting chosen on the inner split (fit 2010–2017, score 2018–2020) |
| Validation | 2021–2023 | 8,366 | 7,673 | Feature-group decisions with the keep rule. **Already used in Phase 3**, so its numbers are optimistic |
| Retrospective | 2024–May 2026 | 7,190 | 6,542 | Locked until the Phase 4 protocol is frozen. Then reported once as a robustness check, not a fresh test |
| Held-out | Editions starting 1 June 2026, finished by 5 November | about 1,300 | about 1,200 | Sealed. Scored once, after the freeze |

Each row adds these to Phase 3's columns:
- both players' serve-return profiles;
- earlier-round values for the round-aware track;
- games played in the previous 14 days;
- a shrunk head-to-head record.

For 2025 to May 2026, TML statistics and minutes fill 758 matches where Sackmann's are blank, under the audit's precedence rules: Sackmann values are never replaced, and one match where the two sources name different winners was skipped.

## Stage 0: safeguards

- **No Phase 1–3 file was changed.** New code reads what it needs itself. A test confirms that computing round-aware Elo leaves the canonical ratings identical.
- **Sealed sources.** The TennisData.app and TML readers remove every outcome column from held-out rows. TML's winner/loser layout is rebuilt into an order that doesn't depend on the winner, and only a frozen Phase 4 protocol unlocks it. Sealed rows are reported in aggregate only, because the players named in a later round reveal who won the earlier ones.
- **Locked retrospective file.** `load_phase4("retrospective")` refuses to open until a frozen protocol exists.
- **Held-out guards.** `holdout` needs `--confirm` and a protocol that is committed and unchanged in git. It refuses if its output folder exists. Tests cover each guard.
- **Logs.** Every run writes its output and a manifest (input hashes, git commit, package versions) to `results/phase4/experiments/`, and appends to `experiments/phase4_log.md`. The Phase 3 log and protocol are never written.
- **Symmetry.** Every feature is antisymmetric (A minus B, a difference times something symmetric, or a contrast like x_A·y_B − x_B·y_A), and the logistic models have no intercept. So P(B wins) = 1 − P(A wins) exactly, which a test checks for every group.
- **Keep rule, unchanged from Phase 3, fixed before any Phase 4 result.** A group is kept only if three conditions hold:
  1. combined validation log loss falls by more than two clustered standard errors;
  2. neither tour gets worse by more than one of its own standard errors;
  3. at least two of the three validation years improve.
- **Equal tuning.** The baseline and the candidate in every comparison are fitted on the same rows. Each gets L2 from the same inner split and grid. Every kept gain is rechecked with the two L2 values swapped.
- **Fixed order.** The order of tests was fixed in the plan and the audit addendum before any validation result existed.

## Serve-return profiles (tuned without outcomes)

Each player's estimate of each statistic, as of a match, pools their **earlier** completed matches:

\[
\hat p = \frac{\sum_k w_k\, s_k + m\,d\,\mu}{\sum_k w_k\, n_k + m\,d}, \qquad w_k = 0.5^{\,\text{age}_k / H}
\]

| Symbol | Meaning |
|---|---|
| \(s_k / n_k\) | Successes over attempts in match \(k\), for example service points won over service points played |
| \(w_k\) | Match \(k\)'s weight. It halves every \(H\) weeks |
| \(\mu\) | The tour average over 2010–2020 |
| \(d\) | The tour's average attempts per match |
| \(m\) | The prior strength in pseudo-matches |

**Opponent adjustment (one-pass Barnett–Clarke).** Before a match is pooled, its serve observation is credited for the opponent's pre-match return strength, \(n\,(\hat r_{opp} - \mu_r)\) extra points won. Its return observation is credited for the opponent's serve strength in the same way.

The settings were chosen per tour by forecasting each player's **service points won in their next match**, a target that ignores who won the match. The forecast is the Barnett–Clarke expected share,
\[
\hat s_{\text{server}} - (\hat r_{\text{returner}} - \mu_r),
\]
scored by binomial loss per point on 2018–2020 matches.

| Tour | Chosen | Loss per point | Best raw (unadjusted) | Tour average only |
|---|---|---:|---:|---:|
| ATP | half-life 52 weeks, prior 4 matches, adjusted | 0.65188 | 0.65200 | 0.65503 |
| WTA | half-life 52 weeks, prior 4 matches, adjusted | 0.68266 | 0.68277 | 0.68462 |

The grid was half-life 26, 52, or 104 weeks or none, by prior 1, 2, 4, 8, or 16 matches. The adjusted estimates beat the raw ones at every setting except WTA without decay, where they tie. The improvement over the tour average looks small per point, but a match has about 150 points, and these are differences in skill estimates, not in match predictions.

## Tournament-start track (primary)

Forward selection in the pre-registered order. Each row compares the model with the group against the model without it, on 2021–2023 (log loss per match; negative is better).

| Step | Group | ATP (se) | WTA (se) | Combined (se) | Years better | Decision |
|---|---|---|---|---|---|---|
| A1 | Serve and return, opponent-adjusted | −0.0036 (0.0011) | −0.0016 (0.0007) | **−0.0027 (0.0007)** | 3 of 3 | **Keep** |
| A2 | Surface-specific serve and return | +0.0002 (0.0009) | −0.0001 (0.0001) | +0.0001 (0.0005) | 2 of 3 | Reject |
| A3 | Recent serve and return (8-week half-life) | +0.0001 (0.0007) | −0.0008 (0.0003) | −0.0004 (0.0004) | 2 of 3 | Reject |
| B1 | First serves in, first- and second-serve points won, ace and double-fault rates | −0.0006 (0.0003) | +0.0002 (0.0002) | −0.0002 (0.0002) | 3 of 3 | Reject |
| B2 | Break points saved and converted | −0.0001 (0.0002) | −0.0001 (0.0002) | −0.0001 (0.0001) | 2 of 3 | Reject |
| C1 | Serve × opposing return product | +0.0000 (0.0000) | −0.0002 (0.0002) | −0.0001 (0.0001) | 1 of 3 | Reject |
| C2 | Elo × serve dominance | +0.0001 (0.0002) | −0.0004 (0.0002) | −0.0002 (0.0002) | 3 of 3 | Reject |
| C3 | Serve and return × grass, × clay | −0.0005 (0.0003) | +0.0000 (0.0001) | −0.0003 (0.0002) | 3 of 3 | Reject |
| C4 | Head-to-head against Elo, shrunk | −0.0002 (0.0001) | +0.0003 (0.0003) | +0.0000 (0.0002) | 1 of 3 | Reject |
| D-ts | Games played in the previous 14 days | +0.0016 (0.0006) | +0.0000 (0.0002) | +0.0009 (0.0003) | 0 of 3 | Reject |

The interactions (C1–C4) were each tested against a model that already held A1, so they had to add something beyond ordinary serve-return differences. **Final check:** the chosen model (Phase 3 groups + A1) passes against the Phase 3 groups, and removing A1 again costs 0.0027.

**The gain is not a regularization artifact.** With the candidate held at the baseline's L2, the gain is −0.0021 (0.0005). Against the baseline at the candidate's L2, it is −0.0026 (0.0006).

**The baseline reproduces Phase 3.** Re-chosen by the same inner split, its L2 is again ATP 1000, WTA 100. Its validation log loss is again 0.6119 ATP, 0.6070 WTA, and 0.6095 combined.

| Model, 2021–2023 | ATP log loss | WTA log loss | Combined | Brier | Accuracy |
|---|---|---|---|---|---|
| Surface Elo, temperature | 0.6196 | 0.6161 | 0.6179 | 0.2150 | 65.26% |
| Phase 3 groups | 0.6119 | 0.6070 | 0.6095 | 0.2113 | 66.10% |
| **Phase 3 groups + serve-return** | **0.6083** | **0.6054** | **0.6069** | **0.2101** | **66.62%** |

**Where the gain holds:**

| Slice | Gain against the Phase 3 groups (se) |
|---|---|
| ATP 2021 / 2022 / 2023 | −0.0026 / −0.0056 / −0.0026 |
| WTA 2021 / 2022 / 2023 | −0.0025 / −0.0011 / −0.0013 |
| Standard errors clustered by month instead of week | −0.0027 (0.0006) |
| Without the 967 overlap-flagged matches | −0.0027 (0.0007) |
| Both players have statistics history (15,364 matches) | −0.0031 (0.0006) |
| Less-observed player has under 10 matches of statistics | −0.0012 (0.0017), not clear |
| … 10 to 30 matches | −0.0030 (0.0009) |
| … over 30 matches | −0.0034 (0.0009) |

By surface: every named surface improves; ATP grass gains the most, 0.6046 to 0.5995. The 51 ATP matches with no recorded surface get worse, 0.6499 to 0.6714. The gain grows with how much serve history exists, which is what a real signal would do.

**Calibration.** On WTA the chosen model stays well calibrated (slope 1.004). On ATP it becomes slightly overconfident. Its calibration slope, from refitting logit P(win) = a + b·logit(p) on the validation rows, is 0.913, against 0.986 for the Phase 3 groups. ATP favorites predicted at 0.931 won 91.1% of the time. Log loss still improves, but a recalibration was not pre-registered and was not tried. This is recorded as a limit.

**Coefficients, fitted on 2010–2020 (feature units):**

| Feature | ATP | WTA |
|---|---:|---:|
| Elo log-odds | −0.286 | −0.169 |
| Surface Elo log-odds | +0.659 | +0.527 |
| log rank, A minus B | −0.191 | −0.176 |
| Unranked, A minus B | −0.973 | −1.550 |
| log(1 + days since last match), A minus B | −0.139 | −0.126 |
| Form, A minus B | +0.144 | +0.295 |
| **logit(serve estimate), A minus B** | **+1.681** | **+1.850** |
| **logit(return estimate), A minus B** | **+1.373** | **+1.242** |
| No statistics history, A minus B | −0.801 | −0.393 |

**How to read the serve and return coefficients:**
- **Size of the effect.** An ATP player who wins 66% of service points, against an opponent at 63%, has a serve logit gap of 0.131. That is worth 1.681 × 0.131 = 0.22 log-odds, roughly 5.5 points of win probability near even odds, beyond Elo, rank, inactivity, and form.
- **The Elo split.** With serve and return in the model, the two Elo coefficients share one signal: their sum is 0.37 (ATP) and 0.36 (WTA). The negative ordinary-Elo coefficient is not interpretable alone, so the matchup report shows the two as one line.
- **Associations, not causes.** These are associations: serve and return records predict outcomes beyond the ratings.

## LightGBM

LightGBM uses Phase 3's procedure:
- it is trained on both orderings of each match, and its prediction is averaged with the swapped prediction;
- leaves and tree count are chosen on the same inner split, with the same constants.

It was run once with the Phase 3 features and once with the chosen features. Both add the same symmetric context: the less experienced player's match count, best-of-5, clay, and grass.

| Model, 2021–2023 | ATP | WTA | Combined |
|---|---|---|---|
| LightGBM, Phase 3 features | 0.6099 | 0.6060 | 0.6080 |
| LightGBM, chosen features | 0.6084 | 0.6051 | 0.6068 |
| Logistic, chosen | 0.6083 | 0.6054 | 0.6069 |

- **The Phase 3 LightGBM is reproduced exactly** (0.6099 and 0.6060).
- **Serve-return helps LightGBM too:** −0.0012 (0.0005), all three years better.
- **But LightGBM is no better than the logistic model with the same features:** −0.0001 (0.0008), so it fails the keep rule.

In Phase 3 LightGBM was 0.0015 ahead. The serve-return features close that gap, which suggests its edge came from information the logistic model lacked, not from non-linearity. The logistic model stays primary. Under the rule fixed in Phase 3's code, LightGBM is not carried into the held-out test as a secondary model.

## Round-aware track: workload and route difficulty

These predictions also use the tournament's own earlier rounds, which are known before a later-round match. That is a different information set, so this track has its own baseline and its own sample:
- **Sample:** eligible matches after an edition's first round. That is 27,304 training rows and 7,829 validation rows, with Davis/BJK Cup ties, round robins, and unorderable editions excluded (audit, A6–A7).
- **Same rows:** every model in the track uses exactly these rows.

| Model, later-round validation matches | ATP | WTA | Combined | Brier | Accuracy |
|---|---|---|---|---|---|
| Reference: the chosen tournament-start model | 0.6062 | 0.6135 | 0.6096 | 0.2114 | 66.30% |
| **R0: + round-aware Elo shifts and earlier-round share of games won** | **0.6012** | **0.6077** | **0.6042** | **0.2092** | **66.73%** |
| D: R0 + games played in earlier rounds | 0.6016 | 0.6080 | 0.6046 | 0.2094 | 66.80% |
| E: R0 + mean pre-tournament Elo of opponents beaten, relative to own | 0.6014 | 0.6075 | 0.6042 | 0.2092 | 66.88% |

| Comparison | ATP (se) | WTA (se) | Combined (se) | Years better | Decision |
|---|---|---|---|---|---|
| R0 vs reference, the value of knowing earlier results | −0.0050 (0.0013) | −0.0059 (0.0018) | **−0.0054 (0.0011)** | 3 of 3 | Passes (baseline, not a hypothesis) |
| D vs R0, workload | +0.0004 (0.0003) | +0.0003 (0.0002) | +0.0003 (0.0002) | 0 of 3 | Reject |
| E vs R0, route difficulty | +0.0002 (0.0002) | −0.0002 (0.0001) | −0.0000 (0.0001) | 1 of 3 | Reject |

D + E and F (workload × route) were pre-registered to run only if both D and E passed, so they were not run.

**Diagnostics (reported only, never used to choose).** All of these were against R0:
- points played instead of games: +0.0003 (0.0002);
- minutes instead of games: +0.0006 (0.0003);
- the strongest opponent beaten: +0.0001 (0.0001).

**The finding holds in every slice:**
- D is +0.0004 in quarterfinals and later (2,407 matches), +0.0001 at Grand Slams, and +0.0003 without qualifiers and lucky losers.
- E is between −0.0000 and +0.0002 everywhere.
- **R0's gain is genuine earlier-round information, not the smaller sample.** R0 also beats the tournament-start features refitted on the *same* later-round rows, by −0.0039 (0.0010).
- **R0 corrects calibration.** The tournament-start model is overconfident on later-round matches (calibration slope 0.886), and R0 brings it to 0.977.

**How to read this.** Long matches and strong opponents in earlier rounds carry no predictive information *once the earlier results are known*. In plain terms, these data show no fatigue penalty that can be measured. They also show no "hardened by a tough draw" bonus beyond what a within-tournament Elo update already captures. These are associations in observational data. The proxies (games, points, minutes) are not measurements of fatigue, and rest days could not be studied because no source has match days before 2025.

## Rehearsal of the held-out pipeline (no outcomes)

The held-out period is built from TML and TennisData.app, not Sackmann. To check that the same code reproduces Sackmann-based predictions, `rehearse` runs it on editions starting 12 January to 17 May 2026, where:
- the provider rows are open;
- Sackmann's own matches for those weeks are removed from the history;
- Sackmann still has the same matches for comparison.

No win/loss outcome of these matches is scored. Only probabilities are compared, for models fitted on 2010–2023.

| Check | Result |
|---|---|
| Provider rows in the window | 2,170 TML; 2,299 TennisData.app main-draw |
| TennisData.app rows matched to TML rows | 2,029. **Both name the same winner in all 2,029** |
| TennisData.app rows added because TML lacks them | 145 (118 more had no usable result: canceled, awarded, or blank) |
| Duplicates removed | 7 TennisData.app rows matching TML rows by player ids; 1 provider match already in Sackmann |
| Player ids | TML: 4,305 by crosswalk, 3 by unique full name, 32 new to Sackmann. TennisData.app: 275 by crosswalk, 3 by unique surname and initial, 26 new |
| Rated matches | 2,240 built from providers; 2,201 in Sackmann; 2,129 matched one-to-one by Sackmann ids, round, and date |
| P3-refit probability, provider-built vs Sackmann-built | mean absolute difference 0.0037, median 0.0010, 90th percentile 0.0085; over 0.05 in 0.5% |
| P4-refit probability, provider-built vs Sackmann-built | mean 0.0041, median 0.0011, 90th percentile 0.0085; over 0.05 in 1.1% |
| Rank-source effect alone (Sackmann rows with provider ranks swapped in) | P3-refit mean 0.0011; P4-refit mean 0.0010; over 0.02 in under 1% |

Individual inputs often differ a little. Elo differences are identical in only 36% of matched rows, and days since the last match in 63%. That is because providers date an event by its first match day, which differs from Sackmann's tournament date by a day or two, so replay order shifts slightly. The probabilities barely move.

**Conclusion:** provider-built held-out features are a close, though not identical, substitute for Sackmann's. The rank-source difference is not material. The rehearsal also caught two bugs before the one-time run:
1. the precedence boundary dropped every provider match in a period Sackmann had been removed from;
2. an edition straddling the boundary could have been counted from both sources.

Both are fixed: the boundary is a parameter, and provider matches already in Sackmann within 14 days are dropped.

## Frozen protocol (ready, not yet frozen)

`python -m matchup_dna.phase4_experiment freeze --dry-run` prints the protocol without writing it. Running `freeze` writes `experiments/phase4_frozen_protocol.json`, which is never overwritten. The held-out command then requires that file to be committed and unchanged.

| Item | Choice |
|---|---|
| Primary claim | P4-refit against P3-refit, on identical held-out matches, tournament-start track |
| P3-refit | Phase 3 groups (rank, inactivity, form) with Elo; L2 ATP 1000, WTA 100 |
| P4-refit | Phase 3 groups + opponent-adjusted serve and return; L2 ATP 10, WTA 0; profiles with a 52-week half-life and a 4-match prior |
| Continuity | P3-original, the Phase 3 final model exactly as fitted on 2010–2023 |
| Secondary | None. LightGBM did not pass against the logistic model |
| Round-aware | R0 (P4 features + round-aware Elo shifts + earlier-round dominance) against the P4-refit predictions, on held-out later-round matches. D and E were not kept |
| Refit | Every model refitted on all rated matches from 2010 to the week of 25 May 2026, L2 held at the values above |
| Held-out population | As in the Data Audit, Part 3: editions starting 1 June 2026 or later and finished by the 5 November file snapshot; main-tour main draws; TML rows first, TennisData.app only where no TML row matches; the seven event families Sackmann omits excluded; best-of from the tournament; completed matches rated |
| Metrics | Log loss (primary), Brier, accuracy, paired gaps with standard errors clustered by week and by month, reliability and calibration line, by tour, month, surface, and round |
| Reporting rule | A gain is called an improvement only if its 95% interval excludes zero |
| Inputs | SHA-256 of the Phase 4 training and validation files, the profile settings, the selection records, both crosswalks, and all ten provider files |

**Minimum detectable gain, written down before the test.** Validation standard errors are scaled to the expected held-out sizes, and 80% power at the 5% level needs 2.8 standard errors:

| Track | Validation se | Expected held-out matches | Held-out se | Smallest gain likely to be detected |
|---|---:|---:|---:|---:|
| Tournament start | 0.0007 | about 2,500 | 0.0018 | **0.0050** |
| Round-aware | 0.0011 | about 1,300 | 0.0027 | **0.0076** |

The validation gain (0.0027) is about half the tournament-start figure. Even if that gain is real, the held-out test has only about a one-in-three chance of confirming it at the 5% level. A null-looking result there would therefore be weak evidence against the feature, and it will be described that way.

## Held-out evaluation, June–October 2026

**Not run.** The held-out outcomes are sealed. This section will report the one-time run, all of it whatever the result.

## Final verification before the freeze

`python -m matchup_dna.phase4_experiment verify` reads no sealed outcome. Every check passed on 6 November 2026:

| Check | Result |
|---|---|
| Phase 3 training and validation files | Match the Phase 3 frozen hashes |
| All 120 inputs of the Phase 3 final run (its protocol, the reserved features, every Sackmann file) | Re-hash to their recorded values |
| Phase 1–3 code, Phase 3's frozen protocol and log, the Phase 2 report | Unchanged since Phase 4 began (`9b24fd6`), in commits and in the working tree. The only uncommitted Phase 1–3 edits are the user's own: blank lines in `rate.py`, and wording in the Phase 3 report |
| Phase 4 train / validation / retrospective files | 57,869 / 16,039 / 13,732 rows, as in Phase 3; every match once; every Phase 3 column equal to Phase 3's file, cell for cell |
| **Truncation test** | Rebuilt with every match from 4 July 2022 on removed, all 109 columns of all 66,236 earlier rows are identical. No feature of a match depends on anything later |
| Seals | 2,643 sealed TML rows carry none of the 40 outcome columns; 11,691 sealed TennisData.app rows carry none of the 31 sealed columns |
| Protocol and runs | No Phase 4 protocol, retrospective run, or held-out run exists yet |
| Unsealing call sites | Exactly two: the retrospective loader and the held-out command, each behind the committed-protocol and frozen-state checks |
| Git | Nothing under `data/` or `results/` is tracked; both provider folders and `results/phase4/` are ignored; nothing is staged |
| Tests | 177 pass |

The truncation test complements the unit tests:
- the unit tests cover the same-week and same-round cases on synthetic tournaments;
- this test covers real data across the whole history at once.

**How the freeze is enforced, not just promised:**
- `freeze` refuses while any code under `matchup_dna/`, `tests/`, `explain.py`, `compare.py`, or `requirements.txt` has uncommitted changes. So the protocol records an exact `code_commit`.
- It also hashes every input: the three Phase 4 data files, the profile settings, the selection records, both crosswalks, Phase 3's frozen protocol, every Sackmann match file, and all ten provider files.
- `retrospective` and `holdout --confirm` stop unless four things hold:
  1. the protocol is committed and unchanged;
  2. every hashed input still matches;
  3. the code has no uncommitted changes;
  4. the code is identical to `code_commit`.

**Deviation policy, recorded in the protocol.** The frozen procedure is run as written. An unexpected or unfavorable retrospective or held-out result is reported, never acted on. Only a genuine implementation defect may interrupt it, and its correction is documented, committed as a new version, and reported next to the original run.

**Complete run history.** Three development runs crashed before saving output, so `experiments/phase4_log.md` doesn't list them:
1. the first `tournament` run, on a subset-mask type error after all its selection steps had printed;
2. two `round-aware` runs, both on a separation failure at L2 = 0 (see concept 8).

The fixes changed no choice. The completed `tournament` rerun printed identical numbers. The round-aware track had produced no decisions before the fixes.

## Validation comparisons and multiple testing

Phase 4 made **22 comparisons on the 2021–2023 validation years**, counting the tour-average diagnostic:
- the tournament track: 11 keep-rule decisions and 1 ablation;
- LightGBM: 2;
- the round-aware track: 3 decisions, 3 diagnostics, and 1 same-rows check.

Phase 3 had already made about two dozen on the same years. With that many looks, some false positives are expected, so the validation numbers above are optimistic. The one kept group passes at about 3.9 standard errors, much more than the keep rule requires. Every interaction and workload test was clearly null rather than borderline. The held-out period is the protection against what remains.

## Limits

- The 2021–2023 validation years were reused from Phase 3 (see above).
- **Profile prior means are fixed constants.** They and the per-match attempt counts are estimated on 2010–2020, so a training-year profile, for 2012 say, is shrunk toward an average that includes later training years. Validation, retrospective, and held-out profiles use no information from their own periods. The same convention as Phase 3's rank fill-in value, which was fitted on the training rows.

  `python -m matchup_dna.phase4_experiment mean-check` repeats everything with strictly point-in-time averages, each year's from the five calendar years before it. Those differ from the fixed values by at most 0.006, in 2010, and by under 0.003 from 2016.
  - **Tuning:** it picks the same settings on both tours (52-week half-life, prior 4, adjusted), with losses within 0.00001.
  - **Features:** the serve and return estimates move by 0.003 on average in training rows and 0.001 in validation rows, and the A-minus-B gaps correlate at 0.9998 or more.
  - **Validation:** the gain against the Phase 3 groups is unchanged at −0.0027 (0.0007), ATP −0.0036 and WTA −0.0016, with all three years better.

  The fixed averages therefore have no measurable effect. They are kept, as selected. This diagnostic is one more look at the validation years, and it could not change the frozen choice.
- Tournament-start features use Phase 3's rule of strictly earlier tournament dates. When a previous event is still running, its last matches can fall after the new event's date (Phase 3's overlap flag). Results without overlap-flagged matches are reported.
- Standard errors are clustered by tournament week, with a month-clustered check. Neither accounts for the same player's results being correlated across months.
- On ATP, the chosen model is slightly overconfident at the top end (calibration slope 0.913). Recalibration was not pre-registered.
- Players with under 10 matches of statistics history gain little, because their profiles are mostly the tour average.
- Sackmann's WTA statistics cover 76–80% of 2010–2015 matches, and its WTA minutes are absent before 2016.
- Round-aware features exclude Davis and BJK Cup ties and round robins.
- Workload omits qualifying matches, which are not in the tour-level files. 14–19% of later-round matches involve a qualifier or lucky loser.
- Rest days, the draw still ahead, and shot-level style could not be studied with these sources.
- **Held-out data differs in source.** In the held-out period, ranks come from the providers, which lag the official lists by one to three weeks in 2026, and about 5% of matches come from TennisData.app without point counts. Both models get the same inputs.
- **The held-out period is small.** At about 2,500 matches it is unlikely to detect a true gain of 0.0027 (see the protocol section).

## Matchup report

```powershell
python explain.py ATP 206173 ATP 104925 20260525 --surface Clay --best-of 5
```

The report uses only matches from tournament weeks before the date, and takes about 30 seconds. It prints:
- the Elo, surface Elo, Phase 3, and Phase 4 probabilities;
- ratings, rank, inactivity, and form;
- each player's opponent-adjusted serve and return estimates, with approximate 90% intervals and history size, plus surface, recent, first- and second-serve, ace, double-fault, and break-point figures;
- the Barnett–Clarke expected service-points-won share each way;
- head-to-head;
- the Phase 4 log-odds broken into terms that add up exactly to the prediction, with correlated inputs combined into one line;
- data warnings.

Two examples, before the 2026 French Open:

| Matchup (clay) | Elo | Phase 3 | Phase 4 | What the serve-return profiles say |
|---|---|---|---|---|
| Sinner vs Djokovic, best of 5 | 83.2% | 75.3% | 73.3% | Sinner expected to win 67.2% of service points, Djokovic 63.1%: +4.0 points toward Sinner |
| Sabalenka vs Swiatek, best of 3 | 72.8% | 63.3% | 54.5% | Swiatek's return (49.7% of return points, against 47.0%) gives her a 2.2-point serve-return edge, which pulls the probability toward even |

The report labels every contribution as an association, not a cause.

## Reproducing

```powershell
pip install -r requirements.txt
python -m matchup_dna.audit_tennisdata
python -m matchup_dna.audit_tennisismylife
python -m matchup_dna.audit_workload
python -m matchup_dna.phase4_experiment profiles
python -m matchup_dna.phase4_experiment dataset
python -m matchup_dna.phase4_experiment tournament
python -m matchup_dna.phase4_experiment gbm
python -m matchup_dna.phase4_experiment round-aware
python -m matchup_dna.phase4_experiment rehearse
python -m matchup_dna.phase4_experiment mean-check
python -m matchup_dna.phase4_experiment verify
python -m matchup_dna.phase4_experiment freeze --dry-run
python -m unittest discover -s tests
```

**After review, in order:**
1. `freeze` writes `experiments/phase4_frozen_protocol.json`. It refuses to overwrite.
2. You commit that file.
3. `retrospective` reports 2024–May 2026 once.
4. `holdout --confirm` scores June–October 2026 once. It refuses without a committed protocol, and refuses to run twice.

**Run times:** about 10 minutes for `profiles`, 4 for `dataset`, 10 for `tournament`, 10 for `round-aware`, 5 for `gbm`, and 10 for `rehearse`.

| File | What it does |
|---|---|
| `matchup_dna/serve_stats.py` | One player's statistics in one match, with eight validity rules |
| `matchup_dna/profiles.py` | Point-in-time shrunk, decayed profiles; surface, recent, and opponent-adjusted variants; next-match forecast scoring |
| `matchup_dna/workload.py`, `matchup_dna/round_aware.py` | Workload of a match, round chronology, earlier-round values, route difficulty, round-aware Elo |
| `matchup_dna/merge.py`, `matchup_dna/heldout.py` | Source precedence, backfill, id reconciliation, and assembling the held-out period |
| `matchup_dna/phase4_features.py` | The dataset: Phase 3 rows checked against their frozen hashes, plus the Phase 4 columns. The locked loader |
| `matchup_dna/phase4_model.py` | Antisymmetric feature groups and the no-intercept logistic model |
| `matchup_dna/selection.py` | Forward selection with the keep rule, equal tuning, cross-L2 checks, the calibration line |
| `matchup_dna/phase4_experiment.py` | Every command above |
| `matchup_dna/matchup.py`, `matchup_dna/interpret.py`, `explain.py` | The matchup report |
| `tests/` | 175 tests, including every check listed above |

## Concepts used in Phase 4

Each entry covers what the concept does, why Phase 4 needs it, the math, where it lives in the Python, how it is checked, and how to read the numbers.

**1. Empirical-Bayes shrinkage.**
- **What:** blends a player's own record with the tour average, more toward the average when the record is short.
- **Why:** 70% of serve points from two matches is mostly luck, while 70% from 200 matches is skill.
- **Math:** \(\hat p = (s + m d \mu)/(n + m d)\). The tour average acts like \(m\) extra matches of average play. This is the mean of a beta posterior with a beta prior centered on \(\mu\).
- **Python:** `ProfileEngine._shrunk`.
- **Checked by:** a hand-computed case in `test_profiles.py`. A player with no history gets exactly \(\mu\).
- **Reading it:** with \(m = 4\), a player needs about four matches of their own before their record weighs as much as the average.

**2. Exponential decay.**
- **What:** older matches count less: weight \(0.5^{\text{age}/H}\).
- **Why:** players change, and a three-year-old serve record says less about today.
- **Python:** `Decayed`. It stores each sum with the day of its last update, so no history is replayed.
- **Checked by:** a one-week half-life gives a seven-day-old match half weight.
- **Reading it:** a 52-week half-life means a match from a year ago counts half as much as one from last week.

**3. Opponent adjustment (Barnett–Clarke).**
- **What:** credits points won against strong opponents.
- **Why:** 65% of serve points against elite returners is more impressive than against weak ones.
- **Math:** expected serve share = own serve − (opponent's return − average return). The same identity adjusts each past observation by the opponent's pre-match strength.
- **Python:** `ProfileEngine.add`.
- **Checked by:** a two-player case in the tests. It beat raw estimates on the outcome-free forecast.
- **Reading it:** an adjusted 71.5% means the player would win about that share against an average returner.

**4. Antisymmetric features and why "serve vs return" is not an interaction.**
- **What:** every feature flips sign when A and B swap. With no intercept, that guarantees P(B) = 1 − P(A).
- **Why it matters here:** the net serve-return edge \((s_A - r_B) - (s_B - r_A)\) equals \((s_A - s_B) + (r_A - r_B)\). It is a sum of ordinary differences, so it adds nothing new. Genuine interactions need products, such as \(a_A b_B - a_B b_A\), or a difference times a symmetric quantity.
- **Checked by:** `test_phase4_model.py` swaps players on random rows for every column.
- **Reading it:** the interactions were tested and added nothing beyond the ordinary differences.

**5. The keep rule and multiple comparisons.**
- **What:** a fixed bar a group must clear on validation data.
- **Why:** with enough tries, some groups look good by chance. Fixing the bar and the order in advance limits that.
- **Math:** the gap must be below −2 clustered standard errors. A group with no real effect clears that on its own about 2% of the time (one-sided), less once the per-tour and per-year conditions are added. Across about 20 tests, about 0.5 false passes are expected.
- **Python:** `experiment.keep_rule`, reused unchanged, and `selection.forward`.
- **Checked by:** `test_selection.py` keeps a planted signal and rejects noise.

**6. Clustered standard errors.**
- **What:** uncertainty that allows matches in the same week to be correlated.
- **Math:** sum the per-match differences within each cluster, then treat the clusters as independent.
- **Reading it:** the month-clustered check gives nearly the same answers (0.0006 against 0.0007), so week-level correlation isn't hiding much.

**7. The calibration line.**
- **What:** fit \(\text{logit}\,P(\text{win}) = a + b\,\text{logit}(p)\) on the evaluation rows.
- **Reading it:** \(b = 1\) and \(a = 0\) is perfect calibration. \(b < 1\) means predictions are too extreme. ATP's \(b = 0.913\) says the chosen model's ATP probabilities are slightly too confident.

**8. Separation.**
- **What:** if a rare indicator is non-zero on only a few rows that all share one outcome, the unpenalized best-fitting coefficient is infinite, and Newton's method fails.
- **Handling:** the L2 search treats such an L2 as unusable, because any positive L2 has a finite answer. It happened only in the round-aware sample, where "rank missing" is non-zero on 9 ATP rows.

**9. Round-aware Elo.**
- **What:** a temporary copy of each player's start-of-week rating, updated round by round inside one tournament, then thrown away.
- **Why:** it captures "has been winning this week" without changing the canonical ratings.
- **Checked by:** canonical ratings identical afterwards. A hand-computed two-round shift. Walkovers don't move it.

**10. Minimum detectable effect.**
- **What:** the smallest true gain a test would detect most of the time.
- **Math:** standard errors shrink like \(1/\sqrt{n}\). For 80% power at the 5% level, the gain must be about 2.8 standard errors.
- **Reading it:** see the protocol section. The held-out period is expected to be too small to confirm a 0.0027 gain.

**11. Contribution decomposition.**
- **What:** for a no-intercept logistic model, log-odds = Σ coefficient × feature. Each term is an exact part of the prediction, and near probability \(p\), a term \(c\) moves the probability by about \(p(1-p)c\).
- **Python:** `Phase4Logistic.contributions` and `interpret.explain`.
- **Checked by:** the terms add up to the prediction (a test).

## What Phase 4 did

Phase 3 built a model from ratings, ranking, time off, and recent results. Phase 4 asked whether knowing *how* players win points — how well they serve and return, against whom, and on which surface — makes its probabilities better. It also asked whether being worn out by a hard road through a tournament matters.

Two new data sources were checked against the existing one first. The newer of them, TennisIsMyLife, records the same matches almost identically and continues to November 2026. The matches from June to October 2026 were set aside unopened, to test the final model once at the end.

For every player before every match, the program estimated how often they win points on their own serve and on their opponent's serve. It used only earlier matches. It gave recent matches more weight, pulled players with little history toward the tour average, and credited points won against strong opponents.

Adding those two estimates to the Phase 3 formula improved the probabilities on both tours and in every test year. The gain is about 0.003 per match. It's modest, but it clearly isn't noise, and it holds for the players with the most history. A player who wins three more points in a hundred on serve than an otherwise equal opponent is about five points more likely to win the match.

Almost everything else tried added nothing:
- surface-specific and recent serving;
- first- and second-serve detail;
- break points;
- special serve-against-return interaction terms;
- head-to-head records;
- how much a player had played in the previous two weeks.

A more flexible model, LightGBM, did no better than the simple formula.

Inside a tournament, knowing who has already won helps clearly. But once those results are counted, how long the earlier matches were and how strong the beaten opponents were made no difference. A player who reaches a final through long, hard matches is predicted just as well without any fatigue adjustment.

The last step is to freeze these choices and test them once on the sealed June–October 2026 matches. Those are about 2,500 matches, which may be too few to confirm a gain this size. Whatever the result, it will be reported.
