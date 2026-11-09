import type { Metadata } from "next";
import Link from "next/link";
import { getHistoryPlayer } from "@/lib/snapshot";
import { EloChart } from "@/components/EloChart";
import { Card, EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Compare players" };

type Props = { searchParams: Promise<{ a?: string; b?: string }> };
type Row = [string, number | string, number | string, "high" | "low" | null];

export default async function Compare({ searchParams }: Props) {
  const { a = "", b = "" } = await searchParams;
  const [pa, pb] = await Promise.all([getHistoryPlayer(a), getHistoryPlayer(b)]);
  if (!pa.ok || !pb.ok) {
    return (
      <>
        <PageHeader title="Compare players" />
        <div className="card"><EmptyState title="Choose two players">Open a player and use Compare with. <Link href="/players" className="link">Browse players</Link></EmptyState></div>
      </>
    );
  }
  const A = pa.data, B = pb.data;
  const rows: Row[] = [
    ["Elo", Math.round(A.elo), Math.round(B.elo), "high"],
    ["Ranking", A.rank ?? "—", B.rank ?? "—", "low"],
    ["Hard Elo", Math.round(A.surfaces.Hard.elo), Math.round(B.surfaces.Hard.elo), "high"],
    ["Clay Elo", Math.round(A.surfaces.Clay.elo), Math.round(B.surfaces.Clay.elo), "high"],
    ["Grass Elo", Math.round(A.surfaces.Grass.elo), Math.round(B.surfaces.Grass.elo), "high"],
    [`${A.season.year} record`, `${A.season.All[0]}–${A.season.All[1]}`, `${B.season.All[0]}–${B.season.All[1]}`, null],
    ["Rated matches", A.rated_matches, B.rated_matches, null],
  ];
  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-2 text-[13px] text-muted">
        <Link href="/players" className="hover:text-text">Players</Link><span className="text-dim">/</span><span className="text-text">Compare</span>
      </nav>
      <PageHeader title={`${A.name} vs ${B.name}`} description="Ratings side by side. A comparison of past results, not a match forecast." />
      <Card title="Elo over time"><EloChart series={[{ name: A.name, points: A.series }, { name: B.name, points: B.series }]} /></Card>
      <Card title="Side by side" className="mt-6" padded={false}>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border text-[12px] text-dim">
              <th className="px-5 py-3 text-left font-normal"><Link href={`/players/${A.id}`} className="hover:text-text">{A.name}</Link></th>
              <th className="py-3 font-normal"><span className="sr-only">Measure</span></th>
              <th className="px-5 py-3 text-right font-normal"><Link href={`/players/${B.id}`} className="hover:text-text">{B.name}</Link></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map(([label, x, y, better]) => {
              const nx = typeof x === "number" ? x : null, ny = typeof y === "number" ? y : null;
              const xb = better !== null && nx !== null && ny !== null && nx !== ny && (better === "high" ? nx > ny : nx < ny);
              const yb = better !== null && nx !== null && ny !== null && nx !== ny && !xb;
              return (
                <tr key={label}>
                  <td className={`num px-5 py-2.5 ${xb ? "font-semibold" : "text-muted"}`}>{x}</td>
                  <td className="py-2.5 text-center text-[12px] text-dim">{label}</td>
                  <td className={`num px-5 py-2.5 text-right ${yb ? "font-semibold" : "text-muted"}`}>{y}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </>
  );
}
