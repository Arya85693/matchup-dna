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
