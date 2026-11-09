import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end checks against the production build, reading the local snapshot (web/.data/snapshot).
 * Uses the Microsoft Edge already installed on this machine, so no browser download is needed.
 *   npm run build && npm run e2e
 * Against a deployed site instead (read-only: the tests only browse), with no local server:
 *   E2E_BASE_URL=https://matchup-dna.vercel.app npm run e2e
 */
const PORT = 3100;
const REMOTE = process.env.E2E_BASE_URL?.replace(/\/$/, "");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  workers: REMOTE ? 2 : 4,   // the accessibility scans are CPU-heavy; a deployed site gets a gentler load
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: REMOTE ?? `http://localhost:${PORT}`, channel: "msedge", trace: "off" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Edge"], channel: "msedge", viewport: { width: 1440, height: 1000 } } },
    { name: "phone", use: { channel: "msedge", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 } },
  ],
  webServer: REMOTE ? undefined : {
    command: `npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { NEXT_TELEMETRY_DISABLED: "1" },
  },
});
