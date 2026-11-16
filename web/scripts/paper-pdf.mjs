// Prints working paper 1 to an A4 PDF with Chrome, from the built site.
//
//   npm run build && npx next start -p 3123      (in one terminal)
//   node scripts/paper-pdf.mjs                    (in another; or: npm run paper:pdf)
//
// Options: --url <page>  --out <file>  --channel <chrome|msedge|chromium>
// The article is printed on its own (site navigation removed) with the print rules in app/globals.css; the running
// footer carries the author, short title, version and page number. Every figure on the page comes from
// content/research/big-match.json, so the PDF shows exactly what the website shows.
import { chromium } from "playwright";

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, arg, i, all) =>
  (arg.startsWith("--") ? [...pairs, [arg.slice(2), all[i + 1]]] : pairs), []));
const url = args.url ?? "http://localhost:3123/research/big-matches";
const out = args.out ?? "public/research/big-matches.pdf";
const channel = args.channel ?? "chrome";

const browser = await chromium.launch(channel === "chromium" ? {} : { channel });
const page = await browser.newPage({ viewport: { width: 900, height: 1200 } });
await page.goto(url, { waitUntil: "networkidle" });
const meta = await page.evaluate(() => {
  const article = document.querySelector("article.paper");
  if (!article) throw new Error("no article.paper on the page");
  const m = article.querySelector("[data-paper-meta]")?.dataset ?? {};
  document.body.replaceChildren(article);
  return { version: m.version ?? "", short: m.short ?? document.title, author: m.author ?? "" };
});
await page.emulateMedia({ media: "print" });
await page.evaluate(() => document.fonts.ready);
const footer = `<div style="width:100%;padding:0 22mm;font-family:Georgia,serif;font-size:8.5px;color:#555;display:flex;justify-content:space-between;">
  <span>${meta.author} · ${meta.short} · Working paper v${meta.version}</span><span class="pageNumber"></span></div>`;
await page.pdf({
  path: out, format: "A4", printBackground: true, preferCSSPageSize: true, scale: 0.86,
  displayHeaderFooter: true, headerTemplate: "<span></span>", footerTemplate: footer,
});
await browser.close();
console.log(`wrote ${out}`);
