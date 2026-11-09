import type { Metadata } from "next";
import Link from "next/link";
import { getHistoryIndex, getHistoryPlayer } from "@/lib/snapshot";
import { CompareView } from "@/components/compare/CompareView";
import { EmptyState, PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Compare players" };

type Props = { searchParams: Promise<{ a?: string; b?: string; tour?: string }> };

export default async function Compare({ searchParams }: Props) {
  const { a, b, tour: wanted } = await searchParams;
  // One tour at a time (ATP and WTA ids and ratings are separate pools); both players are loaded from that tour.
  const tour = wanted === "WTA" ? "WTA" : "ATP";
  const slug = (id: string | undefined) => (id ? getHistoryPlayer(`${tour.toLowerCase()}-${id}`) : Promise.resolve(null));
  const [index, pa, pb] = await Promise.all([getHistoryIndex(), slug(a), slug(b)]);
  const header = (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-2 text-[13px] text-muted">
        <Link href="/players" className="hover:text-text">Players</Link><span className="text-dim">/</span><span className="text-text">Compare</span>
      </nav>
      <PageHeader title="Compare players" description="Pick two players from the same tour to see their head to head, ratings, surface strengths and recent form side by side." />
    </>
  );
  if (!index.ok) {
    return <>{header}<div className="card"><EmptyState title="Player ratings are not available right now">{index.detail}</EmptyState></div></>;
  }
  const options = index.data.players.map(({ id, name, tour, photo, elo_rank }) => ({ id, name, tour, photo, elo_rank }));
  // Send the browser only the meetings between these two, not each player's whole head-to-head table.
  const first = pa?.ok ? pa.data : null;
  const second = pb?.ok && pb.data.id !== first?.id ? pb.data : null;
  const only = (p: typeof first, other: typeof first) => p && { ...p, h2h: other ? { [String(other.id)]: p.h2h[String(other.id)] ?? [] } : {} };
  return (
    <>
      {header}
      <CompareView options={options} tour={tour} a={only(first, second)} b={only(second, first)} />
    </>
  );
}
