import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fakeR2 } from "./fake-r2.mjs";
import { KEEP, upload } from "./upload-snapshot.mjs";

const sha = (text) => createHash("sha256").update(text, "utf8").digest("hex");

async function snapshot(root, stamp, files) {
  for (const [name, body] of Object.entries(files)) {
    await mkdir(path.dirname(path.join(root, "v1", stamp, name)), { recursive: true });
    await writeFile(path.join(root, "v1", stamp, name), body);
  }
  const manifest = { schema_version: "1", snapshot: stamp, files: Object.fromEntries(Object.entries(files).map(([n, b]) => [n, sha(b)])) };
  await writeFile(path.join(root, "v1", "manifest.json"), JSON.stringify(manifest));
}

test("uploads files before the manifest, skips repeats, refuses older or damaged snapshots, and prunes", async () => {
  const r2 = fakeR2();
  const port = await r2.listen();
  const root = await mkdtemp(path.join(tmpdir(), "upload-"));
  const env = { R2_ACCOUNT_ID: "acct", R2_BUCKET: "site", R2_UPLOAD_ACCESS_KEY_ID: "id", R2_UPLOAD_SECRET_ACCESS_KEY: "secret",
                R2_ENDPOINT: `http://127.0.0.1:${port}` };
  const quiet = { env, root, log: () => {} };
  try {
    assert.match(await upload("snapshot", { ...quiet, env: {} }), /not configured/);

    await snapshot(root, "20261109T073500Z", { "status.json": "{\"a\":1}", "matches/index.json": "[]" });
    assert.match(await upload("snapshot", quiet), /uploaded snapshot 20261109T073500Z: 2 files/);
    const puts = r2.requests.filter((r) => r.method === "PUT").map((r) => r.key);
    assert.equal(puts.at(-1), "snapshot/v1/manifest.json");                      // the manifest goes last
    assert.equal(r2.objects.get("site/snapshot/v1/20261109T073500Z/status.json").body.toString(), "{\"a\":1}");
    assert.match(r2.objects.get("site/snapshot/v1/20261109T073500Z/status.json").cache, /immutable/);

    assert.match(await upload("snapshot", quiet), /already hosted/);             // nothing new: nothing sent

    await snapshot(root, "20261108T073500Z", { "status.json": "{}" });           // older than the hosted one
    await assert.rejects(upload("snapshot", quiet), /newer than the local one/);

    await snapshot(root, "20261109T093500Z", { "status.json": "{\"a\":2}" });
    await writeFile(path.join(root, "v1", "20261109T093500Z", "status.json"), "tampered");
    await assert.rejects(upload("snapshot", quiet), /does not match the manifest/);
    assert.equal(JSON.parse(r2.objects.get("site/snapshot/v1/manifest.json").body).snapshot, "20261109T073500Z");

    for (let i = 0; i < KEEP.snapshot + 2; i++) {                                // prune to the newest KEEP
      await snapshot(root, `202611${String(10 + Math.floor(i / 24)).padStart(2, "0")}T${String(i % 24).padStart(2, "0")}3500Z`, { "status.json": `{"i":${i}}` });
      await upload("snapshot", quiet);
    }
    const hosted = new Set([...r2.objects.keys()].filter((k) => /\/v1\/\d{8}T/.test(k)).map((k) => k.split("/")[3]));
    assert.equal(hosted.size, KEEP.snapshot);
    assert.ok(hosted.has(JSON.parse(r2.objects.get("site/snapshot/v1/manifest.json").body).snapshot));
  } finally {
    await r2.close();
    await rm(root, { recursive: true, force: true });
  }
});
