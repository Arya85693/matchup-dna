# Matchup DNA — ITF Extension: Live Forecasting Report (Stages I4–I6)

**Date:** 11 November 2026  
**Status:** built and tested, with a local pilot run. The live record starts when the prospective protocol P2 is frozen and committed (section 6). Until then the cloud job does not run ITF forecasts.  
**Question:** Can the tested ITF model forecast live, on the website, under its own frozen protocol, without touching the main-tour system?  
**Answer:** Yes.

- **Live data:** Flashscore supplies men's and women's ITF fixtures and results with exact start times. TennisExplorer supplies the weekly ATP and WTA rankings.
- **Rating history:** a backfill brought the rating history from June 2026 to now.
- **Players:** Flashscore players are matched to Sackmann's with no winner disagreement in 1,430 overlapping matches.
- **Live model:** M1, the ITF model without serve statistics.
- **Website:** a new ITF section, an ITF players board, and ITF entries wherever the main-tour models appear.

## 1. The live model is M1

M2 (M1 plus serve and return) tested 0.0011 better on the held-out half-year. But ITF serve statistics are no longer published after June 2026: Sackmann's data ends there, and Flashscore's ITF matches carry only "last 10 points" and "match points saved". This was checked on 11 November on finished M15 and W35 matches.

Without new serve counts, M2's inputs would stop following form and drift toward the ITF average. It would also treat every player who began after June as having no serve history. M1 needs only results and rankings, so it stays current. It is the model P2 registers: `models/itf_m1.json`, refitted once on every ITF match before June 2026. A refit reproduces the file byte for byte (`python -m matchup_dna.itf_live model check`).

An **Elo-only forecast** (`itf-elo-v1`) is stored beside each M1 forecast, so the live record also measures what M1 adds over the ratings alone.

## 2. The live sources (stage I4)

### Flashscore: fixtures and results (`matchup_dna/itf_flashscore.py`)

An event page (`/tennis/itf-men-singles/<event>/results/`, likewise for women) carries its matches in the page itself. One request gives the event's finished and upcoming main-draw matches. Each match has:
- a Flashscore match id and a start time as a UTC timestamp;
- the status: scheduled, live, or finished (with a detail code: 3 completed, 8 retired, 9 walkover);
- the round ("1/16-finals" … "Final");
- for each player: a short name, a Flashscore player id, a name slug ("dlimi-yassine") and the country;
- the games and tiebreak points per set, and the winner.

Each event's header gives its level, country and surface: "ITF MEN - SINGLES: M15 Antalya 7 (Turkey), clay". Qualifying, doubles and team events are not read.

- **Outcomes:** a finished match whose winner did not win a majority of finished sets is a retirement. This is the I1 rule, so a partial score never counts as a win.
- **Archive:** every page is kept in `data/raw/flashscore/`, as the match data plus the URL, retrieval time and the SHA-256 of the whole page.
- **Requests:** one a second, compressed, with an identifying User-Agent.

The reader also covers Challenger, ATP, WTA and WTA 125 events. The ITF ratings are all-level, so those results are rating history; they are never forecast.

### TennisExplorer: weekly rankings (`matchup_dna/itf_rankings.py`)

The full ATP and WTA singles lists for each week, 50 players a page (about 2,250–2,300 men and 1,550–1,580 women per list), archived in `data/raw/tennisexplorer/rankings/`. A forecast uses the latest list published on or before both the edition's start and the day of issue, and at most 21 days old. So it uses the rank as it stood before the match, as in training.

Ranks are matched by name first. The two sites write some countries differently, so the country only separates namesakes:

| Flashscore | TennisExplorer |
|---|---|
| World (neutral athletes) | Russia |
| United Kingdom | Great Britain |
| Taiwan | Chinese Taipei |

A unique longer form of a name is also accepted when the country agrees ("makhlouf-nazim" and "Makhlouf Mohamed Nazim"). This raised rank coverage in the pilot from 70% to 79% of player slots. The rest are mostly players with no ranking.

### The backfill

Sackmann's data ends on 1 June 2026, so the ratings needed the five months since. Every event in Flashscore's sitemap was read once: about 1,380 men's and 1,790 women's ITF events, plus the Challenger, ATP, WTA and WTA 125 events. That is 3,978 pages and 27,204 matches dated 25 May to 13 November 2026. The weekly rankings since 25 May were read too: 20 men's lists and 19 women's.

Finished matches per month:

| | Jun | Jul | Aug | Sep | Oct |
|---|---:|---:|---:|---:|---:|
| ITF Men | 1,931 | 2,235 | 1,788 | 1,872 | 1,866 |
| ITF Women | 2,036 | 2,026 | 1,316 | 1,563 | 2,118 |
| ATP Challenger | 388 | 350 | 440 | 385 | 381 |
| ATP | 242 | 252 | 287 | 147 | 289 |
| WTA | 249 | 238 | 267 | 216 | 248 |
| WTA 125 | 217 | 275 | 66 | 323 | 230 |

ITF volume is in line with Sackmann's 2025 rate (about 1,550 rated main-draw matches a month per tour).

### Player matching (`matchup_dna/itf_identity.py`)

- **Matching names:** a Flashscore player is matched to a Sackmann player by name, compared as a set of tokens without accents or order. So "dlimi-yassine" matches "Yassine Dlimi".
- **Namesakes:** when two Sackmann players share a name, the country decides. The mapping from country names to Sackmann's codes is learned from players whose names match uniquely, not typed by hand. "World" carries no country information, since Flashscore uses it for both Russian and Belarusian neutral athletes.
- **New players:** a player with no Sackmann namesake is a new player, with a stable negative id derived from their Flashscore id.
- **Not forecast:** a match with a player whose identity is ambiguous or conflicting is not forecast, and that player's results are left out of the history.

| | Men | Women |
|---|---:|---:|
| Flashscore players | 2,901 | 2,351 |
| Matched to Sackmann | 82.4% | 84.3% |
| New players | 15.0% | 11.8% |
| Ambiguous or conflicting | 2.6% | 3.9% |
| Sackmann ITF matches in the overlap weeks (25 May, 1 June) also found on Flashscore | 746 of 854 | 684 of 798 |
| ... with the same winner | **746 of 746** | **684 of 684** |

## 3. The live pipeline (stage I5, `matchup_dna/itf_live.py`)

A run does seven things:

1. **Fetches:** this week's events in every category read, plus the new weekly ranking lists.
2. **Builds the history:** every Sackmann match to 1 June 2026, then every finished Flashscore match after it, both players resolved. A Flashscore match with the same players and round as a Sackmann match within 14 days is the same match and is not added twice.
3. **Places each upcoming ITF main-draw match into the replay as a placeholder that moves nothing.** A placeholder causes no rating change and adds no rest or form, so it can never affect another forecast; a test checks this. It is dated by its edition's Monday, so its ratings are start-of-week and its history ends before the edition, as for every training row.
4. **Forecasts:** M1 and Elo-only forecasts are stored for every eligible match.
   - *Eligible:* both players resolved, a known start time, and the run at least 5 minutes before it.
   - *Not eligible:* "too_late" or "identity …", recorded with the reason.
5. **Settles:** results are added to every stored match that has finished.
6. **Verifies and exports:** the store's chain is checked and the ledger written.
7. **Writes the ITF players board** (display only).

**Store and ledger.** Forecasts go to `data/store/itf.sqlite`, through the main-tour store's code unchanged:
- forecasts cannot be edited;
- each one is chained by hash;
- a re-run with the same inputs writes nothing new;
- the chain is exported to `forecasts/itf_ledger.jsonl`.

The P1 store, ledger and code are untouched.

**The pilot run.** On 11 November, a local run (not fetching again; separate store, never committed) gave:
- **Forecasts:** 238 issued, 129 men's and 109 women's.
- **Not forecast:** 65 had already started and 18 had an ambiguous or conflicting player.
- **History:** 12,454 men's and 10,727 women's results added since June. 1,889 were skipped as already in Sackmann, and 1,763 for an unresolved player.
- **Board:** 500 men and 500 women. 97% and 95% of them have a rank.
- **Integrity:** the store verifies cleanly, and the run took under two minutes.

The probabilities were checked by hand. Strong favourites came out at 70–80%, and M1 averaged 5.7 percentage points from the Elo-only forecast.

## 4. The cloud job

`.github/workflows/forecast.yml` gains one step, on the live slot only:

| What | How |
|---|---|
| Before P2 exists | The step does nothing |
| After P2 is committed | About every hour (`scripts/cloud/itf_due.py`: due when no ITF run started in the last 50 minutes), pull the ITF store from the state bucket, run, push it back. The pace is the workflow's choice and is not part of the frozen P2 code |
| ITF archive | The Flashscore pages, rankings and board are their own archive (`itfraw`): unpacked at the start of every run, saved after each ITF run. The main-tour archive is never involved |
| Ledger | The bot also commits `forecasts/itf_ledger.jsonl` |
| Isolation | Marked to continue on failure, so an ITF problem never stops the main-tour forecasts, the publish or the ledger commit. The publisher also leaves the ITF files out of a snapshot, with a warning, if building them fails, so the main-tour pages are always published |
| ITF players | A separate daily workflow (`.github/workflows/itf-players.yml`, 13:20 UTC) builds the ITF board's profiles. It never opens a forecast store and has its own concurrency group, so it never waits for, or holds up, the forecasting job |

The cloud already holds Sackmann's ITF files (the static data archive packs all of `data/atp` and `data/wta`). The backfilled Flashscore and ranking pages exist only on the laptop until they are uploaded as the `itfraw` archive (section 6).

## 5. The website (stage I6)

**Labels.** Every match names its circuit, by one rule (`lib/format.ts`):
- main tour: **ATP · Grand Slam**, **WTA · 1000**, **ATP · 250/500**, **WTA · 250**;
- second level: **ATP Challenger**, **WTA 125**;
- ITF: **ITF Men · M15 …**, **ITF Women · W35 …**.

Before, a main-tour event showed only its level ("Grand Slam"), so men's and women's draws looked alike.

| Page | What changed |
|---|---|
| ITF (new, `/itf`) | Upcoming forecasts with the Elo-only figure beside each, recent results, the live record (M1 against Elo only), and the frozen test results |
| Matches | **Main tour \| ITF** switch. The ITF view is the main-tour match board itself, with **ITF Men** and **ITF Women** in place of ATP and WTA, and every ITF match has a full match page (section 5.1) |
| Players | **Main tour \| ITF** boards, the same table on both: sortable Elo, surface Elo, season record, 90-day change and trend, with search and filters. Every ITF player has a profile and can be compared (section 5.1) |
| Forecast Archive | **Main tour \| ITF**: the main-tour archive itself, with every ITF forecast, its result, whether it was counted, and its chain hash |
| Model Lab | New **ITF model** tab: live P2 record, held-out and validation results for all five models, gains with intervals, why M1 and not M2, calibration, frozen weights and the model's fingerprint. The Calibration tab adds the ITF held-out series, and a live ITF series once 30 results are scored |
| Methodology | "Three models", a section on the ITF model, new data sources and limits |
| Home | A card for the ITF section |

The publisher builds `itf.json` from a read-only copy of the ITF store, as it does for the main store. It skips the file while an ITF run is writing.

Forecasts issued before P2 is frozen are shown as a pilot and never scored.

### 5.1 The same pages as the main tour

The ITF tabs use the main-tour components, not a separate design. The ITF pages show initials in place of player photos.

| Page | Built from |
|---|---|
| Match board (`/matches`, ITF tab, and `/itf`) | `itf/matches.json`, in the main-tour match index format |
| Match page (`/matches/I-…`) | `itf/match-pages.json`: every forecast version, its log-odds contributions, the decision timeline, results and integrity hashes. The contributions are rebuilt from each forecast's stored inputs and the frozen `models/itf_m1.json`, and must give back the stored probability to within 1e-9, or the file is not built. ITF has no round-aware model, and the page says so |
| Forecast Archive (ITF tab) | `itf/archive.json`, in the main-tour archive format |
| Players (ITF tab), profiles (`/players/itf/atp-…`), Compare (`/players/itf/compare`) | `web/publisher/itf_players.py`, in the main-tour profile format, in a separate `itf-history` area of the site's storage |

**How the ITF profiles are built:**
- **History:** the history each ITF run reads: Sackmann's files at every level, plus finished Flashscore matches with both players resolved.
- **Ratings:** the ITF model's Elo, one pool across every level, with K = 250 / (matches + 5)^0.4. Surface Elo is blended half and half with overall Elo, as on the main tour.
- **Who is listed:** the ITF board's rule. Players need at least five ITF main-draw matches in the last 52 weeks; the 500 highest rated per tour are listed.
- **Records:** season records and head to heads count matches at every level.
- **Names:** full names from Sackmann's player files. A player known only from Flashscore is shown as "J.J. Wolf", not "Wolf J.J.".

Like the main-tour board, these profiles are for display only: they are never a forecast input and never change a forecast.

The open tab (Main tour or ITF) is kept in the page address, so links and the back button return to it.

## 6. The steps to go live (all done)

The protocol was frozen on 11 November 2026, and the first live ITF run was at 08:00 UTC that day.

1. **Commit and push** I4–I6.
2. **Upload the backfilled pages** as the `itfraw` archive (`node web/scripts/state.mjs pack itfraw data/raw/flashscore data/raw/tennisexplorer data/raw/itf`), so the first cloud run has the history since June. It is a separate archive, so a cloud run writing the main-tour archive at the same moment cannot overwrite it.
3. **Freeze P2** (`python -m matchup_dna.itf_live protocol freeze`). This refuses uncommitted code. It records:
   - the code fingerprint and the model file's SHA-256;
   - the population;
   - the counting rule: the first M1 forecast per match;
   - the window, to 30 June 2027;
   - the metrics: log loss and Brier of M1 against Elo only, paired by edition, plus calibration by tour and tier;
   - the evaluation date: not before 15 July 2027.
4. **Commit the protocol.** The next cloud run starts the live record.

## Tests

| Suite | Result |
|---|---|
| Python | 397 tests, including the ITF reader, rankings, matching, pipeline and board |
| Publisher | 59 tests, including the ITF view (counting rule, pilot, archive), the ITF match files (main-tour formats, revisions, contributions that must give back each probability) and the ITF profiles (listing rule, result order, names). Also: an ITF failure never stops the main-tour publish |
| Website unit tests | 10, including the circuit labels |
| Browser tests | 48, desktop and phone, including `/itf` with accessibility checks, an ITF match page, and the ITF players table, profile and Compare |
| Typecheck | Passes |

## Limits

- **Coverage:** 2.6% of men's and 3.9% of women's Flashscore players have an ambiguous or conflicting identity; their matches are not forecast. A checked name mapping would add them.
- **Unranked players:** about one player slot in five has no rank in the latest list, mostly players with no ranking at all. The model reads that as it did in training: unranked is itself a signal.
- **Page changes:** if Flashscore changes its page format, the ITF step fails visibly while the main-tour job carries on. The reader would then need updating.
- **No odds comparison:** ITF forecasts are model estimates. They are not compared with betting odds on the site.

## In ordinary language

The ITF model now has live data. Flashscore lists every men's and women's ITF match with its start time, and TennisExplorer gives the rankings each week.

Five months of results since June were read in once, so the ratings are up to date. Players are matched to their past records: where both sources cover the same matches, they agree on every winner.

The live model is the one without serve statistics, because those stopped being published. Every forecast is locked before the match, chained so it can't be altered, and scored against a plain Elo forecast once results come in.

The website has an ITF section and labels on every match. The ITF tabs work exactly like the main-tour ones: the same match board and match pages, the same archive, and the same players table with profiles and comparisons. The protocol is frozen, and the cloud keeps the live ITF record by itself, about every hour.
