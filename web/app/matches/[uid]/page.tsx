import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getMatch } from "@/lib/snapshot";
import { MatchIntelligence } from "@/components/MatchIntelligence";
import { EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 300;

type Params = { params: Promise<{ uid: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const page = await getMatch((await params).uid);
  if (!page.ok) return { title: "Match" };
  const m = page.data.match;
  return { title: `${m.players[0].name} v ${m.players[1].name}` };
}

export default async function MatchPage({ params }: Params) {
  const loaded = await getMatch((await params).uid);
  if (!loaded.ok) {
    if (loaded.reason === "not_found") notFound();
    return <><PageHeader title="Match" /><div className="card"><EmptyState title="This match could not be loaded">{loaded.detail}</EmptyState></div></>;
  }
  const m = loaded.data.match;
  return (
    <>
      <h1 className="sr-only">{m.players[0].name} v {m.players[1].name}, {m.edition.name}</h1>
      <MatchIntelligence page={loaded.data} />
    </>
  );
}
