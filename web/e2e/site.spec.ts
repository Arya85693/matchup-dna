import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PAGES = ["/", "/matches", "/players", "/itf", "/lab", "/archive", "/methodology", "/status"];

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
  // Measure colours at rest, not halfway through an entrance animation.
  await page.evaluate(() => Promise.all(document.getAnimations()
    .filter((x) => x.effect?.getComputedTiming().iterations !== Infinity)
    .map((x) => x.finished.catch(() => undefined))));
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
    expect(text).toMatch(/Forecast once a start time is set|Not forecast|No forecast|Identity check/);
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
  await expect(page.locator("main section h2").first()).toBeVisible();          // an event group's title
});

test("old research addresses redirect to the Model Lab", async ({ page }) => {
  await page.goto("/research/market");
  await expect(page).toHaveURL(/\/lab$/);
});

test("players: filters, sorting, row navigation and comparison", async ({ page }) => {
  test.setTimeout(120_000);
  const problems = watch(page);
  await page.goto("/players", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /^WTA/ }).click();
  await expect(page).toHaveURL(/tour=WTA/);
  await page.getByRole("group", { name: "Surface" }).getByRole("button", { name: "Clay" }).click();
  await expect(page.locator('th[aria-sort="descending"]')).toContainText("Clay");
  const elo = page.getByRole("button", { name: "Elo", exact: true });
  await elo.click();
  await expect(page.locator('th[aria-sort="descending"]')).toContainText("Elo");
  await elo.click();
  await expect(page.locator('th[aria-sort="ascending"]')).toContainText("Elo");

  await page.locator("#player-search").fill("zzzz-no-such-player");
  await expect(page.getByText(/No players match/)).toBeVisible();
  await page.getByRole("button", { name: "Clear search and filters" }).click();
  await expect(page.locator("tbody tr")).not.toHaveCount(1);

  const spark = page.locator('tbody svg[role="img"]').first();
  if (await spark.isVisible()) {
    await spark.hover();
    await expect(page.getByRole("tooltip").filter({ hasText: /\d{4}/ }).first()).toBeVisible();
  }

  // Compare opens on the tour being browsed, and only offers players from that tour.
  await page.getByRole("link", { name: "Compare players" }).click();
  await expect(page).toHaveURL(/\/players\/compare\?tour=WTA$/);
  const pickers = page.getByRole("combobox");
  await pickers.nth(0).click();
  for (const text of await page.getByRole("option").allTextContents()) expect(text).toContain("WTA");
  await pickers.nth(0).press("ArrowDown");
  await pickers.nth(0).press("Enter");
  await expect(page).toHaveURL(/\/players\/compare\?tour=WTA&a=-?\d+$/);
  await page.getByRole("combobox").nth(1).click();
  await page.getByRole("option").first().click();
  await expect(page).toHaveURL(/\/players\/compare\?tour=WTA&a=-?\d+&b=-?\d+/);
  await expect(page.getByRole("region", { name: "Statistics" })).toBeVisible();
  const h2h = page.getByRole("region", { name: "Head to head", exact: true });
  await expect(h2h).toContainText(/Never played before|\d+ meetings?/);
  await noHorizontalScroll(page);
  await accessible(page);

  // Switching tour starts a new comparison with that tour's players.
  await page.getByRole("group", { name: "Tour" }).getByRole("button", { name: /^ATP/ }).click();
  await expect(page).toHaveURL(/\/players\/compare\?tour=ATP$/);
  await page.getByRole("combobox").nth(0).click();
  for (const text of await page.getByRole("option").allTextContents()) expect(text).toContain("ATP");

  await page.goto("/players", { waitUntil: "networkidle" });
  await page.locator("tbody tr").first().locator("td").nth(2).click();     // the Elo cell, not the name link
  await expect(page).toHaveURL(/\/players\/(atp|wta)--?\d+$/);
  await expect(page.getByText("Elo over time")).toBeVisible();
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

test("model lab: every tab renders, passes accessibility checks and is keyboard navigable", async ({ page }) => {
  test.setTimeout(120_000);
  const problems = watch(page);
  await page.goto("/lab", { waitUntil: "networkidle" });
  for (const name of ["Live record", "Benchmarks", "Calibration", "Market", "Models"]) {
    await page.getByRole("tab", { name }).click();
    await expect(page.getByRole("tabpanel")).toBeVisible();
    await noHorizontalScroll(page);
    await accessible(page);
  }
  await page.getByRole("tab", { name: "Market" }).click();
  await expect(page.getByText("The betting market forecast better than Matchup DNA.")).toBeVisible();
  await expect(page.getByText("The model did not demonstrate a profitable market edge.")).toBeVisible();
  await page.getByRole("tab", { name: "Market" }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Models" })).toHaveAttribute("aria-selected", "true");
  await expect(page).toHaveURL(/#models$/);
  await page.goto("/lab#calibration", { waitUntil: "networkidle" });
  await expect(page.getByRole("tab", { name: "Calibration" })).toHaveAttribute("aria-selected", "true");
  expect(problems).toEqual([]);
});


test("matches board: majors filter and two-sided bars", async ({ page }) => {
  const problems = watch(page);
  await page.goto("/matches", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Majors and 1000s only" }).click();
  await expect(page).toHaveURL(/majors=1/);
  await page.getByRole("button", { name: "Majors and 1000s only" }).click();
  await expect(page.locator("main section[aria-label] a[href^='/matches/']").first()).toBeVisible();
  await noHorizontalScroll(page);
  expect(problems).toEqual([]);
});

test("match page: forecast summary, contributions, timeline and verification", async ({ page }) => {
  test.setTimeout(90_000);
  const problems = watch(page);
  await page.goto("/matches", { waitUntil: "networkidle" });
  await page.locator("main section[aria-label] a[href^='/matches/']").first().click();
  await expect(page.getByRole("region", { name: "Forecast", exact: true })).toBeVisible();
  const bar = page.getByRole("button", { name: /log-odds toward/ }).first();
  if (await bar.count()) {
    await bar.focus();
    await expect(page.getByText(/log-odds toward/).first()).toBeVisible();
  }
  await expect(page.getByRole("region", { name: "Forecast history" })).toBeVisible();
  await page.getByText("Show records").click();
  await expect(page.getByText("Prediction id").first()).toBeVisible();
  await page.getByRole("tab", { name: /Round-aware/ }).click();
  await expect(page.getByRole("tab", { name: /Round-aware/ })).toHaveAttribute("aria-selected", "true");
  await noHorizontalScroll(page);
  await accessible(page);
  expect(problems).toEqual([]);
});

test("archive: match and ledger views, search, filters and inspection", async ({ page }) => {
  test.setTimeout(90_000);
  const problems = watch(page);
  await page.goto("/archive", { waitUntil: "networkidle" });
  const main = page.locator("main");
  const count = main.getByText(/\d+ of \d+ records/);
  const total = Number((await count.textContent())!.match(/of (\d+)/)![1]);
  expect(total).toBeGreaterThan(0);

  // Match view: open the first forecast version and check its inspection panel.
  const firstVersion = main.locator("li button[aria-expanded]").first();
  await firstVersion.click();
  await expect(firstVersion).toHaveAttribute("aria-expanded", "true");
  await expect(main.getByText("Feature snapshot")).toBeVisible();
  await expect(main.getByText(/matches the frozen protocol|differs from the frozen protocol/).first()).toBeVisible();
  await noHorizontalScroll(page);
  await accessible(page);

  // Search narrows the records; a nonsense query shows the empty state and clearing restores everything.
  await page.getByLabel("Search the archive").fill("zzzz-no-such-player");
  await expect(main.getByText("No forecasts match.")).toBeVisible();
  await main.getByRole("button", { name: "Clear filters" }).click();
  await expect(count).toHaveText(`${total} of ${total} records`);

  // Model filter keeps only one model's records.
  await page.getByRole("group", { name: "Model" }).getByRole("button", { name: "Round-aware" }).click();
  const roundAware = Number((await count.textContent())!.match(/^(\d+)/)![1]);
  expect(roundAware).toBeLessThanOrEqual(total);
  await page.getByRole("group", { name: "Model" }).getByRole("button", { name: "Both models" }).click();

  // Ledger view: one row per stored forecast, sortable, each inspectable.
  await page.getByRole("group", { name: "View" }).getByRole("button", { name: "Ledger records" }).click();
  await expect(main.locator("tbody tr")).toHaveCount(total);
  const position = main.getByRole("columnheader", { name: "#" });
  await position.getByRole("button").click();
  await expect(position).toHaveAttribute("aria-sort", "ascending");
  const positions = await main.locator("tbody tr td:first-child").allTextContents();
  expect(positions.map(Number)).toEqual([...positions.map(Number)].sort((a, b) => a - b));
  await main.getByRole("button", { name: "Inspect" }).first().click();
  await expect(main.getByText("Feature snapshot")).toBeVisible();
  await noHorizontalScroll(page);
  await accessible(page);
  expect(problems).toEqual([]);
});

test("players: ATP and WTA ids are separate, and old addresses redirect only when unambiguous", async ({ page }) => {
  // The players route streams (it has a loading state), so a missing player shows the not-found page with status 200
  // and a noindex tag; check what is rendered rather than the status code.
  const notFound = async (path: string) => {
    await page.goto(path, { waitUntil: "networkidle" });
    return (await page.locator("h1").textContent()) === "Not found";
  };
  // 200748 is Venus Williams on the WTA and a different player on the ATP: each tour address loads its own player.
  await page.goto("/players/wta-200748", { waitUntil: "networkidle" });
  await expect(page.locator("h1")).toHaveText("Venus Williams");
  await page.goto("/players/atp-200748", { waitUntil: "networkidle" });
  await expect(page.locator("h1")).not.toHaveText(/Venus Williams|Not found/);
  expect(await notFound("/players/200748")).toBe(true);                    // ambiguous old address: never guessed
  expect(await notFound("/players/wta-999999999999")).toBe(true);

  // The top ATP player's old numeric address redirects to the tour address when no WTA player shares the id.
  await page.goto("/players", { waitUntil: "networkidle" });
  const href = await page.locator('main a[href^="/players/atp-"]').first().getAttribute("href");
  const id = href!.replace("/players/atp-", "");
  if (await notFound(`/players/wta-${id}`)) {
    await page.goto(`/players/${id}`, { waitUntil: "networkidle" });
    await expect(page).toHaveURL(new RegExp(`/players/atp-${id}$`));
  }
});

test("compare: the tour decides which player an id means", async ({ page }) => {
  await page.goto("/players/compare?tour=WTA&a=200748");
  await expect(page.getByRole("region", { name: "Players" })).toContainText("Venus Williams");
  await page.goto("/players/compare?tour=ATP&a=200748");
  await expect(page.getByRole("region", { name: "Players" })).not.toContainText("Venus Williams");
});

test("ITF: forecasts, the boards and the archive are labelled by circuit", async ({ page }) => {
  await page.goto("/itf");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("ITF World Tennis Tour");
  await expect(page.getByText(/ITF (Men|Women) · [MW]\d+/).first()).toBeVisible();
  const problems = watch(page);
  await page.locator("main a[href^='/matches/I-']").first().click();              // an ITF match page, as on the main tour
  await expect(page.getByRole("region", { name: "Forecast", exact: true })).toBeVisible();
  expect(problems).toEqual([]);
  await page.goto("/players");
  await page.getByRole("button", { name: "ITF", exact: true }).click();
  await expect(page).toHaveURL(/circuit=itf/);
  await page.getByRole("button", { name: /^ITF Women/ }).click();
  await expect(page.getByPlaceholder(/Search \d+ ITF Women players/)).toBeVisible();
  await page.goto("/archive");
  await page.getByRole("button", { name: "ITF", exact: true }).click();
  await expect(page.getByRole("button", { name: "ITF Women", exact: true })).toBeVisible();
});

test("ITF players: the same table, profiles and compare as the main tour", async ({ page }) => {
  await page.goto("/players?circuit=itf");                     // the address opens the ITF tab
  await expect(page.getByRole("button", { name: /^ITF Men/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^ATP/ })).toBeHidden();   // the main-tour board is the hidden one
  const first = page.locator('table a[href^="/players/itf/atp-"]').first();
  const href = await first.getAttribute("href");
  expect(href).toMatch(/^\/players\/itf\/atp--?\d+$/);
  await first.click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  await expect(page.getByText(/ITF Men · Elo #\d+/)).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Players" })).toHaveAttribute("href", "/players?circuit=itf");
  await page.getByRole("link", { name: "Compare with another player" }).click();
  await expect(page).toHaveURL(/\/players\/itf\/compare\?tour=ATP&a=/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Compare ITF players");
});
