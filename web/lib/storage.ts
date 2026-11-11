/**
 * Where the published snapshot is read from.
 *
 * - Hosted (Vercel): a private Cloudflare R2 bucket, read with a read-only key, when R2_ACCOUNT_ID, R2_BUCKET,
 *   R2_READ_ACCESS_KEY_ID and R2_READ_SECRET_ACCESS_KEY are set. The laptop uploads each snapshot there
 *   (scripts/upload-snapshot.mjs) after publishing it.
 * - Local (development): the folders the publishers write, web/.data/snapshot, web/.data/history and
 *   web/.data/itf-history (or SNAPSHOT_DIR, HISTORY_DIR and ITF_HISTORY_DIR).
 *
 * Both hold the same layout: <area>/v1/manifest.json naming a snapshot directory v1/<stamp>/ and every file's sha256.
 * Snapshot directories are never changed after they are written, so their files are cached in memory; the manifest is
 * re-read at most every MANIFEST_SECONDS. Local folders are read fresh every time. Server-only: the keys have no
 * NEXT_PUBLIC_ prefix, so Next.js never sends them to the browser.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { AwsClient } from "aws4fetch";

export type Area = "snapshot" | "history" | "itf-history";

const MANIFEST_SECONDS = 60;
const MAX_CACHED_FILES = 400;

const LOCAL: Record<Area, string> = {
  snapshot: process.env.SNAPSHOT_DIR ?? path.join(process.cwd(), ".data", "snapshot"),
  history: process.env.HISTORY_DIR ?? path.join(process.cwd(), ".data", "history"),
  "itf-history": process.env.ITF_HISTORY_DIR ?? path.join(process.cwd(), ".data", "itf-history"),
};

function remote() {
  const { R2_ACCOUNT_ID: account, R2_BUCKET: bucket, R2_READ_ACCESS_KEY_ID: id, R2_READ_SECRET_ACCESS_KEY: secret } = process.env;
  if (!account || !bucket || !id || !secret) return null;
  // R2_ENDPOINT is for tests against a local stand-in; on Vercel it is left unset.
  const endpoint = (process.env.R2_ENDPOINT ?? `https://${account}.r2.cloudflarestorage.com`).replace(/\/$/, "");
  return { base: `${endpoint}/${bucket}`, client: new AwsClient({ accessKeyId: id, secretAccessKey: secret, service: "s3", region: "auto" }) };
}

const R2 = remote();
export const source = R2 ? "hosted" : "local";

const files = new Map<string, string | null>();
const manifests = new Map<string, { text: string | null; at: number }>();

async function fetchText(area: Area, relative: string): Promise<string | null> {
  if (!R2) {
    try {
      // Local folders for development; kept out of build tracing.
      return await readFile(path.join(/*turbopackIgnore: true*/ LOCAL[area], relative), "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw error;
    }
  }
  const key = `${area}/${relative}`.split("/").map(encodeURIComponent).join("/");
  const signed = await R2.client.sign(`${R2.base}/${key}`, { method: "GET" });
  // A time limit, so a stalled storage request shows "not available" instead of holding the page.
  const response = await fetch(signed.url, { method: "GET", headers: signed.headers, signal: AbortSignal.timeout(15_000) });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`storage answered ${response.status}`);
  return await response.text();
}

/** A file's text, or null when it does not exist. Throws when the storage cannot be read. */
export async function readText(area: Area, relative: string): Promise<string | null> {
  const id = `${area}/${relative}`;
  if (!R2) return fetchText(area, relative);           // local files change during development: never cached
  if (relative.endsWith("manifest.json")) {
    const hit = manifests.get(id);
    if (hit && Date.now() - hit.at < MANIFEST_SECONDS * 1000) return hit.text;
    const text = await fetchText(area, relative);
    manifests.set(id, { text, at: Date.now() });
    return text;
  }
  if (files.has(id)) return files.get(id)!;
  const text = await fetchText(area, relative);
  if (text !== null) {
    if (files.size >= MAX_CACHED_FILES) files.delete(files.keys().next().value!);
    files.set(id, text);
  }
  return text;
}
