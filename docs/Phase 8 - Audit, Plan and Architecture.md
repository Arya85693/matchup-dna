# Matchup DNA — Phase 8 Audit, Plan and Architecture

**Date:** 9 November 2026. **Scope:** move the scheduled work (forecasting, results, publishing) off the laptop to
GitHub Actions, so the site keeps updating when the laptop is asleep, shut down or away. This document is the plan
only; nothing is moved until each step is approved.
**Why now:** on 9 November the laptop went into standby at 18:27. The 19:00 forecasting run and the results checks did
not run until 20:02, and one finished match (Svitolina v Andreeva) waited about two hours for its result.

## Summary

- **Decision (owner, 9 November):** GitHub Actions, with the repository made **public** (unlimited Actions minutes on
  GitHub's standard runners) and the workflow committing the forecast ledger itself.
- **Schedule after the move:** forecasts twice a day as now; results checked every 30 minutes; the site published
  after every run; player ratings daily. The laptop becomes optional.
- **Moving the job does not change the P1 protocol.** The protocol fixes which forecast counts and which code and
  models may issue it, not where they run. Both fingerprints it checks are already platform-independent (part 1.3).
- **One real risk must be measured first:** a forecast counts as "unchanged" only if its inputs match exactly, and Linux
  can round the last digit of some calculations differently from Windows. A dry run measures this before anything
  switches (8D).
- **One machine runs the job at a time, always.** The laptop's tasks are turned off at the switch-over, and every
  workflow that writes the store shares one queue.

## 1. Audit

### 1.1 What the job needs

| Need | On the laptop today | On GitHub Actions |
|---|---|---|
| Python | 3.13.7 | 3.13.7 (`actions/setup-python`) |
| Packages | numpy 2.3.0 (lightgbm and scikit-learn only for tests) | Same pinned versions (`requirements.txt`) |
| Data | `data/` 1.2 GB: atp 260 MB, wta 191 MB, raw 650 MB (ESPN archive and caches), external 83 MB, store 5 MB | Kept in a private R2 bucket; downloaded at the start of each run (part 3) |
| Research files the code reads | `results/phase4/profile_settings.json` (in the P1 code hash) and the rest of `results/` (185 MB) | In the same private bucket |
| Website publishing | Python publisher, Node 22 with `aws4fetch`, R2 upload key | Same; keys held as GitHub secrets |
| Schedule | Windows Task Scheduler | GitHub `schedule` triggers (UTC, see part 3.3) |
| Logs | `data/logs/*.log` | Each run's log on GitHub's Actions tab |

### 1.2 What changes in the code

- **The forecasting, publishing and upload code:** nothing. It has no Windows-only parts; its path handling
  already accepts both `\` and `/`.
- **New:** the workflows (`.github/workflows/`), a small state script that downloads and uploads the store and data to
  the private bucket, and a gate that decides whether a results check is due. The Windows scripts stay for the laptop.

### 1.3 Portability of the P1 fingerprints (checked in the code)

| Fingerprint | How it is computed | Same on Linux? |
|---|---|---|
| Code (`prospective.code_sha256`) | File bytes **with line endings normalized** | Yes |
| Model artifacts (`frozen_models`) | Text read with Python's newline translation, then hashed | Yes |
| A forecast's inputs (`input_sha256`) | Exact JSON of every input number | **Only if every number is identical**; see 8D |

`store.add_prediction` treats a re-run as "unchanged" only when the inputs hash identically. If Linux computed an
input that differs in the 16th digit, its first run would issue a *revision* for each pending match. Revisions are
labelled and never counted, so nothing breaks, but the record would gain noise. Windows' and Linux's maths libraries
can differ in the last digit, so this is measured, not assumed.

### 1.4 Making the repository public (audited 9 November)

| Check | Result |
|---|---|
| Secrets in any commit, ever | None; the only match is the placeholder `<upload token secret>` in `web/HOSTING.md` |
| `.env` files, the store, `data/`, `results/` | Never committed (only the blank `web/.env.example`) |
| Personal file paths in tracked files | None |
| Commit author email | A personal address appears on every commit. Hiding it from now on: GitHub's "Keep my email addresses private" and its noreply address. Past commits keep it unless history is rewritten (not recommended) |
| Site text | The sidebar says "Source Code (Available upon Request)"; once public it can link to the repository again |

The forecast store and the data stay private in R2; only code, documents and the already public ledger are in the
repository.

## 2. Why GitHub Actions, and its limits

**Chosen because:** free for public repositories, no machine to look after, and the run logs are visible on GitHub.

**Limits that shape the design:**
- **Scheduled runs are best-effort.** They often start 5–30 minutes late and are occasionally skipped when GitHub is
  busy. The 30-minute results check tolerates this; the forecasting runs get two triggers each (part 3.3).
- **Every run starts on a blank machine**, so the store and data are downloaded at the start and the store uploaded at
  the end (part 3.1).
- **One job at a time per queue:** GitHub keeps at most one waiting run per concurrency group and cancels older waiting
  ones. Runs never overlap; at worst a waiting check is replaced by a newer one.
- **A run is limited to 6 hours**; the jobs take minutes.

**Other options considered:** Oracle Cloud Always Free (an always-on Arm machine, 2 cores and 12 GB, free; an
account, a card and idle reclamation to manage), a spare home computer, a small paid server, keeping the laptop awake.

## 3. Architecture

```
GitHub Actions (public repository, ubuntu-latest)                    Cloudflare R2
                                                                     state bucket (private): store, data, backups
forecast.yml   07:00 / 19:00 Eastern   restore -> daily job -> save    <-->
results.yml    every 30 min            restore -> gate -> settle -> save
players.yml    07:50 Eastern           restore -> players export
every job ends with publish + upload ------------------------------>  site bucket: snapshot/, history/  <-- Vercel
forecast.yml commits forecasts/ledger.jsonl to main (bot)
```

### 3.1 State between runs

- **Where:** a second private R2 bucket (`matchup-dna-state`), separate from the site's bucket, so the site's read-only
  key can never read it. R2's free allowance covers both.
- **What:** the store (`live.sqlite`, 5 MB) every run; the ESPN archive and caches when they change; the static data
  (Sackmann, TennisIsMyLife, TennisData.app snapshots, `results/`) once, re-uploaded only when updated.
- **Never two writers:** every workflow that writes the store is in one concurrency group, and the upload is
  conditional: it is refused if the stored copy changed since this run downloaded it (an R2 version check). A refused
  upload fails the run loudly; the next run starts from the newer copy.
- **Integrity:** after downloading, each run checks the store's hash chain and the P1 code fingerprint before writing
  anything, and refuses to run on a mismatch.
- **Backups:** the previous 30 days of store copies are kept in the state bucket.

### 3.2 The ledger

After each forecasting run the workflow commits `forecasts/ledger.jsonl` to `main` as a bot (owner's decision), with a
message naming the run. It rebases onto the latest `main` before pushing and retries if `main` moved.
**Your workflow changes:** run `git pull` before starting work and before pushing, since `main` will gain bot commits.

### 3.3 Times and daylight saving

GitHub schedules are in UTC, and Eastern time moves by an hour twice a year. Each forecasting slot gets two triggers an
hour apart (for example 11:00 and 12:00 UTC for 07:00 Eastern), and a run skips itself if that slot has already run.
The results check every 30 minutes is unaffected.

### 3.4 Secrets

Held as GitHub repository secrets, never in files: the site upload key (existing) and a state key limited to the state
bucket. Workflows from forks never receive secrets. The laptop keeps its own keys for development.

## 4. Plan

| Step | What happens | Who | Done when |
|---|---|---|---|
| **8A** Prepare | State bucket and its key; GitHub secrets; commit email set to the noreply address | You, with instructions | Secrets saved in GitHub |
| **8B** Build | Workflows, state script, results gate, ledger commit, Linux test job | Me | Tests pass on GitHub's runner |
| **8C** Go public | You switch the repository to public; the sidebar links to it again | You | Repository public |
| **8D** Dry run: identical numbers | On a frozen copy of the data, GitHub's runner rebuilds the inputs of every stored forecast and recomputes every stored probability; compared byte for byte with the laptop | Me | Identical, or the differences are measured and you decide (part 5) |
| **8E** Shadow days | For 2–3 days the workflows run into a **separate shadow store** and a test folder the site does not read; the laptop stays official. Each run is compared with the laptop's | Me | Shadow matches the laptop forecast for forecast; ESPN works from GitHub |
| **8F** Switch-over | At a quiet time: laptop tasks off; final laptop run; store, ledger and ESPN archive uploaded; hash chain verified; workflows switched to the real store | Both | First runs on GitHub log no errors |
| **8G** Watch and close | Three days of runs; backups confirmed; Phase 8 report | Me | No new errors over 3 days |

**Rollback:** before 8F nothing changes for the live system. After 8F: disable the workflows, download the store from
R2, turn the laptop tasks back on.

## 5. Risks

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Inputs differ in the last digit on Linux | Medium / low (revisions, never counted) | Measured in 8D. If they differ: switch only when no match is pending, and record it in the Phase 8 report. Alternative: Windows runners (minutes are free for public repositories too) |
| Scheduled runs late or skipped | High / low | 30-minute results checks; two triggers per forecasting slot; the status page shows freshness |
| ESPN refuses GitHub's addresses | Low–medium / high | Tested in 8E before anything switches |
| Two writers to the store | Low / high | One concurrency queue, conditional uploads, laptop tasks off at 8F |
| Bot commits conflict with yours | Medium / low | The bot rebases and retries; you `git pull` before pushing |
| Public code | Accepted | Audited (1.4); no secrets or data in the repository |

## Sources

- GitHub Docs, "Billing for GitHub Actions" (free for public repositories on standard runners; 2,000 minutes a month
  for private repositories on GitHub Free) and "Events that trigger workflows: schedule" (UTC, best-effort timing).
