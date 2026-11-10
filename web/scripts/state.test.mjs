import assert from "node:assert/strict";
import test from "node:test";
import { fakeR2 } from "./fake-r2.mjs";
import { bucket } from "./state.mjs";

test("state bucket: checked downloads, and a store never silently overwritten", async () => {
  const r2 = fakeR2();
  const port = await r2.listen();
  const b = bucket({ R2_ACCOUNT_ID: "a", R2_STATE_BUCKET: "state", R2_STATE_ACCESS_KEY_ID: "k", R2_STATE_SECRET_ACCESS_KEY: "s",
                     R2_ENDPOINT: `http://127.0.0.1:${port}` });
  try {
    assert.equal(await b.get("store/live/live.sqlite"), null);

    const first = await b.put("store/live/live.sqlite", Buffer.from("v1"), { "If-None-Match": "*" });
    await assert.rejects(b.put("store/live/live.sqlite", Buffer.from("other"), { "If-None-Match": "*" }), /not overwritten/);

    const runA = await b.get("store/live/live.sqlite");                 // two runs download the same version
    const runB = await b.get("store/live/live.sqlite");
    assert.equal(runA.etag, first);
    await b.put("store/live/live.sqlite", Buffer.from("v2 from A"), { "If-Match": runA.etag });
    await assert.rejects(b.put("store/live/live.sqlite", Buffer.from("v2 from B"), { "If-Match": runB.etag }), /changed since/);
    assert.equal((await b.get("store/live/live.sqlite")).bytes.toString(), "v2 from A");   // A's work kept, B refused

    r2.objects.get("state/store/live/live.sqlite").body = Buffer.from("tampered");          // damaged in storage
    await assert.rejects(b.get("store/live/live.sqlite"), /does not match its recorded sha256/);

    await b.put("store/live/backups/20261109T000000Z.sqlite", Buffer.from("x"));
    await b.put("store/live/backups/20261110T000000Z.sqlite", Buffer.from("y"));
    assert.deepEqual(await b.list("store/live/backups/"),
                     ["store/live/backups/20261109T000000Z.sqlite", "store/live/backups/20261110T000000Z.sqlite"]);
  } finally {
    await r2.close();
  }
});
