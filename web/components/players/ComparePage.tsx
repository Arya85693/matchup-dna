import Link from "next/link";
import type { HistoryIndex, HistoryPlayer } from "@/lib/contract";
import type { Loaded } from "@/lib/snapshot";
import { CompareView } from "@/components/compare/CompareView";
import { EmptyState, PageHeader } from "@/components/ui";

/** The Compare page for either board: the main tour (`base` "/players") or the ITF board ("/players/itf"). */
export async function ComparePage({ query, index, player, base, board, circuit }: {
  query: { a?: string; b?: string; tour?: string };
  index: () => Promise<Loaded<HistoryIndex>>;
  player: (slug: string) => Promise<Loaded<HistoryPlayer>>;
  base: string; board: string; circuit: "main" | "itf";
}) {
  const { a, b, tour: wanted } = query;
  // One tour at a time (ATP and WTA ids and ratings are separate pools); both players are loaded from that tour.
  const tour = wanted === "WTA" ? "WTA" : "ATP";
  const slug = (id: string | undefined) => (id ? player(`${tour.toLowerCase()}-${id}`) : Promise.resolve(null));
  const [loaded, pa, pb] = await Promise.all([index(), slug(a), slug(b)]);
  const itf = circuit === "itf";
  const header = (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-2 text-[13px] text-muted">
        <Link href={board} className="hover:text-text">Players</Link><span className="text-dim">/</span><span className="text-text">{itf ? "Compare ITF players" : "Compare"}</span>
      </nav>
      <PageHeader title={itf ? "Compare ITF players" : "Compare players"}
                  description={itf
                    ? "Pick two players from the same ITF board (men or women) to see their head to head, ITF ratings, surface strengths and recent form side by side."
                    : "Pick two players from the same tour to see their head to head, ratings, surface strengths and recent form side by side."} />
    </>
  );
  if (!loaded.ok) {
    return <>{header}<div className="card"><EmptyState title="Player ratings are not available right now">{loaded.detail}</EmptyState></div></>;
  }
  const options = loaded.data.players.map(({ id, name, tour, photo, elo_rank }) => ({ id, name, tour, photo, elo_rank }));
  // Send the browser only the meetings between these two, not each player's whole head-to-head table.
  const first = pa?.ok ? pa.data : null;
  const second = pb?.ok && pb.data.id !== first?.id ? pb.data : null;
  const only = (p: typeof first, other: typeof first) => p && { ...p, h2h: other ? { [String(other.id)]: p.h2h[String(other.id)] ?? [] } : {} };
  return (
    <>
      {header}
      <CompareView options={options} tour={tour} a={only(first, second)} b={only(second, first)} base={base} circuit={circuit} />
    </>
  );
}
