import type { Metadata } from "next";
import researchJson from "@/content/research/itf.json";
import { getItf } from "@/lib/snapshot";
import { ItfSchema, type Itf } from "@/lib/contract";
import { ItfRecent, ItfUpcoming } from "@/components/ItfLists";
import { Badge, Card, EmptyState, Metric, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "ITF" };

type Research = Itf["research"];
const STATIC_RESEARCH: Research = ItfSchema.shape.research.parse(researchJson);
const ORDER = ["M1", "M2", "B1", "B0", "B2"] as const;

function fixed(x: number | null | undefined, digits = 4) {
  return x === null || x === undefined ? "–" : x.toFixed(digits);
}

function HeldOut({ research }: { research: Research }) {
  const pooled = research.held_out.pooled;
  const c = research.held_out.comparisons;
  const gain = (key: string) => {
    const x = c[key];
    return x ? `${fixed(-x.mean)} (95% interval ${fixed(-x.ci95[1])} to ${fixed(-x.ci95[0])})` : "–";
  };
  return (
    <div className="grid gap-6">
      <table className="w-full text-left text-[13px]">
        <thead className="text-dim">
          <tr><th className="py-2 font-normal">Model</th><th className="py-2 text-right font-normal">Log loss</th><th className="py-2 text-right font-normal">Accuracy</th></tr>
        </thead>
        <tbody className="divide-y divide-border">
          {ORDER.map((k) => {
            const m = pooled[k];
            if (!m) return null;
            const live = k === research.live_model;
            return (
              <tr key={k} className={live ? "font-medium" : "text-muted"}>
                <td className="py-2.5">{research.names[k] ?? k}{live && <span className="ml-2"><Badge tone="accent">Live</Badge></span>}</td>
                <td className="num py-2.5 text-right">{fixed(m.log_loss)}</td>
                <td className="num py-2.5 text-right">{(m.accuracy * 100).toFixed(1)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="max-w-[70ch] text-[13px] text-muted">
        Scored once on {(pooled.M1?.matches ?? 0).toLocaleString()} matches from {research.held_out.period}, after every choice was
        frozen. M1 beats Elo alone by {gain("M1 - B1")} and ranking alone by {gain("M1 - B0")}. The serve model M2 was better
        again by {gain("M2 - M1")}, but serve statistics are not published for ITF matches after June 2026, so M2 cannot be kept
        current: M1 forecasts live.
      </p>
    </div>
  );
}

export default async function ItfPage() {
  const itf = await getItf();
  const research: Research = itf.ok ? itf.data.research : STATIC_RESEARCH;
  const record = itf.ok ? itf.data.record : null;
  return (
    <>
      <PageHeader title="ITF World Tennis Tour"
                  description="Forecasts for ITF men's and women's main-draw matches (M15–M25, W15–W100), from a model built and tested for this level. Model estimates only, never compared with betting odds." />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Matches forecast" value={record ? record.forecast_matches.toLocaleString() : "–"} />
        <Metric label="Results settled" value={record ? record.settled.toLocaleString() : "–"} />
        <Metric label="M1 log loss (live)" value={fixed(record?.m1.log_loss)} note={record ? `${record.m1.matches} scored` : undefined} />
        <Metric label="Elo-only log loss (live)" value={fixed(record?.elo.log_loss)} note="same matches" />
      </div>
      {!itf.ok && (
        <div className="card mt-6"><EmptyState title="Live ITF forecasts are not published yet">{itf.detail} The tested results below are final.</EmptyState></div>
      )}
      {itf.ok && (
        <>
          <Card title="Upcoming" className="mt-6" padded={false}><ItfUpcoming rows={itf.data.upcoming} /></Card>
          <Card title="Recent results" className="mt-6" padded={false}><ItfRecent rows={itf.data.recent} /></Card>
        </>
      )}
      <Card title="How the model was tested" className="mt-6"><HeldOut research={research} /></Card>
    </>
  );
}
