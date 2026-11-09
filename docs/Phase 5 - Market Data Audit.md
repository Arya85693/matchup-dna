# Matchup DNA — Phase 5 Market Data Audit

**Status:** Complete, 8 November 2026. Written before the Phase 5 evaluation. Nothing here compares the models with the market for January 2024 onward.
**Question:** Is the Valuebetennis odds file good enough to be Phase 5's market benchmark? Can it be joined to the model's matches without errors?
**Answer:**

- **Yes, at the levels the model covers.** Opening prices exist for 98–99.5% of Grand Slam, Masters and tour matches in every year. Closing prices are missing for all of 2021 and a quarter of 2022.
- **The join is reliable.** It links 29,688 of the model's 32,224 matches from January 2021 to October 2026 (92%), through a tested player crosswalk with 45 verified name variants.
- **The source has three collection outages,** with no rows at any level: 23 January–9 March 2024, 11–23 October 2024, and 7–25 May 2026.

`python -m matchup_dna.audit_valuebetennis` reproduces every number here. It writes:
- `results/phase5/audit/valuebetennis_audit.txt` and `.json`;
- the player crosswalk, `results/phase5/vb_crosswalk.csv`;
- the match links, `results/phase5/links.csv`.

All of these are gitignored.

## What was read, and what was not computed

The six season files were read in full: `valuebetennis-matchs-2021.csv` to `2026.csv`, in `data/external/valuebetennis/`. They are private copies and are never committed. The license is CC BY 4.0: attribution is required, and commercial use is allowed.

**The audit computes no accuracy, log loss, Brier score or return for the market or the models.** Match results were used for one purpose only: to check that the two sources name the same winner for each linked match.

**Disclosure.** On 6 November an earlier draft of Phase 5, since removed, compared Phase 4 with the opening market on the 2021–2023 development matches. The market won by 0.026 log loss per match. The draft compared nothing for 2024 onward.

## 0. Which matches the earlier phases used

Phase 5 compares the market with the **same matches the earlier phases used**. Those are not only Grand Slam, Masters and main-tour matches.

| Level (Sackmann code) | Training, 2010–2020 | 2021–Oct 2026 |
|---|---:|---:|
| Grand Slam (G) | 10,592 | 5,916 |
| Masters (M) | 5,607 | 3,779 |
| ATP 250 and 500 (A) | 15,883 | 8,687 |
| WTA 1000, 500, 250 (PM, P, I) | 19,352 | 10,980 |
| Davis Cup and Billie Jean King Cup (D) | 5,842 | 1,985 |
| Tour Finals, Olympics, other (F, O, W) | 593 | 662 |
| WTA ITF-level events in Sackmann from 2024 (35+H, 50+H) | – | 215 |

**Rounds.** Every phase used **main-draw rounds only**: R128 to the final, round robins, and bronze-medal matches. No qualifying match is in any model dataset. The only exception is 3 TennisData.app Davis Cup rows from June–October 2026 with an unknown round.

The odds join removes the Valuebetennis qualifying rows (round codes 1–3) before linking, so it cannot attach a qualifying price to a model match.

## 1. The files

| File | Rows | Dates | sha256 (first 16) |
|---|---:|---|---|
| 2021 | 63,728 | 1 Jan – 31 Dec | ea30ae06fab7734a |
| 2022 | 83,381 | 1 Jan – 31 Dec | e4bab3987820ecdd |
| 2023 | 89,826 | 1 Jan – 31 Dec | fa45622d678b1717 |
| 2024 | 79,910 | 1 Jan – 31 Dec | 09437d8208c937d9 |
| 2025 | 80,412 | 1 Jan – 31 Dec | 46bd9c25673228ae |
| 2026 | 76,742 | 1 Jan – 6 Nov | 3e1cc5f501dfbe4a |
| **Total** | **473,999** | | |

- **Format:** a semicolon separator, UTF-8 with a byte-order mark, and one `tournoi_id` per tournament edition.
- **Columns:** a UTC start time, the tournament, category, gender, surface (in French), a round code, two players with Valuebetennis ids, opening and closing decimal prices for each, the winner's id, and the score.

**Round codes are ordinal:**

| Code | Round |
|---|---|
| 1–3 | qualifying |
| 4 | first main-draw round |
| 5–8 | following main-draw rounds |
| 9 | quarterfinal |
| 10 | semifinal |
| 12 | final |
| 13–17 | team-event rubbers (no round) |

## 2. What is in it

| Category | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Grand Slam | 1,912 | 1,908 | 1,894 | 1,902 | 1,911 | 1,586 | 11,113 |
| Masters | 1,467 | 1,492 | 1,915 | 1,677 | 2,226 | 2,026 | 10,803 |
| Main tour | 4,349 | 4,422 | 4,183 | 3,058 | 3,573 | 3,453 | 23,038 |
| Davis / BJK Cup | 146 | 215 | 273 | 156 | 199 | 168 | 1,157 |
| Challenger | 15,742 | 26,305 | 29,503 | 24,744 | 27,748 | 25,959 | 150,001 |
| ITF | 39,757 | 48,525 | 51,550 | 47,940 | 44,309 | 43,087 | 275,168 |
| Blank | 355 | 514 | 508 | 433 | 446 | 463 | 2,719 |

**Collection outages.** The file has no rows at any level from **23 January to 9 March 2024** (46 days: the end of the 2024 Australian Open, all of February, the start of Indian Wells), **11–23 October 2024**, and **7–25 May 2026**. Off-season gaps in December are normal.

These outages are why January 2024–May 2026 links at 87%, against 96–97% elsewhere. An outage has nothing to do with who won, so it shrinks the evaluation window without biasing it.

## 3. Integrity

| Check | Count |
|---|---:|
| Duplicate match ids | 0 |
| Winner who is neither player | 3 |
| A player against himself | 4 |
| Player ids with more than one name | **0** |
| Names with more than one id (common names, all levels) | 36 |
| Tour level: same pair twice on one day | 27 |
| Tour level: start time exactly 00:00:00 (no real time) | 776 |
| Tour level: score blank | 1,383 |
| Names written as a pair "A/B" | 4 |

- **Valuebetennis is internally consistent:** each id always carries the same name.
- **Same pair twice on one day:** these are mostly placeholders timed 00:00:00 next to the real row, at the Davis Cup Finals and the ATP Cup.
- **Doubles hidden as singles.** Some doubles teams appear as two "players": Makoto Ninomiya v Ena Shibahara, Abu Dhabi 2021. No text rule detects them. They fall out at the join, because no such singles match exists.

## 4. Prices

| Category | Opening usable | Closing usable | Median overround, opening | Closing |
|---|---:|---:|---:|---:|
| Grand Slam | 99.5% | 77.4% | 1.035 | 1.030 |
| Masters | 99.0% | 84.1% | 1.034 | 1.029 |
| Main tour | 97.8% | 72.5% | 1.034 | 1.029 |
| Davis / BJK Cup | 58.9% | 41.1% | 1.035 | 1.040 |
| Challenger | 63.0% | 53.6% | 1.061 | 1.048 |
| ITF | 34.0% | 25.6% | 1.074 | 1.069 |

"Usable" means both decimal prices are present and above 1.00.

**Grand Slam, Masters and main tour, by year:**

| Year | Opening usable | Closing usable | Opening overround (1st / 25th / 50th / 75th / 99th percentile) |
|---|---:|---:|---|
| 2021 | 99.4% | **0.0%** | 1.025 / 1.029 / 1.034 / 1.052 / 1.053 |
| 2022 | 98.6% | 74.6% | 1.025 / 1.029 / 1.034 / 1.047 / 1.053 |
| 2023 | 98.7% | 97.8% | 1.021 / 1.029 / 1.034 / 1.047 / 1.049 |
| 2024 | 98.1% | 96.0% | 1.019 / 1.029 / 1.034 / 1.047 / 1.054 |
| 2025 | 98.0% | 97.5% | 1.023 / 1.033 / 1.038 / 1.047 / 1.049 |
| 2026 | 98.3% | 96.8% | 1.023 / 1.032 / 1.034 / 1.043 / 1.052 |

- **The tour-level margin is about 3.4%** (median overround 1.034), the margin of a sharp bookmaker. Phase 0's 1.066 was dominated by ITF rows.
- **No row has an overround below 1.00 or above 1.15.**
- **Prices move between open and close.** Player 1's margin-free probability moves by a median of 0.021, and by more than 0.059 in a tenth of matches. This was computed without results.

**Timing.** Neither price has its own timestamp.
- **The opening price** is treated as the earliest recorded price, and is the only one a decision before the match may use.
- **The closing price** is a benchmark only.
- **The models' probabilities** are tournament-start probabilities. They exist before every match, including the 1,933 linked matches played on the day or days before the model's `tourney_date`: Sackmann dates some events from the Monday, while play starts on the Sunday.

## 5. Removing the margin

Four standard methods are implemented in `matchup_dna/market.py` and tested; each gives two probabilities that sum to 1.

| Method | Favourite's median probability | Mean difference from multiplicative | Largest |
|---|---:|---:|---:|
| Multiplicative (proportional) | 0.6545 | – | – |
| Additive (equal deduction) | 0.6603 | +0.006 | +0.036 |
| Power | 0.6631 | +0.010 | +0.073 |
| Shin | 0.6603 | +0.006 | +0.036 |

This covers 44,293 tour-level matches with opening prices, computed without results.

- **For two outcomes, Shin's model reduces to the additive method.**
- **The choice moves probabilities by up to 7 points on long prices.** The Phase 5 development step chose it on 2021–2023 only.

## 6. The join to the model's matches

`matchup_dna/market_link.py` builds the links, applying the lessons of Phase 4 erratum 1. It never uses prices or results to decide a link, and it never merges anything ambiguous.

1. **Names.** Both players' full names agree, ignoring accents, case, hyphens and word order. Three more conditions must hold:
   - the match day is 3 days before to 16 days after the model's tournament date;
   - quarterfinal, semifinal and final codes agree with the model's round (team-event codes are not compared);
   - exactly one model match fits.

   A row fitting several matches is settled by the tournament edition that the event's other rows link to.
2. **Players.** Valuebetennis ids are mapped to model players only through linked matches, one-to-one.
3. **Name variants.** These are mapped from **opponent evidence**:
   - the player's opponent is already verified, exactly one model match fits, and the names share a surname;
   - all the evidence must point to one model player;
   - two matches are needed, or one when one name only adds words to the other.
4. **One person, several model ids.** A player the model holds under two ids with an identical name is mapped to both. Martin Landaluce has two Sackmann ids.
5. **Ids.** Remaining rows link through both players' verified ids.
6. **One real match, one row.** The row from the linked edition is kept, else the one with a real clock time, else none.
7. **A winner check.** A pair whose sources name different winners is left out.

| Step | Count |
|---|---:|
| Rows considered (tour-level qualifying and "A/B" pairs removed) | 458,758 |
| Linked by names | 26,154 |
| Players mapped by exact names | 1,386 |
| Players mapped as name variants | 45 |
| Players with two model ids under one name, mapped to both | 1 |
| Name-variant candidates rejected | 3 |
| Player conflicts left | 0 |
| Linked by verified player ids | 3,555 |
| Left out for review: a row fitting several matches | 6 |
| Left out for review: several rows claiming one match | 24 |
| Left out: sources name different winners | 21 |
| **Links kept** | **29,688** |

**Name variants.** All 45 are listed in the audit output, and every one was checked by eye as the same person. Without them, every Coco Gauff and Taylor Fritz match was missing, which would have biased the comparison away from top players. Examples:

| Valuebetennis | Model |
|---|---|
| Cori Gauff | Coco Gauff |
| Taylor Harry Fritz | Taylor Fritz |
| Paula Badosa Gibert | Paula Badosa |
| Jeff Wolf | J.J. Wolf |
| Mukund Sasikumar | Sasi Kumar Mukund |
| Lesya Tsurenko | Lesia Tsurenko |
| Daniel Merida Aguilar | Daniel Merida |

Two players are also mapped to both of their identical-name model ids: Johanne Svendsen and Tiantsoa Rakotomanga Rajaonah.

**The three rejections are correct:**
- "Juan Carlos Manuel Aguilar" has one match against a different player, Joaquin Aguilar Cardozo.
- "Luis Queiroz Miguel" has one match, and the names differ by more than added words.
- "Juan Alejandro Hernandez" has one stray vote for a different player.

**Coverage of the model's matches:**

| Period | Model matches | Linked | Opening prices usable | Closing usable |
|---|---:|---:|---:|---:|
| 2021–2023 (development) | 16,039 | 15,393 (96.0%) | 15,164 (94.5%) | 8,924 (55.6%) |
| Jan 2024–May 2026 | 13,732 | 11,914 (86.8%) | 11,540 (84.0%) | 11,367 (82.8%) |
| Jun–Oct 2026 | 2,453 | 2,381 (97.1%) | 2,306 (94.0%) | 2,263 (92.3%) |

| Sackmann level | Linked | Opening usable |
|---|---:|---:|
| Grand Slam (G) | 97.6% | 97.1% |
| Masters (M) | 95.9% | 95.5% |
| ATP 250/500 (A) | 93.3% | 92.2% |
| WTA 1000 (PM) | 94.7% | 94.1% |
| WTA 500 (P) | 91.4% | 90.8% |
| WTA 250 (I) | 94.4% | 93.5% |
| Davis / BJK Cup (D) | 53.6% | 32.6% |
| Finals, Olympics, other (F, O, W) | 97–100% | 97–99% |
| WTA ITF-level (35+H, 50+H) | 94–100% | 65–78% |

**Why 2,536 model matches are not linked:**

| Reason | Matches |
|---|---:|
| One player appears that week; the other does not (mostly Davis / BJK Cup rubbers Valuebetennis lacks) | 997 |
| A row with both names exists, outside the date window (mostly the 2024 outages) | 968 |
| No row for either player that week | 530 |
| A row with both names in the window, left out as ambiguous or by the winner check | 41 |

**The 21 winner disagreements** are left out of every analysis:
- 11 are Next Gen Finals round-robin matches, in every year;
- 5 are Davis Cup or Billie Jean King Cup rubbers;
- 5 are ordinary matches, where one source must be wrong.

## Decisions taken

1. **Population.** Every linked model match with usable opening prices, at every level the model was built on: 15,164 development matches and 13,846 evaluation matches.
2. **Windows.**
   - **2021–2023 for development.** It may choose only the margin method and the blend weights.
   - **January 2024–October 2026 for the one-time evaluation.** The models' outcomes there were seen in Phases 3 and 4. The models were never compared with the market there.
3. **The closing line is a secondary benchmark only,** used where it exists.

## Reproducing

```powershell
python -m matchup_dna.audit_valuebetennis
python -m unittest tests.test_valuebetennis tests.test_market tests.test_market_link
```
