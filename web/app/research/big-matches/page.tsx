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
const v = (name: string, sub?: string) => <>{name}{sub && <sub>{sub}</sub>}</>;

const nullRow = (tour: string, test: string) => rb.null.find((n) => n.tour === tour && n.test === test)!;
const powerRow = (tour: string, test: string) => rb.power.rows.find((p) => p.tour === tour && p.test === test)!;
const slopeTest = (tour: string, bo: number) => rb.slope_tests.find((s) => s.tour === tour && s.best_of === bo);
const game = (tour: string) => rb.games.find((g) => g.tour === tour)!;
const gameSet = (tour: string, set: string) => game(tour).spread.find((s) => s.set === set)!;
const within = (tour: string) => rb.within.find((w) => w.tour === tour)!;
const holm = (tour: string, set: string) => rb.holm.find((h) => h.tour === tour && h.set === set)!.p;
const tauIndex = rb.power.taus.indexOf(0.2);
const bound = (tour: string, test: string) => powerRow(tour, test).bound_points;
const boundText = (tour: string, test: string) => { const b = bound(tour, test); return b === null ? "not reached" : `${pts(b)} points`; };

const SETS: [string, string][] = [
  ["finals only", "Finals only"],
  ["semi-finals + finals", "Semi-finals and finals"],
  ["all big matches", "All big matches"],
  ["regular matches", "Regular matches"],
];
const atpFinals = spread("ATP", "finals only").ratio;
const bigSets = r.spread.filter((s) => s.set !== "regular matches");
const maxBigRatio = Math.max(...bigSets.map((s) => s.ratio));
const minBigRatio = Math.min(...bigSets.map((s) => s.ratio));
const nullTests = rb.null.length / 2;

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
  ["clutch ratio", "Test 1: clutch spread", "big minus regular, beyond luck"],
  ["split-half r", "Test 2: split-half agreement", "two halves of each career"],
  ["forecast z clutch", "Test 3: forecast test", "earlier clutch score"],
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
  "version 1 settings": "Version 1 settings",
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
const atpClutchGames = rb.games.find((g) => g.tour === "ATP")!.clutch;
const byFormat = (bo: number) => rb.format.find((f) => f.best_of === bo)!;

const META: MetaItem[] = [
  { label: "Status", value: <>Post-hoc and descriptive. Not pre-registered. Not peer reviewed.</> },
  { label: "Analysis", value: <>Version 1 run 14 November 2026, definitions fixed in the script before the run. Version 2 robustness analyses written after the version 1 results were known (Section 4.6).</> },
  { label: "Data", value: <>Jeff Sackmann, tennis_atp and tennis_wta, to 25 May 2026 (CC BY-NC-SA 4.0).</> },
  { label: "Reproduce", value: <span className="font-mono text-[11px]">python -m matchup_dna.posthoc_big_match<br />python -m matchup_dna.posthoc_big_match_robustness</span> },
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
          { label: "Introduction", text: <>A common story in tennis is that some players fall short when the stakes are highest. If big-match performance were a stable trait, a match forecast should account for it.</> },
          { label: "Methods", text: <>We used {count(r.matches)} main-tour ATP and WTA matches from {r.window}, {count(r.big_matches)} of them semi-finals, finals, late Slam rounds, Masters quarter-finals or season-ending Finals matches. Each result was compared with a recalibrated surface Elo expectation. Three tests asked whether players differ beyond luck, whether two halves of their big matches agree, and whether {r.periods[0]} predicts {r.periods[1]}. Exact simulation tests, power curves and 95% upper bounds show what the data could have detected, and the results were rechecked with game margins, within-tournament ratings and alternative analysis choices.</> },
          { label: "Results", text: <>Players&apos; big-match results varied {two(minBigRatio)} to {two(maxBigRatio)} times as much as luck alone would produce. Split-half agreement was {signed(sh("ATP").r)} (ATP) and {signed(sh("WTA").r)} (WTA), and earlier scores did not significantly improve forecasts of later big matches. The test that removes general form bounds the spread of a clutch trait: a player one standard deviation above average would beat an equal opponent in a big match by at most about {pts(bound("ATP", "clutch ratio")!)} percentage points (ATP) and {pts(bound("WTA", "clutch ratio")!)} points (WTA) more than usual. On the ATP tour, players&apos; big-match results varied slightly more than their regular-match results would suggest (p = {pv(nullRow("ATP", "clutch ratio").p)} with wins, {pv(atpClutchGames.p)} with game margins, and also within best-of-three matches alone), but this did not survive correction for multiple tests, did not carry over between periods and did not improve forecasts. The WTA showed no sign of a trait.</> },
          { label: "Discussion", text: <>We find no large or forecast-relevant choke or clutch trait in tour-level results. A small one, possibly on the ATP tour, cannot be excluded, and a pre-registered test on later matches could settle it. Big-match records are too noisy to estimate such a trait player by player, so the forecasting model makes no player-specific big-match adjustment. The analysis is post-hoc and descriptive.</> },
        ]} />
      </FrontMatter>

      <Body>
        <Section id="introduction" number="1" title="Introduction">
          <Cols>
            <p>When a leading player loses consecutive finals, the explanation that follows is usually psychological: the pressure got to them. If that were a stable trait, it would matter to a forecasting model. A player who reliably underperforms in big matches should be marked down in semi-finals and finals, and one who reliably rises should be marked up.</p>
            <p>The question here is not whether pressure affects tennis at all. It is narrower, and it is the one a match forecast needs answered: given a player&apos;s overall strength, do their results in big matches depart from expectation in a way that persists? A null answer is only useful if we also say how large an effect the data could have missed, so the paper reports power and upper bounds alongside its tests.</p>
            <p>Section 2 reviews related work, Section 3 describes the data and Section 4 the method. Section 5 gives the results, including what the data rule out and how the results change under other analysis choices. Sections 6 to 9 discuss them.</p>
          </Cols>
        </Section>

        <Section id="related" number="2" title="Related work">
          <Cols>
            <p>Laboratory work shows that high stakes can harm skilled performance (<Cite id="baumeister">Baumeister, 1984</Cite>). Field evidence from sport is mixed. Kickers in penalty shoot-outs were reported to do worse when shooting second (<Cite id="apesteguia">Apesteguia and Palacios-Huerta, 2010</Cite>), a result a larger sample did not reproduce (<Cite id="kocher">Kocher et al., 2012</Cite>).</p>
            <p>In tennis, points are not exactly independent and identically distributed, but the departures are small (<Cite id="klaassen">Klaassen and Magnus, 2001</Cite>). Players differ in how their performance changes on the most important points (<Cite id="gonzalez">González-Díaz et al., 2012</Cite>), and pressure effects at important stages of a match have been reported to differ between men and women (<Cite id="cohenzada">Cohen-Zada et al., 2017</Cite>). These studies work within matches. We ask whether such differences, if they exist, show up in match results and persist across a career.</p>
            <p>The closest methodological precedent is baseball&apos;s search for clutch hitters. Year-to-year correlations of clutch performance gave little evidence of a lasting skill (<Cite id="cramer">Cramer, 1977</Cite>). Separating a player&apos;s true ability from binomial noise is the empirical Bayes problem of <Cite id="efron">Efron and Morris (1975)</Cite>, and <Cite id="brown2008">Brown (2008)</Cite> showed how it predicts second-half batting averages from first-half ones, which is our split-half test. Elo ratings are among the strongest simple predictors of tennis results (<Cite id="kovalchik">Kovalchik, 2016</Cite>), which is why we use them as the expectation.</p>
          </Cols>
        </Section>

        <Section id="data" number="3" title="Data">
          <Cols>
            <p>We use Jeff Sackmann&apos;s ATP and WTA tour-level match files (<Cite id="sackmann">Sackmann, 2026</Cite>) up to 25 May 2026. No result from June 2026 onward is used, so the analysis does not touch the matches held out for the project&apos;s pre-registered evaluations. Ratings are computed over the full history from 1968, and the analysis window starts in 2000.</p>
            <p>Only main-tour events count: Grand Slams, Masters and Premier events, regular tour events, the season-ending Finals and the Olympics. Davis Cup, Billie Jean King Cup, other team events, exhibitions and bronze-medal matches are excluded. As everywhere in the project, only completed best-of-three and best-of-five matches are rated. Every analysed match has a readable score, so the game-margin analysis uses the same matches. Figure 1 shows how the matches flow into the three tests.</p>
          </Cols>
          <Figure number={1} caption={<>Flow of matches and players through the analysis. Counts are for {r.window}; player counts are those meeting each test&apos;s minimum of {r.min_big} matches.</>}>
            <StudyFlow
              source={{ title: "Jeff Sackmann's ATP and WTA tour-level match files", detail: "1968 – 25 May 2026; Elo ratings are run over the full history" }}
              excluded={{ title: "Left out of the analysis", detail: "Matches before 2000; Davis Cup, Billie Jean King Cup and other team events; exhibitions; bronze-medal matches; retirements, walkovers and other incomplete matches" }}
              analysed={{ title: `Rated main-tour matches, ${r.window}`, detail: `n = ${count(r.matches)}` }}
              split={[
                { title: "Big matches", detail: <>n = {count(r.big_matches)}<br />Semi-finals, finals, Slam fourth rounds and quarter-finals, Masters quarter-finals, Finals</> },
                { title: "Regular matches", detail: <>n = {count(r.matches - r.big_matches)}<br />Every other main-tour match</> },
              ]}
              tests={[
                { title: "Test 1: spread beyond luck", detail: <>{r.window}; {count(spread("ATP", "all big matches").players)} ATP and {count(spread("WTA", "all big matches").players)} WTA players for all big matches</> },
                { title: "Test 2: split-half agreement", detail: <>{count(sh("ATP").players)} ATP and {count(sh("WTA").players)} WTA players with {r.min_big}+ big matches in each half</> },
                { title: "Test 3: carry-over between periods", detail: <>{r.periods[0]} against {r.periods[1]}; {ps("ATP").players} ATP and {ps("WTA").players} WTA players</> },
              ]}
            />
          </Figure>
        </Section>

        <Section id="method" number="4" title="Method">
          <Subsection number="4.1" title="Big matches">
            <Cols>
              <p>A big match is any semi-final or final; a Grand Slam fourth round or quarter-final; a Masters quarter-final (ATP Masters 1000, WTA Premier Mandatory, and WTA Tier I before 2009); or any match at the season-ending Finals. Every other main-tour match is a regular match. The definitions in Sections 4.1 to 4.4 were written into the analysis script before it was run.</p>
            </Cols>
          </Subsection>

          <Subsection number="4.2" title="Expected results">
            <Cols>
              <p>Strength is the project&apos;s canonical surface-blended Elo rating (<Cite id="elo">Elo, 1978</Cite>), taken at the start of the tournament week and never refitted. Plain Elo is too confident in best-of-three matches and too cautious in best-of-five. Left uncorrected, players who are usually favourites at the Slams would look clutch for a reason unrelated to pressure.</p>
              <p>Elo&apos;s log-odds are therefore rescaled with one slope <i>b</i><sub>g</sub> per group <i>g</i> = (tour, big or regular, best of three or five), fitted by maximum likelihood on the matches of the window being analysed (equation 1). The residual of player <i>i</i> in match <i>m</i> is the result minus that expectation (equation 2).</p>
            </Cols>
            <Eq number={1}>{v("P", "ij")} = σ ( {v("b", "g")} · logit {v("p", "ij")}<sup>Elo</sup> )</Eq>
            <Eq number={2}>{v("e", "im")} = {v("y", "im")} − {v("P", "im")}, &nbsp; {v("y", "im")} ∈ {"{0, 1}"}</Eq>
          </Subsection>

          <Subsection number="4.3" title="Player scores">
            <Cols>
              <p>A player&apos;s big-match score sums their big-match residuals and shrinks the total hard toward zero, so a short run of results cannot dominate (<Cite id="efron">Efron and Morris, 1975</Cite>). With <i>n</i><sub>i</sub> big matches and a shrinkage constant of {r.shrink}, a player with {r.shrink} big matches is weighted half toward their own record and half toward no effect (equation 3).</p>
              <p>A player whom Elo underrates everywhere, such as a fast-improving young player, would score well in big matches for that reason alone. The clutch score removes this by subtracting the same score computed on regular matches (equation 4).</p>
            </Cols>
            <Eq number={3}>{v("s", "i")} = Σ<sub>m ∈ big</sub> {v("e", "im")} / ( {v("n", "i")} + {r.shrink} )</Eq>
            <Eq number={4}>{v("c", "i")} = {v("s", "i")}<sup>big</sup> − {v("s", "i")}<sup>regular</sup></Eq>
          </Subsection>

          <Subsection number="4.4" title="Three tests">
            <Cols>
              <p><b>Spread beyond luck.</b> For players with at least {r.min_big} matches of a kind, the variance of their mean residuals is split into the part coin-flip luck would produce and the remainder, which estimates the variance of a true trait. The ratio of observed to luck variance is 1 when players differ by exactly as much as luck predicts. The same split gives the shrinkage the data support: the number of matches needed before half of a player&apos;s record is signal.</p>
              <p><b>Split-half agreement.</b> Big matches are divided into two halves by tournament edition, and the halves&apos; mean residuals are correlated across players with at least {r.min_big} big matches in each. The Spearman–Brown formula (<Cite id="spearman">Spearman, 1910</Cite>; <Cite id="brown">Brown, 1910</Cite>) converts this into a full-data reliability.</p>
              <p><b>Carry-over between periods.</b> Scores are computed separately for {r.periods[0]} and {r.periods[1]}, each with its own calibration, and correlated across players with at least {r.min_big} big matches in both. A forecast test then asks whether earlier scores improve the calibrated forecast of every later big match (equation 5), with β fitted by maximum likelihood and its p-value from 1,000 permutations of the earlier scores among players. Intervals are percentile bootstraps over players with 2,000 draws (<Cite id="efron1979">Efron, 1979</Cite>).</p>
            </Cols>
            <Eq number={5}>logit {v("P", "m")} = logit {v("P̂", "m")} + β ( {v("s", "A")} − {v("s", "B")} )</Eq>
          </Subsection>

          <Subsection number="4.5" title="Exact tests, power and upper bounds">
            <Cols>
              <p><b>Exact null tests.</b> The spread ratio has no simple sampling distribution, so we simulate it. Each simulated data set draws every match result from its calibrated probability, refits the calibration and reruns all three tests. Across {count(rb.sims.null)} such data sets with no trait, the share of statistics at least as large as the observed one is its one-sided p-value. Holm&apos;s correction (<Cite id="holm">Holm, 1979</Cite>) is applied across the eight spread sets.</p>
              <p><b>Clutch spread.</b> A version of Test 1 that removes general form. Each player&apos;s mean big-match residual minus their mean regular-match residual is compared with the luck variance of that difference. A player Elo underrates in every match has no excess here, so this is the cleanest test of a pressure-specific trait.</p>
              <p><b>Power and bounds.</b> We then add a known clutch trait. Each player receives θ<sub>i</sub> ~ N(0, τ²) on the log-odds scale, added in big matches only and constant over their career (equation 6). For each of {rb.power.taus.length} values of τ, {count(rb.sims.power)} simulated data sets give each test&apos;s power: the share of simulations beyond the 95th percentile of the no-trait simulations. The 95% upper bound on τ is the smallest τ at which the observed statistic would be among the lowest 5% of simulated values, in the spirit of an equivalence test (<Cite id="lakens">Lakens, 2017</Cite>). We report τ as the edge it gives: the number of percentage points above 50% that a player one standard deviation above average would win against an equal opponent, 100 (σ(τ) − 0.5).</p>
              <p>A trait that stays constant over a career is the easiest kind to detect, so these power figures are best cases. A trait that drifts would be harder to find.</p>
            </Cols>
            <Eq number={6}>logit {v("P", "m")}<sup>true</sup> = logit {v("P̂", "m")} + 1<sub>big</sub>(m) · ( {v("θ", "A")} − {v("θ", "B")} )</Eq>
          </Subsection>

          <Subsection number="4.6" title="Robustness checks (version 2)">
            <Cols>
              <p>Version 2 of this paper adds the analyses below and those in Section 4.5. All of them were written after the version 1 results were known, so they are post-hoc too. Their implementation reproduces every version 1 point estimate to within 10<sup>−14</sup>.</p>
              <p><b>Game margins.</b> A win or loss carries little information, so each result is replaced by the share of games the player won. The expected share comes from a fractional logit on the Elo log-odds, fitted per group (<Cite id="papke">Papke and Wooldridge, 1996</Cite>). The luck variance is each group&apos;s mean squared residual, and the null distributions come from {count(rb.sims.game_permutations)} permutations of residuals among matches within each group. A tie-break that decides a match counts as one game.</p>
              <p><b>Within-tournament ratings.</b> Start-of-week ratings ignore form shown earlier in the same tournament, and players reach late rounds partly because they are in form that week. We repeat the tests with each player&apos;s rating updated through their earlier rounds, using the project&apos;s round-aware Elo. Big matches without a complete earlier-round record ({pct(1 - within("ATP").eligible)} on each tour, including every round-robin match at the Finals) keep the start-of-week rating.</p>
              <p><b>Sensitivity.</b> One choice is changed at a time in the carry-over test: shrinkage constant 10, 50 or 100; a minimum of 5 or 20 big matches; big matches limited to semi-finals and finals; and periods 2008–2015 against 2016 – May 2026. We also test whether the big-match calibration slopes differ from the regular ones. Last, after seeing an ATP excess in the clutch spread, we compared big and regular ATP matches within each format, best of three and best of five.</p>
            </Cols>
          </Subsection>
        </Section>

        <Section id="results" number="5" title="Results">
          <Subsection number="5.1" title="Favourites as a group">
            <Cols>
              <p>If big matches unsettled favourites in general, Elo would need a stronger correction in big matches than in regular ones. On the ATP tour the corrections are nearly identical in both formats (Figure 2, Table 1). On the WTA tour the big-match slope is lower ({two(slope("WTA", "big", 3)!)} against {two(slope("WTA", "regular", 3)!)}, p = {pv(slopeTest("WTA", 3)!.p)}): Elo overstates favourites&apos; edges more in big matches.</p>
              <p>That effect applies to every WTA favourite in a big match, not to particular players, and the per-group calibration removes it before any player is scored. The same calibration is needed in any forecast built on Elo, but it is a property of the matches, not a choke trait.</p>
            </Cols>
            <Figure number={2} caption={<>Elo calibration slopes in big and regular matches, {r.window}. A slope of 1 means Elo&apos;s probabilities were already right; below 1, Elo was too confident.</>}>
              <Dumbbell rows={CALIBRATION_ROWS} domain={[0.6, 1.2]} ticks={[0.6, 0.8, 1.2]} format={two} aLabel="Big matches" bLabel="Regular matches"
                        reference={1} referenceLabel="Elo already right" axisLabel="Calibration slope" ariaLabel="Figure 2: calibration slopes, big against regular matches" />
            </Figure>
            <Table number={1} caption={<>Elo calibration slopes {v("b", "g")} with standard errors, {r.window}, and a Wald test of big against regular.</>}
              head={["Tour and format", "Big", "Regular", "Difference", "z", "p"]}
              rows={rb.slope_tests.map((t) => [`${t.tour}, best of ${t.best_of}`, `${three(t.big)} (${three(t.big_se)})`, `${three(t.regular)} (${three(t.regular_se)})`,
                                               signed(t.big - t.regular), signed(t.z, 2), pv(t.p)])} />
          </Subsection>

          <Subsection number="5.2" title="Spread beyond luck">
            <Cols>
              <p>Players&apos; big-match records differ by about as much as luck predicts (Figure 3, Table 2). The ratio for ATP finals, the biggest matches, is {two(atpFinals)}. No big-match set on either tour exceeds {two(maxBigRatio)}, and the ratios do not rise as the matches get bigger. The largest, {two(spread("ATP", "all big matches").ratio)} for all ATP big matches, has an exact p of {pv(nullRow("ATP", "ratio all big matches").p)} ({pv(holm("ATP", "all big matches"))} after Holm&apos;s correction; Table 6).</p>
              <p>The clutch spread, which removes general form, is {two(nullRow("ATP", "clutch ratio").observed)} on the ATP tour (p = {pv(nullRow("ATP", "clutch ratio").p)}) and {two(nullRow("WTA", "clutch ratio").observed)} on the WTA tour (p = {pv(nullRow("WTA", "clutch ratio").p)}). The ATP value is nominally significant, but it is one of {nullTests} tests per tour and would not survive a correction for that many; Section 5.6 follows it up. Where an excess appears, the shrinkage the data support is above 100 big matches, more than most players play in a career.</p>
              <p>The only clear excess is in regular WTA matches ({two(spread("WTA", "regular matches").ratio)}, p {pv(nullRow("WTA", "ratio regular matches").p)}): ordinary form that Elo is slow to catch, unrelated to pressure.</p>
            </Cols>
            <Figure number={3} caption={<>Spread of players&apos; results against expectation, divided by the spread luck alone would produce, {r.window}; players with at least {r.min_big} matches of each kind. The dashed line at 1 is pure luck.</>}>
              <GroupedBars groups={SPREAD_GROUPS} domain={[0, 1.4]} ticks={[0, 0.5, 1, 1.4]} format={two} reference={1} referenceLabel="Pure luck"
                           axisLabel="Observed spread ÷ spread from luck" ariaLabel="Figure 3: spread of players' results relative to luck, by tour" />
            </Figure>
            <Table number={2}
              caption={<>Spread of players&apos; mean residuals, in win-probability points per match. Implied <i>k</i> is the number of matches before half of a record is signal. p is the exact one-sided p-value from {count(rb.sims.null)} simulations.</>}
              head={["Tour and matches", "Players", "Observed sd", "Luck sd", "Ratio", "Trait sd", "Implied k", "p"]}
              rows={TOURS.flatMap((tour) => SETS.map(([set, label]) => {
                const s = spread(tour, set);
                return [`${tour}, ${label.toLowerCase()}`, count(s.players), pp(s.observed_sd), pp(s.noise_sd), two(s.ratio), pp(s.trait_sd),
                        s.implied_k === null ? "none" : count(Math.round(s.implied_k)), pv(nullRow(tour, `ratio ${set}`).p)];
              }))} />
          </Subsection>

          <Subsection number="5.3" title="Split-half agreement">
            <Cols>
              <p>The two halves of the same players&apos; big matches barely agree (Table 3, and the first rows of Figure 4). Both correlations are small, both intervals include zero, and neither is significant in the exact test (p = {pv(nullRow("ATP", "split-half r").p)} and {pv(nullRow("WTA", "split-half r").p)}). Even with all the data, the implied reliability of a big-match record is below 0.2.</p>
            </Cols>
            <Table number={3} caption={<>Correlation between the two halves of each player&apos;s big matches, split by tournament edition, {r.window}.</>}
              head={["Tour", "Players", "r (95% interval)", "Full-data reliability"]}
              rows={TOURS.map((tour) => [tour, count(sh(tour).players), interval(sh(tour)), signed(sh(tour).spearman_brown)])} />
          </Subsection>

          <Subsection number="5.4" title="Carry-over between periods">
            <Cols>
              <p>Big-match scores from {r.periods[0]} carry into {r.periods[1]} only weakly, and no more than regular-match scores do (Figure 4, Table 4). On the WTA tour the regular-match score carries over more strongly ({signed(ps("WTA").correlations["regular-match"].r)}) than the big-match score ({signed(ps("WTA").correlations["big-match"].r)}).</p>
              <p>What persists is general form that Elo is slow to catch, not something specific to pressure. That explains the one other nominal result in Table 6. The exact test assumes no player differences of any kind, so it treats the WTA big-match score&apos;s forecast gain as surprising (p = {pv(nullRow("WTA", "forecast z big").p)}), but the permutation test, which keeps general form, does not (p = {pv(ps("WTA").forecasts["big-match"].permutation_p)}). Once form is removed, the clutch score barely persists on either tour, and neither score significantly improves the forecast of later big matches (Table 5).</p>
            </Cols>
            <Figure number={4} caption={<>Agreement of player scores, with 95% intervals: between the two halves of each player&apos;s big matches ({r.window}), and between {r.periods[0]} and {r.periods[1]} for the {ps("ATP").players} ATP and {ps("WTA").players} WTA players with at least {r.min_big} big matches in both periods. The dashed line at 0 is no agreement.</>}>
              <Forest groups={FOREST_GROUPS} domain={[-0.4, 0.7]} ticks={[-0.4, 0, 0.4, 0.7]} format={(x) => signed(x, 2)} reference={0} referenceLabel="No agreement"
                      axisLabel="Correlation" ariaLabel="Figure 4: agreement of player scores with 95% intervals" />
            </Figure>
            <Table number={4} caption={<>Correlation of player scores between {r.periods[0]} and {r.periods[1]}, with 95% intervals.</>}
              head={["Tour", "Players", "Big-match", "Clutch", "Regular-match"]}
              rows={TOURS.map((tour) => [tour, ps(tour).players, interval(ps(tour).correlations["big-match"]),
                                         interval(ps(tour).correlations.clutch), interval(ps(tour).correlations["regular-match"])])} />
            <Table number={5}
              caption={<>Forecast test (equation 5): do {r.periods[0]} scores improve the calibrated forecast of {r.periods[1]} big matches? β with its standard error; p from 1,000 permutations.</>}
              head={["Tour and score", "Matches", "With earlier score", "β (se)", "Log loss change", "p"]}
              rows={TOURS.flatMap((tour) => (["big-match", "clutch"] as const).map((key) => {
                const f = ps(tour).forecasts[key];
                return [`${tour}, ${key}`, count(f.matches), count(f.with_history), `${signed(f.beta, 2)} (${two(f.se)})`, signed(f.log_loss_change, 5), three(f.permutation_p)];
              }))} />
          </Subsection>

          <Subsection number="5.5" title="What the data can rule out">
            <Cols>
              <p>The tests are not blind. A clutch trait with τ = 0.4, an edge of {pts(rb.power.evens[rb.power.taus.indexOf(0.4)]!)} points at evens for a player one standard deviation above average, would be detected almost every time by the clutch-spread and split-half tests (Figure 5, Table 7). Below about τ = 0.2, an edge of {pts(rb.power.evens[tauIndex]!)} points, every test has less than even odds of detecting it.</p>
              <p>The observed statistics put upper bounds on the trait. We take the clutch spread as the headline bound because it is the only test that removes general form; its bounds are neither the tightest nor the loosest in Table 7. At 95% confidence, a player one standard deviation above average gains at most {boundText("ATP", "clutch ratio")} at evens in big matches on the ATP tour, and at most {boundText("WTA", "clutch ratio")} on the WTA tour. The split-half test gives similar bounds ({boundText("ATP", "split-half r")} and {boundText("WTA", "split-half r")}).</p>
              <p>So the data rule out the large, persistent effect the choking story usually implies, but not a trait of a few percentage points. Even a trait near the ATP bound would leave a player with 100 big matches with a record that is mostly noise, and a forecast could not tell who had it.</p>
            </Cols>
            <Figure number={5} caption={<>Power of the three tests against the size of an injected clutch trait, {count(rb.sims.power)} simulations per point. The horizontal axis is the edge, in percentage points at evens, of a player one standard deviation above average in big matches. The dashed line is 80% power.</>}>
              <PowerCurves panels={POWER_PANELS} xMax={10} xTicks={[0, 2.5, 5, 7.5, 10]} ariaLabel="Figure 5: power of the clutch-spread, split-half and forecast tests against the size of a clutch trait, by tour" />
            </Figure>
            <Table number={6}
              caption={<>Exact one-sided tests: each observed statistic against {count(rb.sims.null)} simulations with no trait. The 95th percentile is the value a statistic must exceed to be significant at 5%.</>}
              head={["Statistic", "ATP observed", "95th pct", "p", "WTA observed", "95th pct", "p"]}
              rows={NULL_LABELS.map(([test, label]) => {
                const a = nullRow("ATP", test), w = nullRow("WTA", test);
                return [label, signed(a.observed, 2), signed(a.critical, 2), pv(a.p), signed(w.observed, 2), signed(w.critical, 2), pv(w.p)];
              })} />
            <Table number={7}
              caption={<>Power at each trait size and the 95% upper bound on the trait. Trait sizes are τ = {rb.power.taus.map((t) => t.toFixed(2)).join(", ")}, an edge at evens of {rb.power.evens.map(pts).join(", ")} points.</>}
              head={["Tour and test", ...rb.power.evens.map((e) => `${pts(e)}`), "95% bound"]}
              rows={TOURS.flatMap((tour) => NULL_LABELS.filter(([t]) => t !== "ratio regular matches").map(([test, label]) => {
                const p = powerRow(tour, test);
                return [`${tour}, ${label.replace(", big-match score", ", big").replace(", clutch score", ", clutch").toLowerCase()}`, ...p.power.map(pct),
                        p.bound_points === null ? "–" : `${pts(p.bound_points)} pts`];
              }))}
              note="Power is the share of simulations beyond the no-trait 95th percentile. The regular-match spread is left out because the injected trait does not touch regular matches." />
          </Subsection>

          <Subsection number="5.6" title="Robustness">
            <Cols>
              <p><b>Game margins.</b> Measured by games, players differ a lot in every match: the regular-match spread ratio is {two(gameSet("ATP", "regular matches").ratio)} (ATP) and {two(gameSet("WTA", "regular matches").ratio)} (WTA), both p {pv(gameSet("ATP", "regular matches").p)}. Some players win their matches by wide margins and others by narrow ones, beyond what Elo&apos;s win probability says. That style shows up in big matches too, so the big-match spread is above 1 in some sets (Table 8). The clutch spread removes it and repeats the win-based pattern: an excess on the ATP tour ({two(atpGame.clutch.ratio)}, p = {pv(atpGame.clutch.p)}) and none on the WTA tour ({two(wtaGame.clutch.ratio)}, p = {pv(wtaGame.clutch.p)}). One game-based carry-over interval excludes zero, the WTA clutch score ({interval(wtaGame.correlations.clutch)}), but the forecast test using that same score finds nothing (p = {pv(wtaGame.forecasts.clutch.p)}), and its win-based counterpart is {signed(ps("WTA").correlations.clutch.r)}. No earlier game-based score significantly improves forecasts of later big-match wins (p = {pv(atpGame.forecasts.big.p)} and {pv(atpGame.forecasts.clutch.p)} for ATP, {pv(wtaGame.forecasts.big.p)} and {pv(wtaGame.forecasts.clutch.p)} for WTA).</p>
              <p><b>Format.</b> ATP big matches are mostly best of five and regular ones mostly best of three, so a player who is simply better over five sets would look clutch. We checked this after seeing the ATP excess by comparing big and regular matches within each format (Table 11). The excess remains within best-of-three matches alone (wins {two(byFormat(3).wins.ratio)}, p = {pv(byFormat(3).wins.p)}; games {two(byFormat(3).games.ratio)}, p = {pv(byFormat(3).games.p)}), so five-set fitness does not explain it. Within best-of-five matches, wins show no excess ({two(byFormat(5).wins.ratio)}, p = {pv(byFormat(5).wins.p)}), and games show a similar but non-significant one ({two(byFormat(5).games.ratio)}, p = {pv(byFormat(5).games.p)}).</p>
              <p><b>Within-tournament ratings.</b> Updating ratings through the earlier rounds changes little (Table 9). The spread ratios move by at most a few hundredths, the split-half correlations stay near {signed(within("ATP").split_half.r, 2)} and {signed(within("WTA").split_half.r, 2)}, and no forecast test is significant. Form shown earlier in the same week does not explain the results.</p>
              <p><b>Sensitivity.</b> Across the {rb.sensitivity.length / 2} variants of the carry-over test on each tour (Table 10), no forecast p-value falls below {pv(minSensitivityP)}. Clutch correlations range from {signed(Math.min(...rb.sensitivity.map((s) => s.clutch_r)), 2)} to {signed(Math.max(...rb.sensitivity.map((s) => s.clutch_r)), 2)}. One interval excludes zero, the ATP clutch score with periods 2008–2015 and 2016 – May 2026 ({signed(sens("ATP", "periods 2008-2015 / 2016-2026").clutch_r)}), but the forecast test on that split is not significant (p = {pv(sens("ATP", "periods 2008-2015 / 2016-2026").clutch_p)}), and the signs do not agree across choices.</p>
            </Cols>
            <Table number={8}
              caption={<>Game margins: share of games won against expectation, {r.window}. Ratio and trait sd as in Table 2 (trait sd in game-share points); p from {count(rb.sims.game_permutations)} within-group permutations. Carry-over and forecast as in Tables 4 and 5, with game-based scores predicting later big-match wins.</>}
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
              ]} />
            <Table number={9}
              caption={<>Within-tournament ratings: the main statistics with each player&apos;s rating updated through their earlier rounds of the same event.</>}
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
            <Table number={10}
              caption={<>Sensitivity of the carry-over test, one choice changed at a time. Clutch r with its 95% interval; forecast β with its permutation p ({count(rb.sims.permutations)} permutations, drawn afresh, so the first row&apos;s p-values differ slightly from Table 5).</>}
              head={["Tour and variant", "Players", "Clutch r (95% interval)", "β big (p)", "β clutch (p)"]}
              rows={rb.sensitivity.map((s) => [`${s.tour}, ${(SENS_LABEL[s.label] ?? s.label).replace(/^./, (c) => c.toLowerCase())}`, s.players,
                `${signed(s.clutch_r)} (${signed(s.clutch_low, 2)} to ${signed(s.clutch_high, 2)})`,
                `${signed(s.big_beta, 2)} (${pv(s.big_p)})`, `${signed(s.clutch_beta, 2)} (${pv(s.clutch_p)})`])} />
            <Table number={11}
              caption={<>ATP clutch spread within one format, {r.window}: big against regular matches of the same length. Wins with {count(rb.sims.null)} exact simulations, games with {count(rb.sims.game_permutations)} permutations. Added after the ATP excess was seen.</>}
              head={["Format", "Big matches", "Regular matches", "Players", "Clutch ratio, wins (p)", "Clutch ratio, games (p)"]}
              rows={rb.format.map((f) => [`Best of ${f.best_of}`, count(f.big_matches), count(f.regular_matches), f.wins.players,
                `${two(f.wins.ratio)} (${pv(f.wins.p)})`, `${two(f.games.ratio)} (${pv(f.games.p)})`])} />
          </Subsection>
        </Section>

        <Section id="runs" number="6" title="Why losing runs look like a pattern">
          <Cols>
            <p>If there is no large trait, why does the story persist? Part of the answer is the arithmetic of runs. Take a player who wins {pct(r.streak.p_win)} of their finals, a strong record, and treat each final as independent. Over {r.streak.finals} finals, the exact probability of losing at least two in a row somewhere is {pct(r.streak.two)}, and of losing at least three in a row, {pct(r.streak.three)} (Figure 6). A three-final losing run is the likely outcome of a good career, not evidence against it.</p>
            <p>People are quick to read meaning into such runs (<Cite id="gilovich">Gilovich et al., 1985</Cite>), although later work showed that the original hot-hand analysis was itself biased (<Cite id="miller">Miller and Sanjurjo, 2018</Cite>), so we rely only on the exact probabilities. Selection does the rest: with hundreds of players on tour, someone is always in the middle of a losing run, and those are the players written about.</p>
          </Cols>
          <Figure number={6} caption={<>Probability of at least one losing run in finals, for a player who wins {pct(r.streak.p_win)} of their finals, by the number of finals played. Exact calculation, each final independent; the marked values are at {r.streak.finals} finals.</>}>
            <RunCurve p={r.streak.p_win} mark={r.streak.finals} ariaLabel={`Figure 6: probability of a losing run of two or three finals against the number of finals played, for a ${pct(r.streak.p_win)} finals winner`} />
          </Figure>
        </Section>

        <Section id="discussion" number="7" title="Discussion">
          <Cols>
            <p>For forecasting, the implication is direct: the model makes no player-specific big-match adjustment. Even a trait at the upper bound would be hard to estimate player by player. At a typical big-match probability, a record of 100 big matches has a luck standard deviation of about 4.6 percentage points per match, comparable to the largest trait the data allow. A model that chased such records would move probabilities mostly on luck.</p>
            <p>The ATP excess is the one finding worth following up. Two related measures, wins and game margins, show it, and it is not explained by format or by form earlier in the week. Against it: it is one result among many, it does not survive correction for multiple tests, the persistence tests do not detect it, and the WTA, with a similar number of players and matches, shows nothing. Whatever its source, it lies within the bounds of Section 5.5, so it is too small to identify player by player.</p>
            <p>The tour-wide WTA calibration difference is a separate matter. It applies to every favourite in a big match, and any Elo-based forecast should calibrate big and regular matches separately to capture it. It is not evidence that particular players choke.</p>
            <p>The result does not contradict point-level findings. A player may raise or lower their level on important points, as <Cite id="gonzalez">González-Díaz et al. (2012)</Cite> report, and still win big matches at the rate their overall strength predicts, because that skill is part of what their rating already measures. What the data rule out is a large, persistent gap between a player&apos;s big-match results and their strength. A smaller gap, including the ATP excess, could be settled by a pre-registered test on matches played after this analysis, which the project&apos;s live forecast record will provide.</p>
          </Cols>
        </Section>

        <Section id="limitations" number="8" title="Limitations">
          <Cols>
            <p><b>Post-hoc.</b> The version 1 definitions were fixed before the run, but the question arose after recent results had been seen, and every version 2 analysis was written after the version 1 results were known. The analysis was not used to choose or change any model. With {nullTests} statistics per tour, one or two nominal p-values below 0.05 are expected by chance.</p>
            <p><b>Small samples in the period split.</b> Only {ps("ATP").players} ATP and {ps("WTA").players} WTA players had enough big matches in both periods. Section 5.5 quantifies what this costs in power.</p>
            <p><b>Simulation assumptions.</b> The exact tests assume that, without a trait, results are independent given their calibrated probabilities. General form violates this, which is why the big-match statistics in Table 6 can look significant when the clutch statistics do not. The power analysis assumes a normally distributed trait, constant over a career and applied only in big matches.</p>
            <p><b>Expectations.</b> The game-share expectation is a single-slope model per group. Within-tournament ratings cover {pct(within("ATP").eligible)} of big matches; the rest keep start-of-week ratings.</p>
            <p><b>Pressure is not observed.</b> The analysis measures results against expectation, not how players feel, and it cannot show that pressure affects no one.</p>
          </Cols>
        </Section>

        <Section id="conclusion" number="9" title="Conclusion">
          <Cols>
            <p>Across 26 years of tour-level tennis, players&apos; big-match records differ by about as much as luck would make them differ, and an earlier record does not predict a later one beyond ordinary form. The data rule out a large choke or clutch trait. A trait of a few percentage points cannot be excluded, and the ATP results hint at one, but it would be too small to identify player by player. The Matchup DNA forecasts therefore treat a final like any other match between the same two players, apart from the tour-wide calibration.</p>
          </Cols>
        </Section>

        <Statements items={[
          { title: "Data availability statement", text: <>Match data are Jeff Sackmann&apos;s public tennis_atp and tennis_wta repositories (CC BY-NC-SA 4.0), to 25 May 2026. Every figure in this paper is read from the analysis output and checked against the full written report before publication.</> },
          { title: "Analysis status", text: <>This analysis is post-hoc and descriptive. It was not pre-registered and has not been peer reviewed, and it did not change any frozen model or the live forecast record. How the live forecasts are made and scored is described on the <Link href="/methodology" className="ref">Methodology</Link> page.</> },
          { title: "Version history", text: <>Version 1.0 (14 November 2026): the three tests. Version 2.0 ({paperDate(meta.date)}): adds related work, exact simulation tests, power and upper bounds, the clutch spread, game margins, within-tournament ratings, sensitivity analyses, a test of the calibration slopes and a format check of the ATP result, and revises the claims to match. Every version 1 figure is unchanged.</> },
        ]} />

        <References items={[
          { id: "apesteguia", text: <>Apesteguia, J., and Palacios-Huerta, I. (2010). Psychological pressure in competitive environments: evidence from a randomized natural experiment. <i>Am. Econ. Rev.</i> 100, 2548–2564.</> },
          { id: "baumeister", text: <>Baumeister, R. F. (1984). Choking under pressure: self-consciousness and paradoxical effects of incentives on skillful performance. <i>J. Pers. Soc. Psychol.</i> 46, 610–620.</> },
          { id: "brown", text: <>Brown, W. (1910). Some experimental results in the correlation of mental abilities. <i>Br. J. Psychol.</i> 3, 296–322.</> },
          { id: "brown2008", text: <>Brown, L. D. (2008). In-season prediction of batting averages: a field test of empirical Bayes and Bayes methodologies. <i>Ann. Appl. Stat.</i> 2, 113–152.</> },
          { id: "cohenzada", text: <>Cohen-Zada, D., Krumer, A., Rosenboim, M., and Shapir, O. M. (2017). Choking under pressure and gender: evidence from professional tennis. <i>J. Econ. Psychol.</i> 61, 176–190.</> },
          { id: "cramer", text: <>Cramer, R. D. (1977). Do clutch hitters exist? <i>Baseball Res. J.</i> 6, 74–79.</> },
          { id: "efron1979", text: <>Efron, B. (1979). Bootstrap methods: another look at the jackknife. <i>Ann. Stat.</i> 7, 1–26.</> },
          { id: "efron", text: <>Efron, B., and Morris, C. (1975). Data analysis using Stein&apos;s estimator and its generalizations. <i>J. Am. Stat. Assoc.</i> 70, 311–319.</> },
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
      </Body>

      <Footer paper={meta} />
    </Sheet>
  );
}
