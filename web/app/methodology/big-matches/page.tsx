import type { Metadata } from "next";
import Link from "next/link";
import { EvidenceTag, FigureStrip } from "@/components/lab/parts";
import { DotRows, NumbersTable, type Group } from "@/components/research/DotRows";
import { BIG_MATCH } from "@/lib/research";

export const metadata: Metadata = {
  title: "Myth check: do players choke in big matches?",
  description: "26 years of tour-level tennis, checked for players who consistently fall short or rise in semi-finals and finals.",
};

const r = BIG_MATCH;
const signed = (v: number, d = 3) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}`;
const two = (v: number) => v.toFixed(2);
const pctRound = (v: number) => `${Math.round(v * 100)}%`;
const count = (v: number) => v.toLocaleString("en-GB");
const slope = (tour: string, kind: "big" | "regular", bo: number) =>
  r.calibration.find((c) => c.tour === tour && c.kind === kind && c.best_of === bo)!.slope;
const spread = (tour: string, set: string) => r.spread.find((s) => s.tour === tour && s.set === set)!;
const TOURS = ["ATP", "WTA"] as const;

const SETS: [string, string, string?][] = [
  ["finals only", "Finals"],
  ["semi-finals + finals", "Semi-finals and finals"],
  ["all big matches", "All big matches"],
  ["regular matches", "Regular matches", "for reference"],
];
const LUCK: Group[] = SETS.map(([set, label, note]) => ({
  label, note, lanes: TOURS.map((tour) => ({ tour, value: spread(tour, set).ratio })),
}));

const MEASURES: ["big-match" | "clutch" | "regular-match", string, string?][] = [
  ["big-match", "Big-match score"],
  ["clutch", "Clutch score", "big matches minus regular ones"],
  ["regular-match", "Regular-match score", "for reference"],
];
const CARRY: Group[] = MEASURES.map(([key, label, note]) => ({
  label, note,
  lanes: TOURS.map((tour) => {
    const c = r.period_split[tour]!.correlations[key];
    return { tour, value: c.r, low: c.low, high: c.high };
  }),
}));

const atpFinals = spread("ATP", "finals only").ratio;
const ps = (tour: string) => r.period_split[tour]!;
const sh = (tour: string) => r.split_half[tour]!;

export default function BigMatches() {
  return (
    <article className="pb-6">
      <nav aria-label="Breadcrumb" className="text-[12px] text-muted">
        <Link href="/methodology" className="hover:text-text">Methodology</Link>
        <span className="px-2 text-dim" aria-hidden="true">/</span>
        <span className="text-text">Myth check</span>
      </nav>

      <header className="anim-rise mt-10 max-w-[760px]">
        <p className="flex items-center gap-2.5 text-[13px] text-muted">Myth check <EvidenceTag kind="post-hoc" /></p>
        <h1 className="mt-4 text-[34px] font-semibold leading-[1.08] tracking-[-0.025em] sm:text-[48px]">
          Do players choke in big matches?
        </h1>
        <p className="mt-6 max-w-[58ch] text-[17px] leading-relaxed text-muted sm:text-[19px]">
          A star loses a second final in a row and the verdict arrives within the hour: the nerves went. We checked 26 years
          of tour-level tennis for players who keep falling short, or keep rising, when the stakes are highest. The pattern
          is not there.
        </p>
        <p className="mt-6 text-[12px] text-dim">
          Matchup DNA research, 14 November 2026. {count(r.matches)} main-tour matches from {r.window}, {count(r.big_matches)} of them big.
        </p>
      </header>

      <div className="mt-14 grid max-w-[680px] gap-16 text-[15px] leading-[1.75] text-muted">
        <section className="grid gap-5">
          <p className="text-text">
            Every season produces the same story. A player who sails through the early rounds reaches a final, loses it,
            then loses the next one too. By the third, it is a storyline: they cannot handle the big moment.
          </p>
          <p>
            It is a fair hunch, and it would matter to a forecasting model. If some players reliably fall short when it
            counts, the model should mark them down in semi-finals and finals. So before adding a big-match factor, we
            tested whether the trait exists at all.
          </p>
        </section>

        <Section title="How we measured it">
          <p>
            A raw finals record misleads on its own. Finals are played against the strongest opponents, so everyone loses
            more of them. The fair question is whether a player wins big matches less often than their strength predicts.
          </p>
          <dl className="grid gap-4 border-l border-border pl-5 text-[14px]">
            <Def term="Big match">Any semi-final or final, a Grand Slam fourth round or quarter-final, a Masters quarter-final, and every match at the season-ending Finals.</Def>
            <Def term="Expected result">The surface-adjusted Elo rating the models use, taken at the start of the tournament and recalibrated so best-of-five Slams and best-of-three events are each judged fairly.</Def>
            <Def term="A player's score">Big-match wins minus expected wins, pulled hard toward zero so a short streak cannot dominate: {r.shrink} big matches count as half evidence, half &ldquo;no effect&rdquo;.</Def>
            <Def term="Clutch score">The same score in big matches minus the score in regular matches, so a player who is simply better than their rating everywhere is not counted as clutch.</Def>
          </dl>
        </Section>

        <Section title="Favourites as a group mostly hold their nerve">
          <p>
            If big matches got to favourites in general, the rating would overrate them on the big stage and need a
            stronger correction there. On the ATP tour it needs almost exactly the same correction whether the match is a
            first round or a final.
          </p>
          <FigureStrip items={[
            { label: "ATP, best of 3", value: `${two(slope("ATP", "big", 3))}/${two(slope("ATP", "regular", 3))}`, note: "Big / regular" },
            { label: "ATP, best of 5", value: `${two(slope("ATP", "big", 5))}/${two(slope("ATP", "regular", 5))}`, note: "Big / regular" },
            { label: "WTA, best of 3", value: `${two(slope("WTA", "big", 3))}/${two(slope("WTA", "regular", 3))}`, note: "Big / regular" },
          ]} />
          <p className="text-[13px] text-dim">
            Calibration slope: 1.00 means the rating was already right; below 1, it was too confident.
          </p>
          <p>
            The WTA tour shows a small difference: the rating is a little more over-confident in big matches, so favourites&apos;
            edges there are slightly smaller. That applies to every favourite alike, not to particular players, and it is
            corrected before anyone is compared.
          </p>
        </Section>

        <Section title="The differences between players look like luck">
          <p>
            Favourites as a group can be fine while some individuals still choke and others rise. If so, players&apos;
            big-match records should spread out more than chance alone would make them. Flip enough coins for enough players
            and some will look cursed. The question is whether real players spread out further than that.
          </p>
        </Section>
      </div>

      <div className="mt-8 grid max-w-[760px] gap-5">
        <DotRows groups={LUCK} domain={[0.8, 1.4]} reference={1} referenceLabel="Pure luck" format={two} tickFormat={(v) => v.toFixed(1)} ticks={[0.8, 1.2, 1.4]}
                 label="Spread of players' big-match results relative to luck, by tour" />
        <p className="text-[12px] text-dim">
          Spread of players&apos; results against expectation, divided by the spread luck alone would produce
          ({r.window}, players with at least {r.min_big} matches of each kind). 1.00 means the differences between players
          are exactly what luck produces.
        </p>
        <NumbersTable summary="Show the numbers" head={["Matches", "Tour", "Players", "Spread ÷ luck", "Matches for half signal"]}
          rows={SETS.flatMap(([set, label]) => TOURS.map((tour) => {
            const s = spread(tour, set);
            return [label, tour, count(s.players), two(s.ratio), s.implied_k === null ? "never" : count(Math.round(s.implied_k))];
          }))} />
      </div>

      <div className="mt-12 grid max-w-[680px] gap-16 text-[15px] leading-[1.75] text-muted">
        <section className="grid gap-5">
          <Pull figure={two(atpFinals)}>
            ATP finals: the differences between players are what you would get from luck alone.
          </Pull>
          <p>
            No set of big matches on either tour strays far from 1. Where a sliver of excess shows up, a player would need
            more than 100 big matches before half of their record reflected anything real. Almost nobody plays that many.
          </p>
        </section>

        <Section title="A record of choking does not carry forward">
          <p>
            The sharpest test is whether a record carries forward. We scored every player on {r.periods[0]} and asked
            whether that predicted {r.periods[1]}.
          </p>
        </Section>
      </div>

      <div className="mt-8 grid max-w-[760px] gap-5">
        <DotRows groups={CARRY} domain={[-0.4, 0.7]} reference={0} referenceLabel="No carry-over" format={(v) => signed(v)} tickFormat={(v) => signed(v, 1)}
                 ticks={[-0.4, 0.4, 0.7]} label="Correlation between 2012-2018 and 2019-2026 scores, with 95% intervals" />
        <p className="text-[12px] text-dim">
          Correlation between each player&apos;s score in {r.periods[0]} and in {r.periods[1]}, with 95% intervals.{" "}
          {ps("ATP").players} ATP and {ps("WTA").players} WTA players had at least {r.min_big} big matches in both periods.
        </p>
        <NumbersTable summary="Show the numbers" head={["Score", "Tour", "Players", "Correlation", "95% interval"]}
          rows={MEASURES.flatMap(([key, label]) => TOURS.map((tour) => {
            const c = ps(tour).correlations[key];
            return [label, tour, ps(tour).players, signed(c.r), `${signed(c.low)} to ${signed(c.high)}`];
          }))} />
      </div>

      <div className="mt-12 grid max-w-[680px] gap-16 text-[15px] leading-[1.75] text-muted">
        <section className="grid gap-5">
          <p>
            Big-match scores carried over a little, but no more than ordinary results did. A player the rating underrated in
            regular matches tended to stay underrated, pressure or no pressure. Take that out and the clutch score barely
            carries over at all: {signed(ps("ATP").correlations.clutch.r)} on the ATP tour and {signed(ps("WTA").correlations.clutch.r)} on
            the WTA tour, with both intervals spanning zero.
          </p>
          <p>
            Two other checks agree. Splitting each player&apos;s big matches into two halves by tournament gives
            correlations of {signed(sh("ATP").r)} and {signed(sh("WTA").r)}. And added to the forecasts as an input, the
            earlier scores did not significantly improve predictions of later big matches (permutation p ={" "}
            {ps("ATP").forecasts["big-match"].permutation_p.toFixed(3)} ATP and {ps("WTA").forecasts["big-match"].permutation_p.toFixed(3)} WTA
            for the big-match score; {ps("ATP").forecasts.clutch.permutation_p.toFixed(3)} and{" "}
            {ps("WTA").forecasts.clutch.permutation_p.toFixed(3)} for the clutch score).
          </p>
        </section>

        <Section title="So why does the story feel true?">
          <p>
            Because losing runs are normal. Take a player who wins {pctRound(r.streak.p_win)} of their finals, a strong record,
            and give them {r.streak.finals} finals.
          </p>
          <FigureStrip items={[
            { label: "Lose two finals in a row", value: pctRound(r.streak.two), note: `At some point in ${r.streak.finals} finals` },
            { label: "Lose three in a row", value: pctRound(r.streak.three), note: `At some point in ${r.streak.finals} finals` },
          ]} />
          <p>
            A three-final losing run is not a sign that something has broken. For a player who wins six finals in ten, it is
            the likely outcome over a career. And with hundreds of players on tour, someone is always in the middle of one.
            Those are the players who get written about. Players who beat expectations in finals rarely get the opposite
            article.
          </p>
          <blockquote className="border-l-2 border-accent pl-5 text-[19px] leading-snug text-text">
            Streaks are what a good career looks like up close, not evidence against it.
          </blockquote>
        </Section>

        <Section title="What it means for the forecasts">
          <p>
            No big-match adjustment goes into the model. An effect this small cannot be told apart from luck in the data
            available, and a model that chased it would be adding noise: moving probabilities on the strength of streaks
            that say nothing about the next match.
          </p>
          <p>
            This does not prove pressure never matters to anyone. It shows that in tour-level results, any such effect is
            too small to measure. A forecast can only use what can be measured.
          </p>
        </Section>

        <Section title="The fine print">
          <ul className="grid list-disc gap-2 pl-5 text-[14px]">
            <li>This is a post-hoc, descriptive analysis. The definitions were fixed before it ran, but the question came after recent results had been seen. It was not used to choose or change a model.</li>
            <li>Only {ps("ATP").players} ATP and {ps("WTA").players} WTA players had enough big matches in both periods. The test cannot rule out a small effect.</li>
            <li>Ratings are from the start of each tournament; earlier rounds of the same event are not used.</li>
            <li>It measures results against expectation, not how players feel.</li>
            <li>Data: Jeff Sackmann&apos;s ATP and WTA tour-level files to 25 May 2026.</li>
          </ul>
          <p className="text-[14px]">
            <Link href="/methodology" className="link">How the forecasts are made</Link>
            <span className="px-3 text-dim" aria-hidden="true">/</span>
            <Link href="/lab#benchmarks" className="link">Every model comparison in the Model Lab</Link>
          </p>
        </Section>
      </div>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-5">
      <h2 className="text-[22px] font-semibold leading-tight text-text sm:text-[24px]">{title}</h2>
      {children}
    </section>
  );
}

function Def({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="font-medium text-text">{term}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

/** A pull figure: one number set large, with the sentence it stands for. */
function Pull({ figure, children }: { figure: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-3 border-y border-border py-8 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center sm:gap-8">
      <p className="fig text-[56px] font-medium leading-none text-accent sm:text-[72px]">{figure}</p>
      <p className="max-w-[36ch] text-[17px] leading-snug text-text">{children}</p>
    </div>
  );
}
