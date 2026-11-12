"use client";

import type { Itf, Models } from "@/lib/contract";
import { FEATURES, featureLabel } from "@/lib/features";
import { Finding, SectionHead, sgn4 } from "./parts";

type Model = Models["models"][number];
const GROUPS: { name: string; match: (f: string) => boolean }[] = [
  { name: "Ratings", match: (f) => f === "elo_logit" || f === "surface_elo_logit" },
  { name: "Ranking", match: (f) => f.startsWith("log_rank") || f.startsWith("rank_missing") },
  { name: "Activity and form", match: (f) => f.startsWith("log_days") || f.startsWith("form") },
  { name: "Serve and return", match: (f) => f.startsWith("serve") || f.startsWith("return") || f.startsWith("no_stats") },
  { name: "This tournament", match: (f) => f.startsWith("ra_") },
  { name: "Event level", match: (f) => f.endsWith("_x_tier") },
];
const ymd = (n: number) => { const s = String(n); return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`; };

function grouped(features: string[]) {
  const groups = GROUPS.map((g) => ({ name: g.name, features: features.filter(g.match) })).filter((g) => g.features.length);
  const rest = features.filter((f) => !GROUPS.some((g) => g.match(f)));
  return rest.length ? [...groups, { name: "Other", features: rest }] : groups;
}

export function ModelsTab({ models, itf }: { models: Models | null; itf: Itf["research"] }) {
  const ts = models?.models.find((m) => m.kind === "tournament_start");
  const ra = models?.models.find((m) => m.kind === "round_aware");
  return (
    <div className="grid gap-12">
      <Finding kicker="Three frozen models" title="Two for the main tour, one for ITF.">
        All three are logistic regressions fitted separately for each tour, then frozen as files with fingerprints. The
        round-aware model uses everything the tournament-start model uses, plus how each player has done earlier in the same
        tournament. ITF players rarely have main-tour history, so the ITF model rates every player across every level they
        have played. None is refitted to make a forecast; a changed model would need a new version name. How each one
        scored on matches it never saw is in Benchmarks.
      </Finding>
      {!models && <p className="text-muted">The main-tour models could not be loaded.</p>}
      {[ts, ra].filter((m): m is Model => Boolean(m)).map((m, i) => (
        <section key={m.model_version} className={`grid gap-6 ${i > 0 ? "border-t border-border pt-10" : ""}`}>
          <SectionHead title={m.kind === "tournament_start" ? "Tournament start" : "Round-aware update"}
                       action={<span className="mono rounded-md border border-border bg-card px-2 py-1 text-muted">{m.model_version}</span>}>
            {m.label}{m.applies_to ? `. Applies to ${m.applies_to}.` : "."}
          </SectionHead>
          <Architecture features={featuresOf(m)} sha={m.artifact_sha256} base={m.kind === "round_aware" && ts ? new Set(featuresOf(ts)) : undefined} />
          <dl className="grid gap-x-10 gap-y-4 text-[13px] sm:grid-cols-2 lg:grid-cols-4">
            {m.fit && <div><dt className="text-[12px] text-dim">Fitted on</dt><dd className="mt-1">Rated matches, {ymd(m.fit.from)} to the week of {ymd(m.fit.through_week)}</dd></div>}
            <div><dt className="text-[12px] text-dim">One model per tour</dt><dd className="mt-1">{Object.keys(m.features).join(" and ")}</dd></div>
            <div><dt className="text-[12px] text-dim">Registered</dt><dd className="fig mt-1 text-[12px]">{m.registered_at.replace("T", " ").replace("Z", " UTC")}</dd></div>
            {m.population && <div className="sm:col-span-2 lg:col-span-1"><dt className="text-[12px] text-dim">Population</dt><dd className="mt-1 text-muted">{m.population}</dd></div>}
          </dl>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <p className="text-[12px] text-dim">Uses</p>
              <ul className="mt-2 grid gap-1.5 text-[13px]">{m.uses.map((u) => <li key={u} className="flex gap-2"><span className="text-accent" aria-hidden="true">+</span>{u}</li>)}</ul>
            </div>
            <div>
              <p className="text-[12px] text-dim">Does not use (limitations)</p>
              <ul className="mt-2 grid gap-1.5 text-[13px] text-muted">{m.does_not_use.map((u) => <li key={u} className="flex gap-2"><span className="text-dim" aria-hidden="true">−</span>{u}</li>)}</ul>
            </div>
          </div>
          <details className="group rounded-lg border border-border px-4 py-3 text-[13px]">
            <summary className="cursor-pointer list-none text-muted transition-colors hover:text-text">
              <span className="inline-block transition-transform group-open:rotate-90" aria-hidden="true">›</span> Technical fingerprint
            </summary>
            <dl className="mt-3 grid gap-y-2 sm:grid-cols-[160px_minmax(0,1fr)]">
              <dt className="text-dim">Artifact SHA-256</dt><dd className="mono break-all">{m.artifact_sha256}</dd>
              {Object.entries(m.features).map(([tour, f]) => (
                <div key={tour} className="contents"><dt className="text-dim">{tour} features ({f.length})</dt><dd className="mono break-all text-muted">{f.join(", ")}</dd></div>
              ))}
              {m.fit && <><dt className="text-dim">Fit rule</dt><dd className="text-muted">{m.fit.rule}</dd></>}
            </dl>
          </details>
        </section>
      ))}
      <ItfModel itf={itf} />
    </div>
  );
}

const featuresOf = (m: Model) => [...new Set(Object.values(m.features).flat())];
const ITF_TOUR: Record<string, string> = { ATP: "ITF Men", WTA: "ITF Women" };
const lowerFirst = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

/** The ITF model, described from the ITF research file (it is not in models.json): the same layout as the main-tour
 *  models, with its weights in the technical fingerprint. Its held-out test is in Benchmarks. */
function ItfModel({ itf }: { itf: Itf["research"] }) {
  const m = itf.model;
  if (!m) return null;
  const tours = Object.keys(m.tours);
  const features = [...new Set(tours.flatMap((t) => Object.keys(m.tours[t]!.weights)))];
  const about = m.description.replace(/^ITF M1:\s*/, "");
  return (
    <section className="grid gap-6 border-t border-border pt-10">
      <SectionHead title="ITF M1" action={<span className="mono rounded-md border border-border bg-card px-2 py-1 text-muted">{m.version}</span>}>
        {about.charAt(0).toUpperCase() + about.slice(1)}. Applies to ITF Men and ITF Women main-draw matches.
      </SectionHead>
      <Architecture features={features} sha={m.sha256} />
      <dl className="grid gap-x-10 gap-y-4 text-[13px] sm:grid-cols-2 lg:grid-cols-4">
        <div><dt className="text-[12px] text-dim">Fitted on</dt><dd className="mt-1">{tours.map((t) => `${m.tours[t]!.fit_rows.toLocaleString("en-GB")} ${ITF_TOUR[t] ?? t}`).join(" and ")} matches</dd></div>
        <div><dt className="text-[12px] text-dim">One model per tour</dt><dd className="mt-1">{tours.map((t) => ITF_TOUR[t] ?? t).join(" and ")}</dd></div>
      </dl>
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <p className="text-[12px] text-dim">Uses</p>
          <ul className="mt-2 grid gap-1.5 text-[13px]">
            {features.map((f) => (
              <li key={f} className="flex gap-2"><span className="text-accent" aria-hidden="true">+</span>
                <span>{featureLabel(f)}{FEATURES[f]?.help && <span className="text-muted">: {lowerFirst(FEATURES[f]!.help)}</span>}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-[12px] text-dim">Does not use (limitations)</p>
          <ul className="mt-2 grid gap-1.5 text-[13px] text-muted">
            <li className="flex gap-2"><span className="text-dim" aria-hidden="true">−</span>Serve and return statistics: none are published for ITF matches after June 2026, so the serve model (M2) could not be kept current.</li>
            <li className="flex gap-2"><span className="text-dim" aria-hidden="true">−</span>How a player has done earlier in the same event: the ITF model has no round-aware version.</li>
          </ul>
        </div>
      </div>
      <details className="group rounded-lg border border-border px-4 py-3 text-[13px]">
        <summary className="cursor-pointer list-none text-muted transition-colors hover:text-text">
          <span className="inline-block transition-transform group-open:rotate-90" aria-hidden="true">›</span> Technical fingerprint
        </summary>
        <dl className="mt-3 grid gap-y-2 sm:grid-cols-[160px_minmax(0,1fr)]">
          <dt className="text-dim">Artifact SHA-256</dt><dd className="mono break-all">{m.sha256}</dd>
          <dt className="text-dim">Elo variant</dt><dd className="text-muted">{m.elo_variant}</dd>
        </dl>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[420px] text-left text-[13px]">
            <thead className="text-[11px] text-dim">
              <tr><th className="py-2 font-normal">Input</th>{tours.map((t) => <th key={t} className="py-2 text-right font-normal">{ITF_TOUR[t] ?? t} weight</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-border">
              {features.map((f) => (
                <tr key={f} className="text-muted">
                  <td className="py-2">{featureLabel(f)} <span className="mono text-[11px] text-dim">{f}</span></td>
                  {tours.map((t) => { const w = m.tours[t]!.weights[f]; return <td key={t} className="fig py-2 text-right">{w != null ? sgn4(w) : "–"}</td>; })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[12px] text-dim">Weights per unit of each input, fitted separately for men and women.</p>
      </details>
    </section>
  );
}

/** Inputs grouped by kind, flowing into the frozen model and out as one probability. Added groups are highlighted. */
function Architecture({ features, sha, base }: { features: string[]; sha: string; base?: Set<string> }) {
  const groups = grouped(features);
  const baseFeatures = base ?? new Set<string>();
  return (
    <div className="grid items-center gap-4 rounded-xl border border-border bg-card/40 p-5 lg:grid-cols-[minmax(0,1fr)_40px_220px_40px_160px] lg:p-6">
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-1">
        {groups.map((g) => {
          const added = base !== undefined && g.features.every((f) => !baseFeatures.has(f));
          return (
            <div key={g.name} className={`rounded-lg border px-3.5 py-2.5 transition-colors hover:border-border-strong ${added ? "border-accent/50 bg-accent-soft" : "border-border bg-bg"}`}>
              <p className="flex items-center justify-between text-[12px] font-medium">{g.name}{added && <span className="text-[11px] font-normal text-accent">added</span>}</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {g.features.map((f) => <li key={f} title={FEATURES[f]?.help} className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted">{featureLabel(f)}</li>)}
              </ul>
            </div>
          );
        })}
      </div>
      <Arrow />
      <div className="rounded-lg border border-border-strong bg-bg px-4 py-4 text-center">
        <p className="text-[13px] font-medium">Logistic regression</p>
        <p className="mt-1 text-[12px] text-muted">one per tour, frozen</p>
        <p className="mono mt-2 text-[11px] text-dim">{sha.slice(0, 12)}…</p>
      </div>
      <Arrow />
      <div className="rounded-lg border border-accent/40 px-4 py-4 text-center">
        <p className="fig text-[18px] text-accent">P(win)</p>
        <p className="mt-1 text-[12px] text-muted">for each player</p>
      </div>
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex justify-center text-dim" aria-hidden="true">
      <svg width="24" height="24" viewBox="0 0 24 24" className="rotate-90 lg:rotate-0"><path d="M3 12h16M14 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
    </div>
  );
}
