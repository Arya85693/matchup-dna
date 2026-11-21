/**
 * The Research tab's index. Each paper is one entry here plus its page at web/app/research/<slug>/page.tsx.
 * Newest first. `evidence` is the paper's standing, shown as a tag: "post-hoc" for an analysis run after the data
 * were seen, "pre-registered" for one fixed before.
 */
export type Paper = {
  slug: string;
  title: string;
  subtitle: string;
  date: string;          // ISO date of the current version
  version: string;
  number: number;        // the working-paper number, in order of first publication
  evidence: "post-hoc" | "pre-registered";
  abstract: string;      // one paragraph, plain text, for the index card
  keywords: string[];
  readingMinutes: number;
};

export const PAPERS: Paper[] = [
  {
    slug: "big-matches",
    title: "Do Players Choke in Big Matches?",
    subtitle: "Evidence from 26 Years of Professional Tennis",
    date: "2026-11-21",
    version: "4.1",
    number: 1,
    evidence: "post-hoc",
    abstract:
      "Does a tennis player's record in semi-finals, finals and other big matches carry information that Elo ratings " +
      "miss? Using 130,460 ATP and WTA main-tour matches from 2000 to May 2026, I test whether players differ beyond " +
      "chance in big matches, whether those differences persist, and whether past big-match records improve " +
      "out-of-sample forecasts. Big-match records vary about as much as chance predicts, no trait test survives " +
      "multiple-testing correction, and adding a player's big-match or clutch score did not improve forecasts of " +
      "7,476 later big matches. A modest trait cannot be ruled out. One tour-level pattern holds up: Elo is more " +
      "overconfident in WTA big matches than in regular WTA matches.",
    keywords: ["tennis", "forecasting", "Elo", "calibration", "shrinkage", "out-of-sample evaluation", "statistical power"],
    readingMinutes: 30,
  },
];

export const paper = (slug: string) => {
  const found = PAPERS.find((p) => p.slug === slug);
  if (!found) throw new Error(`No paper with slug ${slug}`);
  return found;
};

export const paperDate = (iso: string) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
