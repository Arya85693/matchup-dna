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
        <Card title="Two models">
          <div className="grid gap-3 text-muted">
            <p><span className="text-text">Tournament start</span> uses information from before the tournament began.</p>
            <p><span className="text-text">Round-aware</span> adds this tournament&apos;s completed earlier rounds. It applies to knockout matches after the first round. When it cannot apply, the site shows why and never borrows the other model&apos;s number.</p>
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
            <p>Ranking, inactivity and form improve on Elo alone, and the round-aware update helps later rounds.</p>
            <p>Serve-and-return gains were not confirmed, matchup and fatigue features added nothing, and the betting market forecasts better.</p>
          </div>
        </Card>
        <Card title="Limits">
          <ul className="grid list-disc gap-1.5 pl-4 text-muted">
            <li>Live data has no serve statistics; those estimates refresh with new data files.</li>
            <li>A player without a ranking on record is treated as unranked.</li>
            <li>Unconfirmed identities are not forecast until checked.</li>
            <li>Every result is an association, not a cause. Nothing here is betting advice.</li>
          </ul>
        </Card>
      </div>

      <Card title="Data sources" className="mt-6">
        <p className="text-muted">
          Jeff Sackmann&apos;s ATP and WTA data (CC BY-NC-SA 4.0), TennisIsMyLife and TennisData.app files, ESPN fixtures and
          results, and Valuebetennis prices for research only (CC BY 4.0). Because of the non-commercial licence, this site is
          non-commercial.
        </p>
      </Card>
    </>
  );
}
