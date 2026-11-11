# Matchup DNA — ITF Extension: Data Audit and Plan (Stage I1)

**Date:** 10 November 2026  
**Sources:** Jeff Sackmann's ITF, Challenger/qualifying and main-tour files (the Phase 0 archival mirror, snapshot to early June 2026), plus checks of every live source that could supply ITF matches.  
**Question:** Is there enough clean ITF data to build and test an ITF forecasting model, including serve statistics, and is there a source that can keep it running live?  
**Answer:** Yes for the model, no for live data yet.

- About 180,000 ITF main-draw matches from 2021 to June 2026 can be used, with full serve statistics from January 2025.
- The main-tour model cannot simply be reused. 96% of men's ITF matches involve a player with no main-tour history at all, so ITF needs its own ratings across every level.
- There is no free, permitted live ITF source today. The ITF site blocks automated access, and the sites that list ITF matches forbid scraping. The one candidate is a free API plan the user would have to sign up for.

The rest of this report covers the splits, what the audit found, the live-source search, and the plan for stages I2–I6. The last section, "What the audit did," says it in ordinary language.

## 1. The splits, and the seal

The splits were fixed before any model work, so the final test runs on matches already in the files and never waits for new ones. They live in `experiments/itf_splits.json`, written by `matchup_dna/itf_splits.py`.

| Split | Dates (by the edition's `tourney_date`) | Men's matches | Women's matches | Role |
|---|---|---:|---:|---|
| Burn-in | before 2021 | 433,357 | 310,641 | Ratings warm up; never scored |
| Development | 1 Jan 2021 – 30 Jun 2025 | 72,824 | 73,673 | Building models |
| Validation | 1 Jul – 31 Dec 2025 | 9,270 | 9,265 | Choosing between a few named candidates |
| **Held-out test** | 1 Jan – 1 Jun 2026 (end of data) | **6,894** | **7,224** | Scored once, after the protocol is frozen |

**Scope.** Only ITF main-draw singles are scored:
- men: levels M15 and M25 (and "S", the men's ITF code up to 2019);
- women: W10 to W100.

WTA 125 events and every qualifying round are left out. Women's ITF qualifying coverage falls from about 20,000 rows in 2024 to about 2,300 in 2025, so scoring it would change the population between splits. These matches still feed the ratings as history.

**The seal.** Until a frozen ITF protocol naming this split record is committed, the reader (`itf_splits.rows`) drops every row dated 2026 or later from every file: ITF, Challenger, main tour and rankings. The audit refuses to run if a sealed row gets through. The record also stores the SHA-256 of all 299 input files, and `python -m matchup_dna.itf_splits check` fails if any file changes.

**Revisions.** The record lists both corrections, each with the fingerprint of the file it replaced:

| Revision | What changed |
|---|---|
| 1 | Splits first fixed: development 2021–2023, validation 2024, test 2025 to June 2026 |
| 2 | **Defect fixed.** Revision 1 treated any round starting with "Q" as qualifying, so every quarterfinal ("QF") was left out. Qualifying is now Q followed by a digit. Dates unchanged |
| 3 | **Dates moved, at the user's decision.** ITF serve statistics only exist from 2025, which revisions 1–2 held out entirely. Moving the boundaries lets serve features be built and judged before the test |

**What had been seen before the record.** No 2025 or 2026 ITF winner, score or statistic had been looked at when the dates were chosen. Earlier phases saw main-tour results from 2026, Phase 5 compared the model with the market on a few hundred WTA W35/W50 matches in aggregate, and Phases 0 and 5 summarised ITF odds coverage. For 2026 ITF rows, only counts by level and round, and how many carry statistics and ranks, have been read.

## 2. What the data holds

### Size and shape

| | Men | Women |
|---|---:|---:|
| Scope matches, development | 72,824 | 73,673 |
| of which rated (completed, best of 3) | 95.6% | 96.0% |
| ITF players 2021–2025 | 5,570 | 8,518 |
| of whom ever played a main-tour match | 772 (13.9%) | 973 (11.4%) |

- **Format.** Every match is best of three; almost every draw has 32 players (some women's events have 48). Surfaces are split between hard (about 50%) and clay (about 48%), with a little carpet and grass. No match is missing its surface.
- **Integrity of the rows.** No duplicate match keys, no player missing from the players file, and no scope match that also appears in another file. Two women's rows from 2015–2020 have the same player on both sides; the rating rules already skip them.

### Serve statistics

| Period | Men with full serve counts | Women |
|---|---:|---:|
| 2015–2020 | 0% | 0% |
| Development (2021 – Jun 2025) | 11.5% (all from Jan–Jun 2025) | 11.4% |
| Validation (Jul–Dec 2025) | 97.3% | 98.2% |

Serve counts start in January 2025. That matches the date the ITF switched data partner (Infront replaced Sportradar) and brought in new handheld scoring devices; the files don't say why. Fewer than 0.5% of rows with counts fail the consistency checks (for example, more first serves won than first serves in). Those rows will be treated as missing.

So serve features can be built from January 2025 on, judged on the second half of 2025, and tested on 2026. That is the reason for revision 3.

### Unmarked retirements (new finding)

From 2025, many retirements are recorded as finished matches with a partial score, such as "6-2 0-0" or "6-1 3-0", without the "RET" marker earlier years use.

| Half-year | Men: marked retirements | Men: "finished" but winner did not win 2 sets | Women: marked | Women: unmarked |
|---|---:|---:|---:|---:|
| 2024 H2 | 4.1% | 4 | 3.5% | 0 |
| 2025 H1 | 2.9% | 122 | 2.9% | 86 |
| 2025 H2 | 1.5% | 323 | 1.4% | 300 |

Counted together, the 2025 retirement rate is back to the usual 4–5%. **Rule for I2:** a "completed" match in which the winner has not won a majority of sets is treated as a retirement, so it doesn't move the ratings. Sackmann's main-tour 2025 files do not have this problem (20 such men's rows in 2025, against 25 in 2024).

### Rankings

| | Both ranked | One ranked | Neither |
|---|---:|---:|---:|
| Men, development | 79.9% | 18.5% | 1.7% |
| Women, development | 73.8% | 22.3% | 3.9% |

Missing ranks are common. A missing rank is a real signal, not just a gap: an unranked player usually loses to a ranked one (next table).

### How predictable ITF matches are (development only)

How often the better-ranked player won, among rated matches:

| Level | Both ranked: better-ranked won | One ranked: ranked player won |
|---|---:|---:|
| M15 | 65.5% (33,272) | 76.7% (8,792) |
| M25 | 68.0% (22,209) | 81.4% (4,192) |
| W15 | 63.8% (17,218) | 71.4% (11,285) |
| W25 / W35 | 64.2% / 64.2% | 78.1% / 78.3% |
| W40 / W50 | 65.1% / 64.2% | 84.2% / 80.1% |
| W60 / W75 / W80 | 63.7% / 61.5% / 67.0% | 68.9% / 72.4% / 83.3% |
| W100 | 63.0% (2,202) | 66.3% (92) |

That's close to main-tour predictability. A rank-only model is the baseline every candidate must beat.

### Why the main-tour model can't be reused

The lower-experience player in each development match had this much prior rated history:

| History counted | Men: none | Men: 1–9 | Men: 10+ | Women: none | Women: 1–9 | Women: 10+ |
|---|---:|---:|---:|---:|---:|---:|
| Main tour only (what P1's ratings see) | 95.5% | 4.3% | 0.1% | 81.7% | 14.2% | 4.1% |
| Every level | 4.8% | 18.8% | 76.3% | 1.8% | 8.0% | 90.2% |

The main-tour ratings know almost none of these players. One rating pool across every level (ITF, Challenger, qualifying, WTA 125, main tour) knows most of them. Women's history is deeper because Sackmann's women's ITF file also carries ITF qualifying.

### The women's level renaming

The ITF renamed the women's levels in 2024. Median ranks of first-round entrants show how the old and new levels line up:

| Tier | Before 2024 | Median entrant rank | From 2024 | Median entrant rank |
|---|---|---:|---|---:|
| 1 | W15 (and W10) | 946 (2023) | W15 | 903–919 |
| 2 | W25 | 516 | W35 | 546–549 |
| 3 | W40 | 387 | W50 | 431–451 |
| 4 | W60, W80 | 345–355 | W75 | 306–323 |
| 5 | W100 | 231 | W100 | 234–272 |

The model will use these five tiers rather than the raw codes. Men's levels need no mapping: M15 (median entrant rank about 1,000) and M25 (about 780).

## 3. Live sources

| Source | ITF fixtures and results | Serve stats | Can it be used? |
|---|---|---|---|
| ITF site (itftennis.com, now world.tennis; also live, feeds and player portal) | Yes | Yes | **No.** Every address, even robots.txt, returns an Imperva bot-protection challenge. Getting past it would mean defeating bot protection, which this project doesn't do |
| ESPN (current live source) | **No.** Its archive holds only ATP and WTA main-tour events and about 40 WTA 125s | – | – |
| Sackmann (GitHub) | Up to June 2026 | From 2025 | **No updates.** `tennis_atp` and `tennis_wta` are no longer public; only the Match Charting Project is |
| Match Charting Project | – | 5 men's and 87 women's ITF matches in 2021–2024 | Too few to matter |
| TennisIsMyLife (on disk) | No | – | Main tour only |
| TennisExplorer | Yes | Some | **No.** Its terms forbid scraping and database extraction without written consent |
| tennislive.net | Yes | – | **No.** Its robots.txt blocks its match API and Anthropic's crawler |
| Flashscore, Sofascore and the Apify scrapers built on them | Yes | Some | **No**, without the sites' permission |
| Free API plans: Tennis API (RapidAPI), Matchstat, Live Tennis API | Claimed | Unverified | **Possibly.** The user creates a free key; then test ITF start times, serve counts and the daily request budget |

The user has ruled out paying and asking the ITF. That leaves the free API plans. A free tier of about 100 requests a day can probably cover a day's ITF fixtures and results. It likely cannot fetch serve counts match by match, since there are several hundred ITF matches on a busy day.

**If no free plan works**, the ITF model and its one-time test still go ahead (stages I2–I3). The website gets an ITF research section, but no live ITF forecasts.

**Integrity.** The 2018 Independent Review of Integrity in Tennis found match-fixing concentrated at the lowest professional levels. Any ITF forecasts on the site will be labelled as model estimates, and ITF matches won't be compared with betting odds.

## 4. The plan

| Stage | Work | Needs a live source? |
|---|---|---|
| **I1** (this report) | Splits, audit, plan | No |
| **I2. Data, ratings and features** | Sealed loader for every file, with the unmarked-retirement rule. One Elo pool across all levels. Phase 3 features plus level tier and unranked flags. Serve-return profiles from January 2025 | No |
| **I3. Experiments and the one-time test** | Develop, choose on validation, freeze, then score 2026 once | No |
| I4. Live source | Reader and archive for the chosen API, like `espn.py` | Yes |
| I5. Protocol P2 and the cloud job | A separate frozen prospective protocol. **P1 is never touched**: its amendments must keep eligibility unchanged, so ITF can't join it | Yes |
| I6. Website | An ITF section with its own track record | Partly |

### What I3 will compare

**Baselines:**
- B0, a rank-only logistic model (log rank ratio plus unranked flags);
- B1, all-level Elo on its own;
- B2, the frozen Phase 4 tournament-start model applied unchanged. This tests transfer; it's expected to do poorly.

**Candidates:**
- M1, the Phase 3 feature set rebuilt on all-level ratings, plus level tier and unranked flags, fitted on development;
- M2, M1 plus the Phase 4 serve-return profile from January 2025 statistics.

**Rules declared now:**
- **Elo settings.** A small set is tried on development: Phase 2's settings, a decaying K, and a first rating set from the player's first rank. The best by log loss is kept.
- **Choosing M1 or M2.** Validation decides, by log loss with a paired bootstrap by edition. M2 is chosen only if the 95% interval of its improvement excludes zero.
- **The test.** Run once, on 2026, against B0 and B1. Results are reported by tour and level, with calibration.

### Gates (the user approves each)

1. This plan and the file skeleton below.
2. The Elo settings and the M1/M2 choice, before the protocol is frozen.
3. The one-time held-out run.
4. Anything live (I4–I6).

### Proposed skeleton (committed empty before I2, as in earlier phases)

- `matchup_dna/itf_data.py`: sealed loading of every file, the outcome rule, level tiers;
- `matchup_dna/itf_ratings.py`: the all-level Elo replay and its variants (Phase 2's `run_elo`, unchanged);
- `matchup_dna/itf_features.py`: feature rows (Phase 3's builder and Phase 4's serve engine, imported unchanged);
- `matchup_dna/itf_model.py` and `matchup_dna/itf_experiment.py`: fitting, validation, freeze, the held-out run;
- `tests/test_itf_data.py`, `tests/test_itf_ratings.py`, `tests/test_itf_features.py`, `tests/test_itf_experiment.py`;
- `docs/ITF - Model Report.md`.

No locked file changes. The Phase 3 and 4 modules are imported, never edited, and nothing in P1, the cloud job or the website changes before I4.

## 5. Reproducing this audit

```powershell
python -m matchup_dna.itf_splits check     # inputs and split counts match the record
python -m matchup_dna.audit_itf            # writes results/itf/audit.json (about 2 minutes)
python -m unittest discover -s tests -p "test_itf_splits.py"
```

`results/` is not in git. The audit reads only through the seal, so running it again cannot reveal 2026 results.

## What the audit did

The work so far builds a test the ITF model can't cheat on, then checks the data is fit for it. The last five months of data, January to June 2026, are locked away. No program can read them until the model is finished and frozen, and a file fingerprint shows if anyone changes the data.

The data is good:
- about 180,000 ITF matches, with no duplicates or missing players;
- full serve statistics from 2025 on.

Two things needed fixing:
- **Unmarked retirements.** From 2025, many retirements are written as if the match finished, so a rule now catches them.
- **Renamed levels.** The women's levels were renamed in 2024, so old and new names are matched by how strong their fields are.

The main finding: the existing model can't simply be pointed at ITF matches, because it has never seen almost any of these players. ITF needs ratings built across every level.

Live ITF matches are the open problem. Every site that lists them either blocks automated access or forbids scraping, so live forecasts depend on a free API plan that hasn't been tested yet.
