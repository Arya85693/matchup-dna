import type { Metadata } from "next";
import { getIndex, getItfMatches } from "@/lib/snapshot";
import { CircuitTabs } from "@/components/CircuitTabs";
import { MatchList } from "@/components/MatchList";
import { EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 60;          // results arrive between scheduled publishes; show them within a minute
export const metadata: Metadata = { title: "Matches" };

export default async function MatchesPage() {
  const [index, itf] = await Promise.all([getIndex(), getItfMatches()]);
  return (
    <>
      <PageHeader title="Matches" description="Main tour (ATP and WTA): tournament-start forecasts, with the round-aware update on each match page. ITF (ITF Men and ITF Women): the ITF model's forecasts." />
      <CircuitTabs
        main={index.ok ? <MatchList matches={index.data.matches} /> : <div className="card"><EmptyState title="Match data could not be loaded">{index.detail}</EmptyState></div>}
        itf={itf.ok ? <MatchList matches={itf.data.matches} circuit="itf" />
          : <div className="card"><EmptyState title="ITF forecasts are not published yet">{itf.detail}</EmptyState></div>}
      />
    </>
  );
}
