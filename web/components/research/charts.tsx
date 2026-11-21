/**
 * Charts for the research papers, drawn with the paper's tokens (.paper in globals.css), which are the site's own
 * palette: ATP in the pear accent and WTA in the neutral grey, as in the site's other two-series charts. The bar,
 * dumbbell and forest charts are HTML with percentage positions, so their labels stay full size at phone width; the
 * curve is SVG in a horizontally scrollable frame. Every mark has a native tooltip, and each figure sits next to a
 * table of the same numbers.
 */

const SERIES_COLOR: Record<string, string> = { ATP: "var(--p-s1)", WTA: "var(--p-s2)" };
export const seriesColor = (series: string) => SERIES_COLOR[series] ?? "var(--p-s1)";

const pos = (v: number, [lo, hi]: [number, number]) => `${((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * 100}%`;

function Legend({ items }: { items: { label: string; swatch: React.ReactNode }[] }) {
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-[12.5px] text-[var(--p-muted)]">
      {items.map((i) => <span key={i.label} className="inline-flex items-center gap-1.5">{i.swatch}{i.label}</span>)}
    </div>
  );
}

const Dot = ({ color, hollow = false }: { color: string; hollow?: boolean }) => (
  <span className="inline-block size-2.5 rounded-full" style={hollow ? { border: `2px solid ${color}`, background: "var(--p-bg)" } : { background: color }} aria-hidden="true" />
);
const Dash = () => <span className="inline-block h-3 w-0 border-l border-dashed border-[var(--p-text)]" aria-hidden="true" />;

export const tourLegend = [
  { label: "ATP", swatch: <Dot color={seriesColor("ATP")} /> },
  { label: "WTA", swatch: <Dot color={seriesColor("WTA")} /> },
];

/** The x axis under an HTML chart: ticks and an optional reference label, in a row aligned with the plot column. */
function Axis({ domain, ticks, format, label, directions }: {
  domain: [number, number]; ticks: number[]; format: (v: number) => string; label?: string; directions?: [string, string];
}) {
  // On small screens only every other tick is labelled, counting from zero when zero is a tick.
  const anchor = Math.max(0, ticks.indexOf(0));
  return (
    <div className="grid grid-cols-[var(--lead)_minmax(0,1fr)_var(--tail)] gap-3" aria-hidden="true">
      <span />
      <div>
        <div className="relative h-5 border-t border-[var(--p-text)]/60">
          {ticks.map((t, i) => (
            <span key={t} className={`absolute top-1 -translate-x-1/2 text-[12px] tabular-nums text-[var(--p-muted)] ${(i - anchor) % 2 ? "max-sm:hidden" : ""}`}
                  style={{ left: pos(t, domain) }}>{format(t)}</span>
          ))}
        </div>
        {label && (
          <div className="relative mt-1.5 h-4 text-[12.5px] text-[var(--p-text)]">
            <span className="absolute left-1/2 -translate-x-1/2 whitespace-nowrap">{label}</span>
          </div>
        )}
        {directions && (
          <div className="mt-1.5 flex justify-between gap-4 text-[11.5px] italic text-[var(--p-muted)]">
            <span>← {directions[0]}</span><span className="text-right">{directions[1]} →</span>
          </div>
        )}
      </div>
      <span />
    </div>
  );
}

/** A small heading above the value column at the right of a chart. */
function ValueHead({ text }: { text?: string }) {
  return <span className="relative">{text && <span className="absolute -top-5 left-0 whitespace-nowrap text-[11.5px] text-[var(--p-muted)] max-sm:hidden">{text}</span>}</span>;
}

/** A vertical reference line across the plot column of every row. */
function RefLine({ value, domain, label }: { value: number; domain: [number, number]; label?: string }) {
  return (
    <span className="pointer-events-none absolute inset-y-0 border-l-[1.5px] border-dashed border-[var(--p-text)]/80" style={{ left: pos(value, domain) }} aria-hidden="true">
      {label && <span className="absolute -top-5 -translate-x-1/2 whitespace-nowrap text-[12px] font-semibold text-[var(--p-text)]">{label}</span>}
    </span>
  );
}

// ---------------------------------------------------------------- grouped horizontal bars

export type BarGroup = { label: string; note?: string; divider?: boolean; bars: { series: string; value: number }[] };

export function GroupedBars({ groups, domain, ticks, format, reference, referenceLabel, axisLabel, directions, ariaLabel }: {
  groups: BarGroup[]; domain: [number, number]; ticks: number[]; format: (v: number) => string;
  reference?: number; referenceLabel?: string; axisLabel?: string; directions?: [string, string]; ariaLabel: string;
}) {
  return (
    <div className="grid gap-3 [--lead:150px] [--tail:44px] max-sm:[--lead:92px]" role="img" aria-label={ariaLabel}>
      <Legend items={tourLegend} />
      <div className="relative grid gap-2.5 pt-5">
        <div className="pointer-events-none absolute inset-y-0 grid w-full grid-cols-[var(--lead)_minmax(0,1fr)_var(--tail)] gap-3">
          <span /><div className="relative">{reference !== undefined && <RefLine value={reference} domain={domain} label={referenceLabel} />}</div><span />
        </div>
        {groups.map((g) => (
          <div key={g.label} className={`grid grid-cols-[var(--lead)_minmax(0,1fr)_var(--tail)] items-center gap-x-3 gap-y-[2px] ${g.divider ? "border-t border-[var(--p-rule)] pt-2.5" : ""}`}>
            <p className="row-span-2 self-center pr-1 text-[13px] leading-tight text-[var(--p-text)]">
              {g.label}{g.note && <span className="block text-[11.5px] text-[var(--p-dim)]">{g.note}</span>}
            </p>
            {g.bars.map((b) => (
              <div key={b.series} className="contents" title={`${g.label}, ${b.series}: ${format(b.value)}`}>
                <div className="relative h-[12px]">
                  <span className="absolute inset-y-0 left-0 rounded-r-[4px]" style={{ width: pos(b.value, domain), background: seriesColor(b.series) }} />
                </div>
                <span className="text-[12.5px] tabular-nums text-[var(--p-text)]">{format(b.value)}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <Axis domain={domain} ticks={ticks} format={format} label={axisLabel} directions={directions} />
    </div>
  );
}

// ---------------------------------------------------------------- dumbbell (two values per row)

export type DumbbellRow = { label: string; series: string; a: number; b: number };

export function Dumbbell({ rows, domain, ticks, format, aLabel, bLabel, reference, referenceLabel, axisLabel, directions, valueHead, ariaLabel }: {
  rows: DumbbellRow[]; domain: [number, number]; ticks: number[]; format: (v: number) => string; aLabel: string; bLabel: string;
  reference: number; referenceLabel: string; axisLabel?: string; directions?: [string, string]; valueHead?: string; ariaLabel: string;
}) {
  return (
    <div className="grid gap-3 [--lead:150px] [--tail:88px] max-sm:[--lead:92px] max-sm:[--tail:76px]" role="img" aria-label={ariaLabel}>
      <Legend items={[...tourLegend, { label: aLabel, swatch: <Dot color="var(--p-text)" /> }, { label: bLabel, swatch: <Dot color="var(--p-text)" hollow /> }]} />
      <div className="relative grid gap-2.5 pt-5">
        <div className="pointer-events-none absolute inset-y-0 grid w-full grid-cols-[var(--lead)_minmax(0,1fr)_var(--tail)] gap-3">
          <span /><div className="relative"><RefLine value={reference} domain={domain} label={referenceLabel} /></div><ValueHead text={valueHead} />
        </div>
        {rows.map((r) => {
          const color = seriesColor(r.series);
          const [lo, hi] = r.a < r.b ? [r.a, r.b] : [r.b, r.a];
          return (
            <div key={r.label} className="grid grid-cols-[var(--lead)_minmax(0,1fr)_var(--tail)] items-center gap-3"
                 title={`${r.label}: ${aLabel.toLowerCase()} ${format(r.a)}, ${bLabel.toLowerCase()} ${format(r.b)}`}>
              <span className="text-[13px] text-[var(--p-text)]">{r.label}</span>
              <div className="relative h-5">
                <span className="absolute top-1/2 h-[2px] -translate-y-1/2" style={{ left: pos(lo, domain), width: `calc(${pos(hi, domain)} - ${pos(lo, domain)})`, background: color }} />
                <span className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full" style={{ left: pos(r.b, domain), border: `2px solid ${color}`, background: "var(--p-bg)" }} />
                <span className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--p-bg)]" style={{ left: pos(r.a, domain), background: color }} />
              </div>
              <span className="text-[12.5px] tabular-nums text-[var(--p-text)]">{format(r.a)} / {format(r.b)}</span>
            </div>
          );
        })}
      </div>
      <Axis domain={domain} ticks={ticks} format={format} label={axisLabel} directions={directions} />
    </div>
  );
}

// ---------------------------------------------------------------- forest plot (estimate with interval)

export type ForestGroup = { label: string; note?: string; divider?: boolean; rows: { series: string; value: number; low: number; high: number }[] };

export function Forest({ groups, domain, ticks, format, reference, referenceLabel, axisLabel, directions, valueHead, ariaLabel }: {
  groups: ForestGroup[]; domain: [number, number]; ticks: number[]; format: (v: number) => string;
  reference: number; referenceLabel: string; axisLabel?: string; directions?: [string, string]; valueHead?: string; ariaLabel: string;
}) {
  return (
    <div className="grid gap-3 [--lead:150px] [--tail:150px] max-sm:[--lead:92px] max-sm:[--tail:52px]" role="img" aria-label={ariaLabel}>
      <Legend items={[...tourLegend, { label: "95% interval", swatch: <span className="inline-block h-[2px] w-4 bg-[var(--p-text)]" aria-hidden="true" /> }]} />
      <div className="relative grid gap-2.5 pt-5">
        <div className="pointer-events-none absolute inset-y-0 grid w-full grid-cols-[var(--lead)_minmax(0,1fr)_var(--tail)] gap-3">
          <span /><div className="relative"><RefLine value={reference} domain={domain} label={referenceLabel} /></div><ValueHead text={valueHead} />
        </div>
        {groups.map((g) => (
          <div key={g.label} className={`grid grid-cols-[var(--lead)_minmax(0,1fr)_var(--tail)] items-center gap-x-3 gap-y-1 ${g.divider ? "border-t border-[var(--p-rule)] pt-2.5" : ""}`}>
            <p className="row-span-2 self-center pr-1 text-[13px] leading-tight text-[var(--p-text)]">
              {g.label}{g.note && <span className="block text-[11.5px] text-[var(--p-dim)]">{g.note}</span>}
            </p>
            {g.rows.map((r) => (
              <div key={r.series} className="contents" title={`${g.label}, ${r.series}: ${format(r.value)} (95% ${format(r.low)} to ${format(r.high)})`}>
                <div className="relative h-4">
                  <span className="absolute top-1/2 h-[2px] -translate-y-1/2" style={{ left: pos(r.low, domain), width: `calc(${pos(r.high, domain)} - ${pos(r.low, domain)})`, background: seriesColor(r.series) }} />
                  <span className="absolute top-1/2 size-[11px] -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--p-bg)]" style={{ left: pos(r.value, domain), background: seriesColor(r.series) }} />
                </div>
                <span className="text-[12.5px] tabular-nums text-[var(--p-text)]">
                  {format(r.value)}<span className="text-[var(--p-dim)] max-sm:hidden"> ({format(r.low)} to {format(r.high)})</span>
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <Axis domain={domain} ticks={ticks} format={format} label={axisLabel} directions={directions} />
    </div>
  );
}

// ---------------------------------------------------------------- the losing-run curve

/** Exact probability of at least one run of `k` or more consecutive losses in `n` independent finals won with
 *  probability `p`. Dynamic programme over the length of the current losing run (0 to k-1). */
export function runProbability(n: number, k: number, p: number) {
  let state: number[] = Array.from({ length: k }, (_, i) => (i === 0 ? 1 : 0));
  for (let t = 0; t < n; t++) {
    const total = state.reduce((a, b) => a + b, 0);
    // A won final resets the run to 0; a lost one extends it, and a run reaching k is absorbed (no longer counted).
    state = Array.from({ length: k }, (_, run) => (run === 0 ? total * p : (state[run - 1] ?? 0) * (1 - p)));
  }
  return 1 - state.reduce((a, b) => a + b, 0);
}

export function RunCurve({ p, mark, maxFinals = 40, ariaLabel }: { p: number; mark: number; maxFinals?: number; ariaLabel: string }) {
  const W = 640, H = 300, L = 48, R = 112, T = 18, B = 40;
  const x = (n: number) => L + ((n - 1) / (maxFinals - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - v) * (H - T - B);
  const ns = Array.from({ length: maxFinals }, (_, i) => i + 1);
  const lines = [
    { k: 2, label: "Two in a row", dash: "6 4", color: "var(--p-muted)" },
    { k: 3, label: "Three in a row", dash: "", color: "var(--p-head)" },
  ];
  return (
    <div className="grid gap-3">
      <Legend items={lines.map((l) => ({ label: `At least ${l.label.toLowerCase()}`, swatch: <svg width="18" height="6" aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" stroke={l.color} strokeWidth="2" strokeDasharray={l.dash} /></svg> }))} />
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Figure: probability of a losing run">
        <svg viewBox={`0 0 ${W} ${H}`} className="min-w-[520px] w-full" role="img" aria-label={ariaLabel}>
          {[0, 0.25, 0.5, 0.75, 1].map((v) => (
            <g key={v}>
              <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--p-rule)" strokeWidth="1" />
              <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--p-muted)">{Math.round(v * 100)}%</text>
            </g>
          ))}
          {[1, 10, 20, 30, 40].filter((n) => n <= maxFinals).map((n) => (
            <text key={n} x={x(n)} y={H - B + 18} textAnchor="middle" fontSize="11" fill="var(--p-muted)">{n}</text>
          ))}
          <line x1={L} x2={W - R} y1={y(0)} y2={y(0)} stroke="var(--p-text)" strokeOpacity="0.6" />
          <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" fontSize="11" fill="var(--p-muted)">Number of finals played</text>
          <line x1={x(mark)} x2={x(mark)} y1={y(1)} y2={y(0)} stroke="var(--p-text)" strokeOpacity="0.5" strokeDasharray="3 3" />
          <text x={x(mark)} y={y(1) - 5} textAnchor="middle" fontSize="11" fill="var(--p-text)">{mark} finals</text>
          {lines.map((l) => {
            const d = ns.map((n, i) => `${i ? "L" : "M"}${x(n).toFixed(1)},${y(runProbability(n, l.k, p)).toFixed(1)}`).join(" ");
            const end = runProbability(maxFinals, l.k, p);
            const atMark = runProbability(mark, l.k, p);
            return (
              <g key={l.k}>
                <path d={d} fill="none" stroke={l.color} strokeWidth="2" strokeDasharray={l.dash} strokeLinejoin="round" />
                <circle cx={x(mark)} cy={y(atMark)} r="4.5" fill={l.color} stroke="var(--p-bg)" strokeWidth="2" />
                <text x={x(mark) + (l.k === 2 ? -8 : 8)} y={y(atMark) + (l.k === 2 ? 18 : 14)} textAnchor={l.k === 2 ? "end" : "start"} fontSize="11.5" fill="var(--p-text)">{Math.round(atMark * 100)}%</text>
                <text x={W - R + 8} y={y(end) + 4} fontSize="11.5" fill="var(--p-text)">{l.label}</text>
                {ns.map((n) => (
                  <circle key={n} cx={x(n)} cy={y(runProbability(n, l.k, p))} r="7" fill="transparent">
                    <title>{`${n} finals: ${(runProbability(n, l.k, p) * 100).toFixed(1)}% chance of at least ${l.label.toLowerCase()}`}</title>
                  </circle>
                ))}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- power curves (small multiples)

export type PowerPanel = { title: string; note?: string; series: { series: string; points: { x: number; y: number }[] }[] };

/** One small panel per test: share of simulations that detect a trait (y) against the trait's size (x, the edge in
 *  win-probability points of a player one standard deviation above average against an equal opponent). The viewBox is
 *  kept small so that the type stays legible when three panels share the width of a printed page. */
export function PowerCurves({ panels, xMax, xTicks, target = 0.8, ariaLabel }: {
  panels: PowerPanel[]; xMax: number; xTicks: number[]; target?: number; ariaLabel: string;
}) {
  const W = 250, H = 206, L = 40, R = 10, T = 10, B = 42, FS = 13;
  const x = (v: number) => L + (v / xMax) * (W - L - R);
  const y = (v: number) => T + (1 - v) * (H - T - B);
  const grid = [0, 0.2, 0.4, 0.6, 0.8, 1];
  return (
    <div className="grid gap-4" role="img" aria-label={ariaLabel}>
      <Legend items={[...tourLegend, { label: `${Math.round(target * 100)}% power`, swatch: <Dash /> }]} />
      <div className="grid gap-6 sm:grid-cols-3 sm:gap-5">
        {panels.map((panel) => (
          <div key={panel.title} className="min-w-0">
            <p className="text-[13px] font-semibold leading-tight text-[var(--p-text)]">{panel.title}
              {panel.note && <span className="block text-[11.5px] font-normal text-[var(--p-dim)]">{panel.note}</span>}
            </p>
            <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full max-sm:max-w-[360px]" aria-hidden="true">
              {grid.map((v) => (
                <g key={v}>
                  {v === target
                    ? <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--p-text)" strokeOpacity="0.8" strokeWidth="1.2" strokeDasharray="5 3" />
                    : <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--p-rule)" strokeWidth="1" />}
                  <text x={L - 6} y={y(v) + 4.5} textAnchor="end" fontSize={FS} fill="var(--p-muted)">{Math.round(v * 100)}%</text>
                </g>
              ))}
              <line x1={L} x2={W - R} y1={y(0)} y2={y(0)} stroke="var(--p-text)" strokeOpacity="0.6" />
              {xTicks.map((t) => (
                <g key={t}>
                  <line x1={x(t)} x2={x(t)} y1={y(0)} y2={y(0) + 4} stroke="var(--p-text)" strokeOpacity="0.6" />
                  <text x={x(t)} y={H - B + 18} textAnchor="middle" fontSize={FS} fill="var(--p-muted)">{t}</text>
                </g>
              ))}
              <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" fontSize={FS} fill="var(--p-text)">Trait size (points at even odds)</text>
              {panel.series.map((s) => {
                const color = seriesColor(s.series);
                const d = s.points.map((p, i) => `${i ? "L" : "M"}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");
                return (
                  <g key={s.series}>
                    <path d={d} fill="none" stroke={color} strokeWidth="2.2" strokeLinejoin="round" />
                    {s.points.map((p) => (
                      <g key={p.x}>
                        <circle cx={x(p.x)} cy={y(p.y)} r="3.5" fill={color} stroke="var(--p-bg)" strokeWidth="1.5" />
                        <circle cx={x(p.x)} cy={y(p.y)} r="9" fill="transparent" style={{ pointerEvents: "all" }}>
                          <title>{`${panel.title}, ${s.series}: ${Math.round(p.y * 100)}% power at a ${p.x.toFixed(1)}-point trait`}</title>
                        </circle>
                      </g>
                    ))}
                  </g>
                );
              })}
            </svg>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- study flow (like a PRISMA diagram)

export type FlowBox = { title: string; detail?: React.ReactNode };

function Box({ box, tone = "main" }: { box: FlowBox; tone?: "main" | "side" | "stage" }) {
  const styles = {
    main: "border-[var(--p-rule-strong)] bg-[var(--p-bg)]",
    side: "border-[var(--p-rule)] bg-[var(--p-soft)]",
    stage: "border-[var(--p-text)]/70 bg-[var(--p-soft)]",
  }[tone];
  return (
    <div className={`h-full border px-3.5 py-2.5 text-[12.5px] leading-snug ${styles}`}>
      <p className="font-semibold text-[var(--p-text)]">{box.title}</p>
      {box.detail && <p className="mt-1 text-[var(--p-muted)]">{box.detail}</p>}
    </div>
  );
}

const LINE = "absolute bg-[var(--p-text)]/60";
/** An arrowhead whose tip sits at the bottom of its row, at `left` per cent of the width. */
const Head = ({ left }: { left: number }) => (
  <span className="absolute bottom-0 h-0 w-0 -translate-x-1/2 border-x-[4px] border-t-[6px] border-x-transparent border-t-[var(--p-text)]/60"
        style={{ left: `calc(${left}% + 0.5px)` }} />
);

/** Connector lines between two rows of boxes: down from the points `from` (per cent of the width) on the row above,
 *  along a horizontal bar, and down to the points `to` on the row below. */
function Fork({ from, to }: { from: number[]; to: number[] }) {
  const all = [...from, ...to];
  const lo = Math.min(...all), hi = Math.max(...all);
  return (
    <div className="relative h-6" aria-hidden="true">
      {from.map((x) => <span key={`f${x}`} className={`${LINE} top-0 h-1/2 w-px`} style={{ left: `${x}%` }} />)}
      {hi > lo && <span className={`${LINE} top-1/2 h-px`} style={{ left: `${lo}%`, width: `calc(${hi - lo}% + 1px)` }} />}
      {to.map((x) => <span key={`t${x}`} className={`${LINE} bottom-0 h-1/2 w-px`} style={{ left: `${x}%` }} />)}
      {to.map((x) => <Head key={`h${x}`} left={x} />)}
    </div>
  );
}

/** The study flow, in the manner of a PRISMA diagram: the source files and the matches left out, the analysed
 *  matches, their split into big and regular matches, and the three analyses that use both. */
export function StudyFlow({ source, excluded, analysed, split, tests }: {
  source: FlowBox; excluded: FlowBox; analysed: FlowBox; split: [FlowBox, FlowBox]; tests: FlowBox[];
}) {
  const centres = tests.map((_, i) => ((i + 0.5) / tests.length) * 100);
  return (
    <div className="grid">
      <div className="mx-auto w-full sm:w-[62%]"><Box box={source} /></div>
      <div className="relative grid grid-cols-2" aria-hidden="false">
        <span className={`${LINE} inset-y-0 left-1/2 w-px`} aria-hidden="true" />
        <Head left={50} />
        <span />
        <div className="flex items-center py-2.5">
          <span className="h-px w-5 shrink-0 bg-[var(--p-text)]/60" aria-hidden="true" />
          <div className="min-w-0 flex-1"><Box box={excluded} tone="side" /></div>
        </div>
      </div>
      <div className="mx-auto w-full sm:w-[62%]"><Box box={analysed} /></div>
      <Fork from={[50]} to={[25, 75]} />
      <div className="grid grid-cols-2">
        {split.map((b) => <div key={b.title} className="px-2 sm:px-4"><Box box={b} tone="stage" /></div>)}
      </div>
      <Fork from={[25, 75]} to={centres} />
      <div className="grid" style={{ gridTemplateColumns: `repeat(${tests.length}, minmax(0, 1fr))` }}>
        {tests.map((t) => <div key={t.title} className="px-1 sm:px-2"><Box box={t} /></div>)}
      </div>
    </div>
  );
}
