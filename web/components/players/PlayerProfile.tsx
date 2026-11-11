import Link from "next/link";
import type { HistoryPlayer } from "@/lib/contract";
import { pct, playerSlug, roundLabel } from "@/lib/format";
import { PlayerPhoto } from "@/components/PlayerPhoto";
import { PhotoCredit } from "@/components/PhotoCredit";
import { EloChart } from "@/components/EloChart";
import { Badge, Card, Metric, SurfaceDot } from "@/components/ui";

const SURFACES = ["Hard", "Clay", "Grass"] as const;

export type ProfileForecast = { match_uid: string; opponent: string | null; event: string; p: number; outcome: "won" | "lost" | null };

/** A player's profile, the same for both boards. `base` is the board's address ("/players" or "/players/itf"),
 * `board` the breadcrumb's link back to it, and `tourLabel` how the tour is named ("ATP", or "ITF Men"). */
export function PlayerProfile({ p, listed, forecasts, base, board, tourLabel, ratingNote, footer }: {
  p: HistoryPlayer; listed: Set<number>; forecasts: ProfileForecast[]; base: string; board: string; tourLabel: string;
  ratingNote: string; footer: React.ReactNode;
}) {
  const [w, l] = p.season.All;
  const best = SURFACES.reduce<(typeof SURFACES)[number]>((a, s) => (p.surfaces[s].elo > p.surfaces[a].elo ? s : a), "Hard");
  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-2 text-[13px] text-muted">
        <Link href={board} className="hover:text-text">Players</Link><span className="text-dim">/</span><span className="text-text">{p.name}</span>
      </nav>
      <header className="flex flex-wrap items-center gap-5 pb-8">
        <PlayerPhoto name={p.name} src={p.photo} size={72} />
        <div className="min-w-0 flex-1">
          <h1 className="text-[22px] font-semibold">{p.name}</h1>
          <p className="mt-1 text-muted">{tourLabel} · Elo #{p.elo_rank} · last played {p.last_match}</p>
          <PhotoCredit credit={p.photo_credit} className="mt-1.5" />
        </div>
        <Link href={`${base}/compare?tour=${p.tour}&a=${p.id}`} className="inline-flex items-center gap-2 rounded-md border border-border-strong px-3 py-1.5 text-[13px] transition-colors hover:bg-card">
          Compare with another player
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Elo rating" value={Math.round(p.elo)}
                note={p.elo_change_90d === null ? `${p.rated_matches} rated matches` : `${p.elo_change_90d >= 0 ? "+" : ""}${Math.round(p.elo_change_90d)} in 90 days`}
                tone={p.elo_change_90d === null ? undefined : p.elo_change_90d >= 0 ? "pos" : "neg"} />
        <Metric label={`${p.season.year} record`} value={`${w}–${l}`} note={w + l ? `${Math.round((w / (w + l)) * 100)}% won` : "No matches this season"} />
        <Metric label="Best surface" value={best} note={`Surface Elo ${Math.round(p.surfaces[best].elo)}`} />
        <Metric label="Elo rank" value={`#${p.elo_rank}`} note={ratingNote} />
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
                    {listed.has(r.opponent_id)
                      ? <Link href={`${base}/${playerSlug(p.tour, r.opponent_id)}`} className="truncate hover:text-accent">{r.won ? "Beat" : "Lost to"} {r.opponent}</Link>
                      : <span className="truncate">{r.won ? "Beat" : "Lost to"} {r.opponent}</span>}
                    <p className="text-[12px] text-dim"><span className="inline-flex items-center gap-1.5"><SurfaceDot surface={r.surface} />{r.event} · {roundLabel(r.round)} · {r.date}</span></p>
                  </div>
                  <Badge tone={r.won ? "pos" : "neg"}>{r.won ? "W" : "L"}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {forecasts.length > 0 && (
        <Card title="Matchup DNA forecasts" className="mt-6" padded={false}>
          <ul className="divide-y divide-border">
            {forecasts.map((m) => (
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
      <p className="mt-6 text-[12px] text-dim">{footer}</p>
    </>
  );
}
