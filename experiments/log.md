# Phase 3 experiment log

One entry per run, appended by `python -m matchup_dna.experiment`.

## 2026-11-05T01:38:36 · calibration

commit `6fd2495bc5062b037934bdda02e1db1919893b64+uncommitted`

- Temperature scaling per tour, fitted on 2010-2020; benchmark is 'Surface Elo, temperature'.
- Surface Elo, temperature vs raw surface Elo on validation: ATP -0.0049 (se 0.0010), WTA -0.0022 (se 0.0010), Both -0.0036 (se 0.0008)

## 2026-11-05T01:39:18 · elo-lr

commit `6fd2495bc5062b037934bdda02e1db1919893b64+uncommitted`

- L2 {'ATP': 1000.0, 'WTA': 100.0}
- vs calibrated surface Elo: passed=False, ATP +0.0000 (se 0.0007), WTA -0.0008 (se 0.0005), Both -0.0003 (se 0.0004)

## 2026-11-05T01:40:29 · elo-lr

commit `6fd2495bc5062b037934bdda02e1db1919893b64+uncommitted`

- L2 {'ATP': 1000.0, 'WTA': 100.0}
- vs calibrated surface Elo: passed=False, ATP +0.0000 (se 0.0007), WTA -0.0008 (se 0.0005), Both -0.0003 (se 0.0004)

## 2026-11-05T01:40:42 · elo-lr

commit `6fd2495bc5062b037934bdda02e1db1919893b64+uncommitted`

- L2 {'ATP': 1000.0, 'WTA': 100.0}
- vs calibrated surface Elo: passed=False, ATP +0.0000 (se 0.0007), WTA -0.0008 (se 0.0005), Both -0.0003 (se 0.0004)

## 2026-11-05T01:42:19 · features

commit `6fd2495bc5062b037934bdda02e1db1919893b64+uncommitted`

- Selected groups ['rank', 'inactivity', 'form'], L2 {'ATP': 1000.0, 'WTA': 100.0}
- +rank: passed=True, combined -0.0054 (se 0.0011)
- +experience: passed=False, combined +0.0010 (se 0.0002)
- +surface_experience: passed=False, combined +0.0018 (se 0.0005)
- +inactivity: passed=True, combined -0.0021 (se 0.0006)
- +form: passed=True, combined -0.0005 (se 0.0002)

## 2026-11-05T01:43:44 · gbm

commit `6fd2495bc5062b037934bdda02e1db1919893b64+uncommitted`

- settings {'ATP': {'leaves': 31, 'trees': 68}, 'WTA': {'leaves': 15, 'trees': 138}}
- vs selected logistic: passed=True, combined -0.0015 (se 0.0007)

## 2026-11-05T01:44:51 · same-k

commit `6fd2495bc5062b037934bdda02e1db1919893b64+uncommitted`

- Same-K diagnostic on 2010-2023; see results/phase3/experiments/same-k.txt
