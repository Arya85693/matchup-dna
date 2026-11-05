# Matchup DNA — Phase 0 Feasibility Report

**Date:** 3 November 2026  
**Decision:** Start Phase 1. One live-data check stays open and does not block the first program.

## Decision

The historical files are enough for a first pre-match model. The Sackmann tour-level singles files contain 361,571 ATP and WTA matches, with stable player ids inside each tour, unique match keys, and ranks and serve stats that are mostly filled from 2021 onward.

A path to a site that updates on its own also exists. Live Tennis API and SportsAPI365 both publish ATP and WTA fixtures, scores, and results. A useful plan is free or about $10 to $30 a month. Neither provider was called with a real key, so that check remains open. History for the first model comes from the files.

Odds are good enough for a later study and are not required to start. Valuebetennis opening prices cover almost all Grand Slam, Masters, and main-tour matches since 2021. Closing prices are a separate, less complete timestamp. Those player ids are not Sackmann’s ids. Kalshi also lists ATP and WTA match-winner contracts, and a contract price is already a probability, but its API terms do not allow storing or publishing that data for this project.

Shot-by-shot charting and Grand Slam point-by-point logs are real, incomplete, and unnecessary for the first model.

## What was checked

Four candidate sources from the project brief, measured on 3 November 2026:

- The Jeff Sackmann archive mirror: ATP matches, WTA matches, rankings, player tables, and Grand Slam point-by-point files.
- Valuebetennis season CSVs for 2021 through 2026.
- Live Tennis API, called without a key, plus its pricing page and terms.
- SportsAPI365 on RapidAPI, called without a key, plus its documentation and pricing.

The Match Charting Project was checked through its repository README and license. Its data files were not loaded. The Odds API was left out. The brief treats paid historical odds as optional. Kalshi was checked the same day as an extra market-probability source: the public series endpoints for `KXATPMATCH` and `KXWTAMATCH`, plus the developer agreement and the data terms.

Both API calls returned HTTP 401. Statements below about live coverage, delay, and price come from the providers’ own pages.

## Historical results — Sackmann archive

**Source.** Archival mirror of Jeff Sackmann’s ATP, WTA, and Grand Slam datasets: [github.com/Aneeshers/tennis-sackmann-archive](https://github.com/Aneeshers/tennis-sackmann-archive). The mirror’s README says the ATP and WTA snapshot comes from upstream commits in June 2026, and the point-by-point snapshot comes from October 2024.

**License.** CC BY-NC-SA 4.0. Credit Jeff Sackmann. Noncommercial use. ShareAlike if a remix of the data is redistributed.

### Tour-level singles

The files `atp_matches_YYYY.csv` and `wta_matches_YYYY.csv` hold **361,571** matches: **199,389** ATP and **162,182** WTA. Tournament weeks run from **25 December 1967 through 25 May 2026** on both tours. The 2026 files contain **2,744** matches and stop at the French Open week. Wimbledon 2026 and the rest of that season are outside the snapshot. Futures and qualifying files for 2026 stop on 1–2 June.

`tourney_date` is the Monday of the tournament week, not the day the match was played. A feature built from these files has to treat that Monday as the time stamp, or it will use results from later in the same tournament.

Columns on every match file, including futures and qualifying:

`tourney_id`, `tourney_name`, `surface`, `draw_size`, `tourney_level`, `tourney_date`, `match_num`, winner and loser `id`, `seed`, `entry`, `name`, `hand`, `ht`, `ioc`, `age`, `score`, `best_of`, `round`, `minutes`, serve totals for both players (`ace`, `df`, `svpt`, `1stIn`, `1stWon`, `2ndWon`, `SvGms`, `bpSaved`, `bpFaced`), and `rank` plus `rank_points` for both players.

Inside one tour, `tourney_id` plus `match_num` never repeats. The same pair of values does repeat across the ATP and the WTA, so a match key is tour plus those two fields. Every winner id and loser id exists in that tour’s player file. Four matches list the same id as winner and loser.

Player tables: **66,912** ATP rows and **70,571** WTA rows, with `player_id`, `name_first`, `name_last`, `hand`, `dob`, `ioc`, `height`, and `wikidata_id`. Wikidata is filled for about 7.3% of ATP players and 5.3% of WTA players, so it cannot be the join key.

| Check | All years | 2021–2026 |
|---|---|---|
| Winner id, loser id, names, round, best-of | Complete | Complete |
| Surface missing | 2.2% | 0.5% |
| Winner rank missing | 24.2% | 0.4% |
| Loser rank missing | 27.5% | 1.1% |
| Aces missing | 58.6% | 5.8% |
| Minutes missing | 65.5% | 8.2% |

Surfaces are Hard, Clay, Grass, and Carpet, plus 31 rows spelled `clay` and 7,887 blank surfaces. Serve stats are effectively absent before the 1990s on the ATP and before the 2000s on the WTA. From 2021 on they are usable. The partial 2026 season is a bit thinner: aces are missing on 16% of 2026 tour-level rows.

Scores are present except for 10 empty rows. The text also records unfinished matches: 6,960 retirements, 2,566 walkovers, 192 defaults, and 23 abandoned matches. `best_of` is 3 in 317,972 rows, 5 in 43,461, and 1 in 138. Minutes are under 15 in 349 matches and over 360 in 11. A first model should keep retirements and walkovers as their own outcomes.

ATP levels in these files are Grand Slam (`G`), Masters (`M`), other tour events (`A`), Tour Finals (`F`), Davis Cup (`D`), and a few dozen other events. WTA codes also include the older Premier, International, and Tier labels. Challengers, ITF events, and qualifying draws sit in the yearly futures and qualifying files, which use the same columns. Those files can enlarge a later sample. A tour-level model does not need them.

### Rankings

Ranking files are separate. Columns are `ranking_date`, `rank`, `player`, and `points`. The WTA files also have `tours`. The `player` column is the player id.

The 2020s ATP file has 516,461 rows from 6 January 2020 through 29 December 2025, no missing points, and 570 duplicated player-date rows. The current ATP and WTA ranking files run from 5 January 2026 through 8 June 2026. Sackmann’s own notes say ATP rankings are mostly complete from 1985, with 1982 missing and 1973–1984 only intermittent. The match rows already carry the rank as of the tournament week, which is the safer field for a first model.

### Grand Slam point-by-point

There are 49 singles point files for 2011–2024. Missing events: 2020 Wimbledon, and the Australian Open and French Open in 2022, 2023, and 2024. Sackmann’s notes say those two slams stopped publishing in the old format, and he has not extracted the replacement feed since 2023. The 2024 US Open sample has 253 match rows and 45,289 point rows. Columns include server, score, rally length, serve speed, and serve direction. Which of those columns are filled changes by tournament and year. This set is later work.

## Historical odds — Valuebetennis

**Source.** Six season files, `valuebetennis-matchs-2021.csv` through `2026.csv`, from [valuebetennis.com/en/donnees.htm](https://www.valuebetennis.com/en/donnees.htm). Last generated 3 November 2026. The delimiter is a semicolon, and tournament names are quoted because they contain commas.

**License.** CC BY 4.0. Attribution is required. Commercial use is allowed. The site says the prices are the ones they recorded, so another source can disagree.

**472,682** rows, from 1 January 2021 12:00 UTC through 3 November 2026. No duplicate `match_id`. Men’s rows: 276,476. Women’s rows: 196,206.

Columns: `match_id`, `date` (UTC date and time), `tournoi`, `tournoi_id`, `categorie`, `genre`, `surface`, `tour` (round number), `joueur1`, `joueur1_id`, `joueur2`, `joueur2_id`, opening odds, closing odds, `vainqueur_id`, `score`, `duree_min`.

The population is mostly the lower tours.

| Category | Rows | Opening odds unusable | Closing odds unusable | Score missing |
|---|---:|---:|---:|---:|
| Grand Slam | 11,113 | 0.5% | 22.6% | 3.1% |
| Masters | 10,768 | 1.0% | 16.0% | 1.4% |
| Main tour | 22,996 | 2.2% | 27.5% | 2.7% |
| Challenger | 149,626 | 37.0% | 46.5% | 10.1% |
| Davis / BJK Cup | 1,157 | 41.1% | 58.9% | 23.0% |
| Category missing | 2,719 | 98.7% | 99.1% | 18.4% |
| ITF | 274,303 | 66.0% | 74.4% | 38.6% |

Unusable means at least one of the two prices is missing or is not a decimal odd above 1.00. Across the whole file, opening prices are unusable on 50.8% of rows and closing prices on 60.9%. That average is the ITF and Challenger rows.

Where both opening prices exist, the median overround is 1.066. Where both closing prices exist, it is 1.048. That is a plausible bookmaker margin. Opening and closing stay separate columns. A closing price is a benchmark. It is not a price the model may see before the match.

Duration is empty on 447,564 rows. Three rows have a winner id that is neither player. Surfaces are labeled in French: clay 211,103, hard 205,392, indoor hard 41,560, grass 9,967, indoor carpet 4,660.

The download page says the file is singles only. The file contains doubles pairs filed as main tour, including Ninomiya/Shibahara and Olmos/Gasanova at Abu Dhabi in January 2021. Grand Slam rows also include qualifying, which Sackmann stores outside the main-draw files. A join has to remove those rows first.

## Market probabilities — Kalshi

**Source.** Kalshi’s public trade API, `https://external-api.kalshi.com/trade-api/v2`. Checked 3 November 2026. No API key. `GET /series/KXATPMATCH` and `GET /series/KXWTAMATCH` both returned HTTP 200. The series titles are “ATP Tennis Match” and “WTA Tennis Match,” category Sports. An open-markets call returned live match-winner contracts.

One open match that evening was Tirante versus Struff. The Tirante contract (`KXATPMATCH-26NOV04TIRSTR-TIR`) had a yes bid of 0.30 and about 25 contracts of volume. The Struff contract had a yes bid of 0.67 and about 50 contracts of volume. A separate Michelsen contract had a yes bid of 0.16 and about 1,004 contracts of volume. The two sides of the Tirante–Struff match added to 0.97, not 1.00.

Market-data reads do not require a key. Settled markets move to historical endpoints, including candlesticks at 1, 60, and 1,440 minutes and timestamped trades. A price of 0.30 is already a 30 percent probability, and each trade has a time, so this is a cleaner pre-match timestamp than a bookmaker close. That is the part that fits Phase 5.

It does not fit the way this project stores and publishes data.

The Kalshi Developer Agreement v1.1 limits API use to facilitating a member’s own trading. It prohibits collecting, caching, aggregating, or storing API data except for that trading, sharing the data with anyone else, and using the API for benchmarking, unless Kalshi gives prior written permission. The Kalshi Data Terms of Service allow personal, noncommercial viewing of the site and prohibit public display, compiling a database, and using the data to train a machine-learning model, again unless Kalshi consents in writing. A public endpoint does not waive those terms.

Coverage is only the matches Kalshi has listed. It does not reach back to 1968 or to January 2021. Volume can be a few dozen contracts, which is a weak probability. Tickers are abbreviations (`TIR`, `STR`), a fourth identity system next to Sackmann, Valuebetennis, and SportsAPI365.

Valuebetennis stays the odds source that can be stored, joined, and written about. Kalshi stays out of the repository and off the site unless Kalshi gives written permission for the research and the public comparison.

## Player identity

The Sackmann, Valuebetennis, and SportsAPI365 ids are three different systems. Kalshi does not use these integers. Its tickers abbreviate names, such as TIR for Tirante and STR for Struff.

| Player | Sackmann | Valuebetennis | SportsAPI365 docs |
|---|---:|---:|---:|
| Jannik Sinner | 206173 | 22691 | 47275 |
| Novak Djokovic | 104925 | 625 | — |

Full names do match. Checked tour-level rows, including Kudermetova–Kontaveit and Sabalenka–Hercog in January 2021, are the same two people in both files under different integers.

Last name is unsafe. The ATP player file contains Martin Sinner (101441) and Jannik Sinner (206173), and three different Djokovics. The same integer also identifies different people on the two tours. Inside Sackmann the player key is tour plus `player_id`.

Of the 46,034 Valuebet rows in Grand Slam, Masters, main tour, and Davis/BJK Cup:

| Join result | Rows | Share |
|---|---:|---:|
| Matched a Sackmann main-draw singles match by normalized full name, from one day before the tournament Monday through 16 days after it | 24,960 | 54.2% |
| No such singles pair in the 2021–May 2026 main-draw files | 15,838 | 34.4% |
| Dated after 25 May 2026, and no matching singles pair | 2,782 | 6.0% |
| The two names met in Sackmann, outside that tournament window | 2,454 | 5.3% |

The 15,838 unmatched rows include doubles and Grand Slam qualifying. A name crosswalk is feasible for tour-level singles. It is a later cleaning job. Phase 1 does not need it, because Phase 1 does not need the odds.

## Live providers

### Live Tennis API

Operated by JSB Holdings LLC. [livetennisapi.com](https://livetennisapi.com/). An unauthenticated request to the public matches endpoint returned `{"error":"unauthorized"}` with HTTP 401.

| Plan | Price | Allowance | What it adds |
|---|---|---|---|
| Free | $0 | 100/day, 30/minute | Live and upcoming matches, current scores, players, fixtures, tournaments. About 20 history calls per month as a sample. |
| Basic | $9.99/month | 1,000/day | Completed results, point-by-point from 2023, a 1968–2022 results archive. |
| Pro | $29.99/month | 10,000/day | Match events, match-winner odds, bulk history downloads, rankings. |
| Ultra | $99.99/month | 500,000/day | WebSocket, in-play statistics, their win-probability field, shot-level research data. |

Coverage is described as ATP, WTA, Challenger, and ITF. Prices on the site were dated 6 October 2026. The terms allow responses to be used inside an application, and they allow storage only as far as the application needs it. They prohibit republishing the raw responses as a data feed.

### SportsAPI365

Hosted on RapidAPI as Tennis API - ATP WTA ITF. Documentation: [docs.tennis-api.com/getting-started](https://docs.tennis-api.com/getting-started). An unauthenticated request returned HTTP 401, invalid API key.

| Plan | Price | Allowance | Access |
|---|---|---|---|
| Free | $0 | 50/day, 4/second | Same endpoints as Pro: fixtures, live scores, historical results, point-by-point, rankings, and odds. Their model probabilities are withheld. |
| Pro | $29/month | 150,000/month | The same data, with a larger quota. |
| Ultra | $59/month | 1,200,000/month | Adds their model win probabilities. |
| Mega | $99/month | 3,800,000/month | Adds Socket.IO streaming and written match analysis. |

A player can be requested by numeric id or by name. A shared name returns HTTP 400 with the possible ids. The schedule id, the live id, and the archive id of one match are different, and each fixture carries links between them. Odds use short keys, and the two bookmakers quote different units: Marathonbet totals are in games, Pinnacle totals are in sets.

A direct SportsAPI365 subscription lists different monthly quotas. The dollar prices in this report are the RapidAPI prices.

### What this means for a site that updates itself

A small daily job — today’s fixtures, the live board, yesterday’s results — fits inside either free quota. Live Tennis Free can show current matches and cannot backfill history. SportsAPI365 Free includes results and odds and allows only 50 calls a day. Sackmann already covers history through May 2026, so the API has to cover June 2026 onward, plus the matches on the coming schedule.

The provider stays unchosen until one authenticated response from each has been read. Until then, the supported claim is narrower: a free or low-cost feed can update fixtures and scores, the prediction code should not depend on one vendor, and neither feed has been observed yet.

## Sources left out of the first build

**Match Charting Project.** Shot-by-shot records of charted matches, CC BY-NC-SA 4.0. The upstream README describes a crowdsourced set of more than 5,000 matches, not the whole tour. Useful later for style and matchup research. Not loaded in this audit.

**Paid historical odds feeds**, including The Odds API’s historical product. Valuebetennis already covers opening and closing prices from 2021 under CC BY 4.0. A paid feed would have to solve a gap this audit did not find in the tour-level opening prices.

## Known limitations

- The Sackmann match snapshot ends at the tournament week of 25 May 2026. Later matches have to come from a live provider or a newer snapshot.
- Point-in-time features must use the tournament Monday, the rank stored on the match, and only ranking rows dated on or before that Monday.
- Retirements, walkovers, defaults, and the 138 `best_of = 1` rows need an explicit rule before they become a win/loss label.
- ATP and WTA player ids collide. They have to stay in separate id spaces.
- Valuebetennis ids, Sackmann ids, and SportsAPI365 ids are three systems. Kalshi adds a fourth, built from name abbreviations in the ticker. Tour-level singles can be linked by full name plus a date window, after doubles and qualifying are removed.
- Closing odds are missing on roughly a fifth to a quarter of tour-level matches. ITF and Challenger odds are too sparse for the first odds experiment.
- Valuebetennis duration is almost entirely empty.
- Grand Slam point-by-point is missing the Australian Open and French Open from 2022 through 2024, and the filled columns change by event.
- Live coverage, score delay, withdrawal handling, and the stored shape of a fixture were not confirmed on a real response.
- CC BY-NC-SA covers anything derived from Sackmann or the Match Charting Project. A noncommercial public site can attribute Jeff Sackmann and proceed. A paid product, or a republication of the files, needs another result source. Valuebetennis odds are under CC BY 4.0 and can be used with attribution.
- Kalshi market data may not be stored, used to train the model, or shown on the site under the developer agreement and data terms checked on 3 November 2026. Written permission would change that.

## What Phase 1 can assume

Phase 1 is a local Python program on the Sackmann tour-level singles files for both tours. The entities it needs are already in those files: players, tournaments, surfaces, dates, scores, ranks, and modern serve totals. The player key is tour plus id. The time column is the tournament Monday. Retirements and walkovers stay visible as their own results.

Lower-level files can wait. Odds can wait. Kalshi is not a Phase 1 source. A database, an API, and a website can wait.

The open item to carry forward is a keyed call to each live provider. That call is what confirms identifier shape, score delay, and how retirements and walkovers look in the feed.
