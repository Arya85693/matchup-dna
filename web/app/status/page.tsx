import type { Metadata } from "next";
import { getManifest, getStatus } from "@/lib/snapshot";
import { LocalTime } from "@/components/LocalTime";
import { Badge, Card, EmptyState, Metric, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Data status" };

const JOBS = [["forecast", "Forecast run"], ["settle", "Results run"], ["espn_download", "Fixture download"]] as const;

export default async function StatusPage() {
  const [status, manifest] = await Promise.all([getStatus(), getManifest()]);
  if (!status.ok) {
    return <><PageHeader title="Data status" /><div className="card"><EmptyState title="Status unavailable">{status.detail}</EmptyState></div></>;
  }
  const s = status.data;
  return (
    <>
      <PageHeader title="Data status" description={`The forecasting job runs twice a day. Data counts as late after ${s.stale_after_hours} hours without a run.`}
                  actions={s.ok ? <Badge tone="pos">All systems normal</Badge> : <Badge tone="warn">Attention needed</Badge>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Forecasts stored" value={s.counts.forecasts} />
        <Metric label="Matches tracked" value={s.counts.matches} />
        <Metric label="Results recorded" value={s.counts.settled} />
        <Metric label="Integrity check" value={s.integrity.ok ? "Passed" : `${s.integrity.problems} issues`} tone={s.integrity.ok ? "pos" : "neg"} />
      </div>
      <Card title="Jobs" className="mt-6" padded={false}>
        <ul className="divide-y divide-border">
          {JOBS.map(([key, label]) => {
            const f = s.freshness[key];
            const late = f.hours_ago === null || f.hours_ago > s.stale_after_hours;
            return (
              <li key={key} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                <span className="flex items-center gap-2.5"><span className={`size-1.5 rounded-full ${late ? "bg-warn" : "bg-pos"}`} aria-hidden="true" />{label}</span>
                <span className="num text-[13px] text-muted">{f.last ? <>Last succeeded <LocalTime iso={f.last} style="datetime" /></> : "Never"}</span>
              </li>
            );
          })}
        </ul>
      </Card>
      {manifest.ok && <p className="mt-4 text-[12px] text-dim">Snapshot <span className="mono">{manifest.data.snapshot}</span> · ledger head <span className="mono">{manifest.data.ledger.head?.slice(0, 16)}</span></p>}
    </>
  );
}
