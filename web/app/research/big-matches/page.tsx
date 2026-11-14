import type { Metadata } from "next";
import { Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import { Dumbbell, Forest, GroupedBars, RunCurve, StudyFlow, type BarGroup, type ForestGroup } from "@/components/research/charts";
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
const TOURS = ["ATP", "WTA"] as const;
const two = (v: number) => v.toFixed(2);
const three = (v: number) => v.toFixed(3);
const signed = (v: number, d = 3) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}`;
const pp = (v: number) => (100 * v).toFixed(1);
const pct = (v: number) => `${Math.round(v * 100)}%`;
const count = (v: number) => v.toLocaleString("en-GB");
const slope = (tour: string, kind: "big" | "regular", bo: number) =>
  r.calibration.find((c) => c.tour === tour && c.kind === kind && c.best_of === bo)?.slope;
const spread = (tour: string, set: string) => r.spread.find((s) => s.tour === tour && s.set === set)!;
const ps = (tour: string) => r.period_split[tour]!;
const sh = (tour: string) => r.split_half[tour]!;
const interval = (c: { r: number; low: number; high: number }) => `${signed(c.r)} (${signed(c.low)} to ${signed(c.high)})`;
const v = (name: string, sub?: string) => <>{name}{sub && <sub>{sub}</sub>}</>;

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

const META: MetaItem[] = [
  { label: "Status", value: <>Post-hoc and descriptive. Not pre-registered. Not peer reviewed.</> },
  { label: "Analysis", value: <>Run {paperDate(meta.date)}. Definitions fixed in the script before the run.</> },
  { label: "Data", value: <>Jeff Sackmann, tennis_atp and tennis_wta, to 25 May 2026 (CC BY-NC-SA 4.0).</> },
  { label: "Reproduce", value: <span className="font-mono text-[11px]">python -m matchup_dna.posthoc_big_match</span> },
  { label: "Citation", value: <>Matchup DNA Research ({meta.date.slice(0, 4)}). {meta.title} {meta.subtitle}. Matchup DNA Working Paper {meta.number}, version {meta.version}.</> },
  { label: "Related", value: <><Link href="/methodology" className="ref">How the forecasts are made</Link><br /><Link href="/lab" className="ref">Model Lab</Link></> },
];

export default function BigMatchesPaper() {
  return (
    <Sheet fontClass={serif.variable}>
      <Masthead paper={meta} />

      <FrontMatter meta={META}>
        <TitleBlock paper={meta} authors="Matchup DNA Research" affiliation="Matchup DNA, a non-commercial tennis forecasting project" />
        <Abstract keywords={meta.keywords} parts={[
          { label: "Introduction", text: <>A common story in tennis is that some players fall short when the stakes are highest. If big-match performance were a stable trait, a match forecast should account for it.</> },
          { label: "Methods", text: <>We used {count(r.matches)} main-tour ATP and WTA matches from {r.window}, {count(r.big_matches)} of them semi-finals, finals, late Slam rounds, Masters quarter-finals or season-ending Finals matches. Each result was compared with a recalibrated surface Elo expectation, and each player received a heavily shrunk big-match score and a clutch score (big-match minus regular-match performance). Three tests asked whether players differ beyond luck, whether two halves of their big matches agree, and whether {r.periods[0]} predicts {r.periods[1]}.</> },
          { label: "Results", text: <>The spread of players&apos; big-match results was {two(minBigRatio)} to {two(maxBigRatio)} times the spread luck alone would produce ({two(atpFinals)} for ATP finals). Split-half agreement was {signed(sh("ATP").r)} (ATP) and {signed(sh("WTA").r)} (WTA). Earlier scores did not significantly improve forecasts of later big matches, and the part of a record that carried over was ordinary form, which persisted as much in regular matches.</> },
          { label: "Discussion", text: <>We find no measurable choke or clutch trait in tour-level results. A big-match adjustment would add noise to a forecasting model, not accuracy. The analysis is post-hoc and descriptive.</> },
        ]} />
      </FrontMatter>

      <Body>
        <Section id="introduction" number="1" title="Introduction">
          <Cols>
            <p>When a leading player loses consecutive finals, the explanation that follows is usually psychological: the pressure got to them. If that were a stable trait, it would matter to a forecasting model. A player who reliably underperforms in big matches should be marked down in semi-finals and finals, and one who reliably rises should be marked up.</p>
            <p>The question is not whether pressure affects tennis at all. Point-level studies have found that points are not exactly independent and identically distributed, though the departures are small (<Cite id="klaassen">Klaassen and Magnus, 2001</Cite>), and that players differ in how their performance changes on the most important points within a match (<Cite id="gonzalez">González-Díaz et al., 2012</Cite>). Our question is narrower, and it is the one a match forecast needs answered: given a player&apos;s overall strength, do their results in big matches depart from expectation in a way that persists?</p>
            <p>We answer it with three tests on tour-level results: whether players differ in big matches by more than luck allows, whether two halves of the same players&apos; big matches agree, and whether an earlier period predicts a later one. Section 2 describes the data, Section 3 the method, Section 4 the results, and Sections 5 to 8 discuss them.</p>
          </Cols>
        </Section>

        <Section id="data" number="2" title="Data">
          <Cols>
            <p>We use Jeff Sackmann&apos;s ATP and WTA tour-level match files (<Cite id="sackmann">Sackmann, 2026</Cite>) up to 25 May 2026. No result from June 2026 onward is used, so the analysis does not touch the matches held out for the project&apos;s pre-registered evaluations. Ratings are computed over the full history from 1968, and the analysis window starts in 2000.</p>
            <p>Only main-tour events count: Grand Slams, Masters and Premier events, regular tour events, the season-ending Finals and the Olympics. Davis Cup, Billie Jean King Cup, other team events, exhibitions and bronze-medal matches are excluded. As everywhere in the project, only completed best-of-three and best-of-five matches are rated. Figure 1 shows how the matches flow into the three tests.</p>
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

        <Section id="method" number="3" title="Method">
          <Subsection number="3.1" title="Big matches">
            <Cols>
              <p>A big match is any semi-final or final; a Grand Slam fourth round or quarter-final; a Masters quarter-final (ATP Masters 1000, WTA Premier Mandatory, and WTA Tier I before 2009); or any match at the season-ending Finals. Every other main-tour match is a regular match. All definitions in this section were written into the analysis script before it was run.</p>
            </Cols>
          </Subsection>

          <Subsection number="3.2" title="Expected results">
            <Cols>
              <p>Strength is the project&apos;s canonical surface-blended Elo rating (<Cite id="elo">Elo, 1978</Cite>), taken at the start of the tournament week and never refitted. Plain Elo is too confident in best-of-three matches and too cautious in best-of-five. Left uncorrected, players who are usually favourites at the Slams would look clutch for a reason unrelated to pressure.</p>
              <p>Elo&apos;s log-odds are therefore rescaled with one slope <i>b</i><sub>g</sub> per group <i>g</i> = (tour, big or regular, best of three or five), fitted by maximum likelihood on the matches of the window being analysed (equation 1). The residual of player <i>i</i> in match <i>m</i> is the result minus that expectation (equation 2).</p>
            </Cols>
            <Eq number={1}>{v("P", "ij")} = σ ( {v("b", "g")} · logit {v("p", "ij")}<sup>Elo</sup> )</Eq>
            <Eq number={2}>{v("e", "im")} = {v("y", "im")} − {v("P", "im")}, &nbsp; {v("y", "im")} ∈ {"{0, 1}"}</Eq>
          </Subsection>

          <Subsection number="3.3" title="Player scores">
            <Cols>
              <p>A player&apos;s big-match score sums their big-match residuals and shrinks the total hard toward zero, so a short run of results cannot dominate (<Cite id="efron">Efron and Morris, 1975</Cite>). With <i>n</i><sub>i</sub> big matches and a shrinkage constant of {r.shrink}, a player with {r.shrink} big matches is weighted half toward their own record and half toward no effect (equation 3).</p>
              <p>A player whom Elo underrates everywhere, such as a fast-improving young player, would score well in big matches for that reason alone. The clutch score removes it by subtracting the same score computed on regular matches (equation 4).</p>
            </Cols>
            <Eq number={3}>{v("s", "i")} = Σ<sub>m ∈ big</sub> {v("e", "im")} / ( {v("n", "i")} + {r.shrink} )</Eq>
            <Eq number={4}>{v("c", "i")} = {v("s", "i")}<sup>big</sup> − {v("s", "i")}<sup>regular</sup></Eq>
          </Subsection>

          <Subsection number="3.4" title="Three tests">
            <Cols>
              <p><b>Spread beyond luck.</b> For players with at least {r.min_big} matches of a kind, the variance of their mean residuals is split into the part coin-flip luck would produce and the remainder, which estimates the variance of a true trait. The ratio of observed to luck variance is 1 when players differ by exactly as much as luck predicts. The same split gives the shrinkage the data support: the number of matches needed before half of a player&apos;s record is signal.</p>
              <p><b>Split-half agreement.</b> Big matches are divided into two halves by tournament edition, and the halves&apos; mean residuals are correlated across players with at least {r.min_big} big matches in each. The Spearman–Brown formula (<Cite id="spearman">Spearman, 1910</Cite>; <Cite id="brown">Brown, 1910</Cite>) converts this into a full-data reliability.</p>
              <p><b>Carry-over between periods.</b> Scores are computed separately for {r.periods[0]} and {r.periods[1]}, each with its own calibration, and correlated across players with at least {r.min_big} big matches in both. A forecast test then asks whether earlier scores improve the calibrated forecast of every later big match (equation 5), with β fitted by maximum likelihood and its p-value from 1,000 permutations of the earlier scores among players. Intervals are percentile bootstraps over players (2,000 draws).</p>
            </Cols>
            <Eq number={5}>logit {v("P", "m")} = logit {v("P̂", "m")} + β ( {v("s", "A")} − {v("s", "B")} )</Eq>
          </Subsection>
        </Section>

        <Section id="results" number="4" title="Results">
          <Subsection number="4.1" title="Favourites as a group">
            <Cols>
              <p>If big matches unsettled favourites in general, Elo would need a stronger correction in big matches than in regular ones. On the ATP tour the corrections are nearly identical in both formats (Figure 2, Table 1). On the WTA tour the big-match slope is lower ({two(slope("WTA", "big", 3)!)} against {two(slope("WTA", "regular", 3)!)}): Elo overstates favourites&apos; edges a little more in big matches.</p>
              <p>That is a tour-wide effect on every favourite, not a trait of particular players, and the per-group calibration removes it before any player is scored. Its significance was not tested.</p>
            </Cols>
            <Figure number={2} caption={<>Elo calibration slopes in big and regular matches, {r.window}. A slope of 1 means Elo&apos;s probabilities were already right; below 1, Elo was too confident.</>}>
              <Dumbbell rows={CALIBRATION_ROWS} domain={[0.6, 1.2]} ticks={[0.6, 0.8, 1.2]} format={two} aLabel="Big matches" bLabel="Regular matches"
                        reference={1} referenceLabel="Elo already right" axisLabel="Calibration slope" ariaLabel="Figure 2: calibration slopes, big against regular matches" />
            </Figure>
            <Table number={1} caption={<>Elo calibration slopes {v("b", "g")}, {r.window}.</>}
              head={["Tour and matches", "Best of 3", "Best of 5"]}
              rows={TOURS.flatMap((tour) => (["big", "regular"] as const).map((kind) => [
                `${tour}, ${kind}`, two(slope(tour, kind, 3)!), slope(tour, kind, 5) !== undefined ? two(slope(tour, kind, 5)!) : "–",
              ]))} />
          </Subsection>

          <Subsection number="4.2" title="Spread beyond luck">
            <Cols>
              <p>Players&apos; big-match records differ by almost exactly as much as luck predicts (Figure 3, Table 2). The ratio for ATP finals, the biggest matches, is {two(atpFinals)}. No big-match set on either tour exceeds {two(maxBigRatio)}, and the ratios do not rise as the matches get bigger.</p>
              <p>Where a small excess appears, the shrinkage the data support is above 100 big matches, more than almost any player plays in a career. In practice, a player&apos;s big-match record is mostly noise.</p>
            </Cols>
            <Figure number={3} caption={<>Spread of players&apos; results against expectation, divided by the spread luck alone would produce, {r.window}; players with at least {r.min_big} matches of each kind. The dashed line at 1 is pure luck.</>}>
              <GroupedBars groups={SPREAD_GROUPS} domain={[0, 1.4]} ticks={[0, 0.5, 1, 1.4]} format={two} reference={1} referenceLabel="Pure luck"
                           axisLabel="Observed spread ÷ spread from luck" ariaLabel="Figure 3: spread of players' results relative to luck, by tour" />
            </Figure>
            <Table number={2}
              caption={<>Spread of players&apos; mean residuals, in win-probability points per match. Implied <i>k</i> is the number of matches before half of a record is signal.</>}
              head={["Tour and matches", "Players", "Observed sd", "Luck sd", "Ratio", "Trait sd", "Implied k"]}
              rows={TOURS.flatMap((tour) => SETS.map(([set, label]) => {
                const s = spread(tour, set);
                return [`${tour}, ${label.toLowerCase()}`, count(s.players), pp(s.observed_sd), pp(s.noise_sd), two(s.ratio), pp(s.trait_sd),
                        s.implied_k === null ? "none" : count(Math.round(s.implied_k))];
              }))} />
          </Subsection>

          <Subsection number="4.3" title="Split-half agreement">
            <Cols>
              <p>The two halves of the same players&apos; big matches barely agree (Table 3, and the first rows of Figure 4). Both correlations are small and both intervals include zero. Even with all the data, the implied reliability of a big-match record is below 0.2.</p>
            </Cols>
            <Table number={3} caption={<>Correlation between the two halves of each player&apos;s big matches, split by tournament edition, {r.window}.</>}
              head={["Tour", "Players", "r (95% interval)", "Full-data reliability"]}
              rows={TOURS.map((tour) => [tour, count(sh(tour).players), interval(sh(tour)), signed(sh(tour).spearman_brown)])} />
          </Subsection>

          <Subsection number="4.4" title="Carry-over between periods">
            <Cols>
              <p>Big-match scores from {r.periods[0]} carry into {r.periods[1]} only weakly, and no more than regular-match scores do (Figure 4, Table 4). On the WTA tour the regular-match score carries over more strongly ({signed(ps("WTA").correlations["regular-match"].r)}) than the big-match score ({signed(ps("WTA").correlations["big-match"].r)}).</p>
              <p>What persists is general form that Elo is slow to catch, not something specific to pressure. Once that is removed, the clutch score barely persists on either tour. The forecast test agrees (Table 5): neither score significantly improves the forecast of later big matches.</p>
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
        </Section>

        <Section id="runs" number="5" title="Why losing runs look like a pattern">
          <Cols>
            <p>If the trait is not there, why does the story persist? Part of the answer is the arithmetic of runs. Take a player who wins {pct(r.streak.p_win)} of their finals, a strong record, and treat each final as independent. Over {r.streak.finals} finals, the exact probability of losing at least two in a row somewhere is {pct(r.streak.two)}, and of losing at least three in a row, {pct(r.streak.three)} (Figure 5). A three-final losing run is the likely outcome of a good career, not evidence against it.</p>
            <p>People are quick to read meaning into such runs (<Cite id="gilovich">Gilovich et al., 1985</Cite>), although later work showed that the original hot-hand analysis was itself biased (<Cite id="miller">Miller and Sanjurjo, 2018</Cite>), so we rely only on the exact probabilities. Selection does the rest: with hundreds of players on tour, someone is always in the middle of a losing run, and those are the players written about.</p>
          </Cols>
          <Figure number={5} caption={<>Probability of at least one losing run in finals, for a player who wins {pct(r.streak.p_win)} of their finals, by the number of finals played. Exact calculation, each final independent; the marked values are at {r.streak.finals} finals.</>}>
            <RunCurve p={r.streak.p_win} mark={r.streak.finals} ariaLabel={`Figure 5: probability of a losing run of two or three finals against the number of finals played, for a ${pct(r.streak.p_win)} finals winner`} />
          </Figure>
        </Section>

        <Section id="discussion" number="6" title="Discussion">
          <Cols>
            <p>For forecasting, the implication is direct: no big-match adjustment is added to the model. An effect this small cannot be told apart from luck in tour-level data, and a model that chased it would move probabilities on the strength of runs that say nothing about the next match.</p>
            <p>The result does not contradict point-level findings. A player may raise or lower their level on important points, as <Cite id="gonzalez">González-Díaz et al. (2012)</Cite> report, and still win big matches at the rate their overall strength predicts, because that skill is part of what their rating already measures. What the data rule out is a large, persistent gap between a player&apos;s big-match results and their strength.</p>
          </Cols>
        </Section>

        <Section id="limitations" number="7" title="Limitations">
          <Cols>
            <p><b>Post-hoc.</b> The definitions were fixed before the run, but the question arose after recent results had been seen. The analysis was not used to choose or change any model.</p>
            <p><b>Small samples in the period split.</b> Only {ps("ATP").players} ATP and {ps("WTA").players} WTA players had enough big matches in both periods. The test cannot rule out a small effect; it shows that any effect is too small to measure or forecast with in this data.</p>
            <p><b>Start-of-week ratings.</b> Results from earlier rounds of the same tournament are not used. Both players in a late round have usually won several matches that week, so this affects both sides alike.</p>
            <p><b>Pressure is not observed.</b> The analysis measures results against expectation, not how players feel, and cannot show that pressure affects no one. The WTA calibration difference (Section 4.1) was described but not tested for significance.</p>
          </Cols>
        </Section>

        <Section id="conclusion" number="8" title="Conclusion">
          <Cols>
            <p>Across 26 years of tour-level tennis, players&apos; big-match records differ by about as much as luck would make them differ, and an earlier record does not predict a later one beyond ordinary form. A choke or clutch trait, if it exists, is too small to measure in match results. The Matchup DNA forecasts therefore treat a final like any other match between the same two players.</p>
          </Cols>
        </Section>

        <Statements items={[
          { title: "Data availability statement", text: <>Match data are Jeff Sackmann&apos;s public tennis_atp and tennis_wta repositories (CC BY-NC-SA 4.0), to 25 May 2026. Every figure in this paper is read from the analysis output and checked against the full written report before publication.</> },
          { title: "Analysis status", text: <>This analysis is post-hoc and descriptive. It was not pre-registered and has not been peer reviewed, and it did not change any frozen model or the live forecast record. How the live forecasts are made and scored is described on the <Link href="/methodology" className="ref">Methodology</Link> page.</> },
        ]} />

        <References items={[
          { id: "brown", text: <>Brown, W. (1910). Some experimental results in the correlation of mental abilities. <i>Br. J. Psychol.</i> 3, 296–322.</> },
          { id: "efron", text: <>Efron, B., and Morris, C. (1975). Data analysis using Stein&apos;s estimator and its generalizations. <i>J. Am. Stat. Assoc.</i> 70, 311–319.</> },
          { id: "elo", text: <>Elo, A. E. (1978). <i>The Rating of Chessplayers, Past and Present</i>. New York, NY: Arco.</> },
          { id: "gilovich", text: <>Gilovich, T., Vallone, R., and Tversky, A. (1985). The hot hand in basketball: on the misperception of random sequences. <i>Cogn. Psychol.</i> 17, 295–314.</> },
          { id: "gonzalez", text: <>González-Díaz, J., Gossner, O., and Rogers, B. W. (2012). Performing best when it matters most: evidence from professional tennis. <i>J. Econ. Behav. Organ.</i> 84, 767–781.</> },
          { id: "klaassen", text: <>Klaassen, F. J. G. M., and Magnus, J. R. (2001). Are points in tennis independent and identically distributed? Evidence from a dynamic binary panel data model. <i>J. Am. Stat. Assoc.</i> 96, 500–509.</> },
          { id: "miller", text: <>Miller, J. B., and Sanjurjo, A. (2018). Surprised by the hot hand fallacy? A truth in the law of small numbers. <i>Econometrica</i> 86, 2019–2047.</> },
          { id: "sackmann", text: <>Sackmann, J. (2026). tennis_atp and tennis_wta: ATP and WTA tennis rankings, results and stats. GitHub repositories, data to 25 May 2026.</> },
          { id: "spearman", text: <>Spearman, C. (1910). Correlation calculated from faulty data. <i>Br. J. Psychol.</i> 3, 271–295.</> },
        ]} />
      </Body>

      <Footer paper={meta} />
    </Sheet>
  );
}
