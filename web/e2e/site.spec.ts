import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PAGES = ["/", "/matches", "/players", "/lab", "/archive", "/methodology", "/status"];

/** Fails the test on any console error, uncaught exception or failed request. */
function watch(page: Page) {
  const problems: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`page error: ${e.message}`));
  page.on("requestfailed", (r) => {
    // A navigation cancels in-flight prefetches (net::ERR_ABORTED); that is normal browser behaviour, not a failure.
    if (!r.failure()?.errorText.includes("ERR_ABORTED")) problems.push(`request failed: ${r.url()} ${r.failure()?.errorText ?? ""}`);
  });
  page.on("response", (r) => { if (r.status() >= 400 && !r.url().includes("/matches/M-000")) problems.push(`HTTP ${r.status()}: ${r.url()}`); });
  return problems;
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "page must not scroll sideways").toBeLessThanOrEqual(1);
}

async function accessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")})`)).toEqual([]);
}

for (const path of PAGES) {
  test(`${path} loads without errors, fits the screen and passes accessibility checks`, async ({ page }) => {
    test.setTimeout(60_000);   // the accessibility scan of long tables takes a while under parallel load
    const problems = watch(page);
    const response = await page.goto(path, { waitUntil: "networkidle" });
    expect(response?.status()).toBe(200);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator("main")).not.toContainText("could not be loaded");
    await noHorizontalScroll(page);
    await accessible(page);
    expect(problems).toEqual([]);
  });
}

test("every match page linked from the board loads without errors", async ({ page }) => {
  test.setTimeout(240_000);   // visits every listed match page in turn
  await page.goto("/matches", { waitUntil: "networkidle" });
  const tabs = page.getByRole("tablist", { name: "Day" }).getByRole("tab");
  const hrefs = new Set<string>();
  for (let i = 0; i < (await tabs.count()); i += 1) {
    await tabs.nth(i).click();
    for (const href of await page.locator('main a[href^="/matches/"]').evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""))) hrefs.add(href);
  }
  expect(hrefs.size).toBeGreaterThan(0);
  for (const href of hrefs) {
    const problems = watch(page);
    const response = await page.goto(href, { waitUntil: "networkidle" });
    expect(response?.status(), href).toBe(200);
    await expect(page.getByRole("tablist", { name: "Model" })).toBeVisible();
    await noHorizontalScroll(page).catch((e) => { throw new Error(`${href}: ${e.message}`); });
    expect(problems, href).toEqual([]);
    page.removeAllListeners();
  }
});

test("a match with a forecast passes accessibility checks", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  const first = page.locator('main a[href^="/matches/"]').first();
  await first.click();
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("tablist", { name: "Model" })).toBeVisible();
  await page.getByRole("tab", { name: /Round-aware/ }).click();
  await accessible(page);
});

test("matches without a forecast show a reason and never a number", async ({ page }) => {
  await page.goto("/matches", { waitUntil: "networkidle" });
  const tbc = page.getByRole("tab", { name: /Time TBC/ });
  test.skip((await tbc.count()) === 0, "no unscheduled matches in this snapshot");
  await tbc.click();
  const rows = page.locator("main li a[href^='/matches/']");
  expect(await rows.count()).toBeGreaterThan(0);
  for (const text of await rows.allInnerTexts()) {
    expect(text).not.toMatch(/\d+\.\d%/);
    expect(text).toMatch(/Awaiting start time|Not forecast|No forecast|Identity check/);
  }
});

test("an unknown match is a 404 with a way back", async ({ page }) => {
  const response = await page.goto("/matches/M-000000000000000000000000");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("link", { name: "Back to the overview" })).toBeVisible();
});

test("the tour filter is reflected in the address", async ({ page }) => {
  await page.goto("/matches", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "WTA", exact: true }).click();
  await expect(page).toHaveURL(/tour=WTA/);
  await expect(page.locator("main section h3").first()).toBeVisible();
});

test("old research addresses redirect to the Model Lab", async ({ page }) => {
  await page.goto("/research/market");
  await expect(page).toHaveURL(/\/lab$/);
});

test("players: list, profile, and comparison", async ({ page }) => {
  const problems = watch(page);
  await page.goto("/players", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "WTA", exact: true }).click();
  await page.getByRole("button", { name: /Clay/ }).click();
  const first = page.locator('main a[href^="/players/"]').first();
  await first.click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("Elo over time")).toBeVisible();
  await page.getByRole("button", { name: "3Y" }).click();
  await noHorizontalScroll(page);
  await accessible(page);
  const select = page.locator("#compare-with");
  const second = await select.locator("option:not([disabled])").first().getAttribute("value");
  await select.selectOption(second!);
  await expect(page).toHaveURL(/\/players\/compare\?a=-?\d+&b=-?\d+/);
  await expect(page.getByText("Side by side", { exact: true })).toBeVisible();
  await accessible(page);
  expect(problems).toEqual([]);
});

test("home: the carousel, the walkthrough and the Elo playground respond", async ({ page }) => {
  const problems = watch(page);
  await page.goto("/", { waitUntil: "networkidle" });
  const counter = page.getByText(/of \d+ upcoming forecasts/);
  const before = await counter.innerText();
  await page.getByRole("button", { name: "Next match" }).click();
  if (!before.endsWith("of 1 upcoming forecasts")) await expect(counter).not.toHaveText(before);
  await page.getByRole("button", { name: "After earlier rounds" }).click();
  await page.getByRole("button", { name: /Add the context/ }).click();
  await expect(page.getByText("Serve and return", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Rate every player/ }).click();
  await page.locator("#elo-b").fill("1400");
  await expect(page.getByText(/A wins \d+%/)).toContainText("A wins 98%");
  expect(problems).toEqual([]);
});
