import type { Metadata } from "next";
import { getIndex } from "@/lib/snapshot";
import { MatchList } from "@/components/MatchList";
import { EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Matches" };

export default async function MatchesPage() {
  const index = await getIndex();
  return (
    <>
      <PageHeader title="Matches" description="Tournament-start forecasts for every eligible match. Open a match for the round-aware update and the reasoning." />
      {index.ok ? <MatchList matches={index.data.matches} /> : <div className="card"><EmptyState title="Match data could not be loaded">{index.detail}</EmptyState></div>}
    </>
  );
}
