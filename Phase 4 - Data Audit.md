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
