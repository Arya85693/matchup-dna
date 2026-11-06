# Matchup DNA — Phase 4 Data Audit

**Date:** 5 November 2026  
**Sources:** Jeff Sackmann's tour-level files (the Phase 0–3 source), TennisData.app season files, and TennisIsMyLife (TML) season and ongoing-tournament files.  
**Question:** Together, do these sources give reliable ATP and WTA main-tour data through 5 November 2026, with no match counted twice, and is that data rich enough for serve-return and matchup features?  
**Answer:** Yes.

TML uses Sackmann's layout and carries real point counts. Where it and Sackmann cover the same match, its service-points-won figure is identical to Sackmann's in 98.4% of player-matches. Its counts are complete for 96.9% of ATP and 99.0% of WTA held-out rows.

So the June–October 2026 held-out evaluation can test the full feature set built from point counts:
- serve and return points won, weighted by points;
- first-serve and second-serve figures;
- ace and double-fault rates;
- break points.

TennisData.app's percentages could support only service and return points won, weighted by match.

The held-out period should hold about 2,500–2,600 rated matches: TML's rows plus about 220 TennisData.app rows TML lacks. That is enough to detect a clear improvement, probably not a very small one. The limit on WTA feature history is unchanged by these sources: Sackmann's WTA statistics cover only 76–80% of matches in 2010–2015.

This report replaces "Phase 4 - TennisData.app Data Audit.md". Parts 1–2 audit the two new sources. Part 3 sets how they combine with Sackmann. Part 4 answers the feature question. The last section, "What the audit did," says it in ordinary language.

## What was read, and the seal

| Source | Location | Files | Rows | Role |
|---|---|---|---:|---|
| Sackmann | `data/atp/`, `data/wta/` | yearly `*_matches_YYYY.csv` | 361,571 (through the week of 25 May 2026) | Primary history, unchanged from Phase 3 |
| TennisData.app | `data/external/tennisdata_app/` | 2025 and 2026 ATP and WTA seasons | 42,962 | Cross-check, and held-out matches TML lacks |
| TennisIsMyLife | `data/external/tennisismylife/` | 2025 and 2026 ATP and WTA seasons, ATP and WTA ongoing tournaments | 10,870 | Statistics after May 2026, and the main held-out source |

The TML folder on disk is `tennisismylife`. Neither website was visited, and nothing was downloaded.

**The seal.** Matches from 1 June 2026 on are the candidate held-out period, and their outcomes have not been looked at. Each new source has exactly one reader, and that reader removes outcome information before any other code sees a held-out row:

- **TennisData.app** (`tennisdata.load_provider`). Rows dated 1 June 2026 or later (UTC) lose 31 columns: status, winner, sets and games, odds, and statistics. Each keeps one yes/no flag saying whether it had statistics.
- **TML** (`tennisismylife.load_tml`). TML rows are written from the winner's side, so merely knowing which player is in `winner_id` is knowing the result. Rows dated 1 June 2026 or later are rebuilt:
  - The two players become player A and player B, ordered by player id, so the order says nothing about who won.
  - Each keeps only pre-match fields: rank, points, seed, entry, age, hand, height, and country.
  - The score, the minutes, and all 18 statistic columns are deleted. Two yes/no flags say whether statistics existed.
  - A test checks that the same match gives an identical sealed row whichever player won.

Both readers unlock only with a frozen Phase 4 protocol file, which does not exist yet.

There is a subtler leak. In a knockout draw, the two names in a later-round row show who won the earlier rounds. So for sealed rows the audit programs print **aggregate counts only**, never a per-match list.

TML's 2026 files date each round separately (see Part 2), so its seal is slightly wider than needed. The 12 ATP French Open rows dated in June are sealed, although that event is already in Sackmann and in the Phase 3 reserved evaluation.

---

## Part 1 — TennisData.app

### Files and fields

| File | Rows | Match days (UTC) | Before 1 June 2026 | Sealed |
|---|---:|---|---:|---:|
| `2025-atp-season.csv` | 14,620 | 27 Dec 2024 – 21 Dec 2025 | 14,620 | 0 |
| `2025-wta-season.csv` | 6,112 | 27 Dec 2024 – 14 Dec 2025 | 6,112 | 0 |
| `2026-atp-season.csv` | 15,511 | 2 Jan – 6 Nov 2026 | 7,451 | 8,060 |
| `2026-wta-season.csv` | 6,719 | 2 Jan – 8 Nov 2026 | 3,088 | 3,631 |

Every file has the same **49 columns**. An earlier draft said 48, which was a miscount. 81 rows are dated on or after the day the files were saved, 5 November, so they are unplayed fixtures. The definitions below are inferred from the values. Blank shares are over the 31,271 open rows.

| Column | Blank | Meaning |
|---|---:|---|
| `match_id` | 0% | Unique within a tour. Four values are reused across the ATP and WTA files for different matches, so a match is **tour plus `match_id`** |
| `season_year`, `tour_type`, `tour_type_human` | 0% | Season; 1 ATP Tour, 2 WTA Tour, 3 ATP Challenger, 4 WTA 125 |
| `date_timestamp`, `date_human` | 0% | Match time in Unix seconds. `date_human` equals its UTC date in all 42,962 rows |
| `tournament` | 0% | Event name with suffixes " - Qualification", " - Play Offs", " - WIC" (wheelchair), "(indoor)" |
| `round` | 3.3% | "1/64-finals" (R128) … "Final", "Qualifier". Blank for team events and round robins |
| `surface`, `surface_id` | 0% | hard, clay, grass, "no surface" |
| `status`, `status_extra` | 0% | FINISHED; then FINISHED, RETIRED, WALKOVER, CANCELED, AWARDED |
| `home_name`, `away_name`, `home_id`, `away_id` | 0% | "Surname I." and provider ids. Home and away are listing order only |
| `home_rank`, `away_rank`, `home_points`, `away_points` | 36.0% | Ranking shown for the match |
| `winner_code` | 1.4% | 1 home, 2 away |
| set scores (12 columns) | 2.0% to 99.5% | Sets won, and games in each set. No tiebreak points |
| odds (4 columns) | 3.5% to 6.5% | Decimal match and first-set odds. Opening or closing is not stated |
| aces, double faults (4) | 2.1% | Counts |
| service and return points won % (4) | 2.1% | Whole-number percentages. A player's return % equals 100 minus the opponent's service %, within one point, in 99.4% of rows |
| break points won and saved % (4) | 2.9–3.0% | Percentages. They show 0% when there were no break points at all (see below) |

**What is missing:** serve-point totals, first serves in, and first-serve or second-serve points won. Without point totals, matches can be averaged only as matches, never pooled point by point.

### Coverage and integrity

| | ATP main draw | WTA main draw | Challenger / WTA 125 main draw | Qualifying (tour) | Wheelchair |
|---|---:|---:|---:|---:|---:|
| Rows, all | 5,652 | 5,387 | 13,863 / 3,576 | 2,755 / 2,832 | 3 / 3 |

Integrity findings:
- No match appears twice within a tour, and no row has the same player on both sides.
- In FINISHED rows the winner agrees with the sets 29,620 times out of 29,625.
- The endings are FINISHED 29,629, RETIRED 1,025, CANCELED 446 (no winner), WALKOVER 169, and AWARDED 1.
- **62 walkovers carry statistics**, which is invalid because no points were played. 117 canceled rows also carry statistics. Statistics count only from FINISHED rows, so neither group can enter a profile.
- 9 provider ids carry two spellings, and 13 name strings belong to two ids. Players are keyed by id, never by name.

### Linking to Sackmann

A provider row and a Sackmann match are the same match only when all of these hold:
- they are on the same tour;
- both players' name keys agree (full surname with accents and punctuation removed, plus first initial);
- the match day is −3 to +16 days from Sackmann's `tourney_date`;
- exactly one Sackmann match fits;
- no other row claims that Sackmann match.

A surname alone never links. Only main-tour main-draw rows are linked. As a control, qualifying and Challenger rows, which Sackmann's files don't contain, would produce 185 and 8 false links under the same rule.

| Open main-draw rows | ATP | WTA |
|---|---:|---:|
| Linked by name | 4,008 | 3,706 |
| Ambiguous, never merged | 71 | 36 |
| No candidate | 125 | 299 |

- **Reversed names:** 41 links used a reversed name order. Sackmann stores "Bu Yunchaokete"; the provider has "Bu Y.".
- **Second pass:** 61 more rows linked by validated player ids, catching spelling differences such as "O'Connell" and "Oconnell".
- **Crosswalk:** 777 provider ids, one-to-one, with no conflicts. A draft count of 806 ids and one conflict included qualifying rows and came from a false link of that kind.
- **Events Sackmann omits** link at 0%: the Hopman Cup and the BJK Cup Group I and relegation ties.

### Agreement with Sackmann (7,775 linked matches)

| Field | Agreement |
|---|---|
| Winner | 7,775 of 7,775 |
| Set-by-set games, completed matches | 7,476 of 7,481 |
| Aces, double faults | 99.5% of player-matches exact |
| Service points won % | within 1 point in 98.1% (sd 0.66, the size of rounding to whole percentages) |
| Break points saved %, with at least one faced | within 1 point in 97.4% |
| Surface | the provider never names a different surface; it is blank ("no surface") in 106 |

**Break points can't be used.** In all 469 player-matches where Sackmann shows no break points faced, the provider reports "saved 0%".

**Ranks are stale.** They equal Sackmann's in 83.4% of ATP and 60.7% of WTA player-matches, and are 95.4% blank for WTA in 2025. When they differ, 2,067 of 2,299 match an official list one to five weeks *older*, and 31 match a later list.

**Dates.** Using an event's first main-draw day as its date matches Sackmann's `tourney_date` for 81.9% of editions and is within a day for 96.2%.

---

## Part 2 — TennisIsMyLife

### Files and fields

| File | Rows | `tourney_date` | Open | Sealed |
|---|---:|---|---:|---:|
| `2025_atp.csv` | 2,943 | 29 Dec 2024 – 22 Dec 2025 | 2,943 | 0 |
| `2026_atp.csv` | 2,719 | 2 Jan – 1 Nov 2026 | 1,392 | 1,327 |
| `ongoing_tourneys.csv` (ATP) | 47 | 2–5 Nov 2026 | 0 | 47 |
| `2025_wta.csv` | 2,622 | 30 Dec 2024 – 14 Nov 2025 | 2,622 | 0 |
| `2026_wta.csv` | 2,491 | 4 Jan – 26 Oct 2026 | 1,270 | 1,221 |
| `wta_ongoing_tourneys.csv` | 48 | 2–3 Nov 2026 | 0 | 48 |

**Schema.** Every file has the same **50 columns**: Sackmann's 49 plus `indoor`. The ranks sit after the player's age rather than at the end. The loader refuses any file that differs. The meanings are Sackmann's, with these differences:

| Field | Difference from Sackmann |
|---|---|
| `tourney_id`, `match_num` | Different numbering (`2025-301` against Sackmann's `2025-0301`; separate Grand Slam and United Cup codes), so rows cannot be joined by key |
| `tourney_level` | ATP 250 and 500 where Sackmann has A; WTA 1000, 500, and 250 where Sackmann has PM, P, and I. G, M, F, and D are as in Sackmann. "A" marks team and exhibition-format tour events such as the United Cup |
| `tourney_date` | Tournament start in the 2025 files. **In the 2026 files each round has its own date**: 89 of 116 ATP tournaments carry more than one, and the 2026 Australian Open runs from 20 January (R128) to 1 February (final). An edition's start is therefore its earliest date |
| `indoor` | O (outdoor), I (indoor), or blank (50.2% of open rows). 127 sealed rows carry "0", probably a typo for O |
| Player ids | **ATP ids are the ATP's own codes** (565 of 571 contain letters, e.g. "CD85"). **WTA ids are numbers that usually equal Sackmann's**, but not always (below) |
| `round` | Main-draw rounds only (R128 … F, RR). No qualifying or Challenger matches; qualifiers appear as entry "Q" |

Blank shares on open rows: ranks 0.2–0.8%, height 6.5–9.8%, minutes 4.7%, statistics 2.8% (service games 3.0%). On sealed rows (fields kept): ranks 0.6%, ages 0.7%.

### Coverage

| Level (TML) | ATP rows | WTA rows |
|---|---:|---:|
| Grand Slam (G) | 1,016 | 1,016 |
| Masters / WTA 1000 | 1,542 | 1,660 |
| 500 | 1,008 | 1,031 |
| 250 | 1,614 | 1,255 |
| Team-format tour events (A) | 81 | 56 |
| Tour Finals (F) | 15 | 15 |
| Davis Cup / BJK Cup (D) | 433 | 128 |

Surfaces: hard 6,806, clay 2,869, grass 1,195, with none blank.

**Sackmann matches (weeks from 29 Dec 2024 to 25 May 2026) that TML has:**

| Sackmann level | 2025 ATP | 2026 ATP | 2025 WTA | 2026 WTA |
|---|---|---|---|---|
| Grand Slam | 498/508 | 237/254 | 502/508 | 252/254 |
| Masters / WTA 1000 | 755/775 | 415/435 | 811/830 | 480/490 |
| 250–500 (ATP A; WTA P, I) | 1,257/1,297 | 605/632 | 421/427 P, 635/647 I | 256/258 P, 246/271 I |
| Tour Finals | 27/30 | — | 15/15 | — |
| Davis Cup / BJK Cup | **222/252** | 78/128 | **50/50** | **22/22** |
| WTA "35+H" and "50+H" | — | — | 0/215 | — |

TML covers team events far better than TennisData.app, which had 14 of the 252 ATP 2025 Davis Cup matches. Like TennisData.app, it has none of the lower WTA events in Sackmann's 2025 WTA file. Part of the 2026 ATP Grand Slam shortfall is the French Open's June rounds, which are sealed.

### Integrity

| Check | Result |
|---|---|
| Repeated tournament + match number, or tournament + round + player pair (all rows) | None |
| Same player on both sides (all rows) | None |
| Tournaments in both a season file and an ongoing file | None |
| Endings (open) | ATP: completed 4,163, retired 140, walkover 32. WTA: 3,755, 110, 27 |
| Walkovers carrying statistics (open) | 0 of 59 |
| Open player stat lines | ATP 8,237 complete and valid, 408 entirely blank, 25 with a problem (24 missing service games, 1 missing break points). WTA 7,730 complete and valid, 54 entirely blank |

Each statistic line is checked against eight rules in `serve_stats.py`. For example: first serves in can't exceed serve points, points won on second serve can't exceed second-serve points, and break points saved can't exceed break points faced. A blank is missing, never zero. **No open TML line breaks a rule.**

**Ids and names (all rows, metadata):**
- Two ids carry two spellings: "Diego Dedura" and "Diego Dedura-Palomero"; "Xin Yu Wang" and "Xinyu Wang".
- **Six WTA players appear under two ids each**, for example Teodora Kostovic as 266640 and 267020, and Mary Stoiana as 223168 and 269265.

The held-out build must therefore resolve players through Sackmann identities, never by TML id alone.

### Linking to Sackmann

The rule is the same as for TennisData.app, with **full names** instead of surname and initial. A name may also match in reversed order, and the TML date must be −3 to +16 days from Sackmann's `tourney_date`.

| Open rows | ATP | WTA |
|---|---:|---:|
| Linked | 4,173 | 3,793 |
| Ambiguous, never merged | 61 | 52 |
| No candidate | 101 | 47 |

- **Reversed names:** 42 links used a reversed name order.
- **The crosswalk:** 848 TML ids, one-to-one, with no conflicts. 216 of them rest on a single linked match.
- **WTA ids:** they equal Sackmann's for 376 of 384 linked WTA players. The 8 exceptions are recent debutants, for example Laura Samson (TML 264959, Sackmann 266671). So WTA ids also go through the validated crosswalk.
- **Edition dates:** an edition's earliest TML date is within a day of Sackmann's `tourney_date` for 96.6% of 2025 editions and 98.8% of 2026 editions.

### Agreement with Sackmann (7,966 linked matches)

| Field | Agreement |
|---|---|
| Winner | 7,965 of 7,966. The exception is a Davis Cup match whose deciding tiebreak is [10-8] in TML and [8-10] in Sackmann; one source is wrong |
| Score text | 7,883 of 7,965 identical. Most differences are formatting, e.g. Sackmann's "7-5 6-1 0-0 RET" for TML's "7-5 6-1 RET" |
| Ending, round, best-of | 7,963, 7,960, and 7,959 of 7,965 |
| Surface | 7,902 of 7,965. The differences are TML filling surfaces Sackmann leaves blank, mostly BJK Cup ties |
| Service points won % | **identical in 98.4%**, within 1 point in 99.2% (sd 0.49) |

Individual statistics, over player-matches where both sources have the field:

| Statistic | Identical | Differ | TML only | Sackmann only |
|---|---:|---:|---:|---:|
| Serve points | 14,385 (98.7%) | 187 | 960 | 40 |
| First serves in | 13,928 (95.6%) | 644 | 960 | 40 |
| First-serve points won | 14,075 (96.6%) | 497 | 960 | 40 |
| Second-serve points won | 14,064 (96.5%) | 508 | 960 | 40 |
| Aces | 14,528 (99.7%) | 44 | 960 | 40 |
| Double faults | 14,523 (99.7%) | 49 | 960 | 40 |
| Break points faced | 14,530 (99.7%) | 42 | 959 | 40 |
| Break points saved | 14,539 (99.8%) | 33 | 959 | 40 |
| Service games | 14,331 (98.3%) | 241 | 936 | 40 |

The two sources record the same matches, with occasional corrections that differ, mostly in the first-serve fields. **TML has statistics for 960 player-matches that are blank in Sackmann**, about 6% of 2025–May 2026. Sackmann has 40 that TML lacks.

**Ranks.** TML's ATP ranks equal Sackmann's in 7,925 of 8,284 player-matches (95.7%); 285 of the rest match the list one week older. WTA ranks equal Sackmann's in 6,294 of 7,569 (83.2%). Of the WTA differences:
- 963 match the latest official list before the TML date, where Sackmann's rank is older;
- 84 match a list one to three weeks later;
- about 80 are stale by six weeks or more;
- 128 appear on no list.

So TML ranks are at least as current as Sackmann's, and closer to them than TennisData.app's.

### TML against TennisData.app (open period)

TennisData.app main-draw rows were linked directly to TML rows by surname and initial, tried against every way of splitting TML's full names. The direct links were then checked against Sackmann, which both sources link to on their own:

| Result | Count |
|---|---:|
| Direct link, both sides reach Sackmann: **same** Sackmann match | 7,530 |
| Direct link, both sides reach Sackmann: **different** Sackmann match | **0** |
| Direct link, one side not in Sackmann | 140 |
| Both reach the same Sackmann match but no direct link (ambiguous 13, no candidate 8) | 21 |
| Added by a second pass through validated ids | 68 (10 confirmed by Sackmann, none contradicted) |

Service points won, TennisData.app's percentage against TML's counts: within 1 point in 97.5% of 15,148 player-matches.

**What one source has and the other lacks (open period):**
- **509 TennisData.app rows have no TML row.** 154 are CANCELED (never played), 246 are events Sackmann also omits, and 94 are genuine matches TML lacks.
- **489 TML rows have no TennisData.app row.** 341 of them are Davis Cup and BJK Cup ties.

### The held-out period in TML (metadata only)

| | ATP | WTA |
|---|---:|---:|
| Sealed rows | 1,374 | 1,269 |
| … French Open rounds dated in June (the edition starts in May, already in Sackmann) | 12 | 0 |
| … ongoing files: Paris Masters (from 2 Nov); Chennai and Hong Kong (from 2–3 Nov) | 47 | 48 |
| **Candidate rows**: edition starts 1 June 2026 or later, not ongoing | **1,315** | **1,221** |
| … with all 18 statistics | 1,274 (96.9%) | 1,209 (99.0%) |
| … both players in the TML-Sackmann crosswalk | 1,186 (90.2%) | 1,150 (94.2%) |

The candidates span 89 tournaments, each Davis Cup and BJK Cup tie counting separately. They include Wimbledon, the US Open, and every Masters and WTA 1000 event of the period.

---

## Part 3 — Combining the sources

### Overlap in the held-out period (metadata only)

TennisData.app candidates are defined as in Part 1:
- main draw only, no qualifying or wheelchair rows;
- the edition starts on or after 1 June 2026 and was complete before the 5 November file snapshot.

They were matched to TML candidates the same way as in the open period: names first, then validated ids.

| | ATP | WTA |
|---|---:|---:|
| TennisData.app candidate rows | 1,385 | 1,270 |
| … matched to a TML row (names, then ids) | 1,243 | 1,188 |
| … no TML row | 142 | 82 |
| TML candidate rows with no TennisData.app row | 72 | 33 |
| **Union** (all TML candidates, plus TennisData.app rows TML lacks) | **1,457** | **1,303** |

Most unmatched TennisData.app rows are the Davis Cup World Group I and II (53 ATP rows). The rest are spread thinly across events.

In the open period, about 30% of such rows were canceled matches. Their status is sealed, so they leave only when the period is unsealed. TML completed about 96% of its open rows. **The held-out evaluation should therefore have about 2,500–2,600 rated matches.** As the earlier audit showed, the standard error of a model comparison is about 0.0019 log loss per match at that size.

All eight event names that appear only in the sealed TennisData.app rows are tour-level events in TML too: Estoril, Lyon, Montreal, Davis Cup World Group I and II, Athens, Memphis, and Toronto. They are included.

### Source precedence

The merge module will implement these rules, frozen before any held-out outcome is opened:

1. **Tournament weeks through 25 May 2026 come from Sackmann only**, as in Phase 3. Phase 3's inputs, splits, and results don't change.
   - Where a Sackmann match has blank statistics, the TML statistics for the same linked match fill them, marked as TML-sourced. That covers 960 player-matches in 2025–May 2026.
   - Where both have statistics, Sackmann's are kept.
   - Phase 3 doesn't use statistics, so this affects only Phase 4 profiles.
2. **Editions starting from 1 June 2026, complete before 5 November, come from TML.**
   - A TennisData.app row is added only if it matches no TML row (names, then validated ids), no Sackmann match, and none of the seven event families Sackmann omits.
   - Added rows supply results, which update Elo, form, and inactivity. Their statistics are treated as missing: TennisData.app percentages are never mixed with point counts.
3. **Ongoing editions are history only.** Paris (ATP), and Chennai and Hong Kong (WTA), were still running when the files were saved, so they are not scored. Their completed matches through 5 November feed later matchup reports only. Every held-out edition starts before them, so they can't affect any held-out feature.
4. **Players:**
   - TML and TennisData.app ids are mapped to Sackmann ids through their validated crosswalks.
   - A held-out player in neither crosswalk is matched to a Sackmann player only when exactly one Sackmann player with tour-level history has that full name. Otherwise the player starts as a new player.
   - The six WTA players who carry two TML ids are resolved through Sackmann, so each counts once.
5. **Dates:**
   - a held-out edition's date is TennisData.app's first main-draw day when that edition is in TennisData.app, otherwise TML's earliest date;
   - best-of comes from the tournament, never from the sets played;
   - rated matches are completed ones, Sackmann's definition.
6. **No double counting.** The build stops if a match key appears twice. A test checks that every match updates Elo, form, last-played date, and each profile exactly once.
7. **Ranks in the held-out period come from TML**, falling back to TennisData.app's when TML lacks the match. Before the freeze, a check with no outcomes measures how much Phase 3 and Phase 4 probabilities move on January–May 2026 when TML ranks replace Sackmann's.
8. **After unsealing,** inside the one-time held-out command, the winners and scores of TML/TennisData.app matched pairs are compared and reported as a data check. TML's version is used if they disagree. No modeling choice depends on that check.

### All main-tour data through 5 November 2026

| Period | Source | ATP | WTA | Point counts |
|---|---|---:|---:|---|
| 1968 – week of 25 May 2026 | Sackmann | 199,389 | 162,182 | ATP 88–99% of matches from 2005; WTA 76–80% in 2010–2015, 92–100% from 2016; plus 960 TML-filled player-matches in 2025–26 |
| Editions starting 1 June – 1 November 2026 | TML (+ TennisData.app rows TML lacks) | about 1,457 rows | about 1,303 rows | 96.9% (ATP) and 99.0% (WTA) of TML rows; none for added TennisData.app rows |
| Editions running on 5 November | TML ongoing files | 47 | 48 | History only |

Out of scope here: Challenger and ITF results (TennisData.app has Challenger, but Sackmann's tour-level history doesn't), and point-by-point data.

## Part 4 — Is there enough for richer serve-return and matchup features?

**Yes, from Sackmann and TML together.**

| Feature family | Built from | Before June 2026 | Held-out period | Verdict |
|---|---|---|---|---|
| Service and return points won, point-weighted | serve points, first- and second-serve points won | Sackmann (+ TML backfill) | TML, 96.9% / 99.0% complete | **Usable** |
| First serves in %, first- and second-serve points won % | same | Sackmann | TML; fields identical to Sackmann in 95.6–96.6% | **Usable**. TML's small first-serve corrections are a known difference |
| Ace and double-fault rates per serve point | aces, double faults, serve points | Sackmann | TML; identical in 99.7% | **Usable** |
| Break points saved and converted | break points faced and saved | Sackmann | TML; identical in 99.7–99.8%. "None faced" is a count of 0, not "0% saved" | **Usable**, unlike TennisData.app's percentages |
| Opponent-adjusted serve and return | the above, plus the opponent's pre-match profile | all sources | all sources | **Usable** |
| Matchup interactions (A's serve × B's return, serve dominance × Elo, surface × serve-return, style × return) | the above | | | **Usable** |
| Head-to-head record | results only | all sources | TML + TennisData.app | **Usable** |
| Shot-level style (serve direction, rally length) | not in any of these sources | — | — | Not available |

**What this changes from the earlier plan.** The primary Phase 4 model was restricted to features TennisData.app could also reproduce, because its percentages were the only post-May statistics. TML removes that premise. The restriction becomes: **features defined identically from Sackmann's and TML's point counts.** TennisData.app percentages are still never pooled.

So the first-serve, second-serve, ace, double-fault, and break-point groups move from "development only" into the primary candidate set. They will be tested, kept, or dropped by the same pre-registered keep rule as everything else.

**What doesn't change:**
- **WTA training history.** Sackmann's WTA statistics cover only 76–80% of matches in 2010–2015. Profiles built from those years carry more missing-data indicators, so WTA serve-return features have less to learn from than ATP's.
- **Held-out size.** About 2,500 matches can confirm a clear gain, but probably not a gain of 0.001–0.003 log loss per match. The held-out result will be reported as an estimate with an interval. It will not be called an improvement if the interval includes zero.
- **Identity in the held-out period.** About 10% of ATP and 6% of WTA held-out rows have at least one player outside the TML-Sackmann crosswalk. Those players are matched by full name to a unique Sackmann player, or else start as new players. Their profiles are honest but thin.

## License and provenance

- **TennisData.app:** https://tennisdata.app/downloads/. The user located the Terms of Service at https://tennisdata.app/terms/ (updated 2 November 2026). As the user reports them, Section 18 permits downloading, storing, transforming, and analyzing the data, including for training and evaluating models. I did not read that page myself. The upstream source of the data is not stated, and the home/away layout suggests a third-party live-score feed. That is **not verified**.
- **TennisIsMyLife:** the user placed these files in the repository. **Their license and terms have not been reviewed yet.** The files don't state them, and I didn't visit the site.
  - The layout follows Jeff Sackmann's. If TML derives from Sackmann's work, Sackmann's CC BY-NC-SA 4.0 license, the same as Phase 0–3, would apply to that part.
  - Until the terms are confirmed, the files get the same handling as TennisData.app: private, local, never redistributed, and only aggregate findings published.
  - The upstream source of TML's statistics is **not verified**. Its agreement with Sackmann above is this audit's independent check.
- **Handling for both:** raw files and row-level outputs stay local. Git ignores `data/` and `results/`, and `.gitignore` also names `/data/external/tennisdata_app/*.csv` and `/data/external/tennisismylife/*.csv`. No file under `data/` or `results/` is tracked.

## Decision for you

One decision remains: **please confirm or find the TennisIsMyLife terms of use.** Everything above treats them as unknown and handles the files privately.

Two other questions were settled on the evidence:
- **The primary feature set.** It is broadened from "TennisData.app-portable" to "consistent between Sackmann and TML point counts" (Part 4). Say if you'd rather keep the narrower set.
- **The eight sealed-period event names.** They are all included, since TML has them as ordinary tour events.

## Reproducing

```powershell
python -m matchup_dna.audit_tennisdata
python -m matchup_dna.audit_tennisismylife
python -m unittest tests.test_tennisdata tests.test_tennisismylife tests.test_crosswalk tests.test_serve_stats
```

The two audits take about 20 seconds each. They write `results/phase4/audit/tennisdata_audit.txt` and `results/phase4/audit/tml_audit.txt` with every number in this report, manifests with input file hashes, and the two crosswalks, `results/phase4/crosswalk.csv` and `results/phase4/tml_crosswalk.csv`.

| File | What it does |
|---|---|
| `matchup_dna/tennisdata.py` | The only reader of TennisData.app: the 49-column check, the seal, draw categories, the best-of rule, editions and their dates, and held-out candidates |
| `matchup_dna/tennisismylife.py` | The only reader of TML: the 50-column check, the seal that rebuilds rows with player A and B, ongoing files, and editions with their earliest date |
| `matchup_dna/crosswalk.py` | Name keys, match linking in a date window, one-to-one crosswalks, and id-based second passes |
| `matchup_dna/serve_stats.py` | One player's statistics in one match, the eight validity rules, and points won on serve |
| `matchup_dna/audit_tennisdata.py`, `matchup_dna/audit_tennisismylife.py` | The two audits |
| `tests/test_tennisdata.py`, `tests/test_tennisismylife.py` | The seals. Sealed TML rows don't depend on who won. Unsealing needs a frozen Phase 4 protocol. File shapes, best-of, and editions |
| `tests/test_crosswalk.py` | A surname or full name never links to a namesake. Ambiguous and double-claimed matches stay unlinked. Reversed names are tagged. Conflicts are left out. Id passes use validated ids only |
| `tests/test_serve_stats.py` | Blank is missing, never zero. Each validity rule. "No break points faced" is valid, not 0% |

## What the audit did

Sackmann's files, the data behind Phases 0–3, stop in late May 2026. Two newer sources continue past that date. The audit asked whether they describe the same matches correctly, and whether they can carry the project to 5 November 2026 without counting any match twice.

TennisIsMyLife turned out to be the more useful of the two. It keeps match records the same way Sackmann does, including the number of serve points each player played and won. On the 2025 and early-2026 matches both sources have, it agrees with Sackmann almost exactly. It has the winner right in every match but one. Its serve statistics are identical 98.4% of the time, and it fills in statistics Sackmann is missing. It also covers the June–October 2026 matches with complete statistics for 97–99% of them. TennisData.app agrees with both, but it gives only rounded percentages, so its main job now is supplying the roughly one match in twenty that TennisIsMyLife lacks.

That matters for Phase 4. Earlier it looked as if the new matches could only test a simple version of the serve and return features. With TennisIsMyLife, they can test the full version: first and second serves, aces, double faults, and break points, all counted the same way as in Sackmann's history.

The results of the June-onward matches have not been looked at. The programs that read those rows strip out who won and every statistic before anything else sees them, and they report only totals. Those results will be opened once, after the Phase 4 model and the rules for scoring it are fixed and saved. There will be about 2,500 such matches: enough to show a clear improvement, probably not enough to show a very small one.

---

# Addendum — Physical Workload and Draw-Difficulty Feasibility

**Date:** 5 November 2026. This addendum adds to the audit above and does not change any of its findings or counts.  
**Question:** Can physical workload, recovery, and the difficulty of a player's route through a tournament be measured correctly, without leakage, from the data in hand?  
**Answer:** Mostly yes, with two exceptions.

Within a tournament, the games, points, and (for most years) minutes each player played in earlier rounds can be measured for about 99% of knockout matches. So can the pre-tournament strength of the opponents they beat. That needs a new prediction information set, "round-aware," which is evaluated as its own research track with its own baseline.

Two things can't be learned from these sources:
- **Recovery time between matches.** No source has match days before 2025.
- **Minutes-based features for WTA 2010–2015.** Sackmann records no WTA minutes in those years.

So the pre-registered workload feature uses **games played**, which is known for practically every match. Points and minutes are kept as diagnostics.

Nothing here relates any feature to who won. The audit measures coverage and structure only, so it could not steer which features are pre-registered. No model has been fitted, and no held-out outcome has been opened.

## A1. Why these features, and what they can and cannot show

Consider two finalists. One reached the final through three long matches against strong opponents; the other won quickly against weaker ones. The first may carry more physical load. But that same route also shows the first player is in strong current form, and Elo hasn't caught up: Phase 2's ratings update only after the tournament week, so "the weekly freeze ignores earlier-round wins in the same tournament."

Long matches can also mean a player struggled, which is a form signal, not fatigue. These effects push in opposite directions. Observational data cannot separate them completely, so:

1. Workload and route difficulty are measured separately, and neither is assumed to lower a player's chances.
2. Round-aware features are tested only against a **round-aware baseline**. That baseline already knows the earlier-round results (a temporary within-tournament Elo update) and how dominant the player was (share of games won). Any gain beyond it is reported as an association with workload or route, not as fatigue.
3. The measures are proxies for physical load, not observations of fatigue.

## A2. What was read

- **Sackmann:** all tour-level matches dated 2009 to the week of 25 May 2026, read by a new reader (`workload.load_matches_with_workload`). That reader adds minutes, draw size, and entry codes to the existing match records, leaving `matchup_dna/load.py` unchanged.
- **Elo:** the canonical ratings, from `elo.run_elo` with the fixed Phase 2 settings, read but never changed.
- **TML and TennisData.app:** read only through their sealed readers. For the held-out period, only round labels and availability flags were counted, in aggregate.

## A3. Definitions

For one match, both players share:

| Measure | Definition | Rules |
|---|---|---|
| **Games** | Both players' games in every set; a match tiebreak ("[10-8]") is one game | From the score text. A retirement counts the games played, including the unfinished set |
| **Points** | `w_svpt + l_svpt` (every point is one player's service point) | Both counts present and above zero; fewer than 4 points per game is impossible and is set to missing |
| **Minutes** | Sackmann's `minutes` | Above zero, and between 1.5 and 15 minutes per game; otherwise missing |
| **Sets** | Sets started | From the score |

Rules for kinds of ending:
- **Walkover:** a genuine zero. No court time, never imputed, and never counted as a match played. It is counted separately.
- **Retirement or default:** partial workload. The measures cover what was played, and the match is marked "partial."
- **Retirement or default with no games, abandoned match, unreadable score:** unknown.
- **A blank value is missing, never zero.** A sum over several matches is unknown if any one of them is unknown.

**Round-aware values** cover one player in one edition (tour + `tourney_id`), using only matches in **strictly earlier rounds** of that edition:
- the number of earlier matches, walkovers, and retirements;
- the sums of games, points, minutes, and sets;
- the share of games won, as a dominance measure;
- route difficulty: the mean, over opponents actually played, of (opponent's start-of-week Elo − own start-of-week Elo), and the maximum opponent Elo;
- the count of opponents with fewer than 20 rated matches, whose Elo is unreliable;
- the round-aware Elo shift.

**Round-aware Elo** is a separate calculation:
1. Each player's canonical start-of-week rating is copied.
2. The copy is updated round by round with the same K (32 for Elo; 48, blended half-and-half with the surface rating, for surface Elo). Only completed best-of-3 and best-of-5 matches count. A round's matches are applied together.
3. The shift is the copy minus the start-of-week rating.

The copy is thrown away after the edition, so every match still moves the canonical ratings exactly once, at the end of its week, as in Phase 2. A test checks that computing these features leaves the canonical ratings and predictions identical.

**Tournament-start workload:** a player's games, points, and minutes in matches dated in the 14 days before the tournament's date. It uses strictly earlier tournament dates, the Phase 3 rule.

## A4. Coverage of the inputs (Sackmann)

Shares of matches played on court (completed, retired, or defaulted after play began) with each measure usable:

| Tour | Period | On court | Walkovers | Games | Points | Minutes |
|---|---|---:|---:|---:|---:|---:|
| ATP | 2010–15 | 17,729 | 108 | 100.0% | 89.4% | 82.4% |
| ATP | 2016–20 | 12,937 | 80 | 100.0% | 98.6% | 98.1% |
| ATP | 2021–23 | 8,579 | 57 | 100.0% | 95.5% | 93.2% |
| ATP | 2024–May 2026 | 7,414 | 54 | 100.0% | 92.7% | 90.1% |
| WTA | 2010–15 | 16,483 | 79 | 100.0% | 77.6% | **0.1%** |
| WTA | 2016–20 | 12,494 | 66 | 100.0% | 98.2% | 97.9% |
| WTA | 2021–23 | 7,925 | 76 | 100.0% | 95.0% | 92.6% |
| WTA | 2024–May 2026 | 6,733 | 45 | 100.0% | 95.6% | 91.9% |

By tournament category, the gaps are concentrated:
- **Davis Cup and BJK Cup:** points and minutes missing entirely in 2010–15 and for 50–77% of matches from 2021. These matches are excluded from round-aware features anyway (A6).
- **Grand Slams, 2024–May 2026:** minutes known for only 80% and points for 90%.
- **Olympics:** 2024 ATP Olympic minutes are absent.
- **Regular tour events:** 92–100% complete on both measures from 2016.

**Plausibility, on completed matches 2010–2020 before any rule was applied:**

| | ATP | WTA |
|---|---|---|
| Minutes per game, 0.1st–50th–99.9th percentile | 2.75 – 4.20 – 6.64 | 2.38 – 4.41 – 6.93 |
| Matches outside 1.5–15 minutes per game | 5 | 9 |
| Points per game, 0.1st–50th–99.9th percentile | 4.90 – 6.23 – 8.32 | 4.67 – 6.50 – 9.00 |
| Matches with fewer than 4 points per game (impossible) | 1 | 12 |

The cut-offs sit far outside the observed distribution, so they remove only clear errors. No completed match had an unreadable score.

**How the measures relate** (completed matches 2016–2020 with all three known):

| | Matches | Games–points | Games–minutes | Points–minutes |
|---|---:|---:|---:|---:|
| ATP best of 3 | 9,687 | 0.951 | 0.895 | 0.943 |
| ATP best of 5 | 2,658 | 0.966 | 0.908 | 0.945 |
| WTA best of 3 | 11,886 | 0.953 | 0.919 | 0.954 |

Games carry almost the same information as points (correlation 0.95–0.97). They are known for every match, on both tours, in every year. They also exist for held-out matches that only TennisData.app has, from its set-by-set games, which agree with Sackmann in 7,476 of 7,481 linked matches. **That is why games played is the pre-registered workload measure.**

## A5. Recovery time: not feasible for training

| Source | Match days available |
|---|---|
| Sackmann | None. One tournament date per edition |
| TennisData.app | From late 2024 (open main-draw rows: 102 in 2024, 5,232 in 2025, 2,913 in 2026) |
| TML | 2026 files only. Dates are per round, not per match: in 30 of 53 open 2026 knockout editions a single round carries several dates |

No source has match days for 2010–2023, so a model cannot learn a rest-day effect from the training or validation years. Recovery days are **deferred**. Round order is never converted into rest days.

## A6. Can rounds be ordered?

Editions from 2010 to May 2026:

| Structure | ATP | WTA | Treatment |
|---|---:|---:|---|
| Knockout only | 1,019 | 892 | Ordered by round |
| Round robin, then knockout (Tour Finals, ATP Cup, United Cup, Next Gen) | 32 | 27 | Round-robin matches get no round-aware features; knockout matches use the completed round-robin stage |
| Round robin only | 7 | 0 | No round-aware features |
| A round label that can't be ordered (bronze-medal matches at the Olympics and some team events) | 6 | 4 | Whole edition excluded |
| Davis Cup / BJK Cup ties (level D) | 1,187 | 1,606 | Excluded: the rubbers of a tie have no recorded order |

**Byes.** From 2016, Sackmann records 28-player draws as `draw_size` 32, and 56- and 96-player draws as 64 and 128. In 302 ATP editions recorded as 32-draws, the first round has fewer matches than twice the second round. So byes are read from the draw itself: when the first round has fewer than twice as many matches as the second, a player whose first match is in the second round had a bye. A first-round record missing from the data would look like a bye and understate one match of workload. That is rare in Sackmann's main draws, and it is a known limitation.

**A match is not eligible when:**
- it is a round-robin match;
- it is a Davis Cup or BJK Cup tie;
- its edition has an unordered round;
- a player appears twice in one knockout round;
- a player plays on after losing. That happens in team events coded as ordinary events, such as the ATP Cup and United Cup, where a player can lose a rubber and still play the next tie;
- a player's earlier rounds have a gap.

| Tour | Period | Rated matches | Eligible | Main reasons not eligible |
|---|---|---:|---:|---|
| ATP | 2010–15 | 17,125 | 15,106 (88.2%) | team ties 1,811, round robin 144, unordered round 64 |
| ATP | 2016–20 | 12,587 | 11,323 (90.0%) | team ties 988, round robin 98, unordered 92, team event coded A 86 |
| ATP | 2021–23 | 8,366 | 7,549 (90.2%) | team ties 548, round robin 107, team event coded A 98, unordered 64 |
| ATP | 2024–May 2026 | 7,190 | 6,363 (88.5%) | team ties 631, round robin 83, unordered 63, team event coded A 50 |
| WTA | 2010–15 | 16,008 | 14,096 (88.1%) | team ties 1,733, round robin 117, unordered 62 |
| WTA | 2016–20 | 12,149 | 10,676 (87.9%) | team ties 1,310, round robin 79, unordered 62, a player twice in a round 15, gaps 7 |
| WTA | 2021–23 | 7,673 | 6,979 (91.0%) | team ties 543, round robin 90, unordered 60, missing first round 1 |
| WTA | 2024–May 2026 | 6,542 | 6,238 (95.4%) | team ties 149, round robin 42, unordered 62, team event coded A 50, gap 1 |

In 2010–2023, 98–100% of matches in every knockout round are eligible on both tours. R16, QF, SF, and final are each 98.7–99.6%.

## A7. Round-aware values on eligible matches

"After the first round" means at least one player has an earlier match in the edition. These matches are the round-aware sample. In "both with history," both players have one.

| Tour | Period | Eligible | After the first round | Both with history | Games known | Points known | Minutes known | Route known |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ATP | 2010–15 | 15,106 | 8,275 | 6,510 | 100.0% | 99.8% | 91.9% | 99.9% |
| ATP | 2016–20 | 11,323 | 6,187 | 4,849 | 100.0% | 99.9% | 98.9% | 99.8% |
| ATP | 2021–23 | 7,549 | 4,191 | 3,177 | 100.0% | 99.9% | 97.9% | 99.7% |
| ATP | 2024–May 2026 | 6,363 | 3,537 | 2,623 | 100.0% | 97.8% | 95.5% | 99.7% |
| WTA | 2010–15 | 14,096 | 7,324 | 6,426 | 99.5% | 73.0% | 0.0% | 99.9% |
| WTA | 2016–20 | 10,676 | 5,518 | 4,850 | 100.0% | 99.7% | 98.8% | 99.9% |
| WTA | 2021–23 | 6,979 | 3,638 | 3,100 | 100.0% | 98.5% | 97.3% | 99.9% |
| WTA | 2024–May 2026 | 6,238 | 3,422 | 2,632 | 99.9% | 96.5% | 94.0% | 99.7% |

The last four columns are shares of "both with history."

Among those matches:
- 1.6–3.4% involve an earlier walkover, and 8.6–11.2% an earlier retirement.
- 14–19% involve a qualifier or lucky loser. Their qualifying matches are not in the tour-level files, so their workload is **understated**. This is marked, not corrected.
- 11–16% of opponents faced had fewer than 20 rated matches, so their Elo is unreliable.

**The round-aware sample:**
- training years, 2010–2020: 14,462 ATP and 12,842 WTA matches;
- validation, 2021–23: 4,191 ATP and 3,638 WTA.

## A8. Tournament-start workload (previous 14 days)

| Tour | Period | Player-matches | Some match in the window | Games known | Points known | Minutes known |
|---|---|---:|---:|---:|---:|---:|
| ATP | 2010–15 | 34,250 | 55.6% | 100.0% | 96.3% | 92.5% |
| ATP | 2016–20 | 25,174 | 61.0% | 100.0% | 99.4% | 98.6% |
| ATP | 2021–23 | 16,732 | 61.3% | 100.0% | 97.8% | 96.4% |
| WTA | 2010–15 | 32,016 | 62.9% | 99.8% | 82.4% | 37.1% |
| WTA | 2016–20 | 24,298 | 60.2% | 100.0% | 98.6% | 98.0% |
| WTA | 2021–23 | 15,346 | 57.9% | 100.0% | 96.5% | 96.7% |

No match in the window is a genuine zero. This feature counts only tour-level matches, the same limit as Phase 3's inactivity feature. It also uses Phase 3's rule of strictly earlier tournament dates. So when a previous event is still running, its last matches can fall after the target tournament's date: 967 validation matches carry Phase 3's overlap flag. The robustness check repeats every comparison without them.

## A9. What TML and TennisData.app add, 2025 to May 2026 (open rows)

- **Minutes:** on 7,965 TML matches linked to Sackmann, both sources have minutes for 7,125. They are identical in 94.2% and within 5 minutes in 99.6%. TML has minutes for 486 matches where Sackmann has none; Sackmann has 157 that TML lacks.
- **Points:** TML has both serve-point counts for 480 matches where Sackmann has none; Sackmann has 20 that TML lacks.
- **Games:** TennisData.app's set-by-set games equal Sackmann's in 7,476 of 7,481 linked completed matches.

Under the audit's source-precedence rule 1, these TML values fill Sackmann's blanks only. They never replace a Sackmann value, and they are used only when both sources name the same winner.

## A10. The held-out period (metadata only)

**TML candidate rows by round type, aggregate counts:**

| Round type | ATP | WTA |
|---|---:|---:|
| Knockout, first round of its edition | 532 | 547 |
| Knockout, later round | **676** | **660** |
| Round robin | 7 | 0 |
| Davis Cup / BJK Cup ties | 100 | 14 |

- **Sample size:** the round-aware held-out sample is at most about 1,340 TML matches, plus the few TennisData.app-only later-round matches whose editions can be ordered.
- **Inputs:** points will be available for 97–99% after unsealing. Minutes are sealed columns, so their completeness is unknown until the held-out command runs. Games come from TML or TennisData.app scores.
- **Construction:** round-aware held-out features are built **only inside the frozen held-out command**. They use the same edition rules: TML editions start at their earliest date, and round labels give the order. A TennisData.app-only edition with blank rounds cannot be ordered and is excluded.

**What that size can detect:** at about 1,300 matches, the standard error of a nested model comparison is roughly 0.0026 log loss per match. A real but small workload effect will most likely be reported as inconclusive there.

## A11. Feasibility

| Feature | Information set | Feasible? | Notes |
|---|---|---|---|
| Games played in earlier rounds of the same tournament | Round-aware | **Yes — pre-registered (D)** | 99.5–100% known; also available for TennisData.app-only held-out matches |
| Points played in earlier rounds | Round-aware | Yes — diagnostic | WTA 2010–15 73% known |
| Minutes played in earlier rounds | Round-aware | Partly — diagnostic, ATP all years, WTA from 2016 | WTA 2010–15 0% |
| Sets played, number of earlier matches | Round-aware | Yes — diagnostic | |
| Earlier "unusually long" matches (games at or above the training-years 90th percentile for tour and best-of) | Round-aware | Yes — diagnostic | Threshold fixed on 2010–2020 before any outcome is used |
| Mean pre-tournament Elo of opponents beaten, relative to own Elo | Round-aware | **Yes — pre-registered (E)** | Start-of-week ratings only |
| Maximum opponent Elo; number of strong opponents (Elo at or above the training-years 90th percentile) | Round-aware | Yes — diagnostic | |
| Workload × route difficulty | Round-aware | Conditional (F) | Tested only if both D and E are kept |
| Round-aware Elo shift; dominance (share of games won) in earlier rounds | Round-aware | **Yes — round-aware baseline controls** | Not hypotheses: they define the baseline |
| Games played in the 14 days before the tournament | Tournament-start | **Yes — pre-registered (D-ts)** | Tour-level matches only |
| Points or minutes in the 14 days before | Tournament-start | Yes — diagnostic | WTA 2010–15 minutes 37% |
| Recovery days since the previous match | Either | **No — deferred** | No match days before 2025 |
| Workload in qualifying rounds | Either | **No** | Qualifying is not in tour-level files; marked by entry code |
| Difficulty of the draw still ahead | Tournament-start | **No** | Needs the full draw bracket; using who actually advanced would leak results |
| Challenger/ITF workload, travel, scheduling, physiological measures | Either | **No** | Not in these sources |

## A12. Leakage risks and how they are handled

| Risk | Handling |
|---|---|
| A match using its own result or later rounds | Only strictly earlier rounds. Tests: a semifinal's values don't change when its own score changes, and earlier rounds' values don't change when the final's winner is swapped |
| Same-round order or rest days invented | Never inferred. Matches in one round are treated as simultaneous |
| Round robins, team ties, unusual formats | Excluded or marked not eligible (A6). A test covers each case |
| Missing earlier rounds looking like zero workload | Gaps make the match not eligible. Byes are accepted only in draws that have byes |
| Missing measures treated as zero | A sum is unknown if any part is unknown. A walkover is a genuine zero and is counted separately |
| Opponent strength from after the match | Start-of-week canonical Elo only |
| Round-aware Elo leaking into canonical Elo | A temporary copy per edition. A test checks the canonical ratings are identical afterwards |
| A match counted twice across sources | The merge layer links before adding, and stops the build on a duplicate. A test shows a match held by Sackmann and TML contributes workload once |
| Player ids differing across sources | Validated crosswalks. An unlinked player gets a fixed negative provider-only id, distinct by source and tour |
| Held-out outcomes | Sealed rows cannot become match records (a test). Round-aware held-out features are built only inside the frozen command |
| Comparing different information times | Round-aware models are compared only with each other and with the tournament-start model's predictions on the same matches, labeled as different information |
| Previous events still running | The tournament-start window follows Phase 3's rule; robustness repeats every comparison without overlap-flagged matches |
| Reuse of 2021–2023 | Phase 3 already used these years. Hypotheses, features, and order are fixed here, before any Phase 4 validation result exists. Every comparison is counted in the final report |

## A13. Proposed experiment design (for pre-registration; not yet run)

**Tournament-start track (primary).**
- **Order:** families A–C (serve-return, first/second-serve, opponent-adjusted and matchup interactions), as planned.
- **Then D-ts:** log(1 + games played in the 14 days before the tournament), as A minus B. It is added to the selected tournament-start model and judged by the Phase 3 keep rule, unchanged.

**Round-aware track (secondary, its own baseline).**
- **Sample:** eligible matches after the edition's first round (A7). Every model in the track uses exactly these matches.
- **Reference:** the selected tournament-start model's predictions on the same matches, reported and labeled as an earlier information time.
- **R0, the round-aware baseline:** the selected tournament-start features, plus three controls:
  - the round-aware Elo shift and the round-aware surface-Elo shift (each A minus B, on the log-odds scale);
  - dominance: share of games won in earlier rounds minus 0.5, A minus B, 0 when a player has no earlier games.

  R0 against the reference is reported. It is the value of knowing the earlier results, and it is not counted as a workload finding.
- **D:** R0 + log(1 + games played in earlier rounds), A minus B, plus a missing indicator. Keep rule against R0.
- **E:** R0 + route difficulty: mean(opponent start-of-week Elo − own) × ln 10 / 400, A minus B, 0 when no opponent was played. Keep rule against R0, **independently of D**.
- **D + E:** fitted only if both pass, and kept only if it passes the keep rule against the better of the two.
- **F (conditional):** only if D and E are both kept. It adds one antisymmetric interaction, workload_A × route_A − workload_B × route_B. Keep rule against R0 + D + E.

That is at most five validation comparisons in the round-aware track, four of them keep-rule decisions. LightGBM is not used in this track.

**How every comparison is run:**
- **Fitting:** each tour separately, logistic regression with no intercept, and features divided by their root-mean-square on the fitting rows.
- **Regularization:** L2 chosen by the same inner split for the baseline and the augmented model (fit 2010–2017, score 2018–2020). The two cross-L2 sensitivity checks from the plan are applied to every gain.
- **Metrics:** log loss (primary), Brier score, accuracy, and paired log-loss differences with standard errors clustered by tournament date, plus a sensitivity check clustered by month.
- **Breakdowns:** by tour, by round (R32 to final), by best-of, and for Grand Slams.
- **Robustness:** without overlap-flagged matches, and without matches involving qualifiers or lucky losers.
- **Diagnostics only, never selection:** the points and minutes variants, the long-match and strong-opponent counts, and maximum opponent Elo.

**Final refit and held-out scoring:**
- **Refit:** every selected model and every baseline is refit on all eligible matches from 2010 to the week of 25 May 2026, with its development L2 held fixed.
- **Held-out scoring:** both tracks are scored once, on identical matches within each track, inside the one-time held-out command.
- **Retrospective:** 2024–May 2026 is reported only after the freeze, labeled retrospective.

## A14. What this changes in the Phase 4 protocol

- **Two tracks.** The protocol now defines two tracks, two baselines, the round-aware sample rule, and the order of tests above. Tournament-start results stay the primary claim.
- **Held-out reporting.** The held-out command reports both tracks. The round-aware track is expected to be underpowered there (about 1,300 matches).
- **Frozen before unsealing.** The edition, chronology, and bye rules, the plausibility thresholds, and the source-precedence rules are recorded in the protocol before any held-out outcome is opened.
- **Deferred.** Recovery days, qualifying workload, and draw-ahead difficulty are deferred and named as limits in the Matchup Intelligence Report.

## A15. Files and reproduction

| File | What it does |
|---|---|
| `matchup_dna/workload.py` | Reads Sackmann with minutes, draw size, and entry codes. Workload of one match. Plausibility rules. Tournament-start 14-day window |
| `matchup_dna/round_aware.py` | Round order, edition checks, byes from the draw structure, player chronology, earlier-round workload, dominance, route difficulty, the separate round-aware Elo, and the pre-registered A-minus-B differences |
| `matchup_dna/merge.py` | Source precedence, backfill without overwriting Sackmann, id reconciliation, provider-only ids, refusal of sealed rows, and the duplicate check |
| `matchup_dna/audit_workload.py` | This audit (coverage and structure only) |
| `tests/test_workload.py` | Scores, match tiebreaks, retirements, walkovers as genuine zeros, missing values staying missing, plausibility flags, and the strictly-earlier 14-day window |
| `tests/test_round_aware.py` | A semifinal never uses its own result. A final uses every earlier round. Later results never change earlier features. Missing minutes stay missing. Walkovers add no court time. Gaps, missing first rounds, byes, team ties, bronze-medal rounds, a player twice in a round, and round robins. Canonical Elo untouched. Each earlier match moves the temporary rating once. Swapping players negates every difference. Start-of-week route ratings. A match in two sources counted once. Cross-source duplicates stop the build. Ids reconciled. Sealed rows refused |

```powershell
python -m matchup_dna.audit_workload
python -m unittest tests.test_workload tests.test_round_aware
```

The audit takes about 80 seconds and writes `results/phase4/audit/workload_audit.txt`, with every number in this addendum, plus a manifest.

## A16. Erratum 1: what the audit missed in the held-out data, and the checks that now prevent it

*Added 5 November 2026, after the held-out evaluation. This is a post-unblinding data-integrity correction. The audit above is unchanged; this addendum records where it was wrong. The full correction and its results are in the Matchup Intelligence Report ("Erratum 1") and in `experiments/phase4_erratum_1.json`.*

### What was wrong

The held-out evaluation counted **65 rated matches twice**. There were 68 duplicate rows in all: 3 more were walkovers or canceled matches that rate nothing. Some players also had the wrong identity or two identities. Each duplicate came from TML and TennisData.app spelling a player's name differently:

| TennisData.app | TML | Duplicated matches | How the original build resolved them |
|---|---|---:|---|
| "Vallejo D." (424916) | "Adolfo Daniel Vallejo" (ATP code V0DP) | 23 | TennisData.app copy → Sackmann 118808, **a different player**: Daniel Vallejo, MEX, born 1984. TML copy → 209226, Adolfo Daniel Vallejo, PAR, born 2004 |
| "Merida Aguilar D." (122001) | "Daniel Merida" (M0N7) | 21 | TennisData.app copy → 210017 (correct). TML copy → a new, history-less id, also used in his 22 TML-only matches |
| "Ruse G." (275310) | "Elena Gabriela Ruse" (211817) | 19 | TennisData.app copy → a new id. TML copy → 211817 (correct) |
| "Bassols M.", "Damas M.", "Feldbausch K.", "Choi W. F.", "Tam Sin Hang", "Wu Tung-Lin", "Dahlin M." | full names | 1–2 each | two different ids, at least one of them new |

**Why "Vallejo D." went to the wrong player.** The TennisData.app crosswalk was validated through matches, but its key is surname plus first initial. "Vallejo D." matches only Sackmann 118808 ("Daniel Vallejo"), whose key is "vallejo d". Sackmann itself files Paraguay's 2023–2026 Davis Cup matches under 118808, and those matches validated the link.

Match evidence that does not use names points the other way. In the player's own matches, the Sackmann player opposite a linked opponent, in the same round and dates, is 209226 in 9 matches and 118808 in none, once team-tie rubbers are excluded. It is the only crosswalk entry so contradicted (`phase4_correction diagnose`).

### The three audit failures

1. **Unlinked TennisData.app rows were treated as genuine TML absences.** Part 3 counted 224 held-out rows with "no TML row" and read them as Davis Cup ties and thin coverage. Nothing checked whether a row really had no counterpart, or had one under a different spelling. Linking needed matching surname-and-initial keys for both players, or both players in both crosswalks. "Merida Aguilar D.", "Ruse G.", "Vallejo D." and "Tam Sin Hang" fail both.
2. **Duplicates were checked on source-specific keys, not on real matches.** Rule 6, "the build stops if a match key appears twice", compared keys that differ by construction across sources. The last cross-source guard compared resolved player ids, and those had been resolved differently on the two sides. A test that every match updates Elo once could never see a match stored twice under two keys.
3. **Split TML identities were assumed to be resolved through Sackmann.** Rule 4 said the WTA players with two TML ids "are resolved through Sackmann, so each counts once". Four of five are, because both TML ids carry the full name of one Sackmann player. **Xinran Sun is not:** she has no Sackmann record, so each of her TML ids became a separate new player. The same assumption also missed TML ids with spelling variants: "Aleksandr Shevchenko" against Sackmann's "Alexander", "Abdullah Shelbayh" against "Abedallah", and "Daniel Merida" against "Daniel Merida Aguilar". Those players restarted with no history.

### The checks that now prevent them

The assembly gained a version 2 (`heldout.assemble`). Version 1 is kept so the original evaluation can be reproduced.

| Failure | Check now in place |
|---|---|
| 1 | A third linking pass needs the same tour, the same round (TennisData.app's blank team-event round fits any), the day window and the same tournament edition, with both players name-compatible: a shared surname token, and every initial starting a given name. It never uses results. A row that fits more than one TML match is left out and listed, never merged. |
| 2 | The build stops if any TennisData.app addition is still name-compatible with, or holds the same canonical pair as, a TML match in the same round, window and edition. An independent reconciliation (`phase4_correction reconcile`) uses only canonical ids, dates, rounds and plain surname tokens. It flags a player in two tournaments within 3 days, a player twice in one round, one id carrying unrelated names, one full name split across ids, and overlap with Sackmann's last weeks. It also checks that every TennisData.app row is accounted for exactly once. On the original build it flags all 68 duplicates and the Xinran Sun split. On the corrected build it flags only 3 genuine additions TML lacks: the London R32 Tatjana Maria d. Maria Sakkari, and a Singapore semifinal walkover that is unrated. |
| 3 | Player identity comes from the matches themselves. TennisData.app and TML ids joined by linked matches are one person only if every TML record carries the same full name, every TennisData.app name fits it, and their crosswalk entries agree. Otherwise nothing is merged and the case is listed. A TML player resolves by the TML crosswalk, then a unique exact full name, then the validated crosswalk entry of the linked TennisData.app id. A TennisData.app player resolves to the same id as its TML person. Where the TennisData.app crosswalk disagrees, as for Vallejo, the TML identity is used and the conflict is listed. The unverified surname-and-initial guess is gone: an unresolved player gets a provider-only id and is listed. |

Every case left for review is in `results/phase4/correction/review_players.csv`:
- 5 TML double ids resolved together;
- 3 resolved through the TennisData.app crosswalk (Merida, Shevchenko, Shelbayh);
- 3 TennisData.app-only Davis Cup players with no verifiable identity;
- 1 group not merged because the names disagree: "Amariei I. D." and "Ilinca Amariei".

No possible duplicate was left unresolved. `tests/test_heldout.py` covers every case named here. One of its tests runs on the real files, using only the sealed (outcome-free) rows, and confirms all 68 duplicates now link to their TML rows.

### Elsewhere

- **The January–May 2026 rehearsal** (outcome-free, before the freeze) used the same assembly. It had 41 such duplicates. It was a qualitative fidelity check and is not rerun.
- **Phase 1–4 training, validation and retrospective data** (Sackmann, single source) has no repeat of the same pair and round in two tournaments within three days from 2010 on. All 237 such repeats are in pre-2010 history, which only warms up the ratings; examples start in 1968. Sackmann does file some Davis Cup matches under a second id for one person: Adolfo Daniel Vallejo under 118808, and Menelaos Efstathiou under both 144949 and 213713. Those datasets are frozen and left unchanged; the effect is confined to a few Davis Cup rubbers.
- **The TML statistics backfill** before June 2026 links both players' full names and requires the same winner (one link with different winners was not used), so it cannot duplicate a match.

```powershell
python -m matchup_dna.phase4_correction diagnose    # results/phase4/correction/diagnostics.txt, duplicates.csv, ...
python -m matchup_dna.phase4_correction reconcile   # results/phase4/correction/reconciliation.txt
python -m unittest tests.test_heldout
```
