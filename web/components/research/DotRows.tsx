/**
 * A dot chart for the myth check: one group per measure, one lane per tour, each value drawn against a reference line
 * (1.0 for "pure luck", 0 for "no carry-over"). Optional 95% intervals. Server-rendered HTML, so it reflows to phone
 * width; every mark has a native tooltip, and each chart ships with a table of the same numbers.
 */
export const TOUR_COLOR: Record<string, string> = { ATP: "var(--color-accent)", WTA: "var(--color-neutral)" };

export type Lane = { tour: string; value: number; low?: number; high?: number };
export type Group = { label: string; note?: string; lanes: Lane[] };

export function DotRows({ groups, domain, reference, referenceLabel, format, tickFormat = format, ticks, label }: {
  groups: Group[]; domain: [number, number]; reference: number; referenceLabel: string;
  format: (v: number) => string; tickFormat?: (v: number) => string; ticks: number[]; label: string;
}) {
  const [lo, hi] = domain;
  const x = (v: number) => `${((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * 100}%`;
  return (
    <figure className="m-0" aria-label={label}>
      <div className="grid gap-7">
        {groups.map((g, gi) => (
          <div key={g.label} className="grid gap-2.5">
            <p className="text-[13px]">
              <span className="text-text">{g.label}</span>
              {g.note && <span className="text-dim"> {g.note}</span>}
            </p>
            {g.lanes.map((l) => {
              const tip = `${g.label}, ${l.tour}: ${format(l.value)}${l.low !== undefined && l.high !== undefined ? ` (95% ${format(l.low)} to ${format(l.high)})` : ""}`;
              return (
                <div key={l.tour} className="grid grid-cols-[36px_minmax(0,1fr)_64px] items-center gap-3" title={tip}>
                  <span className="text-[12px] text-muted">{l.tour}</span>
                  <div className="relative h-5">
                    <span className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-track" aria-hidden="true" />
                    <span className="absolute inset-y-[-6px] w-px border-l border-dashed border-muted" style={{ left: x(reference) }} aria-hidden="true" />
                    {l.low !== undefined && l.high !== undefined && (
                      <span className="anim-fill absolute top-1/2 h-0.5 -translate-y-1/2 rounded-full opacity-60"
                            style={{ left: x(l.low), width: `calc(${x(l.high)} - ${x(l.low)})`, background: TOUR_COLOR[l.tour], animationDelay: `${gi * 90}ms` }}
                            aria-hidden="true" />
                    )}
                    <span className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg"
                          style={{ left: x(l.value), background: TOUR_COLOR[l.tour] }} aria-hidden="true" />
                  </div>
                  <span className="fig text-right text-[12px]">{format(l.value)}</span>
                </div>
              );
            })}
          </div>
        ))}
        <div className="grid grid-cols-[36px_minmax(0,1fr)_64px] gap-3" aria-hidden="true">
          <span />
          <div className="relative h-8 border-t border-border">
            {ticks.map((t) => (
              <span key={t} className="fig absolute top-1.5 -translate-x-1/2 text-[11px] text-dim" style={{ left: x(t) }}>{tickFormat(t)}</span>
            ))}
            <span className="absolute top-[22px] -translate-x-1/2 whitespace-nowrap text-[11px] text-muted" style={{ left: x(reference) }}>{referenceLabel}</span>
          </div>
          <span />
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-5 text-[12px] text-muted">
        {Object.entries(TOUR_COLOR).map(([tour, color]) => (
          <span key={tour} className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-full" style={{ background: color }} aria-hidden="true" />{tour}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-0 border-l border-dashed border-muted" aria-hidden="true" />{referenceLabel}
        </span>
      </div>
    </figure>
  );
}

/** "Show the numbers": the same figures as a table, closed by default. */
export function NumbersTable({ summary, head, rows }: { summary: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <details className="group rounded-lg border border-border">
      <summary className="cursor-pointer select-none px-4 py-2.5 text-[13px] text-muted hover:text-text">{summary}</summary>
      <div className="overflow-x-auto border-t border-border" tabIndex={0} role="region" aria-label={summary}>
        <table className="w-full min-w-[520px] text-[13px]">
          <thead>
            <tr className="border-b border-border bg-card text-left text-[11px] text-dim">
              {head.map((h, i) => <th key={h} className={`px-4 py-2.5 font-normal ${i > 1 ? "text-right" : ""}`}>{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr key={r.slice(0, 2).join("|")}>
                {r.map((c, i) => <td key={i} className={`px-4 py-2.5 ${i > 1 ? "fig text-right text-[12px]" : i === 1 ? "text-muted" : ""}`}>{c}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
