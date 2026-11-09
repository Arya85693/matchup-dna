import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getHistoryIndex, getHistoryPlayer, getPlayers } from "@/lib/snapshot";
import { pct, roundLabel } from "@/lib/format";
import { ComparePicker } from "@/components/ComparePicker";
import { EloChart } from "@/components/EloChart";
import { Badge, Card, Metric, PageHeader, SurfaceDot } from "@/components/ui";

export const revalidate = 300;
type Params = { params: Promise<{ id: string }> };
const SURFACES = ["Hard", "Clay", "Grass"] as const;

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const p = await getHistoryPlayer((await params).id);
  return { title: p.ok ? p.data.name : "Player" };
}

export default async function PlayerPage({ params }: Params) {
  const { id } = await params;
  const [loaded, index, forecasts] = await Promise.all([getHistoryPlayer(id), getHistoryIndex(), getPlayers()]);
  if (!loaded.ok) notFound();
  const p = loaded.data;
  const options = index.ok
    ? index.data.players.filter((o) => o.tour === p.tour && o.id !== p.id).map((o) => ({ id: o.id, name: o.name })).sort((a, b) => a.name.localeCompare(b.name))
    : [];
  const forecastMatches = forecasts.ok ? forecasts.data.players.find((f) => f.id === p.id)?.matches ?? [] : [];
  const [w, l] = p.season.All;
  const best = SURFACES.reduce<(typeof SURFACES)[number]>((a, s) => (p.surfaces[s].elo > p.surfaces[a].elo ? s : a), "Hard");
  const rankText = p.rank ? `Ranked ${p.rank}${p.rank_as_of ? ` (as of ${p.rank_as_of})` : ""}` : "Unranked";

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-2 text-[13px] text-muted">
        <Link href="/players" className="hover:text-text">Players</Link><span className="text-dim">/</span><span className="text-text">{p.name}</span>
      </nav>
      <PageHeader title={p.name} description={`${p.tour} · ${rankText} · last played ${p.last_match}`}
                  actions={options.length > 0 ? <ComparePicker id={p.id} options={options} /> : undefined} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Elo rating" value={Math.round(p.elo)}
                note={p.elo_change_90d === null ? `${p.rated_matches} rated matches` : `${p.elo_change_90d >= 0 ? "+" : ""}${Math.round(p.elo_change_90d)} in 90 days`}
                tone={p.elo_change_90d === null ? undefined : p.elo_change_90d >= 0 ? "pos" : "neg"} />
        <Metric label={`${p.season.year} record`} value={`${w}–${l}`} note={w + l ? `${Math.round((w / (w + l)) * 100)}% won` : "No matches this season"} />
        <Metric label="Best surface" value={best} note={`Surface Elo ${Math.round(p.surfaces[best].elo)}`} />
        <Metric label="Elo rank" value={`#${p.elo_rank}`} note={`Among active ${p.tour} players`} />
      </div>

      <Card title="Elo over time" className="mt-6"><EloChart series={[{ name: p.name, points: p.series }]} /></Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="By surface">
          <ul className="grid gap-4">
            {SURFACES.map((s) => {
              const [sw, sl] = p.season[s];
              const width = Math.max(2, Math.min(100, ((p.surfaces[s].elo - 1300) / 1100) * 100));
              return (
                <li key={s}>
                  <div className="flex items-center justify-between text-[13px]">
                    <span className="inline-flex items-center gap-2"><SurfaceDot surface={s} />{s}</span>
                    <span className="num text-muted">{Math.round(p.surfaces[s].elo)} <span className="text-dim">· {sw}–{sl} this season</span></span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-track" aria-hidden="true">
                    <div className="h-full rounded-full bg-accent" style={{ width: `${width}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="mt-4 text-[12px] text-dim">Surface Elo, blended half and half with overall Elo.</p>
        </Card>

        <Card title="Recent results" padded={false}>
          {p.recent.length === 0 ? <p className="px-5 py-4 text-muted">No rated matches.</p> : (
            <ul className="divide-y divide-border">
              {p.recent.map((r, i) => (
                <li key={i} className="flex items-center justify-between gap-4 px-5 py-2.5">
                  <div className="min-w-0">
                    <Link href={`/players/${r.opponent_id}`} className="truncate hover:text-accent">{r.won ? "Beat" : "Lost to"} {r.opponent}</Link>
                    <p className="text-[12px] text-dim"><span className="inline-flex items-center gap-1.5"><SurfaceDot surface={r.surface} />{r.event} · {roundLabel(r.round)} · {r.date}</span></p>
                  </div>
                  <Badge tone={r.won ? "pos" : "neg"}>{r.won ? "W" : "L"}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {forecastMatches.length > 0 && (
        <Card title="Matchup DNA forecasts" className="mt-6" padded={false}>
          <ul className="divide-y divide-border">
            {forecastMatches.map((m) => (
              <li key={m.match_uid}>
                <Link href={`/matches/${m.match_uid}`} className="flex items-center justify-between gap-4 px-5 py-3 hover:bg-card-hover">
                  <span>v {m.opponent} <span className="text-[12px] text-dim">· {m.event}</span></span>
                  <span className="flex items-center gap-3">
                    <span className="num text-muted">{pct(m.p)}% to win</span>
                    {m.outcome === "won" ? <Badge tone="pos">Won</Badge> : m.outcome === "lost" ? <Badge tone="neg">Lost</Badge> : <Badge>Upcoming</Badge>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <p className="mt-6 text-[12px] text-dim">Ratings come from a chronological Elo replay over the match history, refreshed after each daily run. They describe past results; official forecasts are on match pages.</p>
    </>
  );
}
