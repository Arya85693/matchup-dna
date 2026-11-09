/**
 * Reads the published snapshot. Today the source is the local folder the publisher writes (web/.data/snapshot, or
 * SNAPSHOT_DIR); at 7G the same functions read the hosted copy. Every file is checked against the manifest's sha256
 * and the contract before use. Nothing here computes a forecast.
 */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { z } from "zod";
import {
  ArchiveSchema, HistoryIndexSchema, HistoryManifestSchema, HistoryPlayerSchema, LedgerSchema, ManifestSchema, PlayersSchema, MatchIndexSchema, MatchPageSchema, ModelsSchema, StatusSchema, TrackRecordSchema,
  type Archive, type HistoryIndex, type HistoryPlayer, type Ledger, type Manifest, type Players, type MatchIndex, type MatchPage, type Models, type Status, type TrackRecord,
} from "./contract";

const ROOT = process.env.SNAPSHOT_DIR ?? path.join(process.cwd(), ".data", "snapshot");
const HISTORY_ROOT = process.env.HISTORY_DIR ?? path.join(process.cwd(), ".data", "history");

export type Loaded<T> = { ok: true; data: T } | { ok: false; reason: "not_found" | "unavailable"; detail: string };

async function readText(relative: string, root: string = ROOT): Promise<string | null> {
  try {
    // Local-folder source for development; replaced by the hosted snapshot at 7G, so it is kept out of build tracing.
    return await readFile(path.join(/*turbopackIgnore: true*/ root, relative), "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
}

export async function getManifest(): Promise<Loaded<Manifest>> {
  try {
    const text = await readText("v1/manifest.json");
    if (text === null) return { ok: false, reason: "unavailable", detail: "No snapshot has been published yet." };
    const parsed = ManifestSchema.safeParse(JSON.parse(text));
    if (!parsed.success) return { ok: false, reason: "unavailable", detail: "The snapshot manifest is not valid." };
    return { ok: true, data: parsed.data };
  } catch {
    return { ok: false, reason: "unavailable", detail: "The snapshot could not be read." };
  }
}

async function getFile<S extends z.ZodType>(schema: S, name: string): Promise<Loaded<z.infer<S>>> {
  const manifest = await getManifest();
  if (!manifest.ok) return manifest;
  const expected = manifest.data.files[name];
  if (!expected) return { ok: false, reason: "not_found", detail: `${name} is not in the snapshot.` };
  try {
    const text = await readText(`v1/${manifest.data.snapshot}/${name}`);
    if (text === null) return { ok: false, reason: "unavailable", detail: `${name} is listed but missing.` };
    const digest = createHash("sha256").update(text, "utf8").digest("hex");
    if (digest !== expected) return { ok: false, reason: "unavailable", detail: `${name} does not match its hash.` };
    const parsed = schema.safeParse(JSON.parse(text));
    if (!parsed.success) return { ok: false, reason: "unavailable", detail: `${name} failed validation.` };
    return { ok: true, data: parsed.data };
  } catch {
    return { ok: false, reason: "unavailable", detail: `${name} could not be read.` };
  }
}

export const getIndex = (): Promise<Loaded<MatchIndex>> => getFile(MatchIndexSchema, "matches/index.json");
export const getStatus = (): Promise<Loaded<Status>> => getFile(StatusSchema, "status.json");
export const getTrackRecord = (): Promise<Loaded<TrackRecord>> =>
  getFile(TrackRecordSchema, "research/track-record.json");

export const getModels = (): Promise<Loaded<Models>> => getFile(ModelsSchema, "models.json");
export const getArchive = (): Promise<Loaded<Archive>> => getFile(ArchiveSchema, "archive.json");
export const getPlayers = (): Promise<Loaded<Players>> => getFile(PlayersSchema, "players.json");
export const getLedger = (): Promise<Loaded<Ledger>> => getFile(LedgerSchema, "ledger/recent.json");

export async function getMatch(uid: string): Promise<Loaded<MatchPage>> {
  if (!/^M-[0-9a-f]{24}$/.test(uid)) return { ok: false, reason: "not_found", detail: "Unknown match." };
  return getFile(MatchPageSchema, `matches/${uid}.json`);
}

/** Player histories (web/.data/history, written by `python -m web.publisher.players`), checked like the snapshot. */
async function getHistoryFile<S extends z.ZodType>(schema: S, name: string, root: string = HISTORY_ROOT): Promise<Loaded<z.infer<S>>> {
  try {
    const text = await readText("v1/manifest.json", root);
    if (text === null) return { ok: false, reason: "unavailable", detail: "Player histories have not been published yet." };
    const manifest = HistoryManifestSchema.safeParse(JSON.parse(text));
    if (!manifest.success) return { ok: false, reason: "unavailable", detail: "The player manifest is not valid." };
    const expected = manifest.data.files[name];
    if (!expected) return { ok: false, reason: "not_found", detail: "No such player." };
    const body = await readText(`v1/${manifest.data.snapshot}/${name}`, root);
    if (body === null) return { ok: false, reason: "unavailable", detail: `${name} is missing.` };
    if (createHash("sha256").update(body, "utf8").digest("hex") !== expected) {
      return { ok: false, reason: "unavailable", detail: `${name} does not match its hash.` };
    }
    const parsed = schema.safeParse(JSON.parse(body));
    return parsed.success ? { ok: true, data: parsed.data } : { ok: false, reason: "unavailable", detail: `${name} failed validation.` };
  } catch {
    return { ok: false, reason: "unavailable", detail: "Player histories could not be read." };
  }
}

export const getHistoryIndex = (): Promise<Loaded<HistoryIndex>> => getHistoryFile(HistoryIndexSchema, "players/index.json");

/** A player by address, `atp-<id>` or `wta-<id>`. Canonical ids are positive for Sackmann players and negative for
 * players known only from newer providers; ATP and WTA ids are separate pools, so the tour is always part of it. */
export async function getHistoryPlayer(slug: string): Promise<Loaded<HistoryPlayer>> {
  const m = /^(atp|wta)-(-?\d{1,18})$/.exec(slug);
  if (!m) return { ok: false, reason: "not_found", detail: "No such player." };
  const loaded = await getHistoryFile(HistoryPlayerSchema, `players/${m[1]}-${m[2]}.json`);
  if (!loaded.ok) return loaded;
  const p = loaded.data.player;
  return p.tour.toLowerCase() === m[1] && String(p.id) === m[2] ? { ok: true, data: p } : { ok: false, reason: "not_found", detail: "No such player." };
}
