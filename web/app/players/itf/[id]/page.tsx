import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getItfHistoryIndex, getItfHistoryPlayer, getItfMatches } from "@/lib/snapshot";
import { PlayerProfile, type ProfileForecast } from "@/components/players/PlayerProfile";

export const revalidate = 300;
type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const p = await getItfHistoryPlayer((await params).id);
  return { title: p.ok ? p.data.name : "Player" };
}

/** An ITF board player: the same profile as the main tour, rated with the ITF model's Elo. The forecasts listed are
 * the ITF model's, from the ITF match board. */
export default async function ItfPlayerPage({ params }: Params) {
  const { id } = await params;
  const [loaded, index, board] = await Promise.all([getItfHistoryPlayer(id), getItfHistoryIndex(), getItfMatches()]);
  if (!loaded.ok) notFound();
  const p = loaded.data;
  const listed = new Set(index.ok ? index.data.players.filter((x) => x.tour === p.tour).map((x) => x.id) : []);
  const forecasts: ProfileForecast[] = [];
  for (const m of board.ok ? board.data.matches : []) {
    const i = m.players.findIndex((x) => x.id === p.id);
    const f = m.forecasts.tournament_start;
    if (m.tour !== p.tour || i < 0 || !f.available) continue;
    const r = m.result;
    forecasts.push({
      match_uid: m.uid, opponent: m.players[1 - i]!.name, event: m.edition.name, p: f.p[i]!,
      outcome: r && r.status === "completed" && r.winner_index !== null ? (r.winner_index === i ? "won" : "lost") : null,
    });
  }
  const tour = p.tour === "ATP" ? "ITF Men" : "ITF Women";
  return (
    <PlayerProfile p={p} listed={listed} forecasts={forecasts} base="/players/itf" board="/players?circuit=itf" tourLabel={tour}
                   ratingNote={`Among listed ${tour} players`}
                   footer="Ratings are the ITF model's Elo: one replay over every level, from ITF events to the Grand Slams, refreshed once a day. They describe past results and are not on the same scale as the main-tour Elo; official forecasts are on match pages." />
  );
}
