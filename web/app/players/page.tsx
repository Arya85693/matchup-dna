import type { Metadata } from "next";
import { getHistoryIndex } from "@/lib/snapshot";
import { PlayersBrowser } from "@/components/PlayersBrowser";
import { EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Players" };

export default async function PlayersPage() {
  const index = await getHistoryIndex();
  return (
    <>
      <PageHeader title="Players" description="Every ATP and WTA player with a tour-level match in the last year, rated by Elo and updated as results come in." />
      {index.ok ? <PlayersBrowser players={index.data.players} />
        : <div className="card"><EmptyState title="Player ratings are not available yet">{index.detail}</EmptyState></div>}
    </>
  );
}
