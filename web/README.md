# Matchup DNA website (Phase 7)

The public website. It **reads published snapshots and never computes a forecast**. The plan and architecture are in
[`../Phase 7 - Audit, Plan and Architecture.md`](../Phase%207%20-%20Audit%2C%20Plan%20and%20Architecture.md).

| Page | Route | Data |
|---|---|---|
| Home | `/` | snapshot + player histories: featured forecasts, how-it-works walkthrough, top players |
| Matches | `/matches` | snapshot: `matches/index.json` |
| Match Intelligence | `/matches/[uid]` | snapshot: `matches/<uid>.json` |
| Players | `/players`, `/players/[id]`, `/players/compare` | player histories: every active ATP/WTA player (`web/.data/history`) |
| Model Lab | `/lab` | snapshot (live P1, interim) + research export (Phases 2–5) + `models.json` |
| Forecast Archive | `/archive` | snapshot: `archive.json` |
| Methodology | `/methodology` | static text |
| Data status | `/status` | snapshot: `status.json` |

Design: Linear-style app shell (sidebar), charcoal `#10151D`, cards `#19212D`, teal accent `#39C7AD`, Geist type.
Green and red mark favourable and unfavourable outcomes only. Old `/research/*` addresses redirect to `/lab`.

```
web/
  publisher/         Python: read-only snapshot publisher, research export, tests
  content/research/  historical.json, market.json: checked aggregates from the research reports (committed)
  app/               pages
  components/        sidebar shell, UI primitives, match list, match intelligence, players, model lab, archive
  lib/               contract (zod), snapshot reader, research loader, formatting, feature labels
  e2e/               Playwright tests (every page, both screen sizes, accessibility)
  .data/             local snapshot output (gitignored)
```

## Publish a snapshot (twice a day, after the forecasting job)

From the repository root, with the project's usual Python (nothing new is installed):

```
python -m web.publisher.publish
```

What it does:
- opens `data/store/live.sqlite` **read-only**;
- skips if a forecasting run is in progress;
- copies the store with SQLite's backup API, and works only on the copy;
- writes `web/.data/snapshot/v1/<time>/…` plus `manifest.json`.

It never runs the forecasting engine and never writes to a store. Run it between the 07:00 and 19:00 jobs.

## Player histories (after each forecasting job)

```
python -m web.publisher.players
```

Rebuilds every active player's profile from the same history the forecasting job uses (about two minutes).
Profiles include Elo, surface Elo, ranking, season record, Elo trend and recent results. Run it after the job, next
to `publish`.

It is read-only. It skips when:
- a forecasting run is in progress;
- reading the ESPN archive would need a parse cache the job has not written yet.

## Research figures (only when the research changes)

```
python -m web.publisher.research
```

This rebuilds `web/content/research/*.json` from the local `results/` files. It refuses to write if any headline number
differs from the published report.

## Run the site

```
cd web
npm install              # once
npm run dev              # development, http://localhost:3000
npm run build && npx next start -p 3000    # production build
```

Pages read `web/.data/snapshot` and `web/.data/history` (override with `SNAPSHOT_DIR`, `HISTORY_DIR`). When the R2
keys are set, as on Vercel, they read the hosted copy instead (`lib/storage.ts`).

## Hosting

The live site runs on Vercel and reads a private Cloudflare R2 bucket. The scheduled tasks
(`scripts/install_website_schedule.ps1`) publish every two hours and upload each snapshot with
`web/scripts/upload-snapshot.mjs`. Setup, step by step: [`HOSTING.md`](HOSTING.md).

## Tests

```
python -m unittest discover -s web/publisher/tests -t .    # repository root: publisher and research export (24)
cd web && npm test && npm run typecheck                    # formatting helpers (7), types
cd web && npm run build && npm run e2e                     # browser tests: every page, desktop and phone (28)
python -m unittest discover -s tests                       # the existing 323 tests, unchanged
```

The browser tests use the installed Microsoft Edge. They fail on:
- any console error, page error or failed request;
- sideways scrolling at 390 px;
- a serious or critical accessibility problem (axe, WCAG 2.1 AA).

The publisher tests also check:
- the Phase 6 P1 code hash still matches the frozen protocol;
- the publisher imports no forecasting or ingestion module.
