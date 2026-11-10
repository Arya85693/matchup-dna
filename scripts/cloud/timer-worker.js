// Matchup DNA timer (Phase 8): a Cloudflare Worker whose Cron Triggers start the GitHub workflows.
//
// GitHub's own schedule proved unreliable for this repository (on 10 November 2026 it started one scheduled run in
// about eleven hours). A workflow_dispatch request starts a run within seconds, so this Worker sends them:
//   "*/15 * * * *"  every 15 minutes  -> Forecast (forecasts, results, ledger, site)
//   "50 12 * * *"   12:50 UTC daily   -> Players (ratings, head-to-heads, photos); 07:50 Eastern in winter
// Overlapping requests are harmless: the workflows' concurrency group runs them one at a time.
//
// Setup (Cloudflare dashboard, no command line):
//   Workers & Pages -> Create -> Worker "matchup-dna-timer" -> Edit code: paste this file -> Deploy
//   Settings -> Variables and Secrets -> Secret GITHUB_TOKEN = a fine-grained token for Arya85693/matchup-dna only,
//     with Repository permissions -> Actions: Read and write
//   Settings -> Triggers -> Cron Triggers -> "*/15 * * * *" and "50 12 * * *"
// The Worker's web address only shows a short description; it never starts a run.

const REPO = "https://api.github.com/repos/Arya85693/matchup-dna/actions/workflows";
const DAILY_PLAYERS = "50 12 * * *";

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(start(env, event.cron === DAILY_PLAYERS ? "players.yml" : "forecast.yml"));
  },
  async fetch() {
    return new Response("Matchup DNA timer: starts the Forecast workflow every 15 minutes and Players once a day.\n", {
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  },
};

async function start(env, workflow) {
  const response = await fetch(`${REPO}/${workflow}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "matchup-dna-timer",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (response.status !== 204) {
    console.log(`${workflow} not started: HTTP ${response.status} ${await response.text()}`);
  }
}
