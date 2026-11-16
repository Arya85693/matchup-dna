import type { Metadata } from "next";
import { Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import {
  Dumbbell, Forest, GroupedBars, PowerCurves, RunCurve, StudyFlow, type BarGroup, type ForestGroup, type PowerPanel,
} from "@/components/research/charts";
import {
  Abstract, Body, Cite, Cols, Eq, Figure, Footer, FrontMatter, Masthead, References, Section, Sheet, Statements, Subsection,
  Table, TitleBlock, type MetaItem,
} from "@/components/research/Paper";
import { paper, paperDate } from "@/lib/papers";
import { BIG_MATCH } from "@/lib/research";

const serif = Source_Serif_4({ subsets: ["latin", "latin-ext"], variable: "--font-serif", display: "swap" });
const meta = paper("big-matches");

export const metadata: Metadata = { title: meta.title, description: meta.abstract };

const r = BIG_MATCH;
const rb = r.robustness;
const TOURS = ["ATP", "WTA"] as const;
const two = (v: number) => v.toFixed(2);
const three = (v: number) => v.toFixed(3);
const signed = (v: number, d = 3) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}`;
const pp = (v: number) => (100 * v).toFixed(1);
const pct = (v: number) => `${Math.round(v * 100)}%`;
const count = (v: number) => v.toLocaleString("en-GB");
const pv = (p: number) => (p < 0.001 ? "< 0.001" : p.toFixed(3));
const pts = (v: number) => v.toFixed(1);
const slope = (tour: string, kind: "big" | "regular", bo: number) =>
  r.calibration.find((c) => c.tour === tour && c.kind === kind && c.best_of === bo)?.slope;
const spread = (tour: string, set: string) => r.spread.find((s) => s.tour === tour && s.set === set)!;
const ps = (tour: string) => r.period_split[tour]!;
const sh = (tour: string) => r.split_half[tour]!;
const interval = (c: { r: number; low: number; high: number }) => `${signed(c.r)} (${signed(c.low)} to ${signed(c.high)})`;
const corr = (c: { r: number; low: number; high: number }) => `${signed(c.r, 2)} (95% interval ${signed(c.low, 2)} to ${signed(c.high, 2)})`;
const v = (name: string, sub?: string) => <>{name}{sub && <sub>{sub}</sub>}</>;

const nullRow = (tour: string, test: string) => rb.null.find((n) => n.tour === tour && n.test === test)!;
const powerRow = (tour: string, test: string) => rb.power.rows.find((p) => p.tour === tour && p.test === test)!;
const slopeTest = (tour: string, bo: number) => rb.slope_tests.find((s) => s.tour === tour && s.best_of === bo);
const game = (tour: string) => rb.games.find((g) => g.tour === tour)!;
const gameSet = (tour: string, set: string) => game(tour).spread.find((s) => s.set === set)!;
const within = (tour: string) => rb.within.find((w) => w.tour === tour)!;
const holm = (tour: string, set: string) => rb.holm.find((h) => h.tour === tour && h.set === set)!.p;
const tauAt = (tau: number) => rb.power.taus.indexOf(tau);
const evensAt = (tau: number) => rb.power.evens[tauAt(tau)]!;
const powerAt = (tour: string, test: string, tau: number) => powerRow(tour, test).power[tauAt(tau)]!;
const bound = (tour: string, test: string) => powerRow(tour, test).bound_points;
const boundText = (tour: string, test: string) => { const b = bound(tour, test); return b === null ? "not reached" : `${pts(b)} percentage points`; };

const SETS: [string, string][] = [
  ["finals only", "Finals only"],
  ["semi-finals + finals", "Semi-finals and finals"],
  ["all big matches", "All big matches"],
  ["regular matches", "Regular matches"],
];
const bigSets = r.spread.filter((s) => s.set !== "regular matches");
const maxBigRatio = Math.max(...bigSets.map((s) => s.ratio));
const minBigRatio = Math.min(...bigSets.map((s) => s.ratio));
const nullTests = rb.null.length / 2;
const maxReliability = Math.max(sh("ATP").spearman_brown, sh("WTA").spearman_brown);
const strongestAt = (tau: number) => Math.max(...rb.power.rows.filter((p) => p.test !== "ratio regular matches").map((p) => p.power[tauAt(tau)]!));

// Sample sizes by tour. Every analysed match has a readable score, so the game-margin counts are the match counts.
const atpBig = rb.format.reduce((s, f) => s + f.big_matches, 0);
const SAMPLE = {
  ATP: { matches: game("ATP").matches, big: atpBig },
  WTA: { matches: game("WTA").matches, big: r.big_matches - atpBig },
};

// Worked examples for Section 4 (illustrative numbers, not data).
const EXAMPLE_P = 0.7;
const shrunk = (n: number, mean: number) => (n * mean) / (n + r.shrink);
const luckSd100 = 100 * Math.sqrt((EXAMPLE_P * (1 - EXAMPLE_P)) / 100);

const SPREAD_GROUPS: BarGroup[] = SETS.map(([set, label]) => ({
  label, note: set === "regular matches" ? "reference" : undefined,
  bars: TOURS.map((tour) => ({ series: tour, value: spread(tour, set).ratio })),
}));

const CALIBRATION_ROWS = [
  { label: "ATP, best of 3", series: "ATP", a: slope("ATP", "big", 3)!, b: slope("ATP", "regular", 3)! },
  { label: "ATP, best of 5", series: "ATP", a: slope("ATP", "big", 5)!, b: slope("ATP", "regular", 5)! },
  { label: "WTA, best of 3", series: "WTA", a: slope("WTA", "big", 3)!, b: slope("WTA", "regular", 3)! },
];

const FOREST_GROUPS: ForestGroup[] = [
  { label: "Split-half", note: `two halves of ${r.window}`, rows: TOURS.map((t) => ({ series: t, value: sh(t).r, low: sh(t).low, high: sh(t).high })) },
  ...([["big-match", "Big-match score"], ["clutch", "Clutch score"], ["regular-match", "Regular-match score"]] as const).map(([key, label]) => ({
    label, note: key === "regular-match" ? "reference" : `${r.periods[0]} to ${r.periods[1]}`,
    rows: TOURS.map((t) => { const c = ps(t).correlations[key]; return { series: t, value: c.r, low: c.low, high: c.high }; }),
  })),
];

const PRIMARY: [string, string, string][] = [
  ["clutch ratio", "Clutch spread", "big minus regular, beyond luck"],
  ["split-half r", "Split-half agreement", "two halves of each career"],
  ["forecast z clutch", "Forecast test", "earlier clutch score"],
];
const POWER_PANELS: PowerPanel[] = PRIMARY.map(([test, title, note]) => ({
  title, note, series: TOURS.map((tour) => ({ series: tour, points: rb.power.evens.map((x, i) => ({ x, y: powerRow(tour, test).power[i]! })) })),
}));

const NULL_LABELS: [string, string][] = [
  ["ratio finals only", "Spread ratio, finals only"],
  ["ratio semi-finals + finals", "Spread ratio, semi-finals and finals"],
  ["ratio all big matches", "Spread ratio, all big matches"],
  ["ratio regular matches", "Spread ratio, regular matches (reference)"],
  ["clutch ratio", "Clutch spread ratio"],
  ["split-half r", "Split-half r"],
  ["period r big", "Carry-over r, big-match score"],
  ["period r clutch", "Carry-over r, clutch score"],
  ["forecast z big", "Forecast test z, big-match score"],
  ["forecast z clutch", "Forecast test z, clutch score"],
];

const SENS_LABEL: Record<string, string> = {
  "version 1 settings": "Main analysis settings",
  "shrinkage 10": "Shrinkage constant 10",
  "shrinkage 50": "Shrinkage constant 50",
  "shrinkage 100": "Shrinkage constant 100",
  "minimum 5": "Minimum 5 big matches",
  "minimum 20": "Minimum 20 big matches",
  "semi-finals and finals only": "Semi-finals and finals only",
  "periods 2008-2015 / 2016-2026": "Periods 2008–2015 / 2016 – May 2026",
};
const sensitivityPs = rb.sensitivity.flatMap((s) => [s.big_p, s.clutch_p]);
const minSensitivityP = Math.min(...sensitivityPs);
const sens = (tour: string, label: string) => rb.sensitivity.find((s) => s.tour === tour && s.label === label)!;
const altPeriods = sens("ATP", "periods 2008-2015 / 2016-2026");
const byFormat = (bo: number) => rb.format.find((f) => f.best_of === bo)!;

const META: MetaItem[] = [
  { label: "Status", value: <>Post-hoc and descriptive. Not pre-registered. Not peer reviewed.</> },
  { label: "Analysis", value: <>Main analysis run 14 November 2026, with its definitions fixed in the script beforehand. The checks in Sections 4.5 and 4.6 were added afterwards, once the first results were known.</> },
  { label: "Data", value: <>Jeff Sackmann, tennis_atp and tennis_wta, to 25 May 2026 (CC BY-NC-SA 4.0).</> },
  { label: "Reproduce", value: (
    <span className="grid gap-1.5 font-mono text-[11px] [overflow-wrap:anywhere]">
      <span>python -m matchup_dna.<wbr />posthoc_big_match</span>
      <span>python -m matchup_dna.<wbr />posthoc_big_match_robustness</span>
    </span>
  ) },
  { label: "Citation", value: <>Matchup DNA Research ({meta.date.slice(0, 4)}). {meta.title} {meta.subtitle}. Matchup DNA Working Paper {meta.number}, version {meta.version}.</> },
  { label: "Related", value: <><Link href="/methodology" className="ref">How the forecasts are made</Link><br /><Link href="/lab" className="ref">Model Lab</Link></> },
];

export default function BigMatchesPaper() {
  const atpGame = game("ATP"), wtaGame = game("WTA");
  return (
    <Sheet fontClass={serif.variable}>
      <Masthead paper={meta} />

      <FrontMatter meta={META}>
        <TitleBlock paper={meta} authors="Matchup DNA Research" affiliation="Matchup DNA, a non-commercial tennis forecasting project" />
        <Abstract keywords={meta.keywords} parts={[
          { label: "Background", text: <>Tennis commentary often says that certain players “choke” when the stakes are highest, while others raise their game. If either tendency were real and lasting, it would be useful for forecasting matches. We asked whether it shows up in results.</> },
          { label: "Methods", text: <>We studied {count(r.matches)} main-tour ATP and WTA matches played from 2000 to May 2026. Of these, {count(r.big_matches)} were big matches: semi-finals and finals, the closing rounds of Grand Slams and Masters events, and the season-ending Finals. Each result was compared with the outcome expected from a calibrated Elo rating. We then asked three questions. Do players differ in big matches by more than luck would produce? Does one half of a player’s big-match record agree with the other half? And does a record from {r.periods[0]} predict one from {r.periods[1]}? Computer simulation was used to judge each result and to work out how large an effect the tests could have missed.</> },
          { label: "Results", text: <>Players’ big-match records varied {two(minBigRatio)} to {two(maxBigRatio)} times as much as luck alone would make them vary. The two halves of a player’s record barely agreed (correlations of {signed(sh("ATP").r, 2)} on the ATP tour and {signed(sh("WTA").r, 2)} on the WTA tour), and earlier records did not improve forecasts of later big matches. A player one standard deviation better than average under pressure would gain at most about {pts(bound("ATP", "clutch ratio")!)} percentage points against an equal opponent on the ATP tour, and {pts(bound("WTA", "clutch ratio")!)} points on the WTA tour. ATP results showed a slight excess of variation in big matches (p = {pv(nullRow("ATP", "clutch ratio").p)}), but it did not survive correction for the number of tests and did not persist over time.</> },
          { label: "Conclusions", text: <>We find no evidence of a large, lasting choking or clutch trait in professional tennis. A small effect cannot be ruled out, but it would be too small to detect for any individual player, so our forecasts treat a final like any other match between the same two players.</> },
        ]} />
      </FrontMatter>

      <Body>
        {/* ───────────────────────── 1 Introduction ───────────────────────── */}
        <Section id="introduction" number="1" title="Introduction">
          <Cols>
            <p>Few ideas in tennis commentary last as well as the idea that some players choke. A player reaches a final as the favourite and loses. After the second or third time, the losses stop being described as bad days and start being described as part of who the player is: they “cannot close”, they “freeze on the big stage”. The opposite story is just as familiar. Some players are said to have a level they only find in the biggest matches, and their records in finals are offered as the proof.</p>
            <p>Both stories describe a trait, a lasting tendency to do worse, or better, when the stakes are high. Unlike many claims about sporting temperament, this one can be tested. If a player really does fall short in big matches, the shortfall should appear across all of their big matches and not only in the ones people remember. It should also continue: a player who choked in the past should be more likely than their strength suggests to lose big matches in the future.</p>
            <p>That second property is the reason the question matters to this project. Matchup DNA publishes forecasts for professional tennis matches. If choking were real and predictable, it is exactly the kind of information a forecast ought to use. A player known to fall short in finals should be given a lower chance in their next final, and a player known to rise to the occasion a higher one. If the pattern is an illusion, building it into a forecast would make the forecast worse, because it would move probabilities in response to noise.</p>
            <p>The question we ask is therefore a narrow one. We do not ask whether pressure affects tennis players at all. It almost certainly affects some players at some moments, and the studies reviewed in Section 2 find evidence of this at the level of individual points. We ask the question a forecast needs answered: <i>once a player’s general strength is taken into account, do their results in big matches differ from expectation in a way that is consistent and lasting?</i></p>
            <p>Answering it is harder than it first appears, because big matches are rare. Even a leading player reaches only a handful of finals in a season, and a record built from twenty finals can look strikingly good or strikingly bad through chance alone. Most of the work in this paper goes into separating genuine differences between players from the differences that luck produces anyway. The tools come from baseball, where analysts spent decades asking the same question about “clutch hitters”, and from the statistics of small samples. We apply them to {count(r.matches)} tour-level matches from 2000 to May 2026.</p>
            <p>A finding of “no effect” is only informative if we also know how large an effect the analysis could have missed. A study with too little data will find nothing whether or not a trait exists. For that reason we report, alongside every test, how often it would have detected a trait of a given size, and we use this to put an upper limit on how large the trait could be.</p>
            <p>In brief, we find that players’ big-match records vary by about as much as chance alone would make them vary, that one part of a player’s big-match record says very little about another part, and that the data rule out a large choking or clutch trait. A small trait cannot be excluded. The ATP tour shows a weak sign of one, which we examine in detail, but it does not meet the usual standard of evidence once the number of tests is taken into account, and it does not carry forward in time.</p>
            <p>The paper is organised as follows. Section 2 reviews earlier research on pressure and performance. Section 3 describes the data and explains how big matches are defined. Section 4 sets out the method and Section 5 reports the results. Section 6 discusses what the results mean, including why the choking story is so persuasive if the effect behind it is small. Sections 7 and 8 cover the limitations and possible future work, and Section 9 concludes. Supplementary tables and technical details are in the appendices.</p>
          </Cols>
        </Section>

        {/* ───────────────────────── 2 Background ───────────────────────── */}
        <Section id="background" number="2" title="Background and related research">
          <Subsection number="2.1" title="Choking under pressure">
            <Cols>
              <p>Psychologists have studied “choking under pressure” for several decades. In an influential set of experiments, <Cite id="baumeister">Baumeister (1984)</Cite> found that raising the stakes of a skilled task could make performance worse, and linked the effect to heightened self-consciousness: under pressure, people attend to movements that would normally run automatically, and the attention gets in the way. Effects of this kind are well established in the laboratory.</p>
              <p>Laboratory tasks are a long way from a Grand Slam final, however. The tasks are short, the stakes are modest, and the participants are rarely experts. Professional players have spent most of their lives competing under scrutiny, and the players who reach the latter stages of big events are, by construction, those who have handled pressure well enough to get there. Whether laboratory choking carries over to elite sport is an empirical question.</p>
            </Cols>
          </Subsection>

          <Subsection number="2.2" title="Evidence from professional sport">
            <Cols>
              <p>Field studies from sport have produced mixed results. Penalty shoot-outs in football are a natural test case, because the order of kicking is decided by a coin toss. <Cite id="apesteguia">Apesteguia and Palacios-Huerta (2010)</Cite> reported that the team kicking second won less often, which they attributed to the pressure of falling behind. A later study using a larger sample did not reproduce the result (<Cite id="kocher">Kocher et al., 2012</Cite>), a reminder that pressure effects in the field can be smaller and less stable than they first appear.</p>
              <p>Tennis is well suited to this kind of research, because the scoring system makes some points far more important than others. <Cite id="klaassen">Klaassen and Magnus (2001)</Cite> showed that points in tennis are not exactly independent and identically distributed, but that the departures are small, so a simple model of independent points is a good approximation. <Cite id="gonzalez">González-Díaz et al. (2012)</Cite> found that players differ in how their performance changes on the most important points of a match, and <Cite id="cohenzada">Cohen-Zada et al. (2017)</Cite> reported that the effect of pressure at important stages of a match differs between men and women.</p>
              <p>These studies work within matches. They show that pressure can matter for individual points, but they do not tell us whether those point-level differences add up to a visible pattern in match results, or whether they persist across a career. That is the gap this paper addresses. It is also the level at which a forecast operates, since a match forecast is a statement about who wins the match, not about any single point.</p>
            </Cols>
          </Subsection>

          <Subsection number="2.3" title="Lessons from the search for clutch hitters">
            <Cols>
              <p>The closest precedent for our approach comes from baseball. For decades, managers and commentators believed that certain hitters performed better in “clutch” situations, late in close games. <Cite id="cramer">Cramer (1977)</Cite> tested the idea by asking whether a player’s clutch performance in one season predicted his clutch performance in the next. It barely did, and Cramer concluded that clutch hitting, as distinct from hitting in general, showed little evidence of being a lasting skill. Our period carry-over test (Section 4.4) follows the same logic.</p>
              <p>A related statistical problem is how much to believe a record built from a small sample. <Cite id="efron">Efron and Morris (1975)</Cite> showed, using early-season batting averages, that the best predictions of a player’s true ability pull each player’s record toward the group average, and pull hardest when the record is short. This idea, known as empirical Bayes estimation or shrinkage, is central to our method. <Cite id="brown2008">Brown (2008)</Cite> later tested it by predicting second-half batting averages from first-half ones, which is the template for our split-half test.</p>
            </Cols>
          </Subsection>

          <Subsection number="2.4" title="Rating tennis players">
            <Cols>
              <p>To ask whether a player did better or worse than expected, we need an expectation. We use the Elo rating system, first developed for chess (<Cite id="elo">Elo, 1978</Cite>). In a comparison of published methods for predicting tennis results, <Cite id="kovalchik">Kovalchik (2016)</Cite> found Elo ratings to be among the most accurate, despite their simplicity. Elo has a further advantage for this study: it rates players using only results that were known before each match, so the expectation for a match cannot be contaminated by its own outcome.</p>
            </Cols>
          </Subsection>
        </Section>

        {/* ───────────────────────── 3 Data ───────────────────────── */}
        <Section id="data" number="3" title="Data">
          <Subsection number="3.1" title="Source and coverage">
            <Cols>
              <p>Match results come from Jeff Sackmann’s public ATP and WTA match files (<Cite id="sackmann">Sackmann, 2026</Cite>), which record every tour-level match with its date, round, surface, score and players. We use matches up to 25 May 2026. Results from June 2026 onwards are deliberately left out, because those matches are reserved for the project’s pre-registered forecast evaluations and must not be used in any exploratory analysis.</p>
              <p>Elo ratings are computed over the whole history of the files, from 1968, so that every player has a settled rating by the time the analysis begins. The analysis itself covers matches from the start of 2000. This gives more than a quarter of a century of results while keeping the data within the era of consistent record-keeping and modern scheduling.</p>
              <p>Only main-tour matches are included: Grand Slams, Masters and Premier events, regular tour events, the season-ending Finals and the Olympic tournament. Team competitions such as the Davis Cup and Billie Jean King Cup are excluded, because their format and the stakes of individual rubbers differ from ordinary tour matches. Exhibitions and bronze-medal matches are also excluded. As elsewhere in the project, only completed matches are rated, so retirements and walkovers are left out.</p>
            </Cols>
          </Subsection>

          <Subsection number="3.2" title="What counts as a big match">
            <Cols>
              <p>There is no single correct definition of a big match. We wanted one that matches what commentators have in mind when they talk about choking, that includes enough matches to be useful, and, most importantly, that was fixed before any results were seen. We defined a big match as any of the following:</p>
              <ul className="ml-6 list-disc">
                <li>a semi-final or final at any main-tour event;</li>
                <li>a fourth-round or quarter-final match at a Grand Slam;</li>
                <li>a quarter-final at a Masters-level event (ATP Masters 1000, WTA Premier Mandatory, and WTA Tier I before 2009);</li>
                <li>any match at the season-ending Finals.</li>
              </ul>
              <p>Every other main-tour match is a regular match. The Grand Slam and Masters rounds are included because, at those events, reaching the second week or the quarter-finals is itself a significant result, often carrying ranking points and attention comparable to a final at a smaller event. Because some readers will reasonably prefer a stricter definition, we also report results for finals alone and for semi-finals and finals together.</p>
            </Cols>
          </Subsection>

          <Subsection number="3.3" title="The sample">
            <Cols>
              <p>The final sample contains {count(r.matches)} matches, of which {count(r.big_matches)} ({pct(r.big_matches / r.matches)}) are big matches (Table 1). The two tours contribute similar numbers of matches. The main difference between them is format. On the ATP tour, {count(byFormat(5).big_matches)} big matches were played over five sets, nearly all of them at Grand Slams, whereas every WTA match is best of three. This difference matters for the method, as Section 4.1 explains.</p>
              <p>Not every player can be included in every test. A player who has played two big matches tells us almost nothing about how they handle pressure, so each test requires a minimum of {r.min_big} matches of the relevant kind. Figure 1 shows how the matches and players flow into each test.</p>
            </Cols>
            <Table number={1} caption={<>The sample, {r.window}. Player counts are for players meeting each test’s minimum of {r.min_big} big matches.</>}
              head={["", "ATP", "WTA", "Both tours"]}
              rows={[
                ["Matches analysed", count(SAMPLE.ATP.matches), count(SAMPLE.WTA.matches), count(r.matches)],
                ["Big matches", count(SAMPLE.ATP.big), count(SAMPLE.WTA.big), count(r.big_matches)],
                ["Share of matches that are big", pct(SAMPLE.ATP.big / SAMPLE.ATP.matches), pct(SAMPLE.WTA.big / SAMPLE.WTA.matches), pct(r.big_matches / r.matches)],
                ["Big matches played best of five", count(byFormat(5).big_matches), "0", count(byFormat(5).big_matches)],
                ["Regular matches", count(SAMPLE.ATP.matches - SAMPLE.ATP.big), count(SAMPLE.WTA.matches - SAMPLE.WTA.big), count(r.matches - r.big_matches)],
                [`Players with ${r.min_big}+ big matches`, count(spread("ATP", "all big matches").players), count(spread("WTA", "all big matches").players), count(spread("ATP", "all big matches").players + spread("WTA", "all big matches").players)],
                [`Players with ${r.min_big}+ in each half of their record`, count(sh("ATP").players), count(sh("WTA").players), count(sh("ATP").players + sh("WTA").players)],
                [`Players with ${r.min_big}+ in both periods`, count(ps("ATP").players), count(ps("WTA").players), count(ps("ATP").players + ps("WTA").players)],
              ]} />
            <Figure number={1} caption={<>Flow of matches and players through the analysis. Counts are for {r.window}; player counts are those meeting each test’s minimum of {r.min_big} matches.</>}>
              <StudyFlow
                source={{ title: "Jeff Sackmann's ATP and WTA tour-level match files", detail: "1968 – 25 May 2026; Elo ratings are run over the full history" }}
                excluded={{ title: "Left out of the analysis", detail: "Matches before 2000; Davis Cup, Billie Jean King Cup and other team events; exhibitions; bronze-medal matches; retirements, walkovers and other incomplete matches" }}
                analysed={{ title: `Rated main-tour matches, ${r.window}`, detail: `n = ${count(r.matches)}` }}
                split={[
                  { title: "Big matches", detail: <>n = {count(r.big_matches)}<br />Semi-finals, finals, Slam fourth rounds and quarter-finals, Masters quarter-finals, Finals</> },
                  { title: "Regular matches", detail: <>n = {count(r.matches - r.big_matches)}<br />Every other main-tour match</> },
                ]}
                tests={[
                  { title: "Do players differ beyond luck?", detail: <>{r.window}; {count(spread("ATP", "all big matches").players)} ATP and {count(spread("WTA", "all big matches").players)} WTA players for all big matches</> },
                  { title: "Do the two halves agree?", detail: <>{count(sh("ATP").players)} ATP and {count(sh("WTA").players)} WTA players with {r.min_big}+ big matches in each half</> },
                  { title: "Does the past predict the future?", detail: <>{r.periods[0]} against {r.periods[1]}; {ps("ATP").players} ATP and {ps("WTA").players} WTA players</> },
                ]}
              />
            </Figure>
          </Subsection>
        </Section>

        {/* ───────────────────────── 4 Methods ───────────────────────── */}
        <Section id="methods" number="4" title="Methods">
          <Cols>
            <p>The method has three stages. First, we work out how likely each player was to win each match, given their strength at the time. Second, we measure, for each player, how far their big-match results fell above or below those expectations. Third, we ask whether the differences between players are larger, and more repeatable, than chance alone would produce. The definitions in Sections 3.2 and 4.1 to 4.4 were written into the analysis script before it was first run. The checks described in Sections 4.5 and 4.6 were added in a second version of the paper, after the first results were known, and should be read with that in mind.</p>
          </Cols>

          <Subsection number="4.1" title="What result was expected?">
            <Cols>
              <p>Each player’s strength is measured by the project’s surface-blended Elo rating (<Cite id="elo">Elo, 1978</Cite>). An Elo rating rises when a player wins and falls when they lose, by an amount that depends on how surprising the result was: beating a much stronger opponent earns more than beating a weaker one. The surface-blended version gives extra weight to a player’s results on the surface being played, since many players are much stronger on clay, say, than on grass. Ratings are taken at the start of each tournament week and are never refitted using later results.</p>
              <p>Elo’s raw probabilities need one adjustment. In best-of-three matches they are somewhat too confident: favourites win less often than Elo predicts. In best-of-five matches they are about right, because the longer format gives the stronger player more chances to come through. This matters here because most best-of-five matches are Grand Slam matches, and many of those are big matches. Left uncorrected, players who are often favourites at the Slams would appear to excel in big matches for a reason that has nothing to do with pressure.</p>
              <p>We therefore rescale Elo’s predictions separately for each combination of tour, format and match type, as shown in equation (1). Here <i>p</i><sup>Elo</sup> is Elo’s raw probability that player <i>i</i> beats player <i>j</i>, logit converts a probability to log-odds, and σ converts it back. The slope <i>b</i><sub>g</sub> is estimated from the data for each group <i>g</i>. A slope below 1 shrinks Elo’s predictions toward 50%, and a slope above 1 stretches them. Because the slope is fitted separately for big and regular matches, any tendency for favourites as a group to do worse in big matches is absorbed here, before any individual player is assessed. Section 5.1 reports whether such a tendency exists.</p>
            </Cols>
            <Eq number={1}>{v("P", "ij")} = σ ( {v("b", "g")} · logit {v("p", "ij")}<sup>Elo</sup> )</Eq>
          </Subsection>

          <Subsection number="4.2" title="Measuring performance against expectation">
            <Cols>
              <p>For each player in each match, the <i>residual</i> is the result minus the calibrated expectation (equation 2), where the result <i>y</i> is 1 for a win and 0 for a loss. If a player is given a {pct(EXAMPLE_P)} chance and wins, their residual is {signed(1 - EXAMPLE_P, 2)}; if they lose, it is {signed(-EXAMPLE_P, 2)}. A player who performs exactly as their rating predicts will have residuals that average zero over many matches. A player who chokes in big matches would have big-match residuals that are negative on average.</p>
            </Cols>
            <Eq number={2}>{v("e", "im")} = {v("y", "im")} − {v("P", "im")}, &nbsp; {v("y", "im")} ∈ {"{0, 1}"}</Eq>
            <Cols>
              <p>A plain average of residuals is unreliable when a player has played few big matches. Suppose a player has won five finals out of five, each time as a 60% favourite. Each residual is +0.40, so their average is +0.40, an apparently spectacular record. But five finals is a tiny sample, and a 60% favourite will win five in a row about one time in thirteen by chance alone. To guard against this, each player’s <i>big-match score</i> divides the sum of their big-match residuals by the number of big matches plus a constant of {r.shrink} (equation 3). This pulls short records strongly toward zero, the value that corresponds to “no effect”. The player with five wins from five receives a score of {signed(shrunk(5, 0.4), 2)}, while a player with the same average over 100 big matches keeps most of it, scoring {signed(shrunk(100, 0.4), 2)}. With a constant of {r.shrink}, a player with exactly {r.shrink} big matches sits halfway between their own record and zero. This approach follows <Cite id="efron">Efron and Morris (1975)</Cite>.</p>
            </Cols>
            <Eq number={3}>{v("s", "i")} = Σ<sub>m ∈ big</sub> {v("e", "im")} / ( {v("n", "i")} + {r.shrink} )</Eq>
            <Cols>
              <p>A big-match score on its own cannot tell a player who rises to the occasion from one who is simply better than their rating in every match. A young player improving faster than Elo can track, for example, will beat expectations in big and regular matches alike. To separate the two, we compute the same score from regular matches and subtract it, giving a <i>clutch score</i> (equation 4). A player who beats expectations by the same margin in every kind of match has a clutch score near zero. Only a player whose big-match results differ from their regular-match results receives a large positive or negative clutch score, which makes this the closest measure we have to a pressure-specific trait.</p>
            </Cols>
            <Eq number={4}>{v("c", "i")} = {v("s", "i")}<sup>big</sup> − {v("s", "i")}<sup>regular</sup></Eq>
          </Subsection>

          <Subsection number="4.3" title="Do players differ by more than luck allows?">
            <Cols>
              <p>Imagine that every player had exactly the strength their rating says they have, with no choking or clutch trait of any kind. Their big-match records would still differ. Some would win more often than expected and some less, simply because tennis results are partly a matter of chance. The size of this chance variation can be calculated from the match probabilities themselves: a player who plays many close matches will have a noisier record than one who plays many lopsided ones, and a player with few matches will have a noisier record than one with many.</p>
              <p>Our first test compares the observed variation in players’ average residuals with the variation that luck alone would produce. We express this as a ratio. A ratio of 1 means players differ by exactly as much as luck predicts, leaving no room for a trait. A ratio above 1 means players differ by more than luck predicts, and the excess estimates how much they truly differ. The same calculation tells us how many matches a player would need before their record was half signal and half noise. If that number turns out to be larger than the number of big matches most players ever play, then a player’s big-match record is mostly noise even if a trait exists.</p>
              <p>We apply the test to finals alone, to semi-finals and finals together, to all big matches, and to regular matches as a reference point. We also apply it to the difference between each player’s big-match and regular-match residuals. We call this the <i>clutch spread</i>, and it is the most direct test of a pressure-specific trait, because a player who is under-rated in every match shows no excess on it.</p>
            </Cols>
          </Subsection>

          <Subsection number="4.4" title="Do big-match records repeat?">
            <Cols>
              <p>A genuine trait should be consistent. If some players really are better in big matches, a player who did well in one part of their big-match record should tend to do well in another. Our second test checks this directly. We divide each player’s big matches into two halves, keeping all the matches from one edition of a tournament in the same half, and correlate the two halves’ average residuals across players with at least {r.min_big} big matches in each half. A correlation near zero means the halves do not agree. Because each half contains only half the data, we use the Spearman–Brown formula (<Cite id="spearman">Spearman, 1910</Cite>; <Cite id="brown">Brown, 1910</Cite>) to estimate how reliable a player’s full record would be.</p>
              <p>The third test asks whether the past predicts the future, which is the question a forecaster faces. We compute every player’s scores separately for {r.periods[0]} and {r.periods[1]}, each period with its own calibration, and correlate them across the players who have at least {r.min_big} big matches in both periods. We then ask a stricter version of the question: if we had known each player’s {r.periods[0]} score, would our forecasts for big matches in {r.periods[1]} have been better? Equation (5) adds the difference between the two players’ earlier scores to the calibrated forecast, with a weight β estimated from the data. If β is zero, the earlier scores add nothing.</p>
            </Cols>
            <Eq number={5}>logit {v("P", "m")} = logit {v("P̂", "m")} + β ( {v("s", "A")} − {v("s", "B")} )</Eq>
            <Cols>
              <p>To judge whether a value of β is larger than chance would produce, we shuffle the earlier scores at random among players 1,000 times and refit the model each time. If the real scores improve the forecast more than nearly all of the shuffled ones, the improvement is unlikely to be a coincidence. Uncertainty intervals for the correlations come from resampling players 2,000 times (the bootstrap; <Cite id="efron1979">Efron, 1979</Cite>).</p>
            </Cols>
          </Subsection>

          <Subsection number="4.5" title="Judging the results">
            <Cols>
              <p>Some of our statistics, the spread ratio in particular, do not follow any standard textbook distribution, so we judge them by simulation. We generate {count(rb.sims.null)} artificial versions of the 26-year record in which every match result is drawn at random from its calibrated probability. In these simulated worlds there is, by construction, no choking or clutch trait. We then run every test on every simulated data set. The p-value for an observed statistic is the share of simulated statistics that are at least as large. A p-value of 0.05, for example, means that a world with no trait produces a result this extreme only one time in twenty.</p>
              <p>Because we run many tests, some will produce small p-values by chance. With {nullTests} statistics for each tour, one or two values below 0.05 are to be expected even if no trait exists. We therefore apply Holm’s correction (<Cite id="holm">Holm, 1979</Cite>), a standard method for adjusting p-values when several tests are run together.</p>
              <p>Finally, we ask how large a trait the tests could have missed. We repeat the simulations, this time giving every player a hidden clutch trait drawn at random, which raises or lowers their chances in big matches only and stays the same throughout their career. The size of the trait is described by τ, its standard deviation across players on the log-odds scale. For each of {rb.power.taus.length} values of τ we run {count(rb.sims.power)} simulations and record how often each test detects the trait. This is the test’s <i>power</i>. We also find the largest trait that is still consistent with what we observed, which gives a 95% upper bound.</p>
              <p>Log-odds are not intuitive, so we report trait sizes as an <i>edge at evens</i>: the number of percentage points by which a player one standard deviation above average would beat an otherwise equal opponent in a big match. For example, τ = 0.2 means that such a player, who would otherwise have a 50% chance, would instead have a {pts(50 + evensAt(0.2))}% chance, an edge of {pts(evensAt(0.2))} points. A trait that stays constant over a whole career is the easiest kind to detect, so the power figures are best cases. Appendix B gives the technical details.</p>
            </Cols>
          </Subsection>

          <Subsection number="4.6" title="Additional checks">
            <Cols>
              <p>Every analysis rests on choices, and a result that depends on one particular choice is fragile. We therefore repeated the main tests in several different ways. All of these checks were designed after the main results were known, so they are post-hoc. Before running them, we confirmed that the new code reproduced every number from the original analysis.</p>
              <p>The first check uses <i>game margins</i> instead of wins and losses. A single win or loss carries limited information: a player who wins 7–6 in the third set and a player who wins 6–1 6–1 both score a 1. Replacing each result with the share of games the player won gives a more detailed measure of how well they played. The expected share is again derived from the Elo ratings (<Cite id="papke">Papke and Wooldridge, 1996</Cite>).</p>
              <p>The second check uses <i>within-tournament ratings</i>. Players reach the late rounds partly because they are in form that week, and a rating taken at the start of the week does not know this. If in-form players then do well in the semi-finals, they may look clutch when they are simply in form. We therefore repeated the tests with each player’s rating updated through their earlier rounds of the same tournament.</p>
              <p>The third check concerns <i>format</i>. On the ATP tour, big matches are disproportionately best of five, because so many of them are at Grand Slams. A player who is simply better over five sets than over three could therefore look clutch. After seeing a hint of an ATP effect, we compared big and regular matches within each format separately.</p>
              <p>The final checks change one analysis choice at a time: the shrinkage constant (10, 50 or 100 in place of {r.shrink}), the minimum number of big matches (5 or 20 in place of {r.min_big}), a stricter definition of a big match (semi-finals and finals only), and a different division into periods (2008–2015 against 2016 – May 2026). We also tested formally whether Elo’s calibration differs between big and regular matches.</p>
            </Cols>
          </Subsection>
        </Section>

        {/* ───────────────────────── 5 Results ───────────────────────── */}
        <Section id="results" number="5" title="Results">
          <Subsection number="5.1" title="Do favourites as a group struggle in big matches?">
            <Cols>
              <p>Before looking at individual players, we asked whether big matches affect favourites in general. If the pressure of a final caused favourites to underperform across the board, Elo’s predictions would need a stronger correction in big matches than in regular ones, and the calibration slope for big matches would be lower.</p>
              <p>On the ATP tour, there is no sign of this. The slopes for big and regular matches are almost identical in both formats (Figure 2 and Table 2). On the WTA tour, the slope for big matches is noticeably lower ({two(slope("WTA", "big", 3)!)} against {two(slope("WTA", "regular", 3)!)}), and the difference is statistically significant (p = {pv(slopeTest("WTA", 3)!.p)}). In plain terms, Elo overstates the favourite’s chances more in WTA big matches than in WTA regular matches, so WTA big matches are somewhat more open than the ratings suggest.</p>
              <p>This is a property of the matches, not of particular players. It applies to every favourite in a WTA big match, and it could have several explanations: the stronger player may feel more pressure, the weaker player may raise their game, or the players who reach late rounds may be closer in strength than their ratings show. Whatever its cause, our calibration removes it before any player is scored, so it does not affect the tests that follow. It is, however, worth knowing for anyone building a forecast on Elo ratings, and our forecasts calibrate big and regular matches separately for this reason.</p>
            </Cols>
            <Figure number={2} caption={<>Elo calibration slopes in big and regular matches, {r.window}. A slope of 1 means Elo’s probabilities were already right; a slope below 1 means Elo was too confident in the favourite.</>}>
              <Dumbbell rows={CALIBRATION_ROWS} domain={[0.6, 1.2]} ticks={[0.6, 0.8, 1.2]} format={two} aLabel="Big matches" bLabel="Regular matches"
                        reference={1} referenceLabel="Elo already right" axisLabel="Calibration slope" ariaLabel="Figure 2: calibration slopes, big against regular matches" />
            </Figure>
            <Table number={2} caption={<>Elo calibration slopes <i>b</i><sub>g</sub> with standard errors, {r.window}, and a test of whether the big-match slope differs from the regular-match slope.</>}
              head={["Tour and format", "Big", "Regular", "Difference", "z", "p"]}
              rows={rb.slope_tests.map((t) => [`${t.tour}, best of ${t.best_of}`, `${three(t.big)} (${three(t.big_se)})`, `${three(t.regular)} (${three(t.regular_se)})`,
                                               signed(t.big - t.regular), signed(t.z, 2), pv(t.p)])} />
          </Subsection>

          <Subsection number="5.2" title="How much do players differ?">
            <Cols>
              <p>The central result of the first test is that players’ big-match records differ by about as much as luck alone would make them differ (Figure 3 and Table 3). For ATP finals, the matches where the choking story is told most often, the ratio of observed to chance variation is {two(spread("ATP", "finals only").ratio)}. In other words, ATP players’ records in finals are spread out almost exactly as they would be if every final were decided by the ratings and a coin toss. Across all the big-match sets on both tours, the ratio ranges from {two(minBigRatio)} to {two(maxBigRatio)}.</p>
              <p>Nor do the ratios rise steadily as the matches become bigger. On the ATP tour the ratio for finals is the smallest of the three big-match sets. On the WTA tour it is the largest ({two(spread("WTA", "finals only").ratio)}), but only {spread("WTA", "finals only").players} players have enough finals to be included, and a value this high occurs by chance in about one simulated world in {Math.round(1 / nullRow("WTA", "ratio finals only").p)} (p = {pv(nullRow("WTA", "ratio finals only").p)}). The largest ratio for all big matches is {two(spread("ATP", "all big matches").ratio)} on the ATP tour. Its p-value of {pv(nullRow("ATP", "ratio all big matches").p)} is close to the conventional threshold, but after Holm’s correction it rises to {pv(holm("ATP", "all big matches"))}.</p>
              <p>The clutch spread, which removes general form by comparing each player’s big matches with their own regular matches, tells a slightly different story for the two tours. On the WTA tour it is {two(nullRow("WTA", "clutch ratio").observed)}, almost exactly what luck predicts (p = {pv(nullRow("WTA", "clutch ratio").p)}). On the ATP tour it is {two(nullRow("ATP", "clutch ratio").observed)}, which is nominally significant (p = {pv(nullRow("ATP", "clutch ratio").p)}). This is the strongest hint of a clutch trait anywhere in the analysis, and we examine it closely in Section 5.5. On its own it is weak evidence: it is one of {nullTests} statistics computed for each tour, and a p-value of this size would not survive a correction for that many tests.</p>
              <p>Even where an excess appears, it is small in practical terms. The implied number of matches before a player’s record becomes half signal is {count(Math.round(spread("ATP", "all big matches").implied_k!))} for all ATP big matches and {count(Math.round(spread("WTA", "finals only").implied_k!))} for WTA finals. Few players ever play that many, so even for the most experienced players a big-match record would be at least half noise.</p>
              <p>The only clear excess in Table 3 appears in regular WTA matches ({two(spread("WTA", "regular matches").ratio)}, p {pv(nullRow("WTA", "ratio regular matches").p)}). This reflects ordinary changes in form that Elo is slow to catch, such as a player on the way up or recovering from injury. It has nothing to do with pressure, and it is exactly the kind of effect the clutch score is designed to remove.</p>
            </Cols>
            <Figure number={3} caption={<>Spread of players’ results against expectation, divided by the spread that luck alone would produce, {r.window}; players with at least {r.min_big} matches of each kind. The dashed line at 1 marks pure luck.</>}>
              <GroupedBars groups={SPREAD_GROUPS} domain={[0, 1.4]} ticks={[0, 0.5, 1, 1.4]} format={two} reference={1} referenceLabel="Pure luck"
                           axisLabel="Observed spread ÷ spread from luck" ariaLabel="Figure 3: spread of players' results relative to luck, by tour" />
            </Figure>
            <Table number={3}
              caption={<>Spread of players’ average residuals, in percentage points of win probability per match. The trait standard deviation is the part of the observed spread not explained by luck. The implied <i>k</i> is the number of matches before half of a player’s record is signal (“none” where there is no excess). p is from {count(rb.sims.null)} simulations with no trait.</>}
              head={["Tour and matches", "Players", "Observed sd", "Luck sd", "Ratio", "Trait sd", "Implied k", "p"]}
              rows={TOURS.flatMap((tour) => SETS.map(([set, label]) => {
                const s = spread(tour, set);
                return [`${tour}, ${label.toLowerCase()}`, count(s.players), pp(s.observed_sd), pp(s.noise_sd), two(s.ratio), pp(s.trait_sd),
                        s.implied_k === null ? "none" : count(Math.round(s.implied_k)), pv(nullRow(tour, `ratio ${set}`).p)];
              }))} />
          </Subsection>

          <Subsection number="5.3" title="Do big-match records repeat?">
            <Cols>
              <p>If a choking or clutch trait existed, a player’s big-match record should agree with itself. It barely does. The correlation between the two halves of players’ big-match records is {corr(sh("ATP"))} on the ATP tour and {corr(sh("WTA"))} on the WTA tour (Table 4 and the top rows of Figure 4). Both intervals include zero, and neither correlation is significant in the simulation test (p = {pv(nullRow("ATP", "split-half r").p)} and {pv(nullRow("WTA", "split-half r").p)}). Even using all of a player’s big matches, the estimated reliability of their record is at most {two(maxReliability)}. For comparison, a common rule of thumb asks for a reliability of at least 0.7 before a measure is used to tell individuals apart.</p>
            </Cols>
            <Table number={4} caption={<>Agreement between the two halves of each player’s big matches, {r.window}. The full-record reliability applies the Spearman–Brown formula to the split-half correlation.</>}
              head={["Tour", "Players", "Correlation (95% interval)", "Full-record reliability"]}
              rows={TOURS.map((tour) => [tour, count(sh(tour).players), interval(sh(tour)), signed(sh(tour).spearman_brown)])} />
            <Cols>
              <p>The comparison between periods points the same way. Players’ big-match scores from {r.periods[0]} carry over into {r.periods[1]} only weakly, with correlations of {signed(ps("ATP").correlations["big-match"].r, 2)} (ATP) and {signed(ps("WTA").correlations["big-match"].r, 2)} (WTA), and no more strongly than their regular-match scores do (Figure 4 and Table 5). On the WTA tour, the regular-match score in fact carries over much more strongly ({signed(ps("WTA").correlations["regular-match"].r, 2)}) than the big-match score.</p>
              <p>This pattern is informative. What persists from one period to the next is general form, the tendency of some players to be consistently better or worse than their rating, and it persists in regular matches at least as much as in big ones. Once general form is removed, the clutch score carries over hardly at all ({signed(ps("ATP").correlations.clutch.r, 2)} on the ATP tour and {signed(ps("WTA").correlations.clutch.r, 2)} on the WTA tour).</p>
              <p>The forecast test asks the most practical version of the question. Knowing players’ {r.periods[0]} scores would not have significantly improved forecasts of their big matches in {r.periods[1]} (Table 6). None of the four permutation p-values is below 0.1, and the improvements in forecast accuracy, measured by log loss, are tiny. One result needs a brief explanation. In the simulation test of Appendix Table A1, the WTA big-match score appears to improve forecasts (p = {pv(nullRow("WTA", "forecast z big").p)}). That simulation assumes players do not differ in any way beyond their ratings, so it treats any persistence of general form as surprising. The permutation test, which allows for general form, does not find the improvement significant (p = {pv(ps("WTA").forecasts["big-match"].permutation_p)}), and the WTA clutch score, which removes form, adds nothing at all (p = {pv(ps("WTA").forecasts.clutch.permutation_p)}).</p>
            </Cols>
            <Figure number={4} caption={<>Agreement of player scores, with 95% intervals: between the two halves of each player’s big matches ({r.window}), and between {r.periods[0]} and {r.periods[1]} for the {ps("ATP").players} ATP and {ps("WTA").players} WTA players with at least {r.min_big} big matches in both periods. The dashed line at 0 marks no agreement.</>}>
              <Forest groups={FOREST_GROUPS} domain={[-0.4, 0.7]} ticks={[-0.4, 0, 0.4, 0.7]} format={(x) => signed(x, 2)} reference={0} referenceLabel="No agreement"
                      axisLabel="Correlation" ariaLabel="Figure 4: agreement of player scores with 95% intervals" />
            </Figure>
            <Table number={5} caption={<>Correlation of player scores between {r.periods[0]} and {r.periods[1]}, with 95% intervals.</>}
              head={["Tour", "Players", "Big-match score", "Clutch score", "Regular-match score"]}
              rows={TOURS.map((tour) => [tour, ps(tour).players, interval(ps(tour).correlations["big-match"]),
                                         interval(ps(tour).correlations.clutch), interval(ps(tour).correlations["regular-match"])])} />
            <Table number={6}
              caption={<>Forecast test (equation 5): do {r.periods[0]} scores improve the calibrated forecast of {r.periods[1]} big matches? β with its standard error; a negative change in log loss means the forecast improved; p from 1,000 permutations.</>}
              head={["Tour and score", "Big matches", "With an earlier score", "β (se)", "Change in log loss", "p"]}
              rows={TOURS.flatMap((tour) => (["big-match", "clutch"] as const).map((key) => {
                const f = ps(tour).forecasts[key];
                return [`${tour}, ${key} score`, count(f.matches), count(f.with_history), `${signed(f.beta, 2)} (${two(f.se)})`, signed(f.log_loss_change, 5), three(f.permutation_p)];
              }))} />
          </Subsection>

          <Subsection number="5.4" title="How large a trait could the data have missed?">
            <Cols>
              <p>The tests above find little, but that matters only if they were capable of finding something. Figure 5 shows that they were, at least for a trait of moderate size. A clutch trait of τ = 0.4, which gives a player one standard deviation above average an edge of {pts(evensAt(0.4))} percentage points at evens, would be detected by both the clutch-spread and split-half tests in at least {pct(Math.min(...TOURS.flatMap((t) => [powerAt(t, "clutch ratio", 0.4), powerAt(t, "split-half r", 0.4)])))} of simulations on each tour. A trait of that size would not have gone unnoticed.</p>
              <p>Smaller traits are a different matter. At τ = 0.15, an edge of {pts(evensAt(0.15))} points, no test has better than a {pct(strongestAt(0.15))} chance of detecting the trait. The period comparison and forecast tests are weaker throughout, because only about thirty players on each tour have enough big matches in both periods.</p>
              <p>Turning this around gives an upper bound on the size of any trait. We use the clutch spread for the headline figure, because it is the only test that removes general form. At 95% confidence, a player one standard deviation above average gains at most {boundText("ATP", "clutch ratio")} at evens in big matches on the ATP tour, and at most {boundText("WTA", "clutch ratio")} on the WTA tour. The split-half test gives similar bounds ({boundText("ATP", "split-half r")} and {boundText("WTA", "split-half r")}), and the bounds for every test are listed in Appendix Table A2.</p>
              <p>These bounds rule out the large, lasting effect the choking story usually implies, a player who regularly turns winning positions into losses on the big stage. They do not rule out a trait of a few percentage points. Such a trait would, however, be very hard to see in any individual’s record, a point we return to in Section 6.3.</p>
            </Cols>
            <Figure number={5} caption={<>Power of three tests to detect a clutch trait of a given size, {count(rb.sims.power)} simulations per point. The horizontal axis is the edge, in percentage points at evens, of a player one standard deviation above average in big matches. The dashed line marks 80% power, a common target in study design.</>}>
              <PowerCurves panels={POWER_PANELS} xMax={10} xTicks={[0, 2.5, 5, 7.5, 10]} ariaLabel="Figure 5: power of the clutch-spread, split-half and forecast tests against the size of a clutch trait, by tour" />
            </Figure>
          </Subsection>

          <Subsection number="5.5" title="A closer look at the ATP result">
            <Cols>
              <p>The ATP clutch spread of {two(nullRow("ATP", "clutch ratio").observed)} is the one result in the main analysis that hints at a trait. Because it was found after looking at the data, it deserves scepticism, but it also deserves a careful look. We examined it in three ways.</p>
              <p><i>Game margins.</i> If the ATP excess reflected something real, it should also appear when performance is measured by games won rather than matches won. It does. The clutch spread based on game margins is {two(atpGame.clutch.ratio)} on the ATP tour (p = {pv(atpGame.clutch.p)}) and {two(wtaGame.clutch.ratio)} on the WTA tour (p = {pv(wtaGame.clutch.p)}), repeating the pattern found with wins (Appendix Table A3). Game margins also reveal something the win-based analysis cannot. In every kind of match, players differ much more in their margins than Elo predicts, with spread ratios of {two(gameSet("ATP", "regular matches").ratio)} (ATP) and {two(gameSet("WTA", "regular matches").ratio)} (WTA) even for regular matches. Some players consistently win by wide margins and others by narrow ones, beyond what their win probability implies. This is a matter of playing style rather than pressure, and it is why the clutch comparison, which cancels it out, is the appropriate test.</p>
              <p><i>Format.</i> Because so many ATP big matches are played over five sets, a player who is better at five-set tennis could look clutch. When big and regular matches are compared within the same format, the excess remains in best-of-three matches alone (Table 7): {two(byFormat(3).wins.ratio)} with wins (p = {pv(byFormat(3).wins.p)}) and {two(byFormat(3).games.ratio)} with games (p = {pv(byFormat(3).games.p)}). Five-set fitness does not explain it. Within best-of-five matches, wins show no excess ({two(byFormat(5).wins.ratio)}, p = {pv(byFormat(5).wins.p)}), while games show a similar but non-significant one ({two(byFormat(5).games.ratio)}, p = {pv(byFormat(5).games.p)}).</p>
              <p><i>Form within the tournament.</i> Updating each player’s rating through their earlier rounds of the same tournament changes very little (Appendix Table A4). The ATP clutch spread moves from {two(nullRow("ATP", "clutch ratio").observed)} to {two(within("ATP").clutch)}, the split-half correlations stay near {signed(within("ATP").split_half.r, 2)} and {signed(within("WTA").split_half.r, 2)}, and no forecast test becomes significant. So the excess is not explained by players arriving at the late rounds in unusually good form.</p>
              <p>Taken together, these checks show that the ATP excess is not a simple artefact of the scoring measure, the match format or form during the week. Set against that, it is one result among many, it does not survive correction for multiple tests, it does not persist between periods, and it does not improve forecasts. The WTA tour, with a similar number of players and matches, shows nothing comparable. We treat it as an open question rather than a finding.</p>
            </Cols>
            <Table number={7}
              caption={<>The ATP clutch spread within a single format, {r.window}: big matches compared with regular matches of the same length. Wins judged against {count(rb.sims.null)} simulations, games against {count(rb.sims.game_permutations)} permutations. This check was added after the ATP excess had been seen.</>}
              head={["Format", "Big matches", "Regular matches", "Players", "Clutch ratio, wins (p)", "Clutch ratio, games (p)"]}
              rows={rb.format.map((f) => [`Best of ${f.best_of}`, count(f.big_matches), count(f.regular_matches), f.wins.players,
                `${two(f.wins.ratio)} (${pv(f.wins.p)})`, `${two(f.games.ratio)} (${pv(f.games.p)})`])} />
          </Subsection>

          <Subsection number="5.6" title="Sensitivity to analysis choices">
            <Cols>
              <p>The conclusions do not depend on any one analysis choice. Across the {rb.sensitivity.length / 2} variants of the period comparison on each tour (Appendix Table A5), no forecast p-value falls below {pv(minSensitivityP)}, and the clutch correlations between periods range from {signed(Math.min(...rb.sensitivity.map((s) => s.clutch_r)), 2)} to {signed(Math.max(...rb.sensitivity.map((s) => s.clutch_r)), 2)}, with no consistent sign. One interval excludes zero: the ATP clutch score when the periods are 2008–2015 and 2016 – May 2026 ({signed(altPeriods.clutch_r, 2)}). The forecast test on that same split is not significant (p = {pv(altPeriods.clutch_p)}), however, and one interval excluding zero among {rb.sensitivity.length} is about what chance alone would produce.</p>
            </Cols>
          </Subsection>
        </Section>

        {/* ───────────────────────── 6 Discussion ───────────────────────── */}
        <Section id="discussion" number="6" title="Discussion">
          <Subsection number="6.1" title="Summary of findings">
            <Cols>
              <p>Across more than a quarter of a century of professional tennis, we find that players’ records in big matches differ from one another by about as much as luck would make them differ. A player’s record in one half of their big matches says little about the other half, and their record in one period says little about the next once ordinary form is accounted for. The data are sensitive enough to have detected a large trait, and they rule one out. A small trait, of a few percentage points, remains possible, and the ATP results give a weak and inconclusive hint of one.</p>
            </Cols>
          </Subsection>

          <Subsection number="6.2" title="Why the choking story is so persuasive">
            <Cols>
              <p>If there is no large choking trait, why is the story told so often and believed so widely? Part of the answer lies in the arithmetic of runs. Consider a player who wins {pct(r.streak.p_win)} of their finals, which is a strong record. Treat each final as an independent event, so that by assumption there is no choking at all. Over a career of {r.streak.finals} finals, the probability that this player loses at least two finals in a row at some point is {pct(r.streak.two)}, and the probability of at least three in a row is {pct(r.streak.three)} (Figure 6). A run of three lost finals, which would surely be described as a choking problem, is the more likely outcome of an excellent career.</p>
            </Cols>
            <Figure number={6} caption={<>Probability of at least one losing run in finals, for a player who wins {pct(r.streak.p_win)} of their finals, by the number of finals played. Exact calculation, each final independent; the marked values are at {r.streak.finals} finals.</>}>
              <RunCurve p={r.streak.p_win} mark={r.streak.finals} ariaLabel={`Figure 6: probability of a losing run of two or three finals against the number of finals played, for a ${pct(r.streak.p_win)} finals winner`} />
            </Figure>
            <Cols>
              <p>People are quick to see meaning in runs of this kind. The classic study of the “hot hand” in basketball argued that fans and players perceive streaks in what are largely random sequences (<Cite id="gilovich">Gilovich et al., 1985</Cite>). Later work showed that the original analysis was itself biased, and that some genuine streakiness may have been missed (<Cite id="miller">Miller and Sanjurjo, 2018</Cite>). For that reason we do not rely on the hot-hand literature here and use only the exact probabilities above, which are not affected by that bias.</p>
              <p>Selection completes the picture. With hundreds of players on each tour, someone is always in the middle of a losing run in finals, and those are the players whose runs are written about. The many players whose finals records look unremarkable attract no explanation, because nothing about them seems to need one.</p>
            </Cols>
          </Subsection>

          <Subsection number="6.3" title="What this means for forecasting">
            <Cols>
              <p>For the Matchup DNA forecasts, the practical conclusion is that no player-specific adjustment should be made for big matches. Even if a trait existed at the upper bound we found, it could not be measured reliably for individual players. At a typical big-match win probability of about {pct(EXAMPLE_P)}, a player with 100 big matches, a long career by any standard, has a record whose luck alone has a standard deviation of about {pts(luckSd100)} percentage points per match. That is comparable to the largest trait the data allow. A model that adjusted forecasts based on players’ big-match records would therefore be responding mostly to luck, and its forecasts would become less accurate rather than more.</p>
              <p>The tour-wide WTA calibration difference reported in Section 5.1 is a separate matter, and it is useful. Because it applies to all favourites in big matches, it can be estimated from many thousands of matches rather than from one player’s record. The forecasts already calibrate big and regular matches separately, which accounts for it.</p>
            </Cols>
          </Subsection>

          <Subsection number="6.4" title="Interpreting the ATP signal">
            <Cols>
              <p>The ATP clutch excess is the result most worth following up. It appears with two different measures, wins and game margins, and it survives the format and within-tournament checks. On the other hand, it was found among many tests, it does not survive a standard correction for multiple testing, the persistence tests do not detect it, and the WTA tour shows no sign of it.</p>
              <p>Several explanations are possible. The excess could be chance. It could reflect a real but modest difference in how some ATP players respond to big occasions. Or it could reflect something that varies over time rather than a fixed trait: a player might handle pressure better at some stages of their career than others, which would increase the spread of big-match results without producing a consistent pattern from one period to the next. Our data cannot distinguish between these explanations. Whatever its source, the excess lies within the bounds of Section 5.4, so it is too small to identify for any individual player.</p>
            </Cols>
          </Subsection>

          <Subsection number="6.5" title="Relation to earlier research">
            <Cols>
              <p>Our results do not contradict the point-level findings reviewed in Section 2. A player may raise or lower their level on important points, as <Cite id="gonzalez">González-Díaz et al. (2012)</Cite> report, and still win big matches at exactly the rate their overall strength predicts. Their ability to handle important points is part of what makes them strong, and so it is already reflected in their rating. What our data rule out is a large and lasting gap between a player’s results in big matches and their strength in general.</p>
              <p>The results also echo the history of the search for clutch hitters in baseball (<Cite id="cramer">Cramer, 1977</Cite>). In both sports, the belief in a clutch skill is widespread, the individual examples are memorable, and the systematic evidence for a large and lasting effect is weak. In both, the main difficulty is that the matches or at-bats that matter most are too few for any one player’s record to escape the influence of chance.</p>
            </Cols>
          </Subsection>
        </Section>

        {/* ───────────────────────── 7 Limitations ───────────────────────── */}
        <Section id="limitations" number="7" title="Limitations">
          <Cols>
            <p>This study has several limitations. The most important is that it is post-hoc. The definitions used in the main analysis were fixed before it was run, but the question itself arose after recent results had been seen, and every additional check in Sections 4.5 and 4.6 was designed after the main results were known. The analysis was not used to choose or change any forecasting model. With {nullTests} statistics computed for each tour, one or two nominal p-values below 0.05 are expected by chance, and the ATP clutch result should be read in that light.</p>
            <p>Second, the period comparison rests on small numbers of players. Only {ps("ATP").players} ATP and {ps("WTA").players} WTA players had enough big matches in both periods, and Section 5.4 shows that this limits the power of those tests considerably. The spread and split-half tests, which use many more players, carry most of the weight of our conclusions.</p>
            <p>Third, the simulations rest on assumptions. The no-trait simulations assume that, apart from a trait, match results are independent given their calibrated probabilities. Ordinary changes in form violate this assumption, which is why some big-match statistics can look significant when the clutch statistics, which remove form, do not. The power analysis assumes a trait that is normally distributed across players, constant over a career and confined to big matches. A trait that changes over a career would be harder to detect than our power figures suggest.</p>
            <p>Fourth, the expectations themselves are imperfect. Elo ratings miss some information, such as injuries and changes in coaching, and the game-margin expectation is a simple model. Within-tournament ratings could be computed for {pct(within("ATP").eligible)} of big matches; the rest, including all round-robin matches at the season-ending Finals, kept their start-of-week ratings.</p>
            <p>Finally, pressure itself is never observed. We measure results against expectation, not how players feel. A player could experience intense pressure and still perform as expected, and our analysis cannot show that pressure affects no one. It shows only that, if pressure does affect players differently, the effect on their results is not large enough or consistent enough to stand out from chance.</p>
          </Cols>
        </Section>

        {/* ───────────────────────── 8 Future research ───────────────────────── */}
        <Section id="future" number="8" title="Future research">
          <Cols>
            <p>The most direct way to settle the question of a small ATP effect is a pre-registered test on matches played after this analysis. Fixing the hypothesis, the definition of a big match and the test statistic before the data exist would remove the concern that the result was found by searching. The project’s live forecast record, which begins after the data used here end, offers a natural source of such matches, although several seasons will be needed to gather enough big matches.</p>
            <p>Point-by-point data would also help. A match result compresses hundreds of points into a single outcome, and much of the information about how a player handles pressure is lost in that compression. Studying how players perform on break points and in tie-breaks in big matches compared with regular ones, while accounting for their overall strength, could reveal effects too small to see in match results.</p>
            <p>Finally, our definition of a big match is based on the round and the tournament. Other sources of pressure, such as ranking milestones, home crowds, or a first final, may matter more for some players. Testing these alternative definitions would require care, since each new definition adds another test and increases the risk of finding a pattern by chance.</p>
          </Cols>
        </Section>

        {/* ───────────────────────── 9 Conclusion ───────────────────────── */}
        <Section id="conclusion" number="9" title="Conclusion">
          <Cols>
            <p>The belief that some tennis players choke in big matches, and that others rise to them, is one of the most familiar stories in the sport. Across 26 years of tour-level results, we find that players’ big-match records differ from one another by about as much as luck would make them differ, and that a player’s earlier record does not predict their later one beyond ordinary form. The data rule out a large choking or clutch trait. A trait of a few percentage points cannot be excluded, and the ATP results give a faint hint of one, but such a trait would be too small to identify for any individual player. The Matchup DNA forecasts therefore treat a final like any other match between the same two players, apart from a calibration that applies to all big matches alike.</p>
          </Cols>
        </Section>

        <Statements items={[
          { title: "Data availability", text: <>Match data are from Jeff Sackmann’s public tennis_atp and tennis_wta repositories (CC BY-NC-SA 4.0), up to 25 May 2026. Every number in this paper is read directly from the analysis output and checked automatically against the full written report before publication.</> },
          { title: "Code availability", text: <>The main analysis is reproduced by <code className="font-mono text-[13px]">python -m matchup_dna.posthoc_big_match</code> and the additional checks by <code className="font-mono text-[13px]">python -m matchup_dna.posthoc_big_match_robustness</code>.</> },
          { title: "Analysis status", text: <>This analysis is post-hoc and descriptive. It was not pre-registered and has not been peer reviewed, and it did not change any frozen model or the live forecast record. How the live forecasts are made and scored is described on the <Link href="/methodology" className="ref">Methodology</Link> page.</> },
          { title: "Version history", text: <>Version 1.0 (14 November 2026): the main analysis, with three tests. Version 2.0 (14 November 2026): adds the review of related research, simulation-based tests, power analysis and upper bounds, the clutch spread, game margins, within-tournament ratings, sensitivity analyses, a test of the calibration slopes and a format check of the ATP result, and revises the claims to match. Version 2.1 ({paperDate(meta.date)}): rewritten for readability, with fuller explanations of the method and results, and supplementary tables and technical details moved to appendices. No numbers changed.</> },
        ]} />

        <References items={[
          { id: "apesteguia", text: <>Apesteguia, J., and Palacios-Huerta, I. (2010). Psychological pressure in competitive environments: evidence from a randomized natural experiment. <i>Am. Econ. Rev.</i> 100, 2548–2564.</> },
          { id: "baumeister", text: <>Baumeister, R. F. (1984). Choking under pressure: self-consciousness and paradoxical effects of incentives on skillful performance. <i>J. Pers. Soc. Psychol.</i> 46, 610–620.</> },
          { id: "brown", text: <>Brown, W. (1910). Some experimental results in the correlation of mental abilities. <i>Br. J. Psychol.</i> 3, 296–322.</> },
          { id: "brown2008", text: <>Brown, L. D. (2008). In-season prediction of batting averages: a field test of empirical Bayes and Bayes methodologies. <i>Ann. Appl. Stat.</i> 2, 113–152.</> },
          { id: "cohenzada", text: <>Cohen-Zada, D., Krumer, A., Rosenboim, M., and Shapir, O. M. (2017). Choking under pressure and gender: evidence from professional tennis. <i>J. Econ. Psychol.</i> 61, 176–190.</> },
          { id: "cramer", text: <>Cramer, R. D. (1977). Do clutch hitters exist? <i>Baseball Res. J.</i> 6, 74–79.</> },
          { id: "efron1979", text: <>Efron, B. (1979). Bootstrap methods: another look at the jackknife. <i>Ann. Stat.</i> 7, 1–26.</> },
          { id: "efron", text: <>Efron, B., and Morris, C. (1975). Data analysis using Stein’s estimator and its generalizations. <i>J. Am. Stat. Assoc.</i> 70, 311–319.</> },
          { id: "elo", text: <>Elo, A. E. (1978). <i>The Rating of Chessplayers, Past and Present</i>. New York, NY: Arco.</> },
          { id: "gilovich", text: <>Gilovich, T., Vallone, R., and Tversky, A. (1985). The hot hand in basketball: on the misperception of random sequences. <i>Cogn. Psychol.</i> 17, 295–314.</> },
          { id: "gonzalez", text: <>González-Díaz, J., Gossner, O., and Rogers, B. W. (2012). Performing best when it matters most: evidence from professional tennis. <i>J. Econ. Behav. Organ.</i> 84, 767–781.</> },
          { id: "holm", text: <>Holm, S. (1979). A simple sequentially rejective multiple test procedure. <i>Scand. J. Stat.</i> 6, 65–70.</> },
          { id: "klaassen", text: <>Klaassen, F. J. G. M., and Magnus, J. R. (2001). Are points in tennis independent and identically distributed? Evidence from a dynamic binary panel data model. <i>J. Am. Stat. Assoc.</i> 96, 500–509.</> },
          { id: "kocher", text: <>Kocher, M. G., Lenz, M. V., and Sutter, M. (2012). Psychological pressure in competitive environments: new evidence from randomized natural experiments. <i>Manage. Sci.</i> 58, 1585–1591.</> },
          { id: "kovalchik", text: <>Kovalchik, S. A. (2016). Searching for the GOAT of tennis win prediction. <i>J. Quant. Anal. Sports</i> 12, 127–138.</> },
          { id: "lakens", text: <>Lakens, D. (2017). Equivalence tests: a practical primer for t tests, correlations, and meta-analyses. <i>Soc. Psychol. Personal. Sci.</i> 8, 355–362.</> },
          { id: "miller", text: <>Miller, J. B., and Sanjurjo, A. (2018). Surprised by the hot hand fallacy? A truth in the law of small numbers. <i>Econometrica</i> 86, 2019–2047.</> },
          { id: "papke", text: <>Papke, L. E., and Wooldridge, J. M. (1996). Econometric methods for fractional response variables with an application to 401(k) plan participation rates. <i>J. Appl. Econom.</i> 11, 619–632.</> },
          { id: "sackmann", text: <>Sackmann, J. (2026). tennis_atp and tennis_wta: ATP and WTA tennis rankings, results and stats. GitHub repositories, data to 25 May 2026.</> },
          { id: "spearman", text: <>Spearman, C. (1910). Correlation calculated from faulty data. <i>Br. J. Psychol.</i> 3, 271–295.</> },
        ]} />

        {/* ───────────────────────── Appendix A ───────────────────────── */}
        <Section id="appendix-a" number="Appendix A" title="Supplementary tables">
          <Table number="A1"
            caption={<>Simulation tests: each observed statistic against {count(rb.sims.null)} simulated data sets with no trait. The 95th percentile is the value a statistic must exceed to be significant at the 5% level.</>}
            head={["Statistic", "ATP observed", "95th pct", "p", "WTA observed", "95th pct", "p"]}
            rows={NULL_LABELS.map(([test, label]) => {
              const a = nullRow("ATP", test), w = nullRow("WTA", test);
              return [label, signed(a.observed, 2), signed(a.critical, 2), pv(a.p), signed(w.observed, 2), signed(w.critical, 2), pv(w.p)];
            })}
            note={<>Holm-corrected p-values across the eight spread sets: {TOURS.map((tour) => `${tour} ${SETS.map(([set]) => pv(holm(tour, set))).join(", ")}`).join("; ")} (finals, semi-finals and finals, all big, regular).</>} />
          <Table number="A2"
            caption={<>Power of each test at each trait size, and the 95% upper bound on the trait. Trait sizes are τ = {rb.power.taus.map((t) => t.toFixed(2)).join(", ")}, an edge at evens of {rb.power.evens.map(pts).join(", ")} percentage points.</>}
            head={["Tour and test", ...rb.power.evens.map((e) => `${pts(e)}`), "95% bound"]}
            rows={TOURS.flatMap((tour) => NULL_LABELS.filter(([t]) => t !== "ratio regular matches").map(([test, label]) => {
              const p = powerRow(tour, test);
              return [`${tour}, ${label.replace(", big-match score", ", big").replace(", clutch score", ", clutch").toLowerCase()}`, ...p.power.map(pct),
                      p.bound_points === null ? "–" : `${pts(p.bound_points)} pts`];
            }))}
            note="Power is the share of simulations beyond the no-trait 95th percentile. The regular-match spread is left out because the simulated trait does not affect regular matches." />
          <Table number="A3"
            caption={<>Game margins: share of games won against expectation, {r.window}. Ratios as in Table 3; p from {count(rb.sims.game_permutations)} within-group permutations. Carry-over and forecast tests as in Tables 5 and 6, with game-based scores predicting later big-match wins.</>}
            head={["Statistic", "ATP", "WTA"]}
            rows={[
              ["Matches", count(atpGame.matches), count(wtaGame.matches)],
              ["Residual sd per match (points)", pts(100 * atpGame.per_match_sd), pts(100 * wtaGame.per_match_sd)],
              ...SETS.map(([set, label]) => {
                const a = gameSet("ATP", set), w = gameSet("WTA", set);
                return [`Spread ratio, ${label.toLowerCase()}`, `${two(a.ratio)} (p ${pv(a.p)})`, `${two(w.ratio)} (p ${pv(w.p)})`];
              }),
              ["Clutch spread ratio", `${two(atpGame.clutch.ratio)} (p ${pv(atpGame.clutch.p)})`, `${two(wtaGame.clutch.ratio)} (p ${pv(wtaGame.clutch.p)})`],
              ["Split-half r", interval(atpGame.split_half), interval(wtaGame.split_half)],
              ["Carry-over r, big-match score", interval(atpGame.correlations.big), interval(wtaGame.correlations.big)],
              ["Carry-over r, clutch score", interval(atpGame.correlations.clutch), interval(wtaGame.correlations.clutch)],
              ["Carry-over r, regular-match score", interval(atpGame.correlations.regular), interval(wtaGame.correlations.regular)],
              ["Forecast β, big-match score (p)", `${signed(atpGame.forecasts.big.beta, 2)} (${pv(atpGame.forecasts.big.p)})`, `${signed(wtaGame.forecasts.big.beta, 2)} (${pv(wtaGame.forecasts.big.p)})`],
              ["Forecast β, clutch score (p)", `${signed(atpGame.forecasts.clutch.beta, 2)} (${pv(atpGame.forecasts.clutch.p)})`, `${signed(wtaGame.forecasts.clutch.beta, 2)} (${pv(wtaGame.forecasts.clutch.p)})`],
            ]}
            note={<>One game-based carry-over interval excludes zero, the WTA clutch score ({interval(wtaGame.correlations.clutch)}), but the forecast test using the same score finds nothing (p = {pv(wtaGame.forecasts.clutch.p)}), and its win-based counterpart is {signed(ps("WTA").correlations.clutch.r)}.</>} />
          <Table number="A4"
            caption={<>Within-tournament ratings: the main statistics with each player’s rating updated through their earlier rounds of the same event.</>}
            head={["Statistic", "ATP", "WTA"]}
            rows={[
              ["Big matches with a complete earlier-round record", pct(within("ATP").eligible), pct(within("WTA").eligible)],
              ...SETS.map(([set, label]) => [`Spread ratio, ${label.toLowerCase()}`, two(within("ATP").spread[set]!), two(within("WTA").spread[set]!)]),
              ["Clutch spread ratio", two(within("ATP").clutch), two(within("WTA").clutch)],
              ["Split-half r", interval(within("ATP").split_half), interval(within("WTA").split_half)],
              ["Carry-over r, big-match / clutch", `${signed(within("ATP").correlations.big)} / ${signed(within("ATP").correlations.clutch)}`, `${signed(within("WTA").correlations.big)} / ${signed(within("WTA").correlations.clutch)}`],
              ["Forecast β, big-match score (p)", `${signed(within("ATP").forecasts.big.beta, 2)} (${pv(within("ATP").forecasts.big.p)})`, `${signed(within("WTA").forecasts.big.beta, 2)} (${pv(within("WTA").forecasts.big.p)})`],
              ["Forecast β, clutch score (p)", `${signed(within("ATP").forecasts.clutch.beta, 2)} (${pv(within("ATP").forecasts.clutch.p)})`, `${signed(within("WTA").forecasts.clutch.beta, 2)} (${pv(within("WTA").forecasts.clutch.p)})`],
            ]} />
          <Table number="A5"
            caption={<>Sensitivity of the period comparison, one choice changed at a time. Clutch correlation with its 95% interval; forecast β with its permutation p ({count(rb.sims.permutations)} permutations, drawn afresh, so the first row’s p-values differ slightly from Table 6).</>}
            head={["Tour and variant", "Players", "Clutch r (95% interval)", "β big (p)", "β clutch (p)"]}
            rows={rb.sensitivity.map((s) => [`${s.tour}, ${(SENS_LABEL[s.label] ?? s.label).replace(/^./, (c) => c.toLowerCase())}`, s.players,
              `${signed(s.clutch_r)} (${signed(s.clutch_low, 2)} to ${signed(s.clutch_high, 2)})`,
              `${signed(s.big_beta, 2)} (${pv(s.big_p)})`, `${signed(s.clutch_beta, 2)} (${pv(s.clutch_p)})`])} />
        </Section>

        {/* ───────────────────────── Appendix B ───────────────────────── */}
        <Section id="appendix-b" number="Appendix B" title="Technical details">
          <Subsection number="B.1" title="Simulation tests">
            <Cols>
              <p>Each simulated data set draws every match result from its calibrated probability, refits the calibration slopes on the simulated results, and recomputes every statistic exactly as for the real data. Refitting the calibration inside each simulation ensures that the simulated statistics carry the same estimation noise as the observed ones. The one-sided p-value is the share of {count(rb.sims.null)} simulated statistics at least as large as the observed value. Holm’s correction is applied across the eight spread sets (four match sets on each tour).</p>
            </Cols>
          </Subsection>
          <Subsection number="B.2" title="Power and upper bounds">
            <Cols>
              <p>In the power simulations each player receives a trait θ<sub><i>i</i></sub> drawn from a normal distribution with mean zero and standard deviation τ, which is added to the log-odds of the calibrated forecast in big matches only (equation B1). Power is the share of {count(rb.sims.power)} simulations whose statistic exceeds the 95th percentile of the no-trait simulations. The 95% upper bound is the smallest τ at which the observed statistic would fall among the lowest 5% of simulated values, found by interpolation between the simulated values of τ. This is closely related to an equivalence test (<Cite id="lakens">Lakens, 2017</Cite>). The edge at evens is 100 × (σ(τ) − 0.5).</p>
            </Cols>
            <Eq number="B1">logit {v("P", "m")}<sup>true</sup> = logit {v("P̂", "m")} + 1<sub>big</sub>(m) · ( {v("θ", "A")} − {v("θ", "B")} )</Eq>
          </Subsection>
          <Subsection number="B.3" title="Game margins">
            <Cols>
              <p>Each result is replaced by the share of games the player won, with a tie-break that decides a match counted as one game. The expected share is a fractional logit on the Elo log-odds, fitted separately for each group (<Cite id="papke">Papke and Wooldridge, 1996</Cite>). The chance variation is each group’s mean squared residual. Because game shares within a match are not independent draws, the null distributions come from {count(rb.sims.game_permutations)} permutations of residuals among matches within each group, rather than from simulation.</p>
            </Cols>
          </Subsection>
          <Subsection number="B.4" title="Within-tournament ratings">
            <Cols>
              <p>The within-tournament analysis uses the project’s round-aware Elo, which updates each player’s rating after each completed round of the same event. Big matches without a complete earlier-round record ({pct(1 - within("ATP").eligible)} on each tour) keep the start-of-week rating. These include every round-robin match at the season-ending Finals, because the order of group matches is not recorded in the source data.</p>
            </Cols>
          </Subsection>
        </Section>
      </Body>

      <Footer paper={meta} />
    </Sheet>
  );
}
