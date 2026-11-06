# Phase 4 experiment log

One entry per run, appended by `python -m matchup_dna.phase4_experiment`.

## 2026-11-05T17:19:25 · profiles

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- ATP: {'half_life': 52, 'prior_matches': 4, 'representation': 'adjusted', 'loss': 0.6518762978407403, 'best_raw_loss': 0.6519955581594257}
- WTA: {'half_life': 52, 'prior_matches': 4, 'representation': 'adjusted', 'loss': 0.6826591235919297, 'best_raw_loss': 0.6827676105222156}

## 2026-11-05T17:24:08 · dataset

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- train: 57,869 rows
- validation: 16,039 rows
- retrospective: 13,732 rows

## 2026-11-05T17:47:57 · tournament

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- chosen groups ['rank', 'inactivity', 'form', 'serve_return'], L2 {'ATP': 10.0, 'WTA': 0.0}
- +serve_return: passed=True, combined -0.0027 (se 0.0007)
- +surface_serve_return: passed=False, combined +0.0001 (se 0.0005)
- +recent_serve_return: passed=False, combined -0.0004 (se 0.0004)
- +serve_components: passed=False, combined -0.0002 (se 0.0002)
- +break_points: passed=False, combined -0.0001 (se 0.0001)
- +product: passed=False, combined -0.0001 (se 0.0001)
- +dominance_elo: passed=False, combined -0.0002 (se 0.0002)
- +surface_interactions: passed=False, combined -0.0003 (se 0.0002)
- +head_to_head: passed=False, combined +0.0000 (se 0.0002)
- +recent_workload: passed=False, combined +0.0009 (se 0.0003)

## 2026-11-05T18:44:35 · round-aware

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- R0 vs reference: passed=True, combined -0.0054 (se 0.0011)
- D: passed=False, combined +0.0003 (se 0.0002)
- E: passed=False, combined -0.0000 (se 0.0001)
- kept ['rank', 'inactivity', 'form', 'serve_return', 'ra_controls']

## 2026-11-05T18:45:37 · gbm

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- LightGBM chosen vs logistic chosen: passed=False, combined -0.0001 (se 0.0008)
- LightGBM chosen vs LightGBM Phase 3 features: passed=True, combined -0.0012 (se 0.0005)

## 2026-11-05T18:56:33 · rehearse

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- 2129 rehearsal matches compared; see results/phase4/experiments/rehearse.txt

## 2026-11-05T19:10:31 · verify

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- verification: ['Phase 1-3 code, frozen protocol, Phase 3 log, and Phase 2 report unchanged since the Phase 3 final run (c373447)']

## 2026-11-05T19:13:42 · verify

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- verification: passed

## 2026-11-05T19:30:22 · verify

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- verification: passed

## 2026-11-05T19:41:58 · mean-check

commit `d5e7b0439a1b0f1fd1d979a61d93175106f2e3c5+uncommitted`

- ATP: point-in-time tuning chose 52, 4, adjusted
- WTA: point-in-time tuning chose 52, 4, adjusted

## 2026-11-05T19:59:40 · verify

commit `5cea719315eb6c11eb4d422ab9a0145dfae5f9b9+uncommitted`

- verification: passed

## 2026-11-05T20:03:48 · retrospective

commit `66100ee6e2b854e2ba6425633293c7664ec87af9+uncommitted`

- Retrospective check run; see results/phase4/experiments/retrospective.txt

## 2026-11-05T20:22:57 · holdout

commit `00f4f504968d71e50f3673c554a5e1f65ab2cce3+uncommitted`

- Held-out evaluation run; see results/phase4/experiments/holdout.txt

## 2026-11-05 · summary of the frozen evaluations (added by hand from the command outputs)

- Retrospective 2024-May 2026 (13,732 matches, models fitted on 2010-2023): P3-refit 0.6128, P4-refit 0.6114; gap -0.0014 (se 0.0006), 95% interval -0.0026 to -0.0002; ATP -0.0008 (0.0010), WTA -0.0021 (0.0007). Round-aware R0 vs reference -0.0052 (0.0014).
- holdout --confirm first attempt stopped on an implementation defect before any output (merge.tml_match refused unlocked held-out rows); fixed in 4f6076e and recorded as experiments/phase4_protocol_amendment_1.json (00f4f50).
- Held-out June-October 2026 (2,518 matches, run once under amendment 1, models refitted on 87,640 matches 2010-May 2026): P3-refit 0.6148 / Brier 0.2139 / 65.11%; P4-refit 0.6108 / 0.2121 / 65.47%. Gap -0.0040 (se 0.0021, by tournament date), 95% interval -0.0081 to +0.0001, p = 0.055: not called an improvement under the pre-registered rule. ATP -0.0058 (0.0035), WTA -0.0020 (0.0019). Round-aware (1,286 later-round matches): R0 vs reference -0.0072 (0.0023), interval excludes zero.

## 2026-11-05 · post-hoc descriptive benchmark (NOT pre-registered; added by hand)

- `python -m matchup_dna.posthoc_rank_benchmark`: saved held-out predictions only, nothing refitted or rescored. 2,518 held-out matches; 25 with a missing rank, 0 tied; 2,493 eligible.
- Accuracy on the 2,493: higher-ranked player 64.98% (1,620 correct); Phase 3 refit 65.02% (1,621); Phase 3 original 64.94% (1,619); Phase 4 65.34% (1,629). Phase 4 minus ranking +0.36 points; Phase 4 minus Phase 3 +0.32 points (ATP +0.00, WTA +0.68).

## 2026-11-05 · post-hoc long-run analysis, January 2021 - October 2026 (NOT pre-registered; added by hand)

- `python -m matchup_dna.posthoc_longrun`: chronological predictions only; Phase 3/4 validation and Phase 4 retrospective predictions reproduced by re-executing the reported fits and accepted only because all six sets matched their published log loss and accuracy exactly; held-out Elo replayed through the frozen pipeline (no fitting). No model changed.
- Identical eligible matches (missing ranks excluded: 218 / 192 / 25; no ties). Log loss, Phase 3 -> Phase 4: validation 0.6109 -> 0.6083; retrospective 0.6138 -> 0.6125; held-out 0.6160 -> 0.6120; pooled 31,854 matches 0.6125 -> 0.6104. Accuracy pooled: Elo 64.52%, surface Elo 64.87%, Phase 3 65.65%, Phase 4 65.89%, higher-ranked player 64.20%.

## 2026-11-05 · erratum 1: held-out data-integrity correction (POST-UNBLINDING; added by hand)

- Defect, found after unblinding by the post-hoc disagreement analysis: the held-out assembly (heldout.assemble version 1) kept 68 TennisData.app rows that repeat TML matches, 65 of them rated, because players spelled differently in the two sources failed both linking passes and were resolved to different ids. 'Vallejo D.' was linked to the wrong Sackmann player (118808, not 209226), and several players (Merida, Shevchenko, Shelbayh, Ruse, Xinran Sun) got split or history-less ids. Record: `experiments/phase4_erratum_1.json`; diagnosis: Data Audit A16.
- Fix: version 2 assembly (version 1 kept). Third linking pass on round, edition, dates and compatible names; one identity per person from linked matches; unverified surname-and-initial guess removed; build-stopping checks. 23 tests in `tests/test_heldout.py`; suite 205 OK. Independent reconciliation: version 1 flags 68 duplicates and 1 split name; version 2 flags only 3 genuine additions TML lacks.
- `python -m matchup_dna.phase4_correction evaluate`: frozen models refitted on the same 87,640 rows; version-1 rows reproduce all 2,518 saved predictions. Corrected, RETROSPECTIVE, 2,453 matches: P3-refit 0.6114 / 65.61%, P4-refit 0.6065 / 65.86%; P4 - P3 -0.0049 (se 0.0017, -0.0084 to -0.0015, p 0.005); ATP -0.0066 (p 0.033), WTA -0.0031 (p 0.105); round-aware R0 -0.0059 (se 0.0024, -0.0107 to -0.0011). Ran three times (code hashes recorded each time); fix and results identical.
- The pre-registered result is unchanged: 2,518 rows, -0.0040, -0.0081 to +0.0001, p 0.055, not called an improvement. The corrected result is not a second blind test.
