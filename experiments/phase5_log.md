# Phase 5 experiment log

One entry per run, appended by `python -m matchup_dna.phase5_experiment`.

## 2026-11-08T12:48:52 · dataset

commit `0ba82a19835c5935835d86b9b3ac2b4462432bb5+uncommitted`

- 29,010 linked matches with opening prices (15,164 development)
- dataset sha256 e7e55afc7fe9

## 2026-11-08T12:49:26 · develop

commit `0ba82a19835c5935835d86b9b3ac2b4462432bb5+uncommitted`

- development matches 15,164; margin method power
- Phase 4 minus opening market +0.0257 (se 0.0017)
- blend weights {"Phase 4": [1.0991136356299627, -0.0932357919914673], "Phase 3": [1.1140900462373964, -0.11982437195022642]}

## 2026-11-08T12:50:09 · evaluate

commit `0ba82a19835c5935835d86b9b3ac2b4462432bb5+uncommitted`

- evaluation matches 13,846
- Q1 Phase 4 minus opening market +0.0236 (se 0.0019; +0.0198 to +0.0274)
- Q2 frozen blend minus market -0.0000 (se 0.0002; -0.0004 to +0.0003)
- Q5 primary rule ROI -0.089

## 2026-11-08 · freeze (added by hand; `freeze` does not log)

- `experiments/phase5_frozen_protocol.json` written 12:49:42, sha256 df243323af3655e7…, before the evaluation at 12:50:09; records the margin method (power), the blend weights, the four paper rules, the slices, the reporting rule, and the sha256 of 8 code files and 9 inputs. Not committed before the evaluation (the user commits); the evaluation checked every hash.

## 2026-11-08 · post-hoc: round-aware model R0 against the market (NOT pre-registered; added by hand)

- `python -m matchup_dna.posthoc_round_aware_market`: R0 reproduced by re-running the frozen fits on earlier matches only; all three published Phase 4 R0 scores matched. Later-round matches, January 2024 - October 2026 (7,462): R0 minus opening market +0.0132 (+0.0088 to +0.0175), against +0.0187 for the tournament-start Phase 4 model; R0 information slope +0.068 (-0.066 to +0.202). Descriptive; the frozen Phase 5 result is unchanged.
