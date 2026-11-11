import type { Metadata } from "next";
import Link from "next/link";
import { Card, PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Methodology" };

const STEPS = [
  { title: "History", text: "About 360,000 tour-level matches. Every input is built in date order from earlier matches only." },
  { title: "Ratings", text: "Elo (start 1500, K 32) and surface Elo (K 48, blended half and half with overall)." },
  { title: "Inputs", text: "Ranking, days since last match, form against Elo, and opponent-adjusted serve and return." },
  { title: "Model", text: "A logistic regression per tour, fitted 2010 to May 2026 and frozen. Inputs add up to the log-odds." },
  { title: "Record", text: "Issued at least 30 minutes before play, stored unchangeably, hash-chained and scored afterwards." },
];

export default function Methodology() {
  return (
    <>
      <PageHeader title="Methodology" description="How a forecast is made, recorded and judged, and where the method falls short." />

      <ol className="grid gap-3 md:grid-cols-5">
        {STEPS.map((s, i) => (
          <li key={s.title} className="card p-4">
            <p className="num text-[12px] text-accent">{i + 1}</p>
            <p className="mt-2 font-medium">{s.title}</p>
            <p className="mt-1.5 text-[13px] text-muted">{s.text}</p>
          </li>
        ))}
      </ol>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Three models">
          <div className="grid gap-3 text-muted">
            <p><span className="text-text">Tournament start</span> (ATP and WTA) uses information from before the tournament began.</p>
            <p><span className="text-text">Round-aware</span> (ATP and WTA) adds this tournament&apos;s completed earlier rounds. It applies to knockout matches after the first round. When it cannot apply, the site shows why and never borrows the other model&apos;s number.</p>
            <p><span className="text-text">ITF M1</span> (ITF Men and ITF Women) is a separate model for the ITF World Tennis Tour, with its own ratings and its own live record. <Link href="/itf" className="link">ITF</Link></p>
          </div>
        </Card>
        <Card title="How forecasts are judged">
          <div className="grid gap-3 text-muted">
            <p><span className="text-text">Log loss</span> rewards honest probabilities; <span className="text-text">calibration</span> checks that 70% forecasts win about 70% of the time.</p>
            <p>Historical tests were fixed before their results were seen. The live record began on 9 November 2026 and is judged once, after 30 June 2027. <Link href="/lab" className="link">Model Lab</Link></p>
          </div>
        </Card>
        <Card title="What works, and what does not">
          <div className="grid gap-3 text-muted">
            <p>Ranking, inactivity and form improve on Elo alone, and the round-aware update helps later rounds. Official rankings were the benchmark the earlier models had to beat; in post-hoc checks, the model&apos;s probabilities did, though its edge in picking winners narrowed over time.</p>
            <p>Serve-and-return gains were not confirmed, matchup and fatigue features added nothing, and the betting market forecasts better.</p>
          </div>
        </Card>
        <Card title="Limits">
          <ul className="grid list-disc gap-1.5 pl-4 text-muted">
            <li>Live data has no serve statistics; those estimates refresh with new data files.</li>
            <li>A player without a ranking on record is treated as unranked.</li>
            <li>Unconfirmed identities are not forecast until checked.</li>
            <li>ITF forecasts use no serve statistics, and ITF matches are never compared with betting odds.</li>
            <li>Every result is an association, not a cause. Nothing here is betting advice.</li>
          </ul>
        </Card>
      </div>

      <Card title="The ITF model" className="mt-6">
        <div className="grid gap-3 text-muted lg:grid-cols-2 lg:gap-8">
          <div className="grid gap-3">
            <p>
              <span className="text-text">Why a separate model.</span> Almost no ITF player has main-tour history: the main-tour
              model sees most of them as unrated, and on ITF matches it does worse than ranking alone. The ITF model rates
              every player across every level they have played, from ITF events to the Grand Slams, with ratings that
              move faster while a player is new.
            </p>
            <p>
              <span className="text-text">Inputs.</span> Elo and surface Elo over all levels, ATP or WTA rank, days since the last
              match, recent form, and the event&apos;s tier (M15–M25, W15–W100), fitted per tour on ITF main-draw matches from
              2021 to June 2026.
            </p>
          </div>
          <div className="grid gap-3">
            <p>
              <span className="text-text">How it was tested.</span> The data was split before any model work; the first half of
              2026 stayed sealed until every choice was frozen, then was scored once. M1 beat Elo alone, ranking alone and the
              main-tour model on those matches. <Link href="/lab" className="link">Model Lab</Link>
            </p>
            <p>
              <span className="text-text">Why M1, not the serve model.</span> A version with serve and return statistics (M2) tested
              slightly better, but no serve statistics are published for ITF matches after June 2026, so it could not be kept
              current. M1 needs only results and rankings. Its live record (protocol P2) is kept apart from the main-tour
              record and judged the same way.
            </p>
          </div>
        </div>
      </Card>

      <Card title="Data sources" className="mt-6">
        <p className="text-muted">
          Jeff Sackmann&apos;s ATP and WTA data (CC BY-NC-SA 4.0), TennisIsMyLife and TennisData.app files, ESPN fixtures and
          results, Flashscore ITF, Challenger and tour fixtures and results, TennisExplorer weekly ATP and WTA rankings,
          and Valuebetennis prices for research only (CC BY 4.0). Because of the non-commercial licence, this site is
          non-commercial.
        </p>
      </Card>
    </>
  );
}
