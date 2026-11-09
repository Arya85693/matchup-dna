# Matchup DNA — Phase 7 Website Report

**Status, 9 November 2026:** Phase 7 is complete. The public website is live at
[www.matchupdna.com](https://www.matchupdna.com) and [matchup-dna.vercel.app](https://matchup-dna.vercel.app); both
addresses load normally, including on the network that had briefly blocked the new domain. It updates itself from
the forecasting system every two hours, and it passed its launch checks: browser tests against the live site,
Lighthouse audits, and a failure drill. A few operational follow-ups carry over; they are listed under
[Open items](#open-items).
**Design:** [Phase 7 - Audit, Plan and Architecture.md](Phase%207%20-%20Audit%2C%20Plan%20and%20Architecture.md) has
the repository audit, the page specifications, the design concepts, the architecture and the milestone plan.

## Summary

- **The forecasts are public.** Every forecast the Phase 6 system issues appears on the site, with the time it was
  locked, the inputs behind it, and its result once the match is played.
- **The website cannot change a forecast.** It reads published snapshots, never the forecasting database, and the
  browser never computes a probability. Every file is checked against a sha256 manifest and a data contract before it
  is shown; a damaged or missing file shows "not available", never a wrong number.
- **The track record is honest by construction.** Scores are computed with the P1 protocol's own counting functions,
  so the site cannot count a forecast the protocol would not. Revisions, exclusions and pending results are labelled.
- **It runs without anyone.** Scheduled tasks publish every two hours, check for results every two hours between the
  twice-daily forecasting runs, and upload each snapshot to private cloud storage that the hosted site reads.
- **No frozen work changed.** No file in the P1 protocol's code hash, no model artifact and no earlier result was
  modified. The 323 existing tests pass, and the P1 code hash still matches.

## What was built

All website code is in `web/`. The forecasting package (`matchup_dna/forecasting/`) is unchanged; `api.py` was not
extended either, because the publisher's own read-only views were enough.

| Piece | What it does |
|---|---|
| `web/publisher/publish.py`, `views.py`, `contract.py`, `readonly.py` | Opens the live store read-only, skips if a run is in progress, copies it with SQLite's backup API, builds the public views, checks every file against the contract, writes a versioned snapshot and its sha256 manifest |
| `web/publisher/players.py`, `headshots.py` | Player profiles (Elo, surface Elo, trend, season record, recent results, head-to-head) from the same match history the models use; player photos |
| `web/publisher/research.py` | The historical research figures for the Model Lab; refuses to write unless every headline number equals the published reports |
| `web/app`, `web/components`, `web/lib` | The Next.js site: pages, components, the zod contract that re-validates every file, the storage reader |
| `web/scripts/upload-snapshot.mjs` | Uploads each snapshot to a private Cloudflare R2 bucket: files first, manifest last, never replacing a newer snapshot |
| `scripts/run_website.cmd`, `run_settle.ps1`, `install_*_schedule.ps1` | The scheduled tasks |

### Pages

| Page | What a visitor sees |
|---|---|
| Home (`/`) | Today's featured forecasts, how the system works, top-rated players, an Elo playground |
| Matches (`/matches`) | Upcoming matches and results by tournament, with tour, surface and level filters; every match without a forecast says why |
| Match page (`/matches/[uid]`) | Both models' forecasts, what drove them, the forecast history, the result, and a verification panel with every hash |
| Players (`/players`, `/players/[id]`) | Every active ATP and WTA player rated by Elo; profiles with trends, surfaces and recent results |
| Compare (`/players/compare`) | Two same-tour players side by side, with their head-to-head record |
| Model Lab (`/lab`) | The live P1 record (interim), the historical benchmarks, calibration, the market comparison, the model versions |
| Forecast Archive (`/archive`) | Every forecast ever issued, by match or as raw ledger records, searchable, with full inspection |
| Methodology, Data status | How it works; data freshness, run health and the integrity check |

### How data reaches the site

```
laptop (Windows Task Scheduler)                                    Cloudflare R2 (private)      Vercel
07:00, 19:00   forecasting job: forecasts, results, ledger
odd hours      results check (settle only, never forecasts)
every 2 h :35  publish  -> web/.data/snapshot -- upload -->        snapshot/v1/...  <-- read --  the site
07:50 daily    players  -> web/.data/history  -- upload -->        history/v1/...                (refreshes ~5 min)
```

- **Storage:** the bucket is private. The laptop holds a read-and-write key (`web/.env.upload`, never committed);
  Vercel holds a separate read-only key. The forecasting database, logs and file paths never leave the laptop.
- **Freshness:** a new forecast reaches the site about 35 minutes after the run that issued it. A result reaches the
  site within about 2.5 hours of the match ending.
- **Laptop off:** the site keeps serving the last snapshot and marks it "may be out of date" after 18 hours. Missed
  tasks catch up when the laptop wakes.
- **Cost:** about 40,000 uploads a month, against R2's free 1 million. Vercel's Hobby plan is free for
  non-commercial use. The only cost is the domain.

## Decisions made during the phase

These differ from the plan, all deliberately:

| Plan | What was done | Why |
|---|---|---|
| New read functions in `api.py` | In `web/publisher/views.py`; `api.py` unchanged | Keeps the forecasting package untouched |
| pydantic contract | Standard-library checks (`contract.py`) | Nothing new installed in the forecasting environment |
| Direction B "Centre court" design | Rebuilt twice at the owner's request: more spacious, then a quieter Linear-style app shell | Readability; the first version felt cramped |
| Separate research pages | One Model Lab with tabs; old addresses redirect | Fewer, clearer pages |
| Rankings shown on player pages | Not shown; the site notes that the earlier models were benchmarked against rankings | The site rates players by its own Elo |
| On-demand revalidation webhook and secret | Fixed 5-minute refresh | Simpler, no extra secret; at most 5 minutes' delay |
| Publisher twice a day (07:35, 19:35) | Every two hours, plus a results check every two hours | Fresher results and match states |
| Match states "In progress" and a 3-hour grace | "Result pending" from the scheduled start until the result is recorded | Nothing about a match in play is shown; the pre-match forecast stays as it was |
| Player pages (7H) and Compare (7I) after launch | Built before launch | The owner's priority (licensing: see Open items) |

### Player data rules

- **Players are tour-qualified.** Sackmann's ATP and WTA ids collide (id 200748 is both Venus Williams and an ATP
  player), so every address is `atp-<id>` or `wta-<id>`. Old numeric addresses redirect only when unambiguous.
- **Only active players are listed.** A player needs a tour-level match in the last 12 months and no announced
  retirement. Retirements come from a sourced list (`web/content/retired.json`, 8 players), not from inactivity, because
  coverage gaps make active players look inactive. Retired players stay in the match history and every backtest.
- **Head-to-head** counts completed and retired tour-level matches, never walkovers, and says "Never played before" when
  two players have not met.
- **Photos** are matched by identity, never by name alone: official WTA headshots through WTA ids (name plus date of
  birth or country), Wikimedia Commons photos through Wikidata's ATP code and WTA id, then ESPN, then initials. Commons
  photos are credited with author and licence. Coverage: ATP 257 of 455 players, WTA 248 of 326; every ATP top-50 player
  except two, and every WTA top-50 player.

### One exception to the official record

On the owner's decision, one pilot forecast is shown on the Results list: **Gauff v Pegula**, WTA Finals, 8 November
(Gauff 51.9%; Gauff won 6–4 6–7(5) 6–2). It was issued before play, at 19:23 UTC, by the pilot run that preceded the
protocol freeze; the official job first saw the match after it had started. It is read unchanged from
`forecasts/pilot_2026-11-08_ledger.jsonl` and recorded in `web/content/pilot_exceptions.json`. Its match page labels it
"Pilot forecast, not counted". It never enters the counted set, the track record, the archive or any score (tested),
and the live store and official ledger were not changed.

## Verification

### Tests

| Suite | Count | Covers |
|---|---:|---|
| Publisher (`web/publisher/tests`) | 40 | Read-only store access, contract, views, counting, player export, retirements, head-to-head, photos, pilot exception, pruning, match states |
| Website unit (`npm test`) | 8 | Formatting helpers; the uploader against a local R2 stand-in |
| Browser (`npm run e2e`) | 42 | Every page at desktop and phone size: no console errors or failed requests, no sideways scrolling at 390 px, axe accessibility (WCAG 2.1 AA), filters, navigation, comparison, archive inspection |
| Existing project tests | 323 | Unchanged, all passing; the P1 code hash still matches |

### Launch checks (7G), 9 November 2026

**1. Browser tests against the live site:** all 42 pass against `matchup-dna.vercel.app`
(`E2E_BASE_URL=https://matchup-dna.vercel.app npm run e2e`; the tests only browse).

**2. Lighthouse on the live site** (mobile simulation):

| Page | Performance | Accessibility | Best practices | SEO |
|---|---:|---:|---:|---:|
| Home | 89 | 100 | 100 | 100 |
| Matches | 85 | 98 → fixed | 100 | 100 |
| Match page | 89 | 100 | 100 | 100 |
| Players | 84 | 100 | 79 → fixed | 100 |

The two findings were fixed: a skipped heading level on the Matches board, and tracking cookies set by Wikimedia's
image server (its photos now load without credentials, which drops them).

**3. Failure drill:** the production build was run against a copy of the real snapshot in a local stand-in for R2,
then the copy was broken. The real bucket and the live site were not touched.

| Failure | Result |
|---|---|
| Publishing stops for 19 hours | Data still shown, marked "may be out of date" |
| A stored file altered (51.9% changed to 91.9%) | Refused by its hash: "not available", and 91.9% never shown; other pages unaffected |
| Storage unreachable | Pages show "not available"; no crash, no server error |

### Problems found and fixed during the phase

- **ATP and WTA id collision** overwrote some player profiles; fixed with tour-qualified ids.
- **A truncated hosting key** (63 of 64 characters) left the first deployment unable to read storage; diagnosed with
  a read test that never printed the key, and replaced.
- **A results-check guard** read a never-run scheduled task as overdue; it now ignores tasks that have never run.
- **Official ATP headshots** could not be imported automatically; Wikimedia Commons, found through the same ATP
  player codes, was used instead.
- **The new domain was briefly blocked** by a network web filter, which labelled it "high-risk" because it had just
  been registered (the site itself was never down). **Resolved:** on 9 November `matchupdna.com`,
  `www.matchupdna.com` and `matchup-dna.vercel.app` all load normally (HTTP 200) from that network.

## Open items

These carry over; none blocks the site.

1. **Uptime monitor.** A free UptimeRobot account checking `/` and the status page every 5 minutes, with an alert when
   the data is stale. Needs the owner's account.
2. **Three-day log check.** Confirm no new errors in `data/logs/daily.log`, `settle.log` and `website.log` by
   12 November.
3. **TennisIsMyLife terms.** The plan held player pages until its terms were reviewed; they were built first. The
   owner should complete that review or record the decision to proceed.
4. **Forecast cadence.** Forecasts run twice a day. A match whose time is confirmed after the 07:00 run and starts
   before 19:00 is missed. Running the full job every two hours would close that gap without changing which forecast
   counts (the protocol fixes the counting rule, not the schedule). Awaiting the owner's decision.

## Next milestones

- **Phase 6 operational check** closes about 23 November 2026.
- **P1 interim monitoring** continues on the site's Model Lab; the final P1 evaluation is due no earlier than
  15 July 2027.
- **In-play probabilities** are planned as a separate feature in a later phase. Nothing about a match in play is shown
  today.
