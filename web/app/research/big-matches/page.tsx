import type { Metadata } from "next";
import { Source_Serif_4 } from "next/font/google";
import {
  Dumbbell, Forest, GroupedBars, PowerCurves, StudyFlow, type BarGroup, type ForestGroup, type PowerPanel,
} from "@/components/research/charts";
import {
  Abstract, BackLink, Body, Cite, Cols, Eq, Figure, Footer, References, Section, Sheet, Statements, Subsection, Table,
  TitleBlock,
} from "@/components/research/Paper";
import { paper, paperDate } from "@/lib/papers";
import { BIG_MATCH } from "@/lib/research";

const serif = Source_Serif_4({ subsets: ["latin", "latin-ext"], variable: "--font-serif", display: "swap" });
const meta = paper("big-matches");
const AUTHOR = "Aryamaan Roy Choudhury";
const SHORT = "Do Players Choke in Big Matches?";

export const metadata: Metadata = { title: meta.title, description: meta.abstract };

// ---------------------------------------------------------------- data access (every figure comes from the export)
const r = BIG_MATCH;
const rb = r.robustness;
const fc = r.forecast;
const TOURS = ["ATP", "WTA"] as const;

/** A sentence in the text depends on this condition. If a rerun breaks it, the build fails rather than the paper
 *  quietly saying something the data no longer show. */
function ensure(condition: boolean, claim: string) {
  if (!condition) throw new Error(`Working paper 1: the claim "${claim}" no longer holds for the exported results`);
}

const two = (x: number) => x.toFixed(2);
const three = (x: number) => x.toFixed(3);
const signed = (x: number, d = 3) => { const shown = Math.abs(x).toFixed(d); return `${Number(shown) === 0 ? "" : x > 0 ? "+" : "−"}${shown}`; };
const pp = (x: number) => (100 * x).toFixed(1);
const pct = (x: number) => `${Math.round(x * 100)}%`;
const count = (x: number) => x.toLocaleString("en-GB");
const pv = (p: number) => (p < 0.001 ? "< 0.001" : p.toFixed(3));
const pEq = (p: number) => (p < 0.001 ? "p < 0.001" : `p = ${p.toFixed(3)}`); // in running text
const pts = (x: number) => x.toFixed(1);
const milli = (x: number) => signed(1000 * x, 2);              // log-loss differences, in thousandths
const diffCell = (d: number, low: number, high: number) =>
  Math.abs(1000 * low) < 0.005 && Math.abs(1000 * high) < 0.005 ? "0.00 (identical)" : `${milli(d)} (${milli(low)} to ${milli(high)})`;
const v = (name: string, sub?: string) => <>{name}{sub && <sub>{sub}</sub>}</>;
const interval = (c: { r: number; low: number; high: number }) => `${signed(c.r, 2)} (${signed(c.low, 2)} to ${signed(c.high, 2)})`;
const includesZero = (low: number, high: number) => low <= 0 && high >= 0;

const slope = (tour: string, kind: "big" | "regular", bo: number) =>
  r.calibration.find((c) => c.tour === tour && c.kind === kind && c.best_of === bo)!.slope;
const spread = (tour: string, set: string) => r.spread.find((s) => s.tour === tour && s.set === set)!;
const ps = (tour: string) => r.period_split[tour]!;
const sh = (tour: string) => r.split_half[tour]!;
const nullRow = (tour: string, test: string) => rb.null.find((n) => n.tour === tour && n.test === test)!;
const powerRow = (tour: string, test: string) => rb.power.rows.find((p) => p.tour === tour && p.test === test)!;
const game = (tour: string) => rb.games.find((g) => g.tour === tour)!;
const gameSet = (tour: string, set: string) => game(tour).spread.find((s) => s.set === set)!;
const within = (tour: string) => rb.within.find((w) => w.tour === tour)!;
const byFormat = (bo: number) => rb.format.find((f) => f.best_of === bo)!;
const calW = (key: string) => fc.calibration.window.find((c) => c.key === key)!;
const calP = (period: string, key: string) => fc.calibration.periods.find((c) => c.period === period && c.key === key)!;
const evaluation = (tour: string, subset = "big matches") => fc.evaluation.find((e) => e.tour === tour && e.subset === subset)!;
const model = (tour: string, name: string, subset = "big matches") => evaluation(tour, subset).models.find((m) => m.model === name)!;
const playersOf = (tour: string) => r.players.tours.find((t) => t.tour === tour)!;
const tauIndex = (tau: number) => rb.power.taus.indexOf(tau);
const evensAt = (tau: number) => rb.power.evens[tauIndex(tau)]!;
const powerAt = (tour: string, test: string, tau: number) => powerRow(tour, test).power[tauIndex(tau)]!;
const bound = (tour: string, test: string) => powerRow(tour, test).bound_points;
const boundText = (tour: string, test: string) => {
  const p = powerRow(tour, test);
  return p.bound_points === null ? "not reached on the grid"
    : `${pts(p.bound_points)} points (Monte Carlo range ${pts(p.bound_low_points!)} to ${pts(p.bound_high_points!)})`;
};

// ---------------------------------------------------------------- derived figures
const SETS: [string, string][] = [
  ["finals only", "Finals only"], ["semi-finals + finals", "Semi-finals and finals"],
  ["all big matches", "All big matches"], ["regular matches", "Regular matches"],
];
const bigSets = r.spread.filter((s) => s.set !== "regular matches");
const maxBigRatio = Math.max(...bigSets.map((s) => s.ratio));
const minBigRatio = Math.min(...bigSets.map((s) => s.ratio));
const family = rb.null.filter((n) => n.holm !== undefined);
const minHolm = Math.min(...family.map((n) => n.holm!));
const smallestRaw = family.reduce((a, b) => (b.p < a.p ? b : a));
const nominal = family.filter((n) => n.p < 0.05);
const atpClutch = nullRow("ATP", "clutch ratio");
const wtaBigAssoc = ps("WTA").forecasts["big-match"];
const bothEval = evaluation("both");
const bigDiff = model("both", "big").log_loss_diff!;
const clutchDiff = model("both", "clutch").log_loss_diff!;
const SCORE_MODELS = ["big", "clutch", "big_eb", "clutch_eb", "big_recent", "clutch_recent"] as const;
const scoreRows = ["big matches", "big matches, both players with 10+ earlier big"].flatMap((subset) =>
  (["ATP", "WTA", "both"] as const).flatMap((t) => SCORE_MODELS.map((m) => model(t, m, subset))));
const largestScoreGain = Math.min(...scoreRows.map((m) => m.log_loss_diff!));
const wtaCal = calW("WTA bo3");
const wtaM0 = model("WTA", "M0");
const atpM0 = model("ATP", "M0");
const lastPeriod = "2018-2026";
const atpBig = rb.format.reduce((s, f) => s + f.big_matches, 0);
const SAMPLE = {
  ATP: { matches: game("ATP").matches, big: atpBig },
  WTA: { matches: game("WTA").matches, big: r.big_matches - atpBig },
};
const atpBound = bound("ATP", "clutch ratio")!;
const wtaBound = bound("WTA", "clutch ratio")!;
const PER_100_SD = 100 * Math.sqrt((0.7 * 0.3) / 100);        // chance sd per match over 100 matches at p = 0.7
const atpClutchBetas = fc.betas.clutch!.ATP!.map((b) => b.beta);
const minSensitivityP = Math.min(...rb.sensitivity.flatMap((s) => [s.big_p, s.clutch_p]));
const minSensitivityClutchP = Math.min(...rb.sensitivity.map((s) => s.clutch_p));
const power015 = Math.max(...rb.power.rows.filter((p) => p.test !== "ratio regular matches").map((p) => p.power[tauIndex(0.15)]!));
const power04 = Math.min(...TOURS.flatMap((t) => [powerAt(t, "clutch ratio", 0.4), powerAt(t, "split-half r", 0.4)]));

// The claims the text makes about these figures.
ensure(r.matches === SAMPLE.ATP.matches + SAMPLE.WTA.matches, "the tour match counts add up");
ensure(meta.abstract.includes(count(r.matches)) && meta.abstract.includes(count(bothEval.matches)),
  "the index-card abstract (lib/papers.ts) quotes the current match counts");
ensure(minHolm >= 0.05, "no trait statistic is significant after Holm's correction");
ensure(TOURS.every((t) => includesZero(sh(t).low, sh(t).high)), "both split-half intervals include zero");
ensure(scoreRows.every((m) => includesZero(m.log_loss_low!, m.log_loss_high!)), "every player-score interval includes zero");
ensure(Math.abs(bigDiff) < 0.0005 && Math.abs(clutchDiff) < 0.0005, "the primary score models change log loss by under 0.0005");
ensure(wtaM0.log_loss_low! > 0, "separate WTA big-match calibration improves out-of-sample WTA big-match log loss");
ensure(includesZero(atpM0.log_loss_low!, atpM0.log_loss_high!), "the ATP calibration split makes no clear difference");
ensure(wtaCal.cluster_p! < 0.05 && wtaCal.wald_p < 0.05, "the WTA slope difference holds under clustering");
ensure(calP(lastPeriod, "WTA bo3").difference < calP("2009-2017", "WTA bo3").difference
  && calP("2009-2017", "WTA bo3").difference < calP("2000-2008", "WTA bo3").difference, "the WTA gap is largest in the latest of the three periods");
const bo5Share = (key: "big_matches" | "regular_matches") => byFormat(5)[key] / (byFormat(3)[key] + byFormat(5)[key]);
ensure(bo5Share("big_matches") > bo5Share("regular_matches") && bo5Share("big_matches") < 0.5,
  "best of five is a larger share of ATP big than regular matches, but a minority of both");
ensure(calW("ATP bo3").cluster_p! > 0.05 && calW("ATP bo5").cluster_p! > 0.05, "ATP big and regular slopes do not differ");
ensure(ps("WTA").correlations["regular-match"].r > ps("WTA").correlations.clutch.r, "WTA regular-match form persists more than clutch");
ensure(ps("WTA").forecasts.clutch.permutation_p > 0.5, "the WTA clutch score shows no association");
ensure(atpClutchBetas.every((b) => b < 0), "the ATP clutch beta is negative in every evaluation year");
ensure(nominal.length === 1 && smallestRaw.tour === "WTA" && smallestRaw.test === "forecast z big", "the only nominal trait statistic is the WTA big-match association");
ensure(atpClutch.p > 0.05 && game("ATP").clutch.p < 0.05 && byFormat(3).wins.p < 0.05, "the ATP clutch spread is not significant on wins but nominal in two checks");
ensure(model("ATP", "clutch").log_loss_low! < 0 && model("ATP", "clutch").log_loss_high! > 0, "the ATP clutch score did not help out of sample");
ensure(TOURS.every((t) => (spread(t, "all big matches").implied_k ?? Infinity) > 100 && (spread(t, "finals only").implied_k ?? Infinity) > 100),
  "where an excess appears, the implied k is above 100");
ensure(meanOf("ATP", "top").score.late < 0.01 && meanOf("WTA", "top").score.late < 0.01, "the highest fives end near or below zero");

// ---------------------------------------------------------------- figures
const SPREAD_GROUPS: BarGroup[] = SETS.map(([set, label]) => ({
  label, note: set === "regular matches" ? "reference" : undefined,
  bars: TOURS.map((tour) => ({ series: tour, value: spread(tour, set).ratio })),
}));
const CALIBRATION_ROWS = [
  { label: "ATP, best of 3", series: "ATP", a: slope("ATP", "big", 3), b: slope("ATP", "regular", 3) },
  { label: "ATP, best of 5", series: "ATP", a: slope("ATP", "big", 5), b: slope("ATP", "regular", 5) },
  { label: "WTA, best of 3", series: "WTA", a: slope("WTA", "big", 3), b: slope("WTA", "regular", 3) },
];
const FOREST_GROUPS: ForestGroup[] = [
  { label: "Split-half", note: "two halves of 2000–2026", rows: TOURS.map((t) => ({ series: t, value: sh(t).r, low: sh(t).low, high: sh(t).high })) },
  ...([["big-match", "Big-match score"], ["clutch", "Clutch score"], ["regular-match", "Regular-match score"]] as const).map(([key, label]) => ({
    label, note: key === "regular-match" ? "reference" : "2012–18 to 2019–26",
    rows: TOURS.map((t) => { const c = ps(t).correlations[key]; return { series: t, value: c.r, low: c.low, high: c.high }; }),
  })),
];
const OOS_LABELS: [string, string, string?][] = [
  ["M0", "No big-match calibration", "M0 minus M1"],
  ["big", "Big-match score"], ["clutch", "Clutch score"],
  ["big_eb", "Big-match score, EB"], ["clutch_eb", "Clutch score, EB"],
  ["big_recent", "Big-match score, 5 years"], ["clutch_recent", "Clutch score, 5 years"],
];
const OOS_GROUPS: ForestGroup[] = OOS_LABELS.map(([name, label, note]) => ({
  label, note,
  rows: TOURS.map((t) => { const m = model(t, name); return { series: t, value: 1000 * m.log_loss_diff!, low: 1000 * m.log_loss_low!, high: 1000 * m.log_loss_high! }; }),
}));
const PRIMARY: [string, string, string][] = [
  ["clutch ratio", "Clutch spread", "big minus regular, beyond chance"],
  ["split-half r", "Split-half agreement", "two halves of each career"],
  ["forecast z clutch", "Carry-over association", "earlier clutch score"],
];
const POWER_PANELS: PowerPanel[] = PRIMARY.map(([test, title, note]) => ({
  title, note, series: TOURS.map((tour) => ({ series: tour, points: rb.power.evens.map((x, i) => ({ x, y: powerRow(tour, test).power[i]! })) })),
}));
const NULL_LABELS: [string, string][] = [
  ["ratio finals only", "Variance ratio, finals"], ["ratio semi-finals + finals", "Variance ratio, semi-finals and finals"],
  ["ratio all big matches", "Variance ratio, all big matches"], ["ratio regular matches", "Variance ratio, regular (reference)"],
  ["clutch ratio", "Clutch spread"], ["split-half r", "Split-half r"],
  ["period r big", "Carry-over r, big-match score"], ["period r clutch", "Carry-over r, clutch score"],
  ["forecast z big", "Association z, big-match score"], ["forecast z clutch", "Association z, clutch score"],
];
const SENS_LABEL: Record<string, string> = {
  "version 1 settings": "main settings", "shrinkage 10": "shrinkage constant 10", "shrinkage 50": "shrinkage constant 50",
  "shrinkage 100": "shrinkage constant 100", "minimum 5": "minimum 5 big matches", "minimum 20": "minimum 20 big matches",
  "semi-finals and finals only": "semi-finals and finals only", "periods 2008-2015 / 2016-2026": "periods 2008–15 / 2016–26",
};
type PlayerRow = (typeof r.players.tours)[number]["top"][number];
const points = (x: number) => signed(100 * x, 1);
function meanOf(tour: string, group: string) { return playersOf(tour).means[group]!; }
const PLAYER_HEAD = ["", "Player", "2012–18 big", "Won (exp.)", "Score", "2019–26 big", "Won (exp.)", "Score"];
const PLAYER_ALIGN: ("left" | "right")[] = ["left", "left", "right", "right", "right", "right", "right", "right"];
const playerRows = (tour: string): React.ReactNode[][] => {
  const t = playersOf(tour);
  const row = (group: string) => (p: PlayerRow, i: number) => [
    i === 0 ? group : "", p.name, p.early.big, `${p.early.won.toFixed(0)} (${p.early.expected.toFixed(1)})`, points(p.early.score),
    p.late.big, `${p.late.won.toFixed(0)} (${p.late.expected.toFixed(1)})`, points(p.late.score)];
  const mean = (group: "top" | "bottom") => ["", <i key="m">Mean of the five</i>, "", "", points(t.means[group]!.score.early), "", "", points(t.means[group]!.score.late)];
  return [...t.top.map(row("Highest five")), mean("top"), ...t.bottom.map(row("Lowest five")), mean("bottom")];
};
const code = (text: string) => <code className="font-mono text-[13px]">{text}</code>;

export default function BigMatchesPaper() {
  return (
    <Sheet fontClass={serif.variable}>
      <div data-paper-meta data-author={AUTHOR} data-short={SHORT} data-version={meta.version} hidden />
      <div className="print-hide flex flex-wrap items-center justify-between gap-3">
        <BackLink />
        <a href="/research/big-matches.pdf" className="ref text-[13px] text-[var(--p-muted)]">Download PDF</a>
      </div>
      <TitleBlock paper={meta} author={AUTHOR} affiliation="Independent Research · Matchup DNA" />

      <Abstract keywords={meta.keywords}>
        Matchup DNA forecasts professional tennis matches with a model built on Elo ratings. I ask whether a player&apos;s record in big
        matches (semi-finals, finals, the late rounds of Grand Slams and of the top non-Slam tier, and the season-ending
        Finals) contains information the ratings miss. Using {count(r.matches)} ATP and WTA main-tour matches from 2000 to
        May 2026, {count(r.big_matches)} of them big matches, I compare each result with a calibrated Elo forecast. Across
        players, big-match results vary about as much as binomial chance predicts (observed-to-chance variance ratios of
        {" "}{two(minBigRatio)} to {two(maxBigRatio)}), the two halves of a career&apos;s big matches agree only weakly
        (split-half r = {two(sh("ATP").r)} ATP, {two(sh("WTA").r)} WTA), and none of {family.length} trait statistics is
        significant after Holm correction. In a chronological out-of-sample evaluation on {count(bothEval.matches)} big
        matches from 2012 to 2026, adding a player&apos;s past big-match or clutch score to the calibrated baseline changed
        log loss by {signed(bigDiff, 5)} and {signed(clutchDiff, 5)}, with 95% intervals that include zero. The data do not
        exclude a modest trait: under the simulation model, a trait whose standard deviation is worth up to about
        {" "}{pts(atpBound)} (ATP) or {pts(wtaBound)} (WTA) percentage points at even odds remains consistent with the
        results. One tour-level pattern does hold up: Elo is more overconfident in WTA big matches than in regular WTA
        matches (calibration slope {two(wtaCal.big)} against {two(wtaCal.regular)}), the gap is largest in 2018–2026, and
        calibrating WTA big matches separately improved out-of-sample forecasts slightly. The evidence does not support
        adding a player-specific big-match adjustment to Matchup DNA&apos;s forecasting model.
      </Abstract>

      <Body>
        {/* ───────────────────────── 1 Introduction ───────────────────────── */}
        <Section id="introduction" number="1" title="Introduction">
          <Cols>
            <p>Matchup DNA produces probabilistic forecasts for ATP and WTA matches. Its ratings treat a final like any other
              match between the same two players, which raises a practical question: does a player&apos;s history in big
              matches contain information that the ratings do not? If some players consistently fall short in finals and
              others consistently rise to them, a forecast should adjust for it. If big-match records are mostly chance, an
              adjustment would only add noise.</p>
            <p>The idea that some players &quot;choke&quot; is common in tennis commentary, but it is hard to test from match
              results. Big matches are rare. A leading player reaches a handful of finals a season, and a record of twenty
              finals can look unusually good or bad by chance alone. A useful test therefore has to separate differences
              between players from binomial noise, and it has to say how large an effect it could have missed.</p>
            <p>I use {count(r.matches)} tour-level matches from 2000 to May 2026 to ask four questions. Do players&apos;
              big-match results depart from expectation by more than chance? Is a player&apos;s record consistent across the
              two halves of their big matches, and from 2012–2018 to 2019–2026? Would a past big-match record have improved
              forecasts of later big matches, using only information available at the time? And how large a trait could
              these tests have missed? A fifth question concerns favourites in general rather than particular players: is
              Elo calibrated differently in big matches?</p>
            <p>In short, big-match records look mostly like chance, past records do not improve out-of-sample forecasts, and
              a modest trait cannot be ruled out. The one effect that holds up is at the tour level: in WTA big matches,
              Elo overstates the favourite&apos;s chances by more than it does in regular WTA matches.</p>
            <p>This is a post-hoc study. Version 1 fixed its definitions in code before it was run, but the question came
              up after recent results had been seen, and later versions added tests after earlier results were known. Version
              3.0 corrected several errors found in an audit of versions 1 and 2; these and later changes are listed in the
              version history at the end.</p>
          </Cols>
        </Section>

        {/* ───────────────────────── 2 Related research ───────────────────────── */}
        <Section id="related" number="2" title="Related Research">
          <Cols>
            <p>Most quantitative work on pressure in tennis uses point-level data. For modelling purposes, treating points as
              i.i.d. is usually adequate: <Cite id="klaassen">Klaassen and Magnus (2001)</Cite> detected departures in
              Wimbledon data, with servers slightly less successful on important points and some carry-over from one point to
              the next, but the departures were small. <Cite id="gonzalez">González-Díaz et al.
              (2012)</Cite> found persistent differences between players in how they perform on important points at the US
              Open, and that these differences are associated with career success. <Cite id="cohenzada">Cohen-Zada et al.
              (2017)</Cite> compare men and women directly: the decline under rising stakes within a match is consistent only
              for men, women&apos;s results are inconsistent, and where women&apos;s performance does fall, the fall is about
              half as large. <Cite id="paserman">Paserman
              (2023)</Cite> finds that both men and women play less aggressively on important points, and <Cite id="harris">Harris
              et al. (2021)</Cite> find that double faults and unforced errors become more likely as situational pressure
              rises.</p>
            <p>Two studies measure pressure performance for individual players. <Cite id="kovalchikingram">Kovalchik and
              Ingram (2016)</Cite> modelled player-specific responses to the score and to pressure situations in about three
              million ATP and WTA points from 2011–2015; allowing for these responses improved predictions of the 2015
              men&apos;s Grand Slam matches, while for women the player-specific model did no better than one with average
              effects. <Cite id="kovalchikreid">Kovalchik and Reid (2020)</Cite> weighted players&apos; serve and return
              statistics by the importance of each point; in 2011 Grand Slam matches these &quot;clutch averages&quot;
              generally separated winners from losers, and predicted the winner from first-set statistics, better than
              unweighted averages.</p>
            <p>These studies ask whether pressure changes how points are played. This paper asks a coarser question that
              matters for match forecasts: whether such differences add up to persistent differences in big-match results.
              Results also depend on form. <Cite id="jetter">Jetter and Walker (2015)</Cite> find that recent wins predict
              the next match, and that top-ranked players do better at Grand Slams than elsewhere, a clutch effect for the
              group of top players rather than for individuals. Players reach big matches partly by being in form, so a test
              of pressure has to separate the two. <Cite id="gorgi">Gorgi et al. (2019)</Cite> allowed the
              strength gap between ATP players to widen at Grand Slams and found no evidence that it does once the
              best-of-five format is modelled, a tour-level question that Section 4.1 asks of Elo&apos;s calibration on both
              tours.</p>
            <p>The question has also been examined with match results and Elo expectations outside the academic
              literature. <Cite id="sackmann2019a">Sackmann (2019a)</Cite> compared ATP players&apos; results in each round,
              from first matches to finals, with Elo&apos;s predictions and found significant departures in 29 of about
              1,043 player-and-round categories, no more than chance would produce. <Cite id="sackmann2025">Sackmann
              (2025)</Cite> compared men&apos;s best-of-five Grand Slam results with Elo expectations and found virtually no
              correlation between the first and second halves of players&apos; records. These are the closest precedents for
              this paper&apos;s question and approach.</p>
            <p>The statistical framework builds on established approaches from research on clutch hitting in
              baseball. <Cite id="cramer">Cramer (1977)</Cite> found that players&apos; clutch hitting in 1969 did not
              predict their clutch hitting in 1970. <Cite id="james">James (2004)</Cite> argued that a persistence test that
              finds nothing says little unless it could have detected a real effect, and <Cite id="birnbaum">Birnbaum
              (2005)</Cite> estimated the power of Cramer&apos;s test by simulating hitters with clutch talent of known
              size. Comparing the observed spread of players&apos; records with the spread chance would produce, and treating
              any excess as true differences, is a standard approach in that literature (<Cite id="tango">Tango et al., 2007</Cite>). <Cite id="efron">Efron and Morris (1975)</Cite> showed that shrinking early-season
              batting averages toward the group mean predicted the rest of the season with less than half the mean squared
              error of the raw averages, and <Cite id="brown2008">Brown
              (2008)</Cite> compared empirical Bayes methods for predicting batting averages within a season. The variance
              ratios, consistency tests, power analysis and shrinkage used here are related to these approaches.</p>
            <p>The expectation for each match comes from Elo ratings (<Cite id="elo">Elo, 1978</Cite>), which <Cite id="kovalchik">Kovalchik
              (2016)</Cite> found to be among the more accurate published methods for predicting ATP results. Laboratory
              studies of choking, in which pressure such as competition, money or an audience worsened skilled performance
              (<Cite id="baumeister">Baumeister, 1984</Cite>), motivate the question but measure something different:
              short tasks, not results over a professional career.</p>
            <p>Relative to this work, the paper&apos;s contribution is applied. It brings calibrated Elo residuals, variance
              and persistence tests, simulation-based null distributions with multiple-testing correction, and simulated
              power and bounds together in one analysis of {count(r.matches)} ATP and WTA matches; it evaluates past
              big-match and clutch scores chronologically out of sample on {count(bothEval.matches)} big matches; it compares
              Elo&apos;s calibration in big and regular matches on both tours; and it uses the results to decide whether
              Matchup DNA&apos;s forecasting model should include a big-match adjustment.</p>
          </Cols>
        </Section>

        {/* ───────────────────────── 3 Data and Methods ───────────────────────── */}
        <Section id="methods" number="3" title="Data and Methods">
          <Subsection number="3.1" title="Data">
            <Cols>
              <p>Match results come from Jeff Sackmann&apos;s tennis_atp and tennis_wta files (<Cite id="sackmann">Sackmann,
                2026</Cite>), read from a June 2026 snapshot. Elo ratings are computed from 1968, and the analysis covers
                tournaments that started between 1 January 2000 and 24 May 2026. The last edition in the snapshot, Roland
                Garros 2026, started on 25 May and finished in June. Matches from June 2026 onwards are reserved for the
                project&apos;s prospective evaluations, so the whole edition is left out.</p>
              <p>Only main-tour singles events are used: the Grand Slams, the ATP Masters and the WTA&apos;s top non-Slam tier,
                other tour-level events, the season-ending Finals and the Olympics. Team competitions (Davis Cup, Billie Jean
                King Cup, ATP Cup, United Cup, World Team Cup), the Laver Cup, the Next Gen ATP Finals (an under-21 event with
                shortened sets), WTA 125 events and bronze-medal matches are excluded. Only completed best-of-three and
                best-of-five matches are rated, so retirements and walkovers are excluded too. Table 1 summarises the sample.
                Each match is one observation; in the player-level statistics a match contributes one residual to each player,
                with opposite signs.</p>
            </Cols>
            <Table number={1} caption={<>The sample, 2000 – 24 May 2026. Player counts are for players meeting each test&apos;s minimum of {r.min_big} big matches.</>}
              head={["", "ATP", "WTA", "Both"]}
              rows={[
                ["Matches", count(SAMPLE.ATP.matches), count(SAMPLE.WTA.matches), count(r.matches)],
                ["Big matches", count(SAMPLE.ATP.big), count(SAMPLE.WTA.big), count(r.big_matches)],
                ["Big matches, best of five", count(byFormat(5).big_matches), "0", count(byFormat(5).big_matches)],
                ["Players with 10+ big matches", count(spread("ATP", "all big matches").players), count(spread("WTA", "all big matches").players),
                  count(spread("ATP", "all big matches").players + spread("WTA", "all big matches").players)],
                ["… with 10+ in each half of their record", count(sh("ATP").players), count(sh("WTA").players), count(sh("ATP").players + sh("WTA").players)],
                ["… with 10+ in both 2012–18 and 2019–26", count(ps("ATP").players), count(ps("WTA").players), count(ps("ATP").players + ps("WTA").players)],
                [`Big matches in the out-of-sample test, ${fc.first_eval_year}–2026`, count(evaluation("ATP").matches), count(evaluation("WTA").matches), count(bothEval.matches)],
              ]} />
          </Subsection>

          <Subsection number="3.2" title="Big matches">
            <Cols>
              <p>A big match is any semi-final or final; a Grand Slam fourth-round or quarter-final match; a quarter-final at
                the highest tier below the Grand Slams; or any match at the season-ending Finals. Every other main-tour match
                is a regular match. For the ATP the top non-Slam tier is the Masters. For the WTA, Sackmann&apos;s level codes
                are not consistent across years (Premier Mandatory events are coded as Premier in 2016 and 2020–2022, and from
                2023 the Premier Mandatory code covers the whole WTA 1000 tier), so the tier is assigned by event and year:
                Tier I up to 2008, Premier Mandatory and Premier 5 from 2009 to 2020, and WTA 1000 from 2021. The season-ending
                Finals are identified by name, because the same code also marks the second-tier WTA Tournament of Champions and
                Elite Trophy, which are treated as ordinary events. Appendix B.1 gives the rules. I also report results for
                finals alone and for semi-finals and finals together, which do not depend on the tier assignment.</p>
            </Cols>
          </Subsection>

          <Subsection number="3.3" title="Expected results">
            <Cols>
              <p>Player strength is estimated using the project&apos;s surface-blended Elo rating, which combines a
                player&apos;s overall rating and their rating on the match surface with equal weights. In the project&apos;s
                model development, the equal weight gave the lowest log loss on 1990–2009 matches among weights of 0.25, 0.5,
                0.75 and 1. A similar blending approach has previously been described by <Cite id="sackmann2019b">Sackmann
                (2019b)</Cite>. Ratings are taken at the start of each tournament week, so no match is predicted with ratings that include its own result or any other result from that
                week. Raw Elo probabilities are too confident in best-of-three matches and roughly right in best-of-five, and most
                best-of-five matches are Grand Slam matches, many of them big. I therefore rescale Elo&apos;s log-odds with one
                slope <i>b</i><sub>g</sub> per group <i>g</i> = (tour, big or regular, best of three or five), fitted by maximum
                likelihood (equation 1). The residual of player <i>i</i> in match <i>m</i> is the result minus this expectation
                (equation 2). In the descriptive tests the slopes are fitted on the analysis window itself, so the expectation
                is in-sample. The out-of-sample evaluation (Section 3.6) fits them only on earlier years.</p>
            </Cols>
            <Eq number={1}>{v("P", "ij")} = σ ( {v("b", "g")} · logit {v("p", "ij")}<sup>Elo</sup> )</Eq>
            <Eq number={2}>{v("e", "im")} = {v("y", "im")} − {v("P", "im")}, &nbsp; {v("y", "im")} ∈ {"{0, 1}"}</Eq>
          </Subsection>

          <Subsection number="3.4" title="Player scores">
            <Cols>
              <p>A player&apos;s big-match score divides the sum of their big-match residuals by the number of big matches plus
                {" "}{r.shrink} (equation 3). This is fixed shrinkage toward zero: a player with {r.shrink} big matches is weighted
                halfway between their own record and zero. The constant was set before the version 1 run as a round number; it
                was not estimated from the data, so the score resembles an empirical Bayes estimate (<Cite id="efron">Efron and Morris, 1975</Cite>) without being one. Section
                4.6 reports constants of 10, 50 and 100, and the out-of-sample evaluation adds an empirical Bayes score whose
                shrinkage is estimated from earlier data. The clutch score subtracts the same score computed on regular matches
                (equation 4), so a player Elo under-rates in every match, such as a fast-improving young player, is not counted as
                clutch.</p>
            </Cols>
            <Eq number={3}>{v("s", "i")} = Σ<sub>m ∈ big</sub> {v("e", "im")} / ( {v("n", "i")} + {r.shrink} )</Eq>
            <Eq number={4}>{v("c", "i")} = {v("s", "i")}<sup>big</sup> − {v("s", "i")}<sup>regular</sup></Eq>
          </Subsection>

          <Subsection number="3.5" title="Tests for a player trait">
            <Cols>
              <p><i>Variation beyond chance.</i> For players with at least {r.min_big} matches of a kind, I compare the variance
                of their mean residuals with the average variance that binomial chance would produce given their match
                probabilities. A variance ratio of 1 means players differ by exactly as much as chance predicts; any excess
                estimates the variance of a persistent trait, as in the decomposition of observed into true and random variance
                used in baseball research (<Cite id="tango">Tango et al., 2007</Cite>). I compute it for finals, for semi-finals and finals, for all big
                matches, for regular matches as a reference for Elo&apos;s general misfit, and for the difference between each
                player&apos;s big- and regular-match mean residuals (the clutch spread).</p>
              <p><i>Consistency.</i> The split-half test assigns every edition of a tournament to one of two halves (by a hash
                of its identifier) and correlates the two halves&apos; mean big-match residuals across players with at least
                {" "}{r.min_big} big matches in each. The carry-over test correlates scores from 2012–2018 with scores from
                2019 – May 2026, refitting the calibration in each period.</p>
              <p><i>Retrospective association.</i> Versions 1 and 2 called this a forecast test. It adds β(<i>s</i><sub>A</sub>
                {" "}− <i>s</i><sub>B</sub>) to the calibrated 2019–2026 forecasts (equation 5), fits β on those same matches, and
                asks whether log loss improves more than when the earlier scores are shuffled among players (1,000
                permutations). Because β and the calibration are fitted on the matches being scored, this tests association
                between the periods; it does not evaluate forecasts.</p>
            </Cols>
            <Eq number={5}>logit {v("P", "m")} = logit {v("P̂", "m")} + β ( {v("s", "A")} − {v("s", "B")} )</Eq>
          </Subsection>

          <Subsection number="3.6" title="Out-of-sample evaluation">
            <Cols>
              <p>To test forecasting directly, every big match from {fc.first_eval_year} to May 2026 is predicted using only
                matches from earlier calendar years. For each year <i>Y</i>, the calibration slopes are fitted on all matches from
                2000 to the end of <i>Y</i> − 1, player scores are computed from residuals of those matches, and β is fitted on
                the big matches from {fc.first_fit_year} to <i>Y</i> − 1, each with the scores and calibration that were
                available at the start of its own year. A player with no earlier big matches has a score of zero, so no match is
                dropped. Evaluation starts in {fc.first_eval_year} so that every β is fitted on at least eight years of big
                matches.</p>
              <p>All models are scored on the same {count(bothEval.matches)} matches. M0 is Elo with one slope per tour and
                format; M1 has separate big- and regular-match slopes and is the baseline used in the rest of the paper; the
                player models add the big-match or clutch score to M1. Two variants test the shrinkage and the assumption that
                a trait lasts a career: empirical Bayes scores, in which each player&apos;s mean residual is multiplied by
                τ²/(τ² + its noise variance) with τ² estimated from earlier players, and scores built from the previous
                {" "}{fc.recent_years} years only. Differences in log loss and Brier score are paired by match, and their 95%
                intervals come from {count(fc.bootstraps)} bootstrap resamples (<Cite id="efron1979">Efron, 1979</Cite>) of whole tournament editions.</p>
            </Cols>
          </Subsection>

          <Subsection number="3.7" title="Inference">
            <Cols>
              <p><i>Null distributions.</i> The variance ratios and correlations do not have convenient sampling
                distributions, so their p-values come from a parametric bootstrap: {count(rb.sims.null)} data sets in which every
                match result is redrawn from its calibrated probability, the calibration is refitted, and every statistic is
                recomputed. The simulations keep the observed schedule (the same players meet in the same matches), so the null
                is conditional on who reached each round. They also assume no player differences of any kind beyond Elo,
                including ordinary form, so a statistic that picks up form can look significant without indicating pressure.</p>
              <p><i>Multiple testing.</i> Nine statistics per tour test for a trait: three big-match variance ratios, the clutch
                spread, the split-half correlation, two carry-over correlations and two association statistics. I treat these
                {" "}{family.length} as one family and apply Holm&apos;s correction (<Cite id="holm">Holm, 1979</Cite>). This
                family was defined in version 3, after the earlier results were known; within-tour adjustments are in Appendix
                Table A1. Version 2 corrected only the variance ratios. The robustness checks in Section 4.7 re-test the same
                hypotheses and are not corrected separately.</p>
              <p><i>Power and bounds.</i> Similar simulations were used by <Cite id="birnbaum">Birnbaum (2005)</Cite> to
                measure the power of persistence tests for clutch hitting. I add a known trait to the simulations: each player receives θ ~ N(0, τ²) on the
                log-odds scale in big matches only, constant over the career (equation 6). For each τ from 0.05 to 0.4,
                {" "}{count(rb.sims.power)} simulated data sets give each test&apos;s power and the probability of a statistic at or
                below the observed one. The 95% upper bound on τ is the smallest τ at which that probability falls below 5%,
                found by linear interpolation between grid points, in the spirit of an equivalence test (<Cite id="lakens">Lakens,
                2017</Cite>). I express τ as an edge at even odds: a player one standard deviation above average in the trait,
                facing an otherwise equal and average opponent, wins 50 + 100(σ(τ) − 0.5) per cent of big matches. Resampling
                the simulations gives a Monte Carlo range for each bound.</p>
              <p><i>Calibration.</i> Model-based standard errors of the calibration slopes treat matches as independent. I also
                report a cluster bootstrap over tournament editions ({count(fc.bootstraps)} resamples).</p>
            </Cols>
            <Eq number={6}>logit {v("P", "m")}<sup>true</sup> = logit {v("P̂", "m")} + 1<sub>big</sub>(m) · ( {v("θ", "A")} − {v("θ", "B")} )</Eq>
            <Figure number={1} caption={<>Matches and players in each part of the analysis, 2000 – 24 May 2026.</>}>
              <StudyFlow
                source={{ title: "Sackmann's ATP and WTA tour-level files (June 2026 snapshot)", detail: "Elo ratings run from 1968" }}
                excluded={{ title: "Left out", detail: "Before 2000; Roland Garros 2026 (finished in June); team events, Laver Cup, Next Gen Finals, WTA 125s, bronze-medal matches; retirements and walkovers" }}
                analysed={{ title: "Rated main-tour matches", detail: `n = ${count(r.matches)}` }}
                split={[
                  { title: "Big matches", detail: <>n = {count(r.big_matches)}<br />Semi-finals, finals, Slam fourth rounds and quarter-finals, top-tier quarter-finals, Finals</> },
                  { title: "Regular matches", detail: <>n = {count(r.matches - r.big_matches)}</> },
                ]}
                tests={[
                  { title: "Variation beyond chance", detail: <>{count(spread("ATP", "all big matches").players)} ATP and {count(spread("WTA", "all big matches").players)} WTA players</> },
                  { title: "Consistency and carry-over", detail: <>{count(sh("ATP").players)} and {count(sh("WTA").players)} players (halves); {ps("ATP").players} and {ps("WTA").players} (periods)</> },
                  { title: "Out-of-sample forecasts", detail: <>{count(bothEval.matches)} big matches, {fc.first_eval_year} – May 2026</> },
                ]}
              />
            </Figure>
          </Subsection>
        </Section>

        {/* ───────────────────────── 4 Results ───────────────────────── */}
        <Section id="results" number="4" title="Results">
          <Subsection number="4.1" title="Calibration in big matches">
            <Cols>
              <p>On the ATP tour, Elo needs the same correction in big and regular matches in both formats (Figure 2, Table 2).
                On the WTA tour the big-match slope is lower: {three(wtaCal.big)} against {three(wtaCal.regular)}, so Elo
                overstates the favourite&apos;s chances more in WTA big matches. The difference survives the cluster bootstrap
                ({pEq(wtaCal.cluster_p!)}, against {pv(wtaCal.wald_p)} for the model-based test). It is not stable over time
                (Appendix Table A4): it is absent in 2000–2008 ({signed(calP("2000-2008", "WTA bo3").difference)}), moderate in
                2009–2017 ({signed(calP("2009-2017", "WTA bo3").difference)}) and largest in 2018–2026
                ({signed(calP(lastPeriod, "WTA bo3").difference)}, {pEq(calP(lastPeriod, "WTA bo3").wald_p)}).</p>
              <p>The pattern also helps forecasts out of sample. With calibrations fitted only on earlier years, separate
                big-match slopes reduced WTA big-match log loss by {pts(1000 * wtaM0.log_loss_diff!)} thousandths (95% interval
                {" "}{pts(1000 * wtaM0.log_loss_low!)} to {pts(1000 * wtaM0.log_loss_high!)}), from {wtaM0.log_loss.toFixed(4)} to
                {" "}{model("WTA", "M1").log_loss.toFixed(4)}. On the ATP tour they made no clear difference (pooled minus
                separate calibration: {milli(atpM0.log_loss_diff!)} thousandths, interval {milli(atpM0.log_loss_low!)} to
                {" "}{milli(atpM0.log_loss_high!)}). The effect is small, and it concerns every WTA favourite in a big match, not
                particular players.</p>
            </Cols>
            <Figure number={2} caption={<>Elo calibration slopes in big and regular matches, 2000 – May 2026. A slope of 1 means Elo&apos;s probabilities were already right; below 1, Elo was too confident in the favourite.</>}>
              <Dumbbell rows={CALIBRATION_ROWS} domain={[0.6, 1.2]} ticks={[0.6, 0.8, 1.2]} format={two} aLabel="Big matches" bLabel="Regular matches"
                        reference={1} referenceLabel="Elo already right" axisLabel="Calibration slope" ariaLabel="Figure 2: calibration slopes, big against regular matches" />
            </Figure>
            <Table number={2} caption={<>Calibration slopes with model-based standard errors, and the big-minus-regular difference with model-based (Wald) and edition-cluster bootstrap uncertainty.</>}
              head={["Tour and format", "Big", "Regular", "Difference", "Wald p", "Cluster 95% interval", "Cluster p"]}
              rows={fc.calibration.window.map((c) => [c.key.replace(" bo", ", best of "), `${three(c.big)} (${three(c.big_se)})`, `${three(c.regular)} (${three(c.regular_se)})`,
                signed(c.difference), pv(c.wald_p), `${signed(c.cluster_low!)} to ${signed(c.cluster_high!)}`, pv(c.cluster_p!)])} />
          </Subsection>

          <Subsection number="4.2" title="Variation beyond chance">
            <Cols>
              <p>Players&apos; big-match results vary about as much as chance predicts (Figure 3, Table 3). Across the six
                big-match sets the variance ratio runs from {two(minBigRatio)} to {two(maxBigRatio)}; the largest is for WTA finals,
                where only {spread("WTA", "finals only").players} players qualify ({pEq(nullRow("WTA", "ratio finals only").p)}). In
                standard-deviation terms the excess is smaller still: for all ATP big matches the observed spread is
                {" "}{pp(spread("ATP", "all big matches").observed_sd)} points against {pp(spread("ATP", "all big matches").noise_sd)} from
                chance. Where an excess appears, the implied number of matches before a record is half signal is above 100, more
                than most players play.</p>
              <p>The clutch spread is {two(atpClutch.observed)} on the ATP tour ({pEq(atpClutch.p)}; Holm-adjusted
                {" "}{pv(atpClutch.holm!)}) and {two(nullRow("WTA", "clutch ratio").observed)} on the WTA tour ({pEq(nullRow("WTA", "clutch ratio").p)}). The only clear excess in Table 3 is in regular WTA matches
                ({two(spread("WTA", "regular matches").ratio)}, {pEq(nullRow("WTA", "ratio regular matches").p)}), which is
                consistent with ordinary changes in form that Elo is slow to track rather than with pressure.</p>
            </Cols>
            <Figure number={3} caption={<>Variance of players&apos; mean residuals divided by the variance chance alone would produce, 2000 – May 2026; players with at least {r.min_big} matches of each kind. The dashed line at 1 is chance.</>}>
              <GroupedBars groups={SPREAD_GROUPS} domain={[0, 1.4]} ticks={[0, 0.5, 1, 1.4]} format={two} reference={1} referenceLabel="Chance"
                           axisLabel="Observed variance ÷ variance from chance" ariaLabel="Figure 3: variance of players' results relative to chance, by tour" />
            </Figure>
            <Table number={3}
              caption={<>Spread of players&apos; mean residuals. Standard deviations are in percentage points of win probability per match; the ratio is of variances. The trait sd is the square root of the excess variance; implied <i>k</i> is the number of matches before half of a record is signal. p from {count(rb.sims.null)} simulations; Holm across the {family.length} trait statistics.</>}
              head={["Tour and matches", "Players", "Observed sd", "Chance sd", "Variance ratio", "Trait sd", "Implied k", "p", "Holm p"]}
              rows={TOURS.flatMap((tour) => SETS.map(([set, label]) => {
                const s = spread(tour, set), n = nullRow(tour, `ratio ${set}`);
                return [`${tour}, ${label.toLowerCase()}`, count(s.players), pp(s.observed_sd), pp(s.noise_sd), two(s.ratio), pp(s.trait_sd),
                        s.implied_k === null ? "none" : count(Math.round(s.implied_k)), pv(n.p), n.holm === undefined ? "reference" : pv(n.holm)];
              }))} />
          </Subsection>

          <Subsection number="4.3" title="Consistency and carry-over">
            <Cols>
              <p>The two halves of players&apos; big-match records barely agree: r = {interval(sh("ATP"))} on the ATP tour and
                {" "}{interval(sh("WTA"))} on the WTA tour (Figure 4). Applying the Spearman–Brown formula (<Cite id="spearman">Spearman, 1910</Cite>; <Cite id="brown">Brown, 1910</Cite>) to these point estimates
                gives a full-record reliability of {two(sh("ATP").spearman_brown)} and {two(sh("WTA").spearman_brown)}. These are
                estimates with wide uncertainty, not upper limits, and the formula assumes halves of equal length, which unequal
                records only approximate.</p>
              <p>Between periods, big-match scores carry over weakly ({signed(ps("ATP").correlations["big-match"].r, 2)} ATP,
                {" "}{signed(ps("WTA").correlations["big-match"].r, 2)} WTA), and no more strongly than regular-match scores do
                ({signed(ps("ATP").correlations["regular-match"].r, 2)} and {signed(ps("WTA").correlations["regular-match"].r, 2)}). The
                retrospective association test (Table 4) is nominally significant for the WTA big-match score (permutation {pEq(wtaBigAssoc.permutation_p)}), but the WTA clutch score, which removes general form, shows no association
                ({pEq(ps("WTA").forecasts.clutch.permutation_p)}). What persists between periods is a player&apos;s general
                tendency to beat or trail their rating, which persists at least as strongly in regular matches.
                {" "}{nominal.length === 1 ? "It is the only one" : `${nominal.length}`} of the {family.length} trait statistics with a raw
                p below 0.05 (simulation {pEq(smallestRaw.p)}), and after Holm&apos;s correction its p-value is {pv(minHolm)}.</p>
            </Cols>
            <Figure number={4} caption={<>Agreement of player scores with 95% intervals: between the two halves of each player&apos;s big matches, and between 2012–2018 and 2019 – May 2026 for the {ps("ATP").players} ATP and {ps("WTA").players} WTA players with at least {r.min_big} big matches in both periods.</>}>
              <Forest groups={FOREST_GROUPS} domain={[-0.4, 0.7]} ticks={[-0.4, 0, 0.4, 0.7]} format={(x) => signed(x, 2)} reference={0} referenceLabel="No agreement"
                      axisLabel="Correlation" ariaLabel="Figure 4: agreement of player scores with 95% intervals" />
            </Figure>
            <Table number={4}
              caption={<>Retrospective association (equation 5): 2012–2018 scores against 2019–2026 big-match results, with β fitted on the same later matches. Permutation p from 1,000 shuffles of the earlier scores. This is not an out-of-sample test (see Section 4.4).</>}
              head={["Tour and score", "Later big matches", "With an earlier score", "β (se)", "Log-loss change", "Permutation p"]}
              rows={TOURS.flatMap((tour) => (["big-match", "clutch"] as const).map((key) => {
                const f = ps(tour).forecasts[key];
                return [`${tour}, ${key} score`, count(f.matches), count(f.with_history), `${signed(f.beta, 2)} (${two(f.se)})`, signed(f.log_loss_change, 5), pv(f.permutation_p)];
              }))} />
          </Subsection>

          <Subsection number="4.4" title="Out-of-sample forecasts">
            <Cols>
              <p>Predicting each year only from earlier years, no player score produced a statistically reliable improvement in forecasts of big matches (Table 5,
                Figure 5). Across both tours, the big-match score changed log loss by {milli(bigDiff)} thousandths and the clutch
                score by {milli(clutchDiff)}, against a baseline of {model("both", "M1").log_loss.toFixed(4)}. Every interval for a
                player-score model includes zero, including the empirical Bayes and five-year variants and the subset of matches in
                which both players had at least {r.min_big} earlier big matches (Appendix Table A3). The largest point improvement
                of any variant is {pts(-1000 * largestScoreGain)} thousandths.</p>
              <p>The fitted β values help explain this. On the ATP tour the coefficient on the clutch score is negative in every
                evaluation year (between {signed(Math.min(...atpClutchBetas), 2)} and {signed(Math.max(...atpClutchBetas), 2)}): a high
                earlier clutch score, which partly reflects a low regular-match score, is followed by slightly worse big-match
                results relative to the baseline, not better. The empirical Bayes WTA big-match score is zero in most years because
                the estimated trait variance is zero, so that model reproduces the baseline.</p>
            </Cols>
            <Table number={5}
              caption={<>Out-of-sample log loss on every big match, {fc.first_eval_year} – May 2026, each year predicted from earlier years only. Differences are from the baseline M1 in thousandths of log loss; negative means better. 95% intervals from {count(fc.bootstraps)} resamples of tournament editions.</>}
              head={["Model", "ATP log loss", "ATP difference (95%)", "WTA log loss", "WTA difference (95%)"]}
              rows={(["M0", "M1", "big", "clutch", "big_eb", "clutch_eb", "big_recent", "clutch_recent"] as const).map((name) => {
                const cell = (tour: string) => { const m = model(tour, name); return m.log_loss_diff === undefined ? "baseline" : diffCell(m.log_loss_diff, m.log_loss_low!, m.log_loss_high!); };
                return [OOS_LABELS.find(([n]) => n === name)?.[1] ?? "M1: separate big and regular slopes", model("ATP", name).log_loss.toFixed(4), cell("ATP"), model("WTA", name).log_loss.toFixed(4), cell("WTA")];
              })}
              note={<>Matches: {count(evaluation("ATP").matches)} ATP, {count(evaluation("WTA").matches)} WTA. EB = empirical Bayes shrinkage; 5 years = scores from the previous {fc.recent_years} years only. Brier scores and the subset with long histories are in Appendix Table A3.</>} />
            <Figure number={5} caption={<>Out-of-sample change in log loss relative to the baseline M1 (separate big- and regular-match calibration), in thousandths, with 95% intervals; negative is better. The first row is the model without the big-match calibration.</>}>
              <Forest groups={OOS_GROUPS} domain={[-1.5, 1.6]} ticks={[-1.5, 0, 1.5]} format={(x) => signed(x, 2)} reference={0} referenceLabel="Baseline"
                      axisLabel="Change in log loss (thousandths)" ariaLabel="Figure 5: out-of-sample change in log loss for each model against the baseline, by tour" />
            </Figure>
          </Subsection>

          <Subsection number="4.5" title="What the data can rule out">
            <Cols>
              <p>The tests can detect a large trait. At τ = 0.4, an edge of {pts(evensAt(0.4))} points at even odds, the
                clutch-spread and split-half tests detect the trait {power04 >= 0.995 ? "in essentially every simulation" : `in at least ${pct(power04)} of simulations`} on
                both tours (Figure 6). At τ = 0.15 ({pts(evensAt(0.15))} points) no test has better than a {pct(power015)} chance.</p>
              <p>The clutch spread gives the headline bounds because it is the only test that removes general form. At 95%
                confidence the trait&apos;s standard deviation is at most {boundText("ATP", "clutch ratio")} at even odds on the ATP
                tour, and {boundText("WTA", "clutch ratio")} on the WTA tour; the split-half test gives {boundText("ATP", "split-half r")} and
                {" "}{boundText("WTA", "split-half r")}. These bounds hold only under the simulation model: a normally distributed trait,
                constant over a career and confined to the defined big matches. They describe the spread of the trait across
                players, not a maximum for any single player, and an edge of {pts(atpBound)} points (a {pts(50 + atpBound)}% chance against an
                equal opponent) would matter for a forecast if it could be measured.</p>
            </Cols>
            <Figure number={6} caption={<>Power of three tests against the size of a simulated clutch trait, {count(rb.sims.power)} simulations per point. The horizontal axis is the edge at even odds, in percentage points, of a player one standard deviation above average. The dashed line is 80% power.</>}>
              <PowerCurves panels={POWER_PANELS} xMax={10} xTicks={[0, 2.5, 5, 7.5, 10]} ariaLabel="Figure 6: power of the clutch-spread, split-half and association tests against the size of a clutch trait, by tour" />
            </Figure>
          </Subsection>

          <Subsection number="4.6" title="Players with extreme early records, and sensitivity">
            <Cols>
              <p>Tables 6 and 7 follow the five players on each tour with the highest and lowest big-match scores in 2012–2018,
                among the {playersOf("ATP").players} ATP and {playersOf("WTA").players} WTA players with enough big matches in both
                periods. The five highest ATP scores averaged {points(meanOf("ATP", "top").score.early)} points per match in the
                first period and {points(meanOf("ATP", "top").score.late)} in the second; on the WTA tour the highest five went from
                {" "}{points(meanOf("WTA", "top").score.early)} to {points(meanOf("WTA", "top").score.late)} and the lowest five from
                {" "}{points(meanOf("WTA", "bottom").score.early)} to {points(meanOf("WTA", "bottom").score.late)}. The ATP lowest five
                moved from {points(meanOf("ATP", "bottom").score.early)} to {points(meanOf("ATP", "bottom").score.late)}. The tables
                illustrate regression toward zero; they are not a test, and with so few big matches per player every individual
                record in them is dominated by chance. Changes in a player&apos;s record can have causes, such as injury or age, that
                this analysis does not observe.</p>
              <p>Across the {rb.sensitivity.length / 2} variants of the carry-over test per tour (shrinkage constants 10, 50 and 100,
                minimums of 5 and 20 big matches, semi-finals and finals only, and periods split at 2016; Appendix Table A5), no
                clutch-score association has p below {pv(minSensitivityClutchP)}, and the smallest p for either score is
                {" "}{pv(minSensitivityP)}, which is not significant once the number of variants is considered.</p>
            </Cols>
            <Table number={6} align={PLAYER_ALIGN} caption={<>ATP players with the highest and lowest big-match scores in 2012–2018, and their records in 2019 – May 2026. Won (exp.) is wins against calibrated expected wins; the score is equation 3 in percentage points.</>}
              head={PLAYER_HEAD} rows={playerRows("ATP")} />
            <Table number={7} align={PLAYER_ALIGN} caption={<>WTA players with the highest and lowest big-match scores in 2012–2018, and their records in 2019 – May 2026. Columns as in Table 6.</>}
              head={PLAYER_HEAD} rows={playerRows("WTA")} />
          </Subsection>

          <Subsection number="4.7" title="Robustness checks">
            <Cols>
              <p><i>Game margins.</i> Replacing each result with the share of games won (Appendix Table A6), players differ in
                margin far more than Elo predicts in every kind of match (regular-match variance ratios
                {" "}{two(gameSet("ATP", "regular matches").ratio)} ATP and {two(gameSet("WTA", "regular matches").ratio)} WTA), which
                points to playing style. The clutch spread on game margins is {two(game("ATP").clutch.ratio)} on the ATP tour ({pEq(game("ATP").clutch.p)}) and {two(game("WTA").clutch.ratio)} on the WTA tour ({pEq(game("WTA").clutch.p)}).</p>
              <p><i>Format.</i> Best-of-five matches make up a larger share of ATP big matches than of regular ones
                ({pct(bo5Share("big_matches"))} against {pct(bo5Share("regular_matches"))}), so a difference between big and
                regular matches could partly reflect format. Comparing big and
                regular ATP matches within one format (Appendix Table A8), the clutch spread is {two(byFormat(3).wins.ratio)} in
                best-of-three matches ({pEq(byFormat(3).wins.p)}; games {two(byFormat(3).games.ratio)}, {pEq(byFormat(3).games.p)}) and
                {" "}{two(byFormat(5).wins.ratio)} in best-of-five ({pEq(byFormat(5).wins.p)}).</p>
              <p>These checks leave a small, unresolved ATP pattern. The win-based clutch spread on all matches is not significant
                ({pEq(atpClutch.p)}), but the game-margin version and the best-of-three comparison give nominal p-values below 0.05.
                Those checks are not corrected for multiple testing, they re-test the same hypothesis with overlapping data, and the
                ATP clutch score did not help out-of-sample forecasts. They are consistent with a small ATP excess within the bounds
                of Section 4.5, and not with a large one.</p>
              <p><i>Form within the tournament.</i> Updating each player&apos;s rating through their earlier rounds of the same
                event (Appendix Table A7) gives an ATP clutch spread of {two(within("ATP").clutch)} and split-half correlations
                of {signed(within("ATP").split_half.r, 2)} and {signed(within("WTA").split_half.r, 2)}. Round-robin matches and
                others without a complete earlier-round record keep the start-of-week rating ({pct(1 - within("ATP").eligible)} of
                big matches).</p>
            </Cols>
          </Subsection>
        </Section>

        {/* ───────────────────────── 5 Discussion and Limitations ───────────────────────── */}
        <Section id="discussion" number="5" title="Discussion and Limitations">
          <Subsection number="5.1" title="What the evidence supports">
            <Cols>
              <p>Three kinds of significance need to be kept apart. Statistically, no trait statistic is significant once the
                number of tests is taken into account. The nominal results either reflect general form (the WTA big-match
                association, which disappears once regular-match form is removed) or come from robustness checks of an ATP clutch
                spread whose main statistic is not significant. Practically, a trait of a few percentage points cannot be excluded, and the bounds
                allow an effect large enough to matter in a forecast. Predictively, past big-match records did not improve
                out-of-sample forecasts, which is the question the forecasting model needs answered.</p>
              <p>The evidence therefore does not show that choking or clutch traits do not exist. It shows that tour-level
                results contain no reliable, measurable player-specific big-match signal of a size that would justify an
                adjustment. Records of a few dozen big matches are too noisy: at a typical win probability of 70%, chance alone
                gives a record of 100 big matches a standard deviation of about {pts(PER_100_SD)} points per match, comparable to
                the largest trait the bounds allow.</p>
            </Cols>
          </Subsection>
          <Subsection number="5.2" title="The WTA calibration pattern">
            <Cols>
              <p>The lower WTA big-match slope means favourites in WTA big matches win less often than Elo, calibrated on regular
                matches, would predict. This study cannot tell apart the possible explanations. Players who reach late rounds are
                selected for being in form that week, which narrows the true gap between them relative to their start-of-week
                ratings. The players in big matches are stronger on average, and Elo&apos;s rating gaps near the top of the WTA may
                be less informative than elsewhere. The larger gap in 2018–2026 coincides with changes in the WTA calendar and tier
                structure, including the larger WTA 1000 tier, but nothing here shows that either caused it. Pressure on favourites
                is one possibility among these, and the data do not single it out.</p>
            </Cols>
          </Subsection>
          <Subsection number="5.3" title="What the tests cannot see">
            <Cols>
              <p>The bounds assume a trait that is normally distributed and constant over a career. A few players with large
                effects among many with none would add little to the variance ratios and could escape them, and a trait that changes
                over a career would weaken the consistency and carry-over tests; the five-year scores in the out-of-sample test are
                only a partial check on that. The simulations also keep the matches that were actually played, although under the
                null different results would have produced different later-round matches.</p>
              <p>Other limitations are more ordinary. The study is post-hoc, and the multiple-testing family and several checks were
                chosen after earlier results were seen. Only {ps("ATP").players} ATP and {ps("WTA").players} WTA players have enough big
                matches in both periods, so the carry-over tests have little power. The bootstraps resample players or tournament
                editions but not both, so they do not capture every form of dependence between matches that share players. The
                expectation is Elo alone, which misses information such as injuries, and the game-share model is a single-slope
                fractional logit (<Cite id="papke">Papke and Wooldridge, 1996</Cite>). Pressure itself is never observed: the analysis
                measures results against expectation, not players&apos; experience.</p>
            </Cols>
          </Subsection>
          <Subsection number="5.4" title="Implications for Matchup DNA">
            <Cols>
              <p>Matchup DNA&apos;s live model is a frozen logistic regression on Elo and other pre-match features, under evaluation
                in a pre-registered prospective protocol. It has no big-match adjustment of any kind, and this exploratory study
                does not change it. The results argue against adding a player-specific big-match feature. A tour-level adjustment for
                WTA big matches is a better candidate, but its out-of-sample gain is small, it has varied over time, and it would
                have to be specified in advance and evaluated on new matches as a new model version.</p>
            </Cols>
          </Subsection>
        </Section>

        {/* ───────────────────────── 6 Conclusion ───────────────────────── */}
        <Section id="conclusion" number="6" title="Conclusion">
          <Cols>
            <p>In 26 years of tour-level results, players&apos; big-match records differ from one another by about as much as
              chance would make them differ, they are only weakly consistent within careers, and they did not improve forecasts
              of later big matches. The data rule out a large and stable choke or clutch trait, but not a modest one. The available
              evidence does not establish a sufficiently reliable player-specific big-match adjustment to justify adding one to
              Matchup DNA&apos;s forecasting model. The clearest result is a tour-level one: Elo is more overconfident in WTA big
              matches than in regular WTA matches, and that pattern is worth testing prospectively.</p>
          </Cols>
        </Section>

        <Section id="availability" number="7" title="Data and Code Availability">
          <Statements items={[
            { title: "Data and code", text: <>
              Match data are Jeff Sackmann&apos;s tennis_atp and tennis_wta files (CC BY-NC-SA 4.0), read from a June 2026
              snapshot; the data are not redistributed with the code. The analysis is reproduced by {code("python -m matchup_dna.posthoc_big_match")} followed by the
              companion modules {code("posthoc_big_match_robustness")}, {code("posthoc_big_match_players")} and {code("posthoc_big_match_forecast")}; {code("python -m web.publisher.research")} exports
              the figures shown here and refuses if a quoted headline figure differs from the analysis output. The SHA-256 fingerprints of
              the {r.provenance.data_files} input files are recorded in the forecast output (combined fingerprint
              {" "}{r.provenance.data_sha256.slice(0, 16)}…). The analysis code is in the project repository in the same commit
              as this version of the paper. Every random seed is fixed and no result depends on the order in which Python
              iterates over sets, so rerunning the commands on that commit with the same input files should reproduce the
              reported results. Step-by-step instructions are in docs/research/big-matches/README.md in the
              project repository.</> },
            { title: "Version history", text: <>
              This is version {meta.version} ({paperDate(meta.date)}). Version 3.0 corrected errors in versions 1 and 2: the sample had
              included Roland Garros 2026 and several team and other non-standard events and had used inconsistent WTA tier
              codes, and Holm&apos;s correction had covered only the variance ratios. The corrections changed the sample from
              131,649 to {count(r.matches)} matches and moved most figures. Versions 3.1 and 4.0 expanded the related research
              and attribution and made the split-half bootstrap reproducible (ATP interval now {signed(sh("ATP").low, 2)} to
              {" "}{signed(sh("ATP").high, 2)}). The full history is in docs/research/big-matches/CHANGELOG.md in the project
              repository.</> },
          ]} />
        </Section>

        <section aria-labelledby="acknowledgements-h" className="statements grid gap-2">
          <h2 id="acknowledgements-h" className="text-[23px] font-semibold sm:text-[25px]">Acknowledgements</h2>
          <p className="text-[15.5px] leading-[1.6]">Claude Code (Anthropic) was used to assist with the implementation of
            statistical analyses, generation of figures and tables, and drafting and editing of the manuscript. The author
            takes responsibility for the content, reported results, and any remaining errors.</p>
        </section>

        <References items={[
          { id: "baumeister", text: <>Baumeister, R. F. (1984). Choking under pressure: Self-consciousness and paradoxical effects of incentives on skillful performance. <i>Journal of Personality and Social Psychology</i>, 46(3), 610–620. https://doi.org/10.1037/0022-3514.46.3.610</> },
          { id: "birnbaum", text: <>Birnbaum, P. (2005). Clutch hitting and the Cramer test. <i>By the Numbers</i>, 15(1). Reprinted in <i>Baseball Research Journal</i>, 37 (2008). https://sabr.org/journal/article/clutch-hitting-and-the-cramer-test/</> },
          { id: "brown2008", text: <>Brown, L. D. (2008). In-season prediction of batting averages: A field test of empirical Bayes and Bayes methodologies. <i>Annals of Applied Statistics</i>, 2(1), 113–152. https://doi.org/10.1214/07-AOAS138</> },
          { id: "brown", text: <>Brown, W. (1910). Some experimental results in the correlation of mental abilities. <i>British Journal of Psychology</i>, 3(3), 296–322. https://doi.org/10.1111/j.2044-8295.1910.tb00207.x</> },
          { id: "cohenzada", text: <>Cohen-Zada, D., Krumer, A., Rosenboim, M., and Shapir, O. M. (2017). Choking under pressure and gender: Evidence from professional tennis. <i>Journal of Economic Psychology</i>, 61, 176–190. https://doi.org/10.1016/j.joep.2017.04.005</> },
          { id: "cramer", text: <>Cramer, R. D. (1977). Do clutch hitters exist? <i>Baseball Research Journal</i>, 6. Society for American Baseball Research. https://sabr.org/journal/article/do-clutch-hitters-exist/</> },
          { id: "efron1979", text: <>Efron, B. (1979). Bootstrap methods: Another look at the jackknife. <i>Annals of Statistics</i>, 7(1), 1–26. https://doi.org/10.1214/aos/1176344552</> },
          { id: "efron", text: <>Efron, B., and Morris, C. (1975). Data analysis using Stein&apos;s estimator and its generalizations. <i>Journal of the American Statistical Association</i>, 70(350), 311–319. https://doi.org/10.1080/01621459.1975.10479864</> },
          { id: "elo", text: <>Elo, A. E. (1978). <i>The Rating of Chessplayers, Past and Present</i>. New York: Arco.</> },
          { id: "gonzalez", text: <>González-Díaz, J., Gossner, O., and Rogers, B. W. (2012). Performing best when it matters most: Evidence from professional tennis. <i>Journal of Economic Behavior &amp; Organization</i>, 84(3), 767–781. https://doi.org/10.1016/j.jebo.2012.09.021</> },
          { id: "gorgi", text: <>Gorgi, P., Koopman, S. J., and Lit, R. (2019). The analysis and forecasting of tennis matches by using a high dimensional dynamic model. <i>Journal of the Royal Statistical Society Series A</i>, 182(4), 1393–1409. https://doi.org/10.1111/rssa.12464</> },
          { id: "harris", text: <>Harris, D. J., Vine, S. J., Eysenck, M. W., and Wilson, M. R. (2021). Psychological pressure and compounded errors during elite-level tennis. <i>Psychology of Sport and Exercise</i>, 56, 101987. https://doi.org/10.1016/j.psychsport.2021.101987</> },
          { id: "holm", text: <>Holm, S. (1979). A simple sequentially rejective multiple test procedure. <i>Scandinavian Journal of Statistics</i>, 6(2), 65–70. https://www.jstor.org/stable/4615733</> },
          { id: "james", text: <>James, B. (2004). Underestimating the fog. <i>Baseball Research Journal</i>, 33. Society for American Baseball Research. https://sabr.org/research/article/underestimating-the-fog/</> },
          { id: "jetter", text: <>Jetter, M., and Walker, J. K. (2015). Game, set, and match: Do women and men perform differently in competitive situations? <i>Journal of Economic Behavior &amp; Organization</i>, 119, 96–108. https://doi.org/10.1016/j.jebo.2015.07.017</> },
          { id: "klaassen", text: <>Klaassen, F. J. G. M., and Magnus, J. R. (2001). Are points in tennis independent and identically distributed? Evidence from a dynamic binary panel data model. <i>Journal of the American Statistical Association</i>, 96(454), 500–509. https://doi.org/10.1198/016214501753168217</> },
          { id: "kovalchik", text: <>Kovalchik, S. A. (2016). Searching for the GOAT of tennis win prediction. <i>Journal of Quantitative Analysis in Sports</i>, 12(3), 127–138. https://doi.org/10.1515/jqas-2015-0059</> },
          { id: "kovalchikingram", text: <>Kovalchik, S., and Ingram, M. (2016). Hot heads, cool heads, and tacticians: Measuring the mental game in tennis. MIT Sloan Sports Analytics Conference, Research Papers Competition (paper 1464). https://martiningram.github.io/papers/hot-heads-cool-heads.pdf</> },
          { id: "kovalchikreid", text: <>Kovalchik, S. A., and Reid, M. (2020). Measuring clutch performance in professional tennis. <i>Statistica Applicata – Italian Journal of Applied Statistics</i>, 30(2), 255–268. https://doi.org/10.26398/IJAS.0030-011</> },
          { id: "lakens", text: <>Lakens, D. (2017). Equivalence tests: A practical primer for t tests, correlations, and meta-analyses. <i>Social Psychological and Personality Science</i>, 8(4), 355–362. https://doi.org/10.1177/1948550617697177</> },
          { id: "papke", text: <>Papke, L. E., and Wooldridge, J. M. (1996). Econometric methods for fractional response variables with an application to 401(k) plan participation rates. <i>Journal of Applied Econometrics</i>, 11(6), 619–632. https://doi.org/10.1002/(SICI)1099-1255(199611)11:6&lt;619::AID-JAE418&gt;3.0.CO;2-1</> },
          { id: "paserman", text: <>Paserman, M. D. (2023). Gender differences in performance in competitive environments? Evidence from professional tennis players. <i>Journal of Economic Behavior &amp; Organization</i>, 212, 590–609. https://doi.org/10.1016/j.jebo.2023.05.042</> },
          { id: "sackmann2019a", text: <>Sackmann, J. (2019a, February 20). Dominic Thiem, Tennys Sandgren, and playing your way in. <i>Tennis Abstract</i>. https://www.tennisabstract.com/blog/2019/02/20/dominic-thiem-tennys-sandgren-and-playing-your-way-in/</> },
          { id: "sackmann2019b", text: <>Sackmann, J. (2019b, December 3). An introduction to tennis Elo. <i>Tennis Abstract</i>. https://www.tennisabstract.com/blog/2019/12/03/an-introduction-to-tennis-elo/</> },
          { id: "sackmann2025", text: <>Sackmann, J. (2025, January 17). Matteo Berrettini and best-of-five puzzles. <i>Tennis Abstract</i>. https://www.tennisabstract.com/blog/2025/01/17/matteo-berrettini-and-best-of-five-puzzles/</> },
          { id: "sackmann", text: <>Sackmann, J. (2026). Tennis databases, files, and algorithms: tennis_atp and tennis_wta [data sets]. Jeff Sackmann / Tennis Abstract. Licensed CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/). Read from a June 2026 snapshot (archive mirror github.com/Aneeshers/tennis-sackmann-archive); the original repositories at github.com/JeffSackmann were unavailable on 16 November 2026.</> },
          { id: "spearman", text: <>Spearman, C. (1910). Correlation calculated from faulty data. <i>British Journal of Psychology</i>, 3(3), 271–295. https://doi.org/10.1111/j.2044-8295.1910.tb00206.x</> },
          { id: "tango", text: <>Tango, T. M., Lichtman, M. G., and Dolphin, A. E. (2007). <i>The Book: Playing the Percentages in Baseball</i>. Washington, DC: Potomac Books.</> },
        ]} />

        {/* ───────────────────────── Appendix A ───────────────────────── */}
        <div className="page-break" />
        <Section id="appendix-a" number="Appendix A" title="Supplementary Tables">
          <Table number="A1"
            caption={<>Simulation tests: each statistic against {count(rb.sims.null)} simulated data sets with no trait. Holm-adjusted p across the {family.length} trait statistics (both tours) and within each tour.</>}
            head={["Statistic", "ATP obs.", "ATP p", "Holm", "Holm (tour)", "WTA obs.", "WTA p", "Holm", "Holm (tour)"]}
            rows={NULL_LABELS.map(([test, label]) => {
              const a = nullRow("ATP", test), w = nullRow("WTA", test);
              const h = (x?: number) => (x === undefined ? "–" : pv(x));
              return [label, signed(a.observed, 2), pv(a.p), h(a.holm), h(a.holm_tour), signed(w.observed, 2), pv(w.p), h(w.holm), h(w.holm_tour)];
            })} />
          <Table number="A2"
            caption={<>Power at each trait size and the 95% upper bound on the trait, with its Monte Carlo range. Trait sizes τ = {rb.power.taus.map((t) => t.toFixed(2)).join(", ")}, an edge at even odds of {rb.power.evens.map(pts).join(", ")} points.</>}
            head={["Tour and test", ...rb.power.evens.map((e) => pts(e)), "Bound (range)"]}
            rows={TOURS.flatMap((tour) => NULL_LABELS.filter(([t]) => t !== "ratio regular matches").map(([test, label]) => {
              const p = powerRow(tour, test);
              return [`${tour}, ${label.toLowerCase()}`, ...p.power.map(pct),
                      p.bound_points === null ? "–" : `${pts(p.bound_points)} (${pts(p.bound_low_points!)}–${pts(p.bound_high_points!)})`];
            }))} />
          <Table number="A3"
            caption={<>Out-of-sample evaluation in full: differences from M1 in thousandths of log loss (and, for both tours, of Brier score) with 95% edition-bootstrap intervals. The lower block is limited to big matches in which both players had at least {r.min_big} earlier big matches.</>}
            head={["Model", "ATP Δ log loss", "WTA Δ log loss", "Both Δ log loss", "Both Δ Brier"]}
            rows={["big matches", "big matches, both players with 10+ earlier big"].flatMap((subset) =>
              (["M0", "big", "clutch", "big_eb", "clutch_eb", "big_recent", "clutch_recent"] as const).map((name) => {
                const cell = (tour: string) => { const m = model(tour, name, subset); return diffCell(m.log_loss_diff!, m.log_loss_low!, m.log_loss_high!); };
                const b = model("both", name, subset);
                return [`${OOS_LABELS.find(([n]) => n === name)![1]}${subset === "big matches" ? "" : " (long histories)"}`, cell("ATP"), cell("WTA"), cell("both"),
                        diffCell(b.brier_diff!, b.brier_low!, b.brier_high!)];
              }))}
            note={<>Matches: all big matches {count(evaluation("ATP").matches)} ATP, {count(evaluation("WTA").matches)} WTA; long histories {count(evaluation("ATP", "big matches, both players with 10+ earlier big").matches)} ATP, {count(evaluation("WTA", "big matches, both players with 10+ earlier big").matches)} WTA. Baseline log loss (M1), all big matches: ATP {model("ATP", "M1").log_loss.toFixed(4)}, WTA {model("WTA", "M1").log_loss.toFixed(4)}.</>} />
          <Table number="A4"
            caption={<>Calibration slopes by period, big against regular, with model-based p-values.</>}
            head={["Period", "Tour and format", "Big", "Regular", "Difference", "Wald p"]}
            rows={fc.calibration.periods.map((c) => [c.period.replace("-", "–"), c.key.replace(" bo", ", best of "), three(c.big), three(c.regular), signed(c.difference), pv(c.wald_p)])} />
          <Table number="A5"
            caption={<>Sensitivity of the carry-over association, one setting changed at a time: clutch-score correlation with 95% interval, and β with permutation p for each score ({count(rb.sims.permutations)} permutations, drawn afresh, so the first rows differ slightly from Table 4).</>}
            head={["Tour and variant", "Players", "Clutch r (95%)", "β big (p)", "β clutch (p)"]}
            rows={rb.sensitivity.map((s) => [`${s.tour}, ${SENS_LABEL[s.label] ?? s.label}`, s.players, `${signed(s.clutch_r, 2)} (${signed(s.clutch_low, 2)} to ${signed(s.clutch_high, 2)})`,
              `${signed(s.big_beta, 2)} (${pv(s.big_p)})`, `${signed(s.clutch_beta, 2)} (${pv(s.clutch_p)})`])} />
          <Table number="A6"
            caption={<>Game margins: share of games won against a fitted expectation. Variance ratios with permutation p ({count(rb.sims.game_permutations)} permutations within strata of format, match type and closeness).</>}
            head={["Statistic", "ATP", "WTA"]}
            rows={[
              ["Matches", count(game("ATP").matches), count(game("WTA").matches)],
              ...SETS.map(([set, label]) => [`Variance ratio, ${label.toLowerCase()}`, `${two(gameSet("ATP", set).ratio)} (p ${pv(gameSet("ATP", set).p)})`, `${two(gameSet("WTA", set).ratio)} (p ${pv(gameSet("WTA", set).p)})`]),
              ["Clutch spread", `${two(game("ATP").clutch.ratio)} (p ${pv(game("ATP").clutch.p)})`, `${two(game("WTA").clutch.ratio)} (p ${pv(game("WTA").clutch.p)})`],
              ["Split-half r", interval(game("ATP").split_half), interval(game("WTA").split_half)],
              ["Carry-over r, clutch score", interval(game("ATP").correlations.clutch), interval(game("WTA").correlations.clutch)],
              ["Association β, clutch score (p)", `${signed(game("ATP").forecasts.clutch.beta, 2)} (${pv(game("ATP").forecasts.clutch.p)})`, `${signed(game("WTA").forecasts.clutch.beta, 2)} (${pv(game("WTA").forecasts.clutch.p)})`],
            ]} />
          <Table number="A7"
            caption={<>Within-tournament ratings: the main statistics with each player&apos;s rating updated through their earlier rounds of the same event.</>}
            head={["Statistic", "ATP", "WTA"]}
            rows={[
              ["Big matches with a complete earlier-round record", pct(within("ATP").eligible), pct(within("WTA").eligible)],
              ...SETS.map(([set, label]) => [`Variance ratio, ${label.toLowerCase()}`, two(within("ATP").spread[set]!), two(within("WTA").spread[set]!)]),
              ["Clutch spread", two(within("ATP").clutch), two(within("WTA").clutch)],
              ["Split-half r", interval(within("ATP").split_half), interval(within("WTA").split_half)],
              ["Association β, clutch score (p)", `${signed(within("ATP").forecasts.clutch.beta, 2)} (${pv(within("ATP").forecasts.clutch.p)})`, `${signed(within("WTA").forecasts.clutch.beta, 2)} (${pv(within("WTA").forecasts.clutch.p)})`],
            ]} />
          <Table number="A8"
            caption={<>ATP clutch spread within one format: big against regular matches of the same length. Wins against {count(rb.sims.null)} simulations; games against {count(rb.sims.game_permutations)} permutations. Added in version 2, after an ATP result had been seen.</>}
            head={["Format", "Big matches", "Regular matches", "Players", "Wins (p)", "Games (p)"]}
            rows={rb.format.map((f) => [`Best of ${f.best_of}`, count(f.big_matches), count(f.regular_matches), f.wins.players,
              `${two(f.wins.ratio)} (${pv(f.wins.p)})`, `${two(f.games.ratio)} (${pv(f.games.p)})`])} />
        </Section>

        {/* ───────────────────────── Appendix B ───────────────────────── */}
        <Section id="appendix-b" number="Appendix B" title="Technical Details">
          <Subsection number="B.1" title="Match classification">
            <Cols>
              <p>Events are main-tour levels in Sackmann&apos;s files (ATP: Grand Slam, Masters, tour, Finals, Olympics; WTA: Grand
                Slam, Tier I–V, Premier Mandatory, Premier, International, Finals, Olympics and the 2021 events coded W), minus
                events whose names identify them as the ATP Cup, United Cup, Laver Cup, Next Gen Finals or a WTA 125 event, and the
                World Team Cup (Düsseldorf round robin, 2000–2012). The season-ending Finals are the events named Masters Cup and Tour
                Finals (ATP) and WTA Tour Championships, WTA Championships, WTA Finals and their host-city names from 2016 on (WTA).
                WTA top-tier events by year are listed in the analysis code (WTA_TOP_TIER in matchup_dna/posthoc_big_match.py) and
                were checked against season records: Premier Mandatory (Indian Wells, Miami, Madrid, Beijing) and Premier 5 (Dubai or
                Doha, Rome, Canada, Cincinnati, and Tokyo to 2013 or Wuhan from 2014) for 2009–2020, and the WTA 1000 events actually
                played from 2021.</p>
            </Cols>
          </Subsection>
          <Subsection number="B.2" title="Simulations, power and bounds">
            <Cols>
              <p>Each simulated data set draws one Bernoulli outcome per match from its calibrated probability, so the two players&apos;
                results are always complementary. The calibration is refitted on the simulated outcomes before any statistic is
                computed, so the simulated statistics carry the same estimation noise as the observed ones. One-sided p-values are
                (1 + number at least as large) / (1 + number of simulations). In the power simulations the trait θ<sub><i>i</i></sub> is
                drawn once per player and added to the log-odds of every big match (equation 6). The Monte Carlo range of a bound is
                the 2.5th to 97.5th percentile of the bound over 1,000 resamples of the simulated statistics at each grid point; it
                reflects simulation noise only, not sampling uncertainty in the data.</p>
            </Cols>
          </Subsection>
          <Subsection number="B.3" title="Game margins">
            <Cols>
              <p>Each result is replaced by the share of games the player won, with a tie-break that decides a match counted as one
                game. The expected share is a fractional logit on the Elo log-odds, fitted per tour, match type and format. Residuals
                are permuted among matches within strata defined by those groups and by decile of the absolute Elo log-odds, and each
                stratum&apos;s mean squared residual is its noise variance, because close matches have more variable game shares than
                one-sided ones. Version 2 permuted within the groups only.</p>
            </Cols>
          </Subsection>
          <Subsection number="B.4" title="Empirical Bayes scores">
            <Cols>
              <p>In the out-of-sample variant, a player&apos;s mean big-match residual <i>m</i><sub><i>i</i></sub>, with noise variance
                {" "}<i>v</i><sub><i>i</i></sub> = Σ<i>p</i>(1 − <i>p</i>)/<i>n</i><sub><i>i</i></sub>², is shrunk to
                {" "}<i>m</i><sub><i>i</i></sub> τ²/(τ² + <i>v</i><sub><i>i</i></sub>), where τ² is the mean of <i>m</i><sub><i>i</i></sub>²
                minus the mean of <i>v</i><sub><i>i</i></sub> over players with at least {r.min_big} big matches before the year being
                predicted, floored at zero. The clutch version applies the same formula to the difference between the big- and
                regular-match means, with the two noise variances added.</p>
            </Cols>
          </Subsection>
        </Section>
      </Body>

      <Footer paper={meta} author={AUTHOR} />
    </Sheet>
  );
}
