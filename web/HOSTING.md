# Hosting the website (Phase 7G)

The live site runs on **Vercel** and reads its data from a private **Cloudflare R2** bucket. Your laptop keeps doing
all the work: the forecasting job, the publisher, and the upload. Vercel never runs Python, never sees the forecast
database, and holds only a read-only key.

```
laptop (Task Scheduler)                                  Cloudflare R2 (private)        Vercel
07:00 / 19:00  forecasting job -> live.sqlite
every 2 h      publish  -> web/.data/snapshot  --upload-->  snapshot/v1/...   <--read--  the site (refreshes
07:50 daily    players  -> web/.data/history   --upload-->  history/v1/...                about every 5 min)
```

Both free tiers cover this site with room to spare. It uploads about 35,000 files a month: R2 allows 1 million
writes a month, 10 GB of storage and free downloads. Vercel's Hobby plan is for non-commercial use, which this site is.

## 1. Cloudflare R2: a bucket and two keys

1. Sign in at dash.cloudflare.com and open **R2 Object Storage**. Cloudflare asks for a payment method before it
   switches R2 on, even on the free tier.
2. **Create bucket**: name it `matchup-dna-site` and leave the location on Automatic. Keep it private: don't connect a
   public domain or turn on the r2.dev URL.
3. Note your **Account ID**, shown on the R2 overview page.
4. Open **Manage API tokens**, then create two tokens, each **limited to the `matchup-dna-site` bucket**:
   - an upload token with **Object Read & Write**, for your laptop;
   - a site token with **Object Read only**, for Vercel.
   For each, copy the **Access Key ID** and **Secret Access Key**. The secret is shown only once.

## 2. Your laptop: the upload key

Create `web/.env.upload`. It is ignored by git; see `web/.env.example`.

```
R2_ACCOUNT_ID=<account id>
R2_BUCKET=matchup-dna-site
R2_UPLOAD_ACCESS_KEY_ID=<upload token access key id>
R2_UPLOAD_SECRET_ACCESS_KEY=<upload token secret>
```

Then upload once by hand, from the repository root:

```
node web/scripts/upload-snapshot.mjs snapshot
node web/scripts/upload-snapshot.mjs history
```

Each should print `uploaded ... files`. From then on the scheduled tasks upload after every publish. Check
`data/logs/website.log` for `uploaded snapshot ...` lines.

## 3. Vercel: the site

1. At vercel.com, use **Add New > Project** and import the GitHub repository `matchup-dna`.
2. Set **Root Directory** to `web`. The framework (Next.js), build command and output are detected automatically.
3. Under **Environment Variables**, add the **read-only** key, for Production and Preview:

   | Name | Value |
   |---|---|
   | `R2_ACCOUNT_ID` | your account id |
   | `R2_BUCKET` | `matchup-dna-site` |
   | `R2_READ_ACCESS_KEY_ID` | site token access key id |
   | `R2_READ_SECRET_ACCESS_KEY` | site token secret |

   Never add the upload key to Vercel.
4. Click **Deploy**. Do step 2 first: the build reads the data, so the bucket should already hold a snapshot.

Every push to `main` redeploys the site. Data updates need no push: the site picks up each upload within about five
minutes.

## Day to day

- **Laptop on:** nothing to do.
- **Laptop off or asleep:** the site keeps serving the last upload. After 18 hours the sidebar shows the data as
  stale. Scheduled tasks catch up when the laptop wakes.
- **Upload failing:** the publish itself still succeeds locally; `website.log` shows `upload failed: ...`, and the
  task's exit code is 3.
- **Stop hosting:** delete `web/.env.upload`. Uploads stop, and the site keeps the last snapshot until you remove
  the project from Vercel.

## Checks built in

- **Integrity:** the uploader checks every file against the publisher's sha256 manifest before sending anything. It
  uploads the files first and the manifest last, so the site never reads a half-uploaded snapshot. It never replaces
  a newer hosted snapshot with an older one.
- **What is uploaded:** only the publisher's public output, `web/.data/snapshot` and `web/.data/history`.
- **Pruning:** it keeps the newest 24 forecast snapshots and 3 player snapshots in the bucket.
- **Reading:** the site re-checks every file's sha256 and the data contract before showing it, exactly as it does
  locally.
- **Tests:** `cd web && npm test` runs the uploader against a local stand-in for R2 (`scripts/fake-r2.mjs`).
