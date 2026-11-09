/** Shared building blocks. Quiet by default: thin borders, one accent, numbers in tabular figures. */
import { favourite, pct } from "@/lib/format";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 pb-8">
      <div>
        <h1 className="text-[22px] font-semibold">{title}</h1>
        {description && <p className="mt-1.5 max-w-[60ch] text-muted">{description}</p>}
      </div>
      {actions}
    </header>
  );
}

export function Card({ title, action, children, className = "", padded = true }: {
  title?: React.ReactNode; action?: React.ReactNode; children: React.ReactNode; className?: string; padded?: boolean;
}) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-3.5">
          <h2 className="text-[13px] font-medium">{title}</h2>
          {action}
        </div>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}

export function Metric({ label, value, note, tone }: { label: string; value: React.ReactNode; note?: React.ReactNode; tone?: "pos" | "neg" }) {
  return (
    <div className="card px-5 py-4">
      <p className="label">{label}</p>
      <p className={`num mt-2 text-[24px] font-semibold leading-none ${tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : ""}`}>{value}</p>
      {note && <p className="mt-2 text-[12px] text-dim">{note}</p>}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "accent" | "warn" | "pos" | "neg" }) {
  const styles = {
    neutral: "border-border-strong text-muted",
    accent: "border-accent/40 text-accent bg-accent-soft",
    warn: "border-warn/40 text-warn",
    pos: "border-pos/40 text-pos",
    neg: "border-neg/40 text-neg",
  }[tone];
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2 py-[1px] text-[11px] font-medium ${styles}`}>{children}</span>;
}

const SURFACE_DOT: Record<string, string> = { Hard: "bg-hard", Clay: "bg-clay", Grass: "bg-grass" };

export function SurfaceDot({ surface, withLabel = false }: { surface: string | null; withLabel?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`size-2 rounded-full ${SURFACE_DOT[surface ?? ""] ?? "bg-dim"}`} aria-hidden="true" />
      {withLabel && <span>{surface ?? "Surface unknown"}</span>}
    </span>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="px-6 py-12 text-center">
      <p className="font-medium">{title}</p>
      {children && <p className="mx-auto mt-1.5 max-w-[48ch] text-muted">{children}</p>}
    </div>
  );
}

/**
 * Probability bar in the Polymarket manner: the favourite's share in the accent colour, the rest as a track.
 * Shows stored probabilities only.
 */
export function ProbBar({ p, height = 6, animate = true }: { p: readonly [number, number]; height?: number; animate?: boolean }) {
  const fav = favourite(p);
  return (
    <div className="w-full overflow-hidden rounded-full bg-track" style={{ height }} aria-hidden="true">
      <div className={`flex h-full w-full ${animate ? "anim-fill" : ""}`}>
        <span className={fav === 0 ? "bg-accent" : "bg-transparent"} style={{ width: `${p[0] * 100}%` }} />
        <span className={fav === 1 ? "bg-accent" : "bg-transparent"} style={{ width: `${p[1] * 100}%` }} />
      </div>
    </div>
  );
}

/** "64.6%" with the favourite highlighted. */
export function Prob({ value, strong }: { value: number; strong: boolean }) {
  return <span className={`num ${strong ? "font-semibold text-text" : "text-muted"}`}>{pct(value)}%</span>;
}

export function Unavailable({ children }: { children: React.ReactNode }) {
  return <span className="text-[12px] text-dim">{children}</span>;
}
