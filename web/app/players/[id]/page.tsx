import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { getHistoryIndex, getHistoryPlayer, getPlayers } from "@/lib/snapshot";
import { playerSlug } from "@/lib/format";
import { PlayerProfile } from "@/components/players/PlayerProfile";

export const revalidate = 300;
type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const p = await getHistoryPlayer((await params).id);
  return { title: p.ok ? p.data.name : "Player" };
}

export default async function PlayerPage({ params }: Params) {
  const { id } = await params;
  const [loaded, forecasts, index] = await Promise.all([getHistoryPlayer(id), getPlayers(), getHistoryIndex()]);
  if (!loaded.ok) {
    // Older addresses carried only the id; send them on when exactly one player (on either tour) has it.
    const same = /^-?\d{1,18}$/.test(id) && index.ok ? index.data.players.filter((x) => String(x.id) === id) : [];
    if (same.length === 1) permanentRedirect(`/players/${playerSlug(same[0]!.tour, same[0]!.id)}`);
    notFound();
  }
  const p = loaded.data;
  const listed = new Set(index.ok ? index.data.players.filter((x) => x.tour === p.tour).map((x) => x.id) : []);
  const matches = forecasts.ok ? forecasts.data.players.find((f) => f.id === p.id)?.matches ?? [] : [];
  return (
    <PlayerProfile p={p} listed={listed} forecasts={matches} base="/players" board="/players" tourLabel={p.tour}
                   ratingNote={`Among active ${p.tour} players`}
                   footer="Ratings come from a chronological Elo replay over the match history, refreshed after each daily run. They describe past results; official forecasts are on match pages." />
  );
}
