import type { Metadata } from "next";
import Link from "next/link";
import { DotRows, type Group } from "@/components/research/DotRows";
import {
  Abstract, Body, Cite, Contents, Eq, Figure, P, PaperHeader, References, Section, Subsection, Table, type TocEntry,
} from "@/components/research/Paper";
import { paper } from "@/lib/papers";
import { BIG_MATCH } from "@/lib/research";

const meta = paper("big-matches");

export const metadata: Metadata = {
  title: meta.title,
  description: meta.abstract,
};

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

const SETS: [string, string][] = [
  ["finals only", "Finals only"],
  ["semi-finals + finals", "Semi-finals and finals"],
  ["all big matches", "All big matches"],
  ["regular matches", "Regular matches (reference)"],
];
const LUCK: Group[] = SETS.map(([set, label]) => ({ label, lanes: TOURS.map((tour) => ({ tour, value: spread(tour, set).ratio })) }));

const MEASURES: ["big-match" | "clutch" | "regular-match", string, string?][] = [
  ["big-match", "Big-match score"],
  ["clutch", "Clutch score", "big minus regular"],
  ["regular-match", "Regular-match score", "reference"],
];
const CARRY: Group[] = MEASURES.map(([key, label, note]) => ({
  label, note, lanes: TOURS.map((tour) => { const c = ps(tour).correlations[key]; return { tour, value: c.r, low: c.low, high: c.high }; }),
}));

const TOC: TocEntry[] = [
  { id: "introduction", number: "1", title: "Introduction" },
  { id: "data", number: "2", title: "Data" },
  { id: "method", number: "3", title: "Method" },
  { id: "results", number: "4", title: "Results" },
  { id: "runs", number: "5", title: "Why losing runs look like a pattern" },
  { id: "discussion", number: "6", title: "Discussion" },
  { id: "limitations", number: "7", title: "Limitations" },
  { id: "conclusion", number: "8", title: "Conclusion" },
  { id: "availability", number: "", title: "Data and code" },
  { id: "references", number: "", title: "References" },
];

const atpFinals = spread("ATP", "finals only").ratio;
const maxOtherRatio = Math.max(...r.spread.filter((s) => s.set !== "regular matches").map((s) => s.ratio));
const minOtherRatio = Math.min(...r.spread.filter((s) => s.set !== "regular matches").map((s) => s.ratio));

const v = (name: string, sub?: string) => <><i>{name}</i>{sub && <sub>{sub}</sub>}</>;

export default function BigMatchesPaper() {
  return (
    <article className="pb-6">
      <PaperHeader paper={meta} authors="Matchup DNA Research" />

      <Abstract keywords={meta.keywords}>
        <p>
          A common story in tennis is that some players fall short when the stakes are highest. We test whether
          big-match performance is a stable player trait, using {count(r.matches)} main-tour ATP and WTA matches from{" "}
          {r.window}, {count(r.big_matches)} of them semi-finals, finals, late Slam rounds, Masters quarter-finals or
          season-ending Finals matches. Each result is compared with a recalibrated surface Elo expectation, and each player
          receives a heavily shrunk big-match score and a clutch score (big-match minus regular-match performance). Three
          tests find no measurable trait. The spread of players&apos; big-match results is {two(minOtherRatio)} to{" "}
          {two(maxOtherRatio)} times the spread luck alone would produce ({two(atpFinals)} for ATP finals). Split-half
          agreement is {signed(sh("ATP").r)} (ATP) and {signed(sh("WTA").r)} (WTA). Scores from {r.periods[0]} do not
          significantly improve forecasts of {r.periods[1]} big matches, and the part of a record that carries over is
          ordinary form, which persists equally in regular matches. We conclude that a big-match adjustment would add noise
          to a forecasting model, not accuracy. The analysis is post-hoc and descriptive.
        </p>
      </Abstract>

      <Contents entries={TOC} />

      <Body>
        <Section id="introduction" number="1" title="Introduction">
          <P>
            When a leading player loses consecutive finals, the explanation that follows is usually psychological: the
            pressure got to them. If that were a stable trait, it would matter to a forecasting model. A player who
            reliably underperforms in big matches should be marked down in semi-finals and finals, and one who reliably
            rises should be marked up.
          </P>
          <P>
            The question is not whether pressure affects tennis at all. Point-level studies have found that points are
            not exactly independent and identically distributed, though the departures are small (
            <Cite id="klaassen">Klaassen and Magnus, 2001</Cite>), and that players differ in how their performance changes
            on the most important points within a match (<Cite id="gonzalez">González-Díaz, Gossner and Rogers, 2012</Cite>).
            Our question is narrower and is the one a match forecast needs answered: given a player&apos;s overall strength,
            do their results in big matches depart from expectation in a way that persists?
          </P>
          <P>
            We answer it with three tests on tour-level results: whether players differ in big matches more than luck
            would allow, whether two halves of the same players&apos; big matches agree, and whether an earlier period
            predicts a later one.
          </P>
        </Section>

        <Section id="data" number="2" title="Data">
          <P>
            We use Jeff Sackmann&apos;s ATP and WTA tour-level match files (<Cite id="sackmann">Sackmann, 2026</Cite>) up to 25
            May 2026. No result from June 2026 onward is used, so the analysis does not touch the matches held out for the
            project&apos;s pre-registered evaluations. Only main-tour events count: Grand Slams, Masters and Premier events,
            regular tour events, the season-ending Finals and the Olympics. Davis Cup, Billie Jean King Cup, other team
            events, exhibitions and bronze-medal matches are excluded. As everywhere in the project, only completed
            best-of-three and best-of-five matches are rated; retirements and walkovers are left out.
          </P>
          <P>
            The window for the first two tests is {r.window}: {count(r.matches)} matches, of which {count(r.big_matches)}{" "}
            are big matches. The third test compares {r.periods[0]} with {r.periods[1]}.
          </P>
        </Section>

        <Section id="method" number="3" title="Method">
          <P>All definitions below were written into the analysis script before it was run.</P>

          <Subsection number="3.1" title="Big matches">
            <P>
              A big match is any semi-final or final; a Grand Slam fourth round or quarter-final; a Masters quarter-final
              (ATP Masters 1000, WTA Premier Mandatory, and WTA Tier I before 2009); or any match at the season-ending
              Finals. Every other main-tour match is a regular match.
            </P>
          </Subsection>

          <Subsection number="3.2" title="Expected results">
            <P>
              Strength is the project&apos;s canonical surface-blended Elo rating (<Cite id="elo">Elo, 1978</Cite>), taken at
              the start of the tournament week and never refitted. Plain Elo is too confident in best-of-three matches and
              too cautious in best-of-five. Left uncorrected, players who are usually favourites at the Slams would look
              clutch for a reason unrelated to pressure. Elo&apos;s log-odds are therefore rescaled with one slope{" "}
              {v("b", "g")} per group {v("g")} = (tour, big or regular, best of three or five), fitted by maximum likelihood
              on the matches of the window being analysed:
            </P>
            <Eq number={1}>{v("P", "ij")} = σ( {v("b", "g")} · logit {v("p", "ij")}<sup>Elo</sup> )</Eq>
            <P>
              The residual of player {v("i")} in match {v("m")} is the result minus that expectation:
            </P>
            <Eq number={2}>{v("e", "im")} = {v("y", "im")} − {v("P", "im")},&nbsp;&nbsp; {v("y", "im")} ∈ {"{0, 1}"}</Eq>
          </Subsection>

          <Subsection number="3.3" title="Player scores">
            <P>
              A player&apos;s big-match score sums their big-match residuals and shrinks the total hard toward zero, so that
              a short run of results cannot dominate (<Cite id="efron">Efron and Morris, 1975</Cite>). With {v("n", "i")}{" "}
              big matches and a shrinkage constant of {r.shrink}, a player with {r.shrink} big matches is weighted half
              toward their own record and half toward no effect:
            </P>
            <Eq number={3}>{v("s", "i")} = Σ<sub><i>m</i>∈big</sub> {v("e", "im")} / ( {v("n", "i")} + {r.shrink} )</Eq>
            <P>
              A player whom Elo underrates everywhere, such as a fast-improving young player, would score well in big
              matches for that reason alone. The clutch score removes it by subtracting the same score computed on regular
              matches:
            </P>
            <Eq number={4}>{v("c", "i")} = {v("s", "i")}<sup>big</sup> − {v("s", "i")}<sup>regular</sup></Eq>
          </Subsection>

          <Subsection number="3.4" title="Three tests">
            <P>
              <span className="text-text">Spread beyond luck.</span> For players with at least {r.min_big} matches of a
              kind, the variance of their mean residuals is split into the part that coin-flip luck would produce and the
              remainder, which estimates the variance of a true trait. The ratio of observed to luck variance is 1 when
              players differ by exactly as much as luck predicts. The same split gives the shrinkage the data support:
              the number of matches needed before half of a player&apos;s record is signal.
            </P>
            <P>
              <span className="text-text">Split-half agreement.</span> Big matches are divided into two halves by
              tournament edition, and the two halves&apos; mean residuals are correlated across players with at least{" "}
              {r.min_big} big matches in each. This asks whether any stable trait exists, ignoring change over a career.
              The Spearman–Brown formula (<Cite id="spearman">Spearman, 1910</Cite>; <Cite id="brown">Brown, 1910</Cite>)
              converts the half-data correlation into a full-data reliability.
            </P>
            <P>
              <span className="text-text">Carry-over between periods.</span> Scores are computed separately for{" "}
              {r.periods[0]} and {r.periods[1]}, each with its own calibration, and correlated across players with at least{" "}
              {r.min_big} big matches in both. A forecast test then asks whether earlier scores improve the calibrated
              forecast of every later big match:
            </P>
            <Eq number={5}>logit {v("P", "m")} = logit {v("P̂", "m")} + β ( {v("s", "A")} − {v("s", "B")} )</Eq>
            <P>
              β is fitted by maximum likelihood, and its p-value comes from 1,000 permutations of the earlier scores among
              players, which respects that one player appears in many matches. All intervals are percentile bootstraps over
              players (2,000 draws).
            </P>
          </Subsection>
        </Section>

        <Section id="results" number="4" title="Results">
          <Subsection number="4.1" title="Favourites as a group">
            <P>
              If big matches unsettled favourites in general, Elo would need a stronger correction in big matches than in
              regular ones. On the ATP tour the corrections are nearly identical in both formats (Table 1). On the WTA tour
              the big-match slope is lower ({two(slope("WTA", "big", 3)!)} against {two(slope("WTA", "regular", 3)!)}): Elo
              overstates favourites&apos; edges a little more in big matches. That is a tour-wide effect on every
              favourite, not a trait of particular players, and the per-group calibration removes it before any player is
              scored. Its significance was not tested.
            </P>
            <Table number={1}
              caption={<>Elo calibration slopes {v("b", "g")}, {r.window}. 1.00 means Elo&apos;s probabilities were already right; below 1, Elo was too confident; above 1, too cautious.</>}
              head={["Tour and matches", "Best of 3", "Best of 5"]}
              rows={TOURS.flatMap((tour) => (["big", "regular"] as const).map((kind) => [
                `${tour}, ${kind}`, two(slope(tour, kind, 3)!), slope(tour, kind, 5) !== undefined ? two(slope(tour, kind, 5)!) : "–",
              ]))} />
          </Subsection>

          <Subsection number="4.2" title="Spread beyond luck">
            <P>
              Players&apos; big-match records differ by almost exactly as much as luck predicts (Figure 1, Table 2). The
              ratio for ATP finals, the biggest matches, is {two(atpFinals)}. No big-match set on either tour exceeds{" "}
              {two(maxOtherRatio)}, and the ratios do not rise as the matches get bigger. Where a small excess appears, the
              shrinkage the data support is above 100 big matches: more than almost any player plays in a career.
            </P>
            <Figure number={1} caption={<>Spread of players&apos; results against expectation, divided by the spread luck alone would produce, {r.window}; players with at least {r.min_big} matches of each kind. The dashed line at 1.00 is pure luck.</>}>
              <DotRows groups={LUCK} domain={[0.8, 1.4]} reference={1} referenceLabel="Pure luck" format={two}
                       tickFormat={(t) => t.toFixed(1)} ticks={[0.8, 1.2, 1.4]} label="Figure 1: spread relative to luck, by tour" />
            </Figure>
            <Table number={2}
              caption={<>Spread of players&apos; mean residuals, in win-probability points per match. Implied {v("k")} is the number of matches before half of a record is signal.</>}
              head={["Tour and matches", "Players", "Observed sd", "Luck sd", "Ratio", "Trait sd", "Implied k"]}
              rows={TOURS.flatMap((tour) => SETS.map(([set, label]) => {
                const s = spread(tour, set);
                return [`${tour}, ${label.replace(" (reference)", "").toLowerCase()}`, count(s.players), pp(s.observed_sd), pp(s.noise_sd),
                        two(s.ratio), pp(s.trait_sd), s.implied_k === null ? "none" : count(Math.round(s.implied_k))];
              }))} />
          </Subsection>

          <Subsection number="4.3" title="Split-half agreement">
            <P>
              The two halves of the same players&apos; big matches barely agree (Table 3). Both correlations are small and
              both intervals include zero. Even with all the data, the implied reliability of a big-match record is below
              0.2.
            </P>
            <Table number={3}
              caption={<>Correlation between the two halves of each player&apos;s big matches, split by tournament edition, {r.window}.</>}
              head={["Tour", "Players", "r (95% interval)", "Full-data reliability"]}
              rows={TOURS.map((tour) => [tour, count(sh(tour).players), interval(sh(tour)), signed(sh(tour).spearman_brown)])} />
          </Subsection>

          <Subsection number="4.4" title="Carry-over between periods">
            <P>
              Big-match scores from {r.periods[0]} carry into {r.periods[1]} only weakly, and no more than regular-match
              scores do (Figure 2, Table 4). On the WTA tour the regular-match score carries over more strongly (
              {signed(ps("WTA").correlations["regular-match"].r)}) than the big-match score (
              {signed(ps("WTA").correlations["big-match"].r)}). What persists is general form that Elo is slow to catch,
              not something specific to pressure. Once that is removed, the clutch score barely persists on either tour.
            </P>
            <Figure number={2} caption={<>Correlation between each player&apos;s score in {r.periods[0]} and in {r.periods[1]}, with 95% intervals; {ps("ATP").players} ATP and {ps("WTA").players} WTA players with at least {r.min_big} big matches in both periods. The dashed line at 0 is no carry-over.</>}>
              <DotRows groups={CARRY} domain={[-0.4, 0.7]} reference={0} referenceLabel="No carry-over" format={(x) => signed(x)}
                       tickFormat={(t) => signed(t, 1)} ticks={[-0.4, 0.4, 0.7]} label="Figure 2: carry-over between periods, by tour" />
            </Figure>
            <Table number={4}
              caption={<>Correlation of player scores between periods, with 95% intervals.</>}
              head={["Tour", "Players", "Big-match", "Clutch", "Regular-match"]}
              rows={TOURS.map((tour) => [tour, ps(tour).players, interval(ps(tour).correlations["big-match"]),
                                         interval(ps(tour).correlations.clutch), interval(ps(tour).correlations["regular-match"])])} />
            <P>
              The forecast test (equation 5) agrees (Table 5). Neither score significantly improves the forecast of later
              big matches on either tour; the largest change in log loss is a thousandth of a unit per match.
            </P>
            <Table number={5}
              caption={<>Forecast test: do {r.periods[0]} scores improve the calibrated forecast of {r.periods[1]} big matches? β with its standard error; p from 1,000 permutations.</>}
              head={["Tour and score", "Matches", "With earlier score", "β (se)", "Log loss change", "p"]}
              rows={TOURS.flatMap((tour) => (["big-match", "clutch"] as const).map((key) => {
                const f = ps(tour).forecasts[key];
                return [`${tour}, ${key}`, count(f.matches), count(f.with_history), `${signed(f.beta, 2)} (${two(f.se)})`,
                        signed(f.log_loss_change, 5), three(f.permutation_p)];
              }))} />
          </Subsection>
        </Section>

        <Section id="runs" number="5" title="Why losing runs look like a pattern">
          <P>
            If the trait is not there, why does the story persist? Part of the answer is the arithmetic of runs. Take a
            player who wins {pct(r.streak.p_win)} of their finals, a strong record, and treat each of {r.streak.finals}{" "}
            finals as independent. The exact probability of losing at least two in a row somewhere in those finals is{" "}
            {pct(r.streak.two)}; of losing at least three in a row, {pct(r.streak.three)}. A three-final losing run is the
            likely outcome of a good career, not evidence against it.
          </P>
          <P>
            People are quick to read meaning into such runs (<Cite id="gilovich">Gilovich, Vallone and Tversky, 1985</Cite>),
            although later work showed that the original hot-hand analysis was itself biased (
            <Cite id="miller">Miller and Sanjurjo, 2018</Cite>), so we rely only on the exact probabilities above. Selection
            does the rest: with hundreds of players on tour, someone is always in the middle of a losing run, and those are
            the players written about. Players who beat expectations in finals rarely get the opposite article.
          </P>
        </Section>

        <Section id="discussion" number="6" title="Discussion">
          <P>
            For forecasting, the implication is direct: no big-match adjustment is added to the model. An effect this small
            cannot be told apart from luck in tour-level data, and a model that chased it would move probabilities on the
            strength of runs that say nothing about the next match.
          </P>
          <P>
            The result does not contradict point-level findings. A player may raise or lower their level on important
            points, as <Cite id="gonzalez">González-Díaz et al. (2012)</Cite> report, and still win big matches at the rate
            their overall strength predicts, because that skill is part of what their rating already measures. What the data
            rule out is a large, persistent gap between a player&apos;s big-match results and their strength.
          </P>
        </Section>

        <Section id="limitations" number="7" title="Limitations">
          <ul className="grid max-w-[68ch] list-disc gap-2.5 pl-5">
            <li><span className="text-text">Post-hoc.</span> The definitions were fixed before the run, but the question arose after recent results had been seen. The analysis was not used to choose or change any model.</li>
            <li><span className="text-text">Small samples in the period split.</span> Only {ps("ATP").players} ATP and {ps("WTA").players} WTA players had enough big matches in both periods. The test cannot rule out a small effect; it shows that any effect is too small to measure or forecast with in this data.</li>
            <li><span className="text-text">Start-of-week ratings.</span> Results from earlier rounds of the same tournament are not used. Both players in a late round have usually won several matches that week, so this affects both sides alike.</li>
            <li><span className="text-text">Pressure is not observed.</span> The analysis measures results against expectation, not how players feel, and cannot show that pressure affects no one.</li>
            <li><span className="text-text">The WTA calibration difference</span> (section 4.1) was described but not tested for significance.</li>
          </ul>
        </Section>

        <Section id="conclusion" number="8" title="Conclusion">
          <P>
            Across 26 years of tour-level tennis, players&apos; big-match records differ by about as much as luck would make
            them differ, and an earlier record does not predict a later one beyond ordinary form. A choke or clutch trait, if
            it exists, is too small to measure in match results. The Matchup DNA forecasts therefore treat a final like any
            other match between the same two players.
          </P>
        </Section>

        <Section id="availability" number="" title="Data and code">
          <P>
            Match data: Jeff Sackmann&apos;s tennis_atp and tennis_wta repositories (CC BY-NC-SA 4.0). The analysis is
            reproduced by <span className="mono text-text">python -m matchup_dna.posthoc_big_match</span>; every figure on
            this page is read from its output and checked against the full written report before publication. How the live
            forecasts are made and scored is described on the <Link href="/methodology" className="link">Methodology</Link>{" "}
            page and in the <Link href="/lab" className="link">Model Lab</Link>.
          </P>
        </Section>

        <Section id="references" number="" title="References">
          <References items={[
            { id: "brown", text: <>Brown, W. (1910). Some experimental results in the correlation of mental abilities. <i>British Journal of Psychology</i>, 3(3), 296–322.</> },
            { id: "efron", text: <>Efron, B., and Morris, C. (1975). Data analysis using Stein&apos;s estimator and its generalizations. <i>Journal of the American Statistical Association</i>, 70(350), 311–319.</> },
            { id: "elo", text: <>Elo, A. E. (1978). <i>The Rating of Chessplayers, Past and Present</i>. New York: Arco.</> },
            { id: "gilovich", text: <>Gilovich, T., Vallone, R., and Tversky, A. (1985). The hot hand in basketball: On the misperception of random sequences. <i>Cognitive Psychology</i>, 17(3), 295–314.</> },
            { id: "gonzalez", text: <>González-Díaz, J., Gossner, O., and Rogers, B. W. (2012). Performing best when it matters most: Evidence from professional tennis. <i>Journal of Economic Behavior &amp; Organization</i>, 84(3), 767–781.</> },
            { id: "klaassen", text: <>Klaassen, F. J. G. M., and Magnus, J. R. (2001). Are points in tennis independent and identically distributed? Evidence from a dynamic binary panel data model. <i>Journal of the American Statistical Association</i>, 96(454), 500–509.</> },
            { id: "miller", text: <>Miller, J. B., and Sanjurjo, A. (2018). Surprised by the hot hand fallacy? A truth in the law of small numbers. <i>Econometrica</i>, 86(6), 2019–2047.</> },
            { id: "sackmann", text: <>Sackmann, J. (2026). tennis_atp and tennis_wta: ATP and WTA tennis rankings, results and stats. GitHub repositories, data to 25 May 2026.</> },
            { id: "spearman", text: <>Spearman, C. (1910). Correlation calculated from faulty data. <i>British Journal of Psychology</i>, 3(3), 271–295.</> },
          ]} />
        </Section>
      </Body>
    </article>
  );
}
