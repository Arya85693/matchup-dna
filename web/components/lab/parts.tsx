/** Building blocks for the Model Lab: open sections, figure strips and evidence labels, rather than stacked cards. */

export type Evidence = "held-out" | "pre-registered" | "retrospective" | "post-hoc" | "development" | "interim" | "frozen";

export const EVIDENCE: Record<Evidence, { label: string; tone: string; meaning: string }> = {
  "pre-registered": { label: "Pre-registered", tone: "border-accent/50 text-accent", meaning: "Rules and analysis fixed before the outcome was seen; run once." },
  "held-out": { label: "Held-out", tone: "border-accent/50 text-accent", meaning: "Scored once on matches kept aside from all model building." },
  frozen: { label: "Frozen protocol", tone: "border-accent/50 text-accent", meaning: "Comparison rules written and frozen before it was run." },
  retrospective: { label: "Retrospective", tone: "border-border-strong text-muted", meaning: "Re-run after the outcomes were known; supporting evidence only." },
  development: { label: "Development", tone: "border-border-strong text-muted", meaning: "Years used to build and choose models; optimistic by design." },
  "post-hoc": { label: "Post-hoc", tone: "border-warn/50 text-warn", meaning: "Not planned in advance; descriptive only." },
  interim: { label: "Interim", tone: "border-warn/50 text-warn", meaning: "The live record is still running; nothing here is a final result." },
};

export function EvidenceTag({ kind }: { kind: Evidence }) {
  const e = EVIDENCE[kind];
  return <span title={e.meaning} className={`inline-flex items-center whitespace-nowrap rounded-full border px-2 py-[1px] text-[11px] font-medium ${e.tone}`}>{e.label}</span>;
}

/** The opening statement of a tab: the finding first, in words, with its evidence level. */
export function Finding({ kicker, title, children, evidence, aside }: {
  kicker: string; title: React.ReactNode; children?: React.ReactNode; evidence?: Evidence; aside?: React.ReactNode;
}) {
  return (
    <section className="grid gap-8 border-b border-border pb-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-end lg:gap-14">
      <div>
        <p className="flex items-center gap-2.5 text-[12px] text-muted">{kicker}{evidence && <EvidenceTag kind={evidence} />}</p>
        <h2 className="mt-3 text-[26px] font-semibold leading-[1.2] sm:text-[30px]">{title}</h2>
        {children && <div className="mt-4 max-w-[58ch] text-[14px] leading-relaxed text-muted">{children}</div>}
      </div>
      {aside && <div className="min-w-0">{aside}</div>}
    </section>
  );
}

/** A horizontal strip of figures separated by hairlines (no boxes). */
export function FigureStrip({ items }: { items: { label: string; value: React.ReactNode; note?: React.ReactNode; tone?: "pos" | "neg" | "warn" }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-6 lg:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]">
      {items.map((i) => (
        <div key={i.label} className="min-w-0 border-l border-border pl-4">
          <dt className="text-[12px] text-muted">{i.label}</dt>
          <dd className={`fig mt-1.5 text-[24px] font-medium leading-none ${i.tone === "pos" ? "text-pos" : i.tone === "neg" ? "text-neg" : i.tone === "warn" ? "text-warn" : "text-text"}`}>{i.value}</dd>
          {i.note && <dd className="mt-1.5 text-[12px] text-dim">{i.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

export function SectionHead({ title, children, action }: { title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h3 className="text-[15px] font-medium">{title}</h3>
        {children && <p className="mt-1 max-w-[70ch] text-[13px] text-muted">{children}</p>}
      </div>
      {action}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; options: [T, React.ReactNode][]; label: string;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex gap-0.5 rounded-md border border-border bg-bg p-0.5">
      {options.map(([v, l]) => (
        <button key={v} aria-pressed={value === v} onClick={() => onChange(v)}
                className={`rounded px-2.5 py-1 text-[12px] transition-colors ${value === v ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>{l}</button>
      ))}
    </div>
  );
}

export const f4 = (v: number) => v.toFixed(4);
export const sgn4 = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(4)}`;
export const pc = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;
