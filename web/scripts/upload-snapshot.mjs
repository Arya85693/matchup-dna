#!/usr/bin/env node
/**
 * Uploads the newest local snapshot to the hosted copy (a private Cloudflare R2 bucket) that the deployed site reads.
 *
 *     node web/scripts/upload-snapshot.mjs snapshot     after `python -m web.publisher.publish`
 *     node web/scripts/upload-snapshot.mjs history      after `python -m web.publisher.players`
 *
 * Run by scripts/run_website.cmd after each scheduled publish. Keys come from web/.env.upload (never committed):
 * R2_ACCOUNT_ID, R2_BUCKET, R2_UPLOAD_ACCESS_KEY_ID, R2_UPLOAD_SECRET_ACCESS_KEY. Without them it does nothing and
 * says so, so the schedule works before hosting is set up.
 *
 * Order matters, so a reader never sees a half-uploaded snapshot:
 * 1. check every local file against the local manifest's sha256 (a damaged export is never uploaded);
 * 2. upload the files of v1/<stamp>/ (immutable once written);
 * 3. replace v1/manifest.json, which switches readers to the new snapshot;
 * 4. delete older snapshot directories, keeping the newest KEEP[area] (always including the new one).
 * Only public website files are uploaded: the publisher's output folders, nothing else.
 */
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AwsClient } from "aws4fetch";

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STAMP = /^\d{8}T\d{6}Z$/;
export const KEEP = { snapshot: 24, history: 3 };
const PARALLEL = 8;
const TIMEOUT_MS = 60_000;

export function storage(env) {
  const { R2_ACCOUNT_ID: account, R2_BUCKET: bucket, R2_UPLOAD_ACCESS_KEY_ID: id, R2_UPLOAD_SECRET_ACCESS_KEY: secret } = env;
  if (!account || !bucket || !id || !secret) return null;
  const endpoint = (env.R2_ENDPOINT ?? `https://${account}.r2.cloudflarestorage.com`).replace(/\/$/, "");
  const client = new AwsClient({ accessKeyId: id, secretAccessKey: secret, service: "s3", region: "auto", retries: 0 });
  const base = `${endpoint}/${bucket}`;
  const url = (key) => `${base}/${key.split("/").map(encodeURIComponent).join("/")}`;

  async function call(target, init = {}) {
    for (let attempt = 1; ; attempt++) {
      try {
        // Signed here, sent with a time limit, so a stalled connection fails (and is retried) instead of hanging.
        const response = await fetch(await client.sign(target, init), { signal: AbortSignal.timeout(TIMEOUT_MS) });
        if (response.status < 500 || attempt === 3) return response;
      } catch (error) {
        if (attempt === 3) throw error;
      }
      await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
    }
  }
  async function ok(response, what) {
    if (!response.ok) throw new Error(`${what}: storage answered ${response.status} ${(await response.text()).slice(0, 200)}`);
    return response;
  }
  return {
    async get(key) {
      const response = await call(url(key));
      if (response.status === 404) return null;
      return (await ok(response, `read ${key}`)).text();
    },
    async put(key, body, cacheControl) {
      await ok(await call(url(key), { method: "PUT", body,
        headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": cacheControl } }), `upload ${key}`);
    },
    async remove(key) {
      const response = await call(url(key), { method: "DELETE" });
      if (response.status !== 404) await ok(response, `delete ${key}`);
    },
    /** Keys under `prefix`; with `folders`, the immediate sub-folders instead. */
    async list(prefix, folders = false) {
      const found = [];
      let token = null;
      do {
        const q = new URLSearchParams({ "list-type": "2", prefix, ...(folders ? { delimiter: "/" } : {}),
                                        ...(token ? { "continuation-token": token } : {}) });
        const xml = await (await ok(await call(`${base}?${q}`), `list ${prefix}`)).text();
        const tag = folders ? /<Prefix>([^<]*)<\/Prefix>/g : /<Key>([^<]*)<\/Key>/g;
        const unescape = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&");
        for (const m of (folders ? xml.split("<CommonPrefixes>").slice(1).join("") : xml).matchAll(tag)) found.push(unescape(m[1]));
        token = /<IsTruncated>true<\/IsTruncated>/.test(xml) ? (/<NextContinuationToken>([^<]*)</.exec(xml)?.[1] ?? null) : null;
      } while (token);
      return found;
    },
  };
}

async function pool(items, work) {
  const queue = [...items];
  await Promise.all(Array.from({ length: Math.min(PARALLEL, queue.length) }, async () => {
    while (queue.length) await work(queue.shift());
  }));
}

/** Uploads the local snapshot of `area` ("snapshot" or "history"); returns a one-line summary. */
export async function upload(area, { env = process.env, root = path.join(WEB, ".data", area), log = console.log } = {}) {
  if (!(area in KEEP)) throw new Error(`unknown area "${area}": use snapshot or history`);
  const store = storage(env);
  if (!store) return "upload skipped: hosting is not configured (web/.env.upload)";
  const manifestText = await readFile(path.join(root, "v1", "manifest.json"), "utf8");
  const manifest = JSON.parse(manifestText);
  const stamp = manifest.snapshot;
  if (!STAMP.test(stamp)) throw new Error(`manifest names an invalid snapshot "${stamp}"`);

  const current = await store.get(`${area}/v1/manifest.json`);
  const hosted = current ? JSON.parse(current).snapshot : null;
  if (hosted === stamp) return `${area} ${stamp} is already hosted`;
  if (hosted && hosted > stamp) throw new Error(`the hosted ${area} (${hosted}) is newer than the local one (${stamp}); not replaced`);

  const names = Object.keys(manifest.files).sort();
  const bodies = new Map();
  for (const name of names) {
    if (name.includes("..") || name.startsWith("/")) throw new Error(`unsafe file name ${name}`);
    const body = await readFile(path.join(root, "v1", stamp, name), "utf8");
    if (createHash("sha256").update(body, "utf8").digest("hex") !== manifest.files[name]) {
      throw new Error(`${name} does not match the manifest; nothing uploaded`);
    }
    bodies.set(name, body);
  }
  await pool(names, (name) => store.put(`${area}/v1/${stamp}/${name}`, bodies.get(name), "public, max-age=31536000, immutable"));
  await store.put(`${area}/v1/manifest.json`, manifestText, "no-cache");

  const stamps = (await store.list(`${area}/v1/`, true))
    .map((p) => p.slice(`${area}/v1/`.length).replace(/\/$/, "")).filter((s) => STAMP.test(s)).sort();
  const old = stamps.filter((s) => s !== stamp).slice(0, Math.max(0, stamps.length - KEEP[area]));
  for (const s of old) {
    await pool(await store.list(`${area}/v1/${s}/`), (key) => store.remove(key));
  }
  return `uploaded ${area} ${stamp}: ${names.length} files${old.length ? `; removed ${old.length} older` : ""}`;
}

async function main() {
  const area = process.argv[2];
  const envFile = path.join(WEB, ".env.upload");
  if (existsSync(envFile)) process.loadEnvFile(envFile);
  try {
    console.log(await upload(area));
  } catch (error) {
    console.error(`upload failed: ${error.message}`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
