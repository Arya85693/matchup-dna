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
    title: "Do players choke in big matches?",
    subtitle: "Persistence of big-match performance in professional tennis, 2000–2026",
    date: "2026-11-14",
    version: "1.0",
    number: 1,
    evidence: "post-hoc",
    abstract:
      "Using 131,649 tour-level matches, we test whether some players consistently win semi-finals, finals and late " +
      "Slam and Masters rounds more or less often than their strength predicts. Differences between players in big " +
      "matches are about as large as luck alone would produce, and a player's record in 2012–2018 does not predict " +
      "their record in 2019–2026 beyond ordinary form. We find no measurable choke or clutch trait.",
    keywords: ["tennis", "pressure", "Elo", "calibration", "empirical Bayes", "persistence"],
    readingMinutes: 12,
  },
];

export const paper = (slug: string) => {
  const found = PAPERS.find((p) => p.slug === slug);
  if (!found) throw new Error(`No paper with slug ${slug}`);
  return found;
};

export const paperDate = (iso: string) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
