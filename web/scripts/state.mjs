#!/usr/bin/env node
/**
 * Moves the forecasting state between a machine and the private state bucket (Cloudflare R2), for runs on GitHub
 * Actions (Phase 8). The state bucket is separate from the site's bucket; the site's key cannot read it.
 *
 *     node web/scripts/state.mjs pack <name> <path> [<path> ...]     tar.gz the paths (from the repo root) and upload
 *     node web/scripts/state.mjs unpack <name>                       download, check, and extract into the repo root
 *     node web/scripts/state.mjs pull-store <slot> [--allow-missing]  download store/<slot>/live.sqlite
 *     node web/scripts/state.mjs push-store <slot>                    upload it back, only if nobody changed it meanwhile
 *     node web/scripts/state.mjs put <key> <file> | get <key> <file>  one file (e.g. a rehearsal store for comparison)
 *
 * <slot> is "live" for the official store and "shadow" for the trial runs, which never touch the official one.
 * Keys: R2_ACCOUNT_ID, R2_STATE_BUCKET, R2_STATE_ACCESS_KEY_ID, R2_STATE_SECRET_ACCESS_KEY, from the environment
 * (GitHub secrets) or web/.env.state (never committed).
 *
 * Safety rules:
 * - Every object carries the sha256 of its bytes; a download that does not match is refused.
 * - push-store uploads with If-Match on the version pull-store downloaded (If-None-Match for a new store), so two runs
 *   can never silently overwrite each other: the later upload is refused (HTTP 412) and the run fails loudly.
 * - Each push-store also keeps a dated backup copy (store/<slot>/backups/), the newest BACKUPS kept.
 */
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AwsClient } from "aws4fetch";

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = path.resolve(WEB, "..");
const BACKUPS = 60;
const SLOTS = new Set(["live", "shadow", "itf"]);   // itf: the ITF extension's store (data/store/itf.sqlite)
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
// On Windows, Windows' own tar (bsdtar). Git Bash's GNU tar, first on the PATH on GitHub's Windows machines, reads
// "C:\..." as a remote host called C.
const TAR = process.platform === "win32" ? path.join(process.env.SystemRoot ?? "C:\\Windows", "System32", "tar.exe") : "tar";

export function bucket(env = process.env) {
  const { R2_ACCOUNT_ID: account, R2_STATE_BUCKET: name = "matchup-dna-state",
          R2_STATE_ACCESS_KEY_ID: id, R2_STATE_SECRET_ACCESS_KEY: secret } = env;
  if (!account || !id || !secret) throw new Error("state keys are missing (R2_ACCOUNT_ID, R2_STATE_ACCESS_KEY_ID, R2_STATE_SECRET_ACCESS_KEY)");
  const endpoint = (env.R2_ENDPOINT ?? `https://${account}.r2.cloudflarestorage.com`).replace(/\/$/, "");
  const client = new AwsClient({ accessKeyId: id, secretAccessKey: secret, service: "s3", region: "auto", retries: 0 });
  const url = (key) => `${endpoint}/${name}/${key.split("/").map(encodeURIComponent).join("/")}`;

  async function call(key, init, minutes = 10, target = url(key)) {
    for (let attempt = 1; ; attempt++) {
      try {
        const response = await fetch(await client.sign(target, init), { signal: AbortSignal.timeout(minutes * 60_000) });
        if (response.status < 500 || attempt === 3) return response;
      } catch (error) {
        if (attempt === 3) throw error;
      }
      await new Promise((r) => setTimeout(r, 2000 * attempt));
    }
  }
  return {
    /** Uploads bytes with their sha256 as metadata. `condition`: {"If-Match": etag} or {"If-None-Match": "*"}. */
    async put(key, bytes, condition = {}) {
      const response = await call(key, { method: "PUT", body: bytes, headers: {
        "x-amz-content-sha256": "UNSIGNED-PAYLOAD", "x-amz-meta-sha256": sha256(bytes),
        "Content-Type": "application/octet-stream", ...condition } });
      const text = await response.text();
      if (response.status === 412) throw new Error(`${key} changed since it was downloaded (or already exists); not overwritten`);
      if (!response.ok) throw new Error(`upload ${key}: ${response.status} ${text.slice(0, 200)}`);
      return response.headers.get("etag");
    },
    /** {bytes, etag} or null when absent; refuses bytes that do not match their recorded sha256. */
    async get(key) {
      const response = await call(key, { method: "GET" });
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`download ${key}: ${response.status} ${(await response.text()).slice(0, 200)}`);
      const bytes = Buffer.from(await response.arrayBuffer());
      const recorded = response.headers.get("x-amz-meta-sha256");
      if (recorded && recorded !== sha256(bytes)) throw new Error(`${key} does not match its recorded sha256; refused`);
      return { bytes, etag: response.headers.get("etag") };
    },
    async list(prefix) {
      const target = `${endpoint}/${name}?list-type=2&prefix=${encodeURIComponent(prefix)}`;
      const response = await call(prefix, { method: "GET" }, 2, target);
      const xml = await response.text();
      return [...xml.matchAll(/<Key>([^<]*)<\/Key>/g)].map((m) => m[1]);
    },
    async remove(key) {
      const response = await call(key, { method: "DELETE" });
      if (!response.ok && response.status !== 404) throw new Error(`delete ${key}: ${response.status}`);
    },
  };
}

const storeFile = (slot) => path.join(ROOT, "data", "store", slot === "live" ? "live.sqlite" : `${slot}.sqlite`);
const etagFile = (slot) => path.join(ROOT, "data", "store", `.${slot}.etag`);

async function main([command, ...args]) {
  const envFile = path.join(WEB, ".env.state");
  if (existsSync(envFile)) process.loadEnvFile(envFile);
  const b = bucket();
  if (command === "pack") {
    const [name, ...paths] = args;
    if (!name || !paths.length) throw new Error("pack <name> <path> [...]");
    const archive = path.join(tmpdir(), `state-${name}-${process.pid}.tar.gz`);
    execFileSync(TAR, ["-czf", archive, "--exclude", "*.etag", ...paths], { cwd: ROOT, stdio: "inherit" });
    const bytes = readFileSync(archive);
    rmSync(archive);
    await b.put(`archives/${name}.tar.gz`, bytes);
    console.log(`packed ${name}: ${(bytes.length / 1e6).toFixed(1)} MB (${paths.join(", ")})`);
  } else if (command === "unpack") {
    const [name] = args;
    const found = await b.get(`archives/${name}.tar.gz`);
    if (!found) throw new Error(`archive ${name} not found`);
    const archive = path.join(tmpdir(), `state-${name}-${process.pid}.tar.gz`);
    writeFileSync(archive, found.bytes);
    execFileSync(TAR, ["-xzf", archive], { cwd: ROOT, stdio: "inherit" });
    rmSync(archive);
    console.log(`unpacked ${name}: ${(found.bytes.length / 1e6).toFixed(1)} MB`);
  } else if (command === "pull-store") {
    const [slot, flag] = args;
    if (!SLOTS.has(slot)) throw new Error(`slot must be one of ${[...SLOTS].join(", ")}`);
    mkdirSync(path.dirname(storeFile(slot)), { recursive: true });
    const found = await b.get(`store/${slot}/live.sqlite`);
    if (!found) {
      if (flag !== "--allow-missing") throw new Error(`no ${slot} store in the state bucket`);
      writeFileSync(etagFile(slot), "*");
      console.log(`no ${slot} store yet; the first push will create it`);
      return;
    }
    writeFileSync(storeFile(slot), found.bytes);
    writeFileSync(etagFile(slot), found.etag);
    console.log(`pulled ${slot} store: ${(found.bytes.length / 1e6).toFixed(1)} MB, sha256 ${sha256(found.bytes).slice(0, 12)}`);
  } else if (command === "push-store") {
    const [slot] = args;
    if (!SLOTS.has(slot)) throw new Error(`slot must be one of ${[...SLOTS].join(", ")}`);
    if (!existsSync(etagFile(slot))) throw new Error(`pull-store ${slot} first: there is no version to check against`);
    const etag = readFileSync(etagFile(slot), "utf8").trim();
    const bytes = readFileSync(storeFile(slot));
    const condition = etag === "*" ? { "If-None-Match": "*" } : { "If-Match": etag };
    const next = await b.put(`store/${slot}/live.sqlite`, bytes, condition);
    writeFileSync(etagFile(slot), next);
    const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
    await b.put(`store/${slot}/backups/${stamp}.sqlite`, bytes);
    const backups = (await b.list(`store/${slot}/backups/`)).sort();
    for (const old of backups.slice(0, Math.max(0, backups.length - BACKUPS))) await b.remove(old);
    console.log(`pushed ${slot} store: ${(bytes.length / 1e6).toFixed(1)} MB, sha256 ${sha256(bytes).slice(0, 12)}; backup ${stamp}`);
  } else if (command === "put") {
    const [key, file] = args;
    await b.put(key, readFileSync(path.resolve(file)));
    console.log(`put ${key}`);
  } else if (command === "get") {
    const [key, file] = args;
    const found = await b.get(key);
    if (!found) throw new Error(`${key} not found`);
    mkdirSync(path.dirname(path.resolve(file)), { recursive: true });
    writeFileSync(path.resolve(file), found.bytes);
    console.log(`got ${key}`);
  } else {
    throw new Error("commands: pack, unpack, pull-store, push-store, put, get");
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    await main(process.argv.slice(2));
  } catch (error) {
    console.error(`state: ${error.message}`);
    process.exitCode = 1;
  }
}
