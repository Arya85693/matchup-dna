/**
 * A minimal in-memory stand-in for the S3 API that Cloudflare R2 offers (GET, PUT, DELETE, ListObjectsV2), for tests
 * of the uploader and the hosted reader. It checks that every request is signed, not that the signature is valid.
 *
 *     node web/scripts/fake-r2.mjs 4599      serve on a port until stopped
 */
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import path from "node:path";

export function fakeR2() {
  const objects = new Map();          // "bucket/key" -> { body, headers }
  const requests = [];
  const server = createServer(async (req, res) => {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const url = new URL(req.url, "http://localhost");
    const [bucket, ...rest] = url.pathname.slice(1).split("/");
    const key = rest.map(decodeURIComponent).join("/");
    requests.push({ method: req.method, key, query: url.search });
    if (!/^AWS4-HMAC-SHA256 Credential=/.test(req.headers.authorization ?? "")) {
      res.writeHead(403).end("unsigned");
      return;
    }
    const id = `${bucket}/${key}`;
    if (req.method === "PUT") {
      const existing = objects.get(id);
      if ((req.headers["if-none-match"] === "*" && existing) ||
          (req.headers["if-match"] && (!existing || existing.etag !== req.headers["if-match"]))) {
        res.writeHead(412).end("<Error><Code>PreconditionFailed</Code></Error>");
        return;
      }
      const body = Buffer.concat(chunks);
      const etag = `"${createHash("md5").update(body).update(String(Date.now() + Math.random())).digest("hex")}"`;
      objects.set(id, { body, etag, type: req.headers["content-type"], cache: req.headers["cache-control"],
                        sha256: req.headers["x-amz-meta-sha256"] });
      res.writeHead(200, { ETag: etag }).end();
    } else if (req.method === "DELETE") {
      objects.delete(id);
      res.writeHead(204).end();
    } else if (req.method === "GET" && url.searchParams.get("list-type") === "2") {
      const prefix = url.searchParams.get("prefix") ?? "";
      const delimiter = url.searchParams.get("delimiter");
      const keys = [...objects.keys()].filter((k) => k.startsWith(`${bucket}/${prefix}`)).map((k) => k.slice(bucket.length + 1)).sort();
      const folders = delimiter ? [...new Set(keys.map((k) => k.slice(prefix.length)).filter((k) => k.includes(delimiter))
        .map((k) => prefix + k.slice(0, k.indexOf(delimiter) + 1)))] : [];
      const contents = delimiter ? keys.filter((k) => !k.slice(prefix.length).includes(delimiter)) : keys;
      res.writeHead(200, { "Content-Type": "application/xml" }).end(
        `<?xml version="1.0"?><ListBucketResult><Name>${bucket}</Name><Prefix>${prefix}</Prefix><IsTruncated>false</IsTruncated>` +
        contents.map((k) => `<Contents><Key>${k}</Key></Contents>`).join("") +
        folders.map((p) => `<CommonPrefixes><Prefix>${p}</Prefix></CommonPrefixes>`).join("") + `</ListBucketResult>`);
    } else if (req.method === "GET") {
      const hit = objects.get(id);
      if (!hit) res.writeHead(404).end("<Error><Code>NoSuchKey</Code></Error>");
      else res.writeHead(200, { "Content-Type": hit.type ?? "application/octet-stream", ETag: hit.etag,
                                ...(hit.sha256 ? { "x-amz-meta-sha256": hit.sha256 } : {}) }).end(hit.body);
    } else {
      res.writeHead(405).end();
    }
  });
  return {
    objects, requests,
    listen: (port = 0) => new Promise((resolve) => server.listen(port, "127.0.0.1", () => resolve(server.address().port))),
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = await fakeR2().listen(Number(process.argv[2] ?? 4599));
  console.log(`fake R2 on http://127.0.0.1:${port}`);
}
