# Matchup DNA — Phase 4 TennisData.app Data Audit

**Date:** 5 November 2026  
**Question:** Can the four TennisData.app season files support Phase 4: a check on the Sackmann records, and a genuinely new held-out evaluation from June 2026?  
**Answer:** Yes, for a narrower model than Sackmann allows.

The files agree with Sackmann almost perfectly where both cover the same match: the winner in 7,775 of 7,775 linked main-draw matches, aces and double faults exactly in 99.5% of player-matches, and service points won within one percentage point in 98.1%. Players link to Sackmann ids one-to-one with no conflicts.

The limits are in what the files contain:
- They give service and return points won as rounded percentages, with no point counts.
- They give no first-serve or second-serve figures.
- Their break-point percentages report 0% when a player had no break points at all.
- Their 2026 ranks lag the official list by one to three weeks.

So the held-out period, June to October 2026, can test a model built from Elo, rank, inactivity, form, and service and return points won. It cannot test first-serve, second-serve, break-point, ace-rate, or double-fault features.

The last section, "What the audit did," says this in ordinary language.

## What was read

The four files sit in `data/external/tennisdata_app/` and were not downloaded again. The website was not visited or scraped.

| File | Rows | Match days (UTC) | Before 1 June 2026 | Sealed (1 June 2026 on) |
|---|---:|---|---:|---:|
| `2025-atp-season.csv` | 14,620 | 27 Dec 2024 – 21 Dec 2025 | 14,620 | 0 |
| `2025-wta-season.csv` | 6,112 | 27 Dec 2024 – 14 Dec 2025 | 6,112 | 0 |
| `2026-atp-season.csv` | 15,511 | 2 Jan 2026 – 6 Nov 2026 | 7,451 | 8,060 |
| `2026-wta-season.csv` | 6,719 | 2 Jan 2026 – 8 Nov 2026 | 3,088 | 3,631 |
| **All** | **42,962** | | **31,271** | **11,691** |

**The seal.** Every row dated 1 June 2026 or later belongs to the candidate held-out period, and its outcomes have not been looked at. The only reader of these files is `tennisdata.load_provider()`. It deletes 31 columns from sealed rows before any other code sees them:
- status;
- winner;
- sets and set-by-set games;
- the four odds columns;
- the twelve statistic columns.

It keeps one yes/no flag saying whether the row has serve statistics. Unsealing requires a frozen Phase 4 protocol file, which does not exist yet. The audit prints the columns that reached it from sealed rows, and none of the 31 is among them. Everything in this report about the sealed period is therefore metadata: dates, tournaments, rounds, surfaces, player names, ids, ranks, and whether statistics exist.

An earlier exploratory pass, made before this code existed, followed the same rule. It counted only metadata and the presence of fields for sealed rows.

The files were last modified on 5 November 2026. 81 rows are dated on or after that day, which means they are fixtures that hadn't been played when the files were saved.

## Fields

Each file has the same **49 columns** in the same order, and the loader refuses a file that doesn't. An earlier planning draft said 48; that was a miscount. The definitions below are inferred from the values and from cross-checks against Sackmann. The site's own field descriptions were not consulted. Blank shares are over the 31,271 open rows.

| Column | Type | Blank | Meaning |
|---|---|---:|---|
| `match_id` | integer | 0% | Provider match number. Unique within a tour. Four values are reused across the ATP and WTA files for different matches, so a match is identified by **tour plus `match_id`** |
| `season_year` | integer | 0% | The file's season |
| `tour_type`, `tour_type_human` | integer, text | 0% | 1 ATP Tour, 2 WTA Tour, 3 ATP Challenger, 4 WTA 125 (labeled "WTA Chall") |
| `date_timestamp` | integer | 0% | Match time in Unix seconds. Its UTC date is the match day |
| `date_human` | text | 0% | "27 Dec 2024". It equals the UTC date of `date_timestamp` in all 42,962 rows |
| `tournament` | text | 0% | Event name, with suffixes " - Qualification", " - Play Offs" (knockout stage of a team event or finals), " - WIC" (wheelchair), and "(indoor)". 871 distinct names |
| `round` | text | 3.3% | "1/64-finals" (R128), "1/32-finals" (R64), "1/16-finals" (R32), "1/8-finals" (R16), "Quarter-finals", "Semi-finals", "Final", "Qualifier", and one "3rd place". Blank for team events and round robins |
| `surface`, `surface_id` | text, integer | 0% | hard (1), clay (2), grass (3), "no surface" (4) |
| `status` | text | 0% | FINISHED, plus one SCHEDULED row |
| `status_extra` | text | 0% | FINISHED, RETIRED, WALKOVER, CANCELED, AWARDED, SCHEDULED |
| `home_name`, `away_name` | text | 0% | "Surname I.", for example "Carreno-Busta P.". Home and away are listing order, not a home venue or who served first |
| `home_id`, `away_id` | integer | 0% | Provider player ids. Different from Sackmann's ids |
| `home_rank`, `away_rank` | integer | 36.0% | Ranking shown for the match (see "Ranks" below) |
| `home_points`, `away_points` | integer | 36.0% | Ranking points, blank whenever the rank is blank |
| `winner_code` | integer | 1.4% | 1 home won, 2 away won, blank with no result |
| `home_set_score`, `away_set_score` | integer | 2.0% | Sets won |
| `home_set_1_score` … `away_set_5_score` | integer | 2.0% (set 1) to 99.5% (set 5) | Games in each set. Tiebreak points are not given |
| `home_odds_match_winner`, `away_odds_match_winner` | decimal | 3.5% | Decimal match-winner odds. Whether they are opening or closing prices is not stated |
| `home_odds_first_set_winner`, `away_odds_first_set_winner` | decimal | 6.5% | Decimal first-set odds |
| `home_aces`, `away_aces`, `home_double_faults`, `away_double_faults` | integer | 2.1% | Counts |
| `home_service_points_won_perc`, `away_…` | integer | 2.1% | Percent of the player's own service points won, rounded to a whole number |
| `home_return_points_won_perc`, `away_…` | integer | 2.1% | Percent of the opponent's service points won. Equals 100 minus the opponent's service figure, within one point, in 99.4% of rows |
| `home_break_points_won_perc`, `away_…` | decimal | 2.9% | Percent of break-point chances converted |
| `home_break_points_saved_perc`, `away_…` | decimal | 3.0% | Percent of break points faced that were saved |

**Statistics are match-level percentages only.** There are no service-point totals, no first serves in, and no first-serve or second-serve points won. Without point totals, two matches can't be pooled into one "points won out of points played" figure. A 70% from a 40-point match and a 60% from a 120-point match can only be averaged as matches, never weighted by points.

## Coverage

| Tour | Circuit | Main draw | Qualifying | Wheelchair |
|---|---|---:|---:|---:|
| ATP | ATP Tour | 5,652 | 2,755 | 3 |
| ATP | Challenger | 13,863 | 7,858 | — |
| WTA | WTA Tour | 5,387 | 2,832 | 3 |
| WTA | WTA 125 | 3,576 | 1,033 | — |

All rows, open and sealed. Surfaces: hard 22,029, clay 17,398, grass 2,845, and "no surface" 690, which is mostly team events and finals.

**Main tour against Sackmann.** Sackmann's tour-level files hold only main-tour main draws, so only those provider rows are comparable. The table shows how many Sackmann matches from the 27 December 2024 to 25 May 2026 weeks have a provider row.

| Sackmann level | 2025 ATP | 2026 ATP | 2025 WTA | 2026 WTA |
|---|---|---|---|---|
| Grand Slam | 506/508 | 241/254 | 500/508 | 236/254 |
| Masters / WTA 1000 | 770/775 | 431/435 | 818/830 | 483/490 |
| ATP 250–500 / WTA 500 | 1,274/1,297 | 617/632 | 425/427 | 252/258 |
| WTA 250 (I) | — | — | 620/647 | 267/271 |
| Tour Finals | 29/30 | — | 15/15 | — |
| Davis Cup / BJK Cup | 14/252 | 78/128 | 14/50 | 0/22 |
| WTA "35+H" and "50+H" | — | — | 0/215 | — |

The 2026 Grand Slam shortfall is the French Open: its matches played in June are sealed provider rows and can't be linked yet. Two gaps are real:
- **Team events.** The provider carries Davis Cup and BJK Cup only partly.
- **Lower WTA events.** It has none of the 215 matches in the lower WTA events that Sackmann's 2025 WTA file includes.

So an Elo replay built from provider results will see slightly fewer team-event and lower-level WTA matches than one built from Sackmann.

**Event names Sackmann does not have.** A provider tournament name is treated as part of Sackmann's population if at least half of its open main-draw rows link to a Sackmann match. 127 of 134 names pass. The seven that fail link at 0%:
- the ATP and WTA Hopman Cup;
- Billie Jean King Cup Group I (four names);
- the BJK Cup World Group relegation play-offs.

Names that link at 84–87%, such as Hamburg, Rouen, and Chennai, are ordinary tour events whose missing rows are name-spelling misses.

## Integrity

Open rows unless stated.

| Check | Result |
|---|---|
| Duplicate match within a tour (`match_id`, or same day and same two players), all rows | None |
| Same player id on both sides, all rows | None |
| Service % + opponent's return % = 100 (±1) | 60,832 of 61,216 player-pairs (99.4%) |
| Break points won % + opponent's saved % = 100 (±1) | 58,451 of 60,706 (96.3%) |
| Percentages outside 0–100 / negative statistics | 2 / 1 |
| FINISHED rows: winner agrees with sets won | 29,620 of 29,625 |
| FINISHED rows: sets won agree with set-by-set games | 29,618 of 29,625 |
| Provider ids with more than one spelling | 9, e.g. "Pacheco S." and "Pacheco Benasayag S." under one id |
| Name strings carried by more than one id | 13, e.g. "Zhang Z.", "Jones M.", "Wang Y." |

| Ending (`status_extra`) | Rows | Winner blank | Serve statistics present |
|---|---:|---:|---:|
| FINISHED | 29,629 | 3 | 29,407 |
| RETIRED | 1,025 | 2 | 1,021 |
| WALKOVER | 169 | 0 | **62** |
| CANCELED | 446 | 446 | 117 |
| AWARDED | 1 | 0 | 1 |
| SCHEDULED | 1 | 1 | 0 |

A walkover has no points played, so the 62 walkovers that carry statistics are invalid statistics. The 117 canceled rows with statistics are probably matches stopped partway. In Phase 4, statistics count only from FINISHED rows, so neither group can enter a player's profile.

**Identity rules that follow from this:** a provider player is identified by tour plus id, never by name, and a name is used only to find candidate matches.

## Linking to Sackmann

**Rule.** A provider row and a Sackmann match are the same match only when all of these hold:
- They are on the same tour.
- Both players' name keys agree. A key is the full surname with accents and punctuation removed, plus the first initial; "Carreño-Busta P." becomes `carrenobusta, p`.
- The provider's match day is between 3 days before and 16 days after Sackmann's `tourney_date`.
- Exactly one Sackmann match fits.
- No other provider row claims that Sackmann match.

A surname alone never links. Linking runs only on main-tour main-draw rows. As a control, qualifying and Challenger rows, which Sackmann's files don't contain, would produce 185 and 8 false links under the same rule. Those are two players meeting in qualifying and again in a main draw within the window.

| Main-draw open rows | ATP | WTA |
|---|---:|---:|
| Linked | 4,008 | 3,706 |
| Ambiguous, not linked | 71 | 36 |
| No candidate | 125 | 299 |
| Name without an initial | 2 | 0 |

- **Reversed names.** 41 links needed a reversed-order key. Sackmann stores "Bu Yunchaokete" with first and last names the other way round from the provider's "Bu Y.".
- **Second pass.** 61 more rows linked by ids: both provider ids were already in the crosswalk, and exactly one Sackmann match between those two players fell in the window. These are spelling differences such as "O'Connell" and "Oconnell", and "Auger-Aliassime" and "Auger Aliassime".
- **What stayed unlinked.** Mostly the BJK Cup Group I and relegation ties, the Davis Cup preliminary rounds, and the Hopman Cup.

**Crosswalk.** Each linked match pairs two provider ids with two Sackmann ids. A provider id is accepted only if two things hold:
- every one of its linked matches pairs it with the same Sackmann id;
- no other provider id pairs with that Sackmann id.

777 ids are accepted and none conflict. 205 of them rest on a single linked match. The crosswalk is saved to `results/phase4/crosswalk.csv`, which is gitignored.

The planning draft reported 806 ids and one conflict. That count included qualifying and Challenger rows, and the conflict came from one of the false links the control above describes. Restricting to main draws removed both.

## Agreement with Sackmann

7,775 linked main-draw matches (7,714 by name, 61 by id), compared field by field. "Player-matches" counts each player in each match.

| Field | Agreement |
|---|---|
| Winner | 7,775 of 7,775 |
| Ending | 7,766 of 7,775 agree. Of the rest, 7 are Sackmann retirements the provider lists as FINISHED, and 2 the reverse |
| Surface | 7,669 agree, and the provider never names a different surface. In 106 matches it says "no surface" where Sackmann has hard (92), clay (11), or grass (3) |
| Set-by-set games, completed matches | 7,476 of 7,481 |
| Round | 7,527 agree. Provider blank in 248 (221 round robin, 27 Davis Cup knockouts) |
| Best-of from the tournament rule (ATP Grand Slam main draw = 5) | 7,754 of 7,775 |
| Aces / double faults exact | 14,629 / 14,637 of 14,704 player-matches (99.5%) |
| Service points won % within 1 point | 14,417 of 14,692 (98.1%). Mean difference −0.01, sd 0.66 |
| Return points won % within 1 point | 14,417 of 14,692 (98.1%) |
| Break points saved % within 1 point, when Sackmann shows at least one faced | 13,771 of 14,139 (97.4%) |
| Break points won % within 1 point, when there was at least one chance | 13,770 of 14,139 (97.4%) |
| Statistics present | Both 14,704, provider only 604, Sackmann only 30, neither 212 |

**Service points won.** A standard deviation of 0.66 points is what rounding to whole percentages produces. The two sources record the same serve performance. More than 5 points apart in 31 matches (0.4%):
- 28 completed matches where the sources genuinely disagree;
- 2 with the sides swapped;
- 1 retirement.

Which source is right can't be told from the files.

**The break-point pitfall.** In every one of the 469 player-matches where Sackmann shows no break points faced, the provider reports "saved 0%". Its break-points-won figure behaves the same way when there were no chances. "None faced" and "faced some, saved none" therefore look identical, so **break-point percentages from this source cannot be used as features**.

## Ranks

Provider ranks are blank for 95.4% of WTA 2025 player-matches. The 171 WTA players who do have a 2025 rank almost never change it during the season. Otherwise, ranks are blank about 2–3% of the time in 2026 and 35% for ATP 2025.

They match Sackmann's rank on the same match in 83.4% of ATP player-matches and 60.7% of WTA player-matches. ATP agreement is about 100% from January to July 2025. From August 2025 it varies between 17% and 100% per month, and between 42% and 87% in every month of 2026. When the two differ, the official ranking lists in Sackmann's ranking files show where the provider's number comes from:

| Nearest official list with the provider's rank, relative to the last list before the match | ATP | WTA |
|---|---:|---:|
| 1–5 weeks older | 1,214 | 853 |
| The last list before the match | 75 | 115 |
| A later list | 24 | 7 |
| On no list | 11 | 0 |

The provider's rank is usually an older list, not a future one. A later list matches in 31 of 2,299 differing cases (1.3%), which equal rank values on nearby lists can explain. Provider ranks are **pre-match but stale by one to three weeks** in 2026. Sackmann's are as of the tournament week.

The held-out period has to use provider ranks, because Sackmann's ranking files end on 8 June 2026. Before the Phase 4 protocol is frozen, a check with no outcomes will measure how much the Phase 3 and Phase 4 probabilities move on January–May 2026 when provider ranks replace Sackmann's. Both models will get identical rank inputs.

## Tournament dates

Phase 3 uses Sackmann's `tourney_date` as the cutoff: a match's features use only matches with an earlier date. Provider rows have only match days, so each event gets a date from a rule. Rows are grouped into editions: same tour, same name with " - Play Offs" removed, and no gap of more than seven days.

| Rule for an edition's date | Exact match with Sackmann | Within one day |
|---|---|---|
| **First main-draw match day (chosen)** | 149 of 182 linked editions (81.9%) | 175 (96.2%) |
| Monday of that week, weekend starts moved to the next Monday | 115 (63.2%) | 147 (80.8%) |

The remaining differences have two sources. Sackmann dates some Sunday starts on the Sunday (Geneva, Hamburg, Mallorca, Umag) and others on the Monday (the Grand Slams, Brisbane, Monte Carlo). It also dates each round of the Davis Cup Finals separately. No single rule reproduces both.

A date one day off only reorders events that start a day apart. Players in the earlier event's late rounds can't be playing the later event, so this does not let a match's own result into its features.

## The sealed period (metadata only)

| | ATP | WTA |
|---|---:|---:|
| Main-tour main-draw rows dated 1 June 2026 or later | 1,446 | 1,346 |
| French Open rows dated in June. The edition starts 24 May, Sackmann already has it, and Phase 3 scored it | −11 | −11 |
| Editions still running when the files were saved: Paris (ATP); Chennai, Hong Kong, and the WTA Finals (WTA) | −50 | −65 |
| **Candidate held-out rows** | **1,385** | **1,270** |
| … with both players already in the crosswalk | 1,252 (90.4%) | 1,185 (93.3%) |
| … with one player | 110 | 84 |
| … with neither | 23 | 1 |
| … with serve statistics present | 1,274 (92.0%) | 1,221 (96.1%) |

The candidate rows cover 59 editions (31 ATP, 28 WTA) from the grass season through the Asian swing, including Wimbledon and the US Open. Eight event names don't appear in the open period:
- ATP: Davis Cup World Group I, Davis Cup World Group II, Estoril, Lyon, Montreal;
- WTA: Athens, Memphis, Toronto.

These are calendar changes, such as the Canadian event alternating between Toronto and Montreal, and new or renamed tour events. None belongs to the seven families Sackmann leaves out, so the proposed rule includes them.

The 2,655 candidate rows are an upper bound. Retirements, walkovers, and cancellations are sealed. In the open period 94.7% of rows ended FINISHED, so the held-out evaluation should have **about 2,500 rated matches**.

**What that size can detect.** The Phase 3 nested-model gaps had a clustered standard error of about 0.0008 on 13,732 matches. On 2,500 matches that becomes about 0.0019. A serve-return gain of 0.001–0.003 log loss per match would likely fall inside its own uncertainty. Phase 4 will report the held-out result as an estimate with an interval. It will not treat it as a pass-or-fail test, and it will not call it an improvement if the interval includes zero.

## License and provenance

- **Source:** the free season CSVs from https://tennisdata.app/downloads/, placed in the repository by the user.
- **Terms:** the user located the site's Terms of Service at https://tennisdata.app/terms/, updated 2 November 2026. As the user reports it, Section 18, "Intellectual Property and Permitted Data Use," permits downloading, storing, transforming, and analyzing lawfully obtained data for personal, academic, research, and commercial purposes, including training and evaluating machine-learning models. I did not open that page, so this report records what the user found rather than an independent reading of the terms.
- **Handling in this project:**
  - Raw files and row-level outputs derived from them stay local. Git ignores `data/` and `results/`, and `.gitignore` also names `/data/external/tennisdata_app/*.csv`. No file under `data/` or `results/` is tracked.
  - Only aggregate findings are published: counts, agreement rates, and model scores. The files and substantial reproductions of them are not redistributed.
- **Provenance:** the files don't say where the provider gets its data. The home/away layout, `winner_code`, and round names like "1/16-finals" look like a third-party live-score feed. The upstream source is **not verified**, and this report does not claim it is. The agreement with Sackmann above is the independent check of accuracy that this audit can offer.

## What this means for Phase 4

1. **Portable features only for the primary model.** Only service points won and return points won are defined the same way in both sources. The feature engine will:
   - average them as match-level whole-number percentages, rounding Sackmann's to whole numbers too, so both sources go through the same process;
   - never weight provider percentages by points.

   Break points are excluded because of the 0% pitfall. Aces and double faults are excluded because, without point counts, they can't become rates. First-serve and second-serve figures are Sackmann-only development experiments.
2. **Match key** is tour plus `match_id`.
3. **Held-out population:**
   - main-tour main draws only: no qualifying, wheelchair, or Challenger/WTA 125 rows;
   - without the seven event families Sackmann omits;
   - editions starting 1 June 2026 or later, and finished before the files were saved;
   - best-of from the tournament, never from the sets played;
   - rated matches are FINISHED rows, matching Sackmann's "completed".
4. **Event date** is the edition's first main-draw day, with play-off stages joined to their event.
5. **Source precedence:**
   - Sackmann through the week of 25 May 2026, and provider rows only for editions starting 1 June 2026 or later;
   - any provider row that also matches a Sackmann match is dropped;
   - no match may update ratings or profiles twice.
6. **Players:**
   - the 777-id crosswalk links provider players to Sackmann ids;
   - a held-out player not in it is matched by name key to a Sackmann player only when exactly one Sackmann player with tour-level matches fits;
   - otherwise the player starts as a new player.
7. **Ranks come from the provider in the held-out period.** Their one-to-three-week lag is a known difference, measured before the freeze without outcomes.

## Decision needed from you before the freeze

Please confirm that the eight event names new in the sealed period (Estoril, Lyon, Montreal, Davis Cup World Group I and II; Athens, Memphis, Toronto) should be in the held-out population. Including them is the proposed default.

## Reproducing

```powershell
python -m matchup_dna.audit_tennisdata
python -m unittest tests.test_tennisdata tests.test_crosswalk
```

The audit takes about 20 seconds. It writes `results/phase4/audit/tennisdata_audit.txt` with every number in this report, a manifest with the input file hashes, and `results/phase4/crosswalk.csv`.

| File | What it does |
|---|---|
| `matchup_dna/tennisdata.py` | The only reader of the provider files: the 49-column check, the seal, draw categories, best-of rule, and editions with their dates |
| `matchup_dna/crosswalk.py` | Name keys, match linking with the date window, the one-to-one crosswalk, and the id-based second pass |
| `matchup_dna/audit_tennisdata.py` | This audit |
| `tests/test_tennisdata.py` | Sealed rows lose 31 columns at 1 June 2026 UTC. Unsealing needs a frozen Phase 4 protocol. The file shape is checked. Blank is missing, never zero. Best-of comes from the tournament. Editions split on gaps and join play-off stages. The same `match_id` on two tours is two matches |
| `tests/test_crosswalk.py` | A surname alone never links. The date window, ambiguous candidates, and a Sackmann match claimed twice are each left unlinked. Reversed names are tagged. Tours never mix. Conflicting ids are left out both ways. The second pass uses validated ids only |

## What the audit did

TennisData.app gives a second record of the same tennis matches that Sackmann records, and it continues past May 2026, where Sackmann stops. The audit asked two things: whether the new files describe the same matches correctly, and whether they can stand in for Sackmann after May.

On the 2025 and early-2026 matches that both sources have, they agree almost completely. They agree on who won, on the scores, and on the aces and double faults. They agree on the share of serve points each player won, to within the rounding the new files use. Players in the new files can be tied to Sackmann's player numbers without guessing. Two matches count as the same only when both full player names and the dates line up, and a name that could belong to two people is left unlinked.

The new files record less, though. For serve and return they keep one percentage per match, not the counts behind it, so a long match and a short match can't be weighed against each other. They record nothing about first and second serves. Their break-point numbers show 0% when a player never faced a break point, which can't be told apart from saving none. Their rankings in 2026 are a week or more out of date.

So Phase 4 will use the new files for one job: a fresh test, on about 2,500 matches from June to October 2026, of a model that uses only information both sources record the same way. Those matches' results have not been looked at, and won't be until the Phase 4 model and the rules for scoring it are fixed and saved. About 2,500 matches is enough to show a clear improvement. It probably isn't enough to show a very small one, and the report will say so if that is what happens.
