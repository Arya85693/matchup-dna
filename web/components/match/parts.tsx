/** Shared building blocks for the match board and the match page. Stored probabilities only; nothing is computed. */
import { eventLabel, favourite, pct } from "@/lib/format";

export type Tier = "slam" | "premier" | "tour";

/** Grand Slams stand out most; 1000-level events, the Finals and the Olympics a little; everything else is plain. */
export function tierOf(level: string | null): Tier {
  if (level === "G") return "slam";
  if (level === "M" || level === "PM" || level === "F" || level === "O") return "premier";
  return "tour";
}

export function TierBadge({ tour, level }: { tour: string; level: string | null }) {
  const tier = tierOf(level);
  const label = eventLabel(tour, level);
  if (tier === "tour") return <span className="text-[12px] text-dim">{label}</span>;
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-[1px] text-[11px] font-medium ${tier === "slam" ? "border border-accent/50 text-accent" : "border border-border-strong text-muted"}`}>
      {label}
    </span>
  );
}

/**
 * One two-sided bar: the left player's share from the left, the right player's from the right, meeting at the stored
 * split. The favourite's side is in the accent; the other side stays visible in a muted tone. A tick marks 50%.
 */
export function ProbabilitySplit({ p, height = 8, animate = true, showTick = true }: {
  p: readonly [number, number]; height?: number; animate?: boolean; showTick?: boolean;
}) {
  const fav = favourite(p);
  return (
    <div className="relative w-full" style={{ height }} aria-hidden="true">
      <div className={`flex h-full w-full gap-[2px] ${animate ? "anim-fill" : ""}`}>
        <span className={`h-full rounded-l-full ${fav === 0 ? "bg-accent" : "bg-underdog"}`} style={{ width: `${p[0] * 100}%` }} />
        <span className={`h-full rounded-r-full ${fav === 1 ? "bg-accent" : "bg-underdog"}`} style={{ width: `${p[1] * 100}%` }} />
      </div>
      {showTick && <span className="absolute -bottom-1 -top-1 left-1/2 w-px -translate-x-1/2 bg-text/40" />}
    </div>
  );
}

/** "64.6%" with the favourite in the accent and the underdog muted but readable. */
export function Pct({ value, fav, size = "md" }: { value: number; fav: boolean; size?: "sm" | "md" | "xl" }) {
  const sizes = { sm: "text-[13px]", md: "text-[15px]", xl: "text-[40px] leading-none sm:text-[48px]" };
  return <span className={`fig ${sizes[size]} ${fav ? "font-semibold text-accent" : "text-muted"}`}>{pct(value)}<span className="text-[0.6em] opacity-80">%</span></span>;
}
