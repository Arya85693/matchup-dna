"use client";

import type { Itf } from "@/lib/contract";
import { featureLabel } from "@/lib/features";
import { f4, Finding, FigureStrip, pc, SectionHead, sgn4 } from "./parts";

const ORDER = ["M1", "M2", "B1", "B0", "B2"] as const;

/** The ITF model (P2): its live record, the one-time held-out test, and the frozen weights. */
export function ItfTab({ research, record }: { research: Itf["research"]; record: Itf["record"] | null }) {
  const held = research.held_out;
  const c = held.comparisons;
  const gain = (k: string) => {
    const x = c[k];
    return x ? `${sgn4(x.mean)} (95% ${sgn4(x.ci95[0])} to ${sgn4(x.ci95[1])})` : "–";
  };
  const live = record?.m1;
  const model = research.model;
  const men = model?.tours.ATP;
  const women = model?.tours.WTA;
  return (
    <div className="grid gap-12">
      <Finding kicker="ITF Men and ITF Women" evidence="held-out"
               title="A separate model for the ITF tour, tested once on matches it had never seen.">
        ITF players rarely have main-tour history, so the ITF model rates every player across every level they have
        played. It was built on 2021 to mid-2025, chosen on the second half of 2025 and scored once on the first half of
        2026 after every choice was frozen. Its live record (protocol P2) is kept apart from the main-tour record.
      </Finding>

      <section className="grid gap-6">
        <SectionHead title="Live record (P2)">
          Each match&apos;s first M1 forecast counts, with the Elo-only forecast for the same match beside it. Forecasts made
          before P2 was frozen are a pilot and are not scored.
        </SectionHead>
        <FigureStrip items={[
          { label: "Matches forecast", value: record ? record.forecast_matches.toLocaleString() : "–" },
          { label: "Scored", value: live ? live.matches.toLocaleString() : "–", note: "completed matches only" },
          { label: "M1 log loss", value: live?.log_loss != null ? f4(live.log_loss) : "–" },
          { label: "Elo-only log loss", value: record?.elo.log_loss != null ? f4(record.elo.log_loss) : "–", note: "same matches" },
          { label: "M1 accuracy", value: live?.accuracy != null ? pc(live.accuracy) : "–" },
        ]} />
      </section>

      <section className="grid gap-6 border-t border-border pt-10">
        <SectionHead title={`Held-out test: ${held.period}`}>
          {(held.pooled.M1?.matches ?? 0).toLocaleString()} ITF main-draw matches, scored once. Lower log loss is better.
        </SectionHead>
        <table className="w-full text-left text-[13px]">
          <thead className="text-dim">
            <tr>
              <th className="py-2 font-normal">Model</th>
              <th className="py-2 text-right font-normal">Log loss</th>
              <th className="py-2 text-right font-normal">Brier</th>
              <th className="py-2 text-right font-normal">Accuracy</th>
              <th className="hidden py-2 text-right font-normal sm:table-cell">Validation log loss</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {ORDER.map((k) => {
              const m = held.pooled[k];
              if (!m) return null;
              const v = research.validation.pooled[k];
              return (
                <tr key={k} className={k === research.live_model ? "font-medium" : "text-muted"}>
                  <td className="py-2.5">{research.names[k] ?? k}</td>
                  <td className="fig py-2.5 text-right">{f4(m.log_loss)}</td>
                  <td className="fig py-2.5 text-right">{f4(m.brier)}</td>
                  <td className="fig py-2.5 text-right">{pc(m.accuracy)}</td>
                  <td className="fig hidden py-2.5 text-right sm:table-cell">{v ? f4(v.log_loss) : "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <dl className="grid gap-2 text-[13px] text-muted sm:grid-cols-2">
          <div><dt className="inline text-text">M1 against Elo only: </dt><dd className="fig inline">{gain("M1 - B1")}</dd></div>
          <div><dt className="inline text-text">M1 against ranking only: </dt><dd className="fig inline">{gain("M1 - B0")}</dd></div>
          <div><dt className="inline text-text">M1 against the main-tour model: </dt><dd className="fig inline">{gain("M1 - B2")}</dd></div>
          <div><dt className="inline text-text">Serve model M2 against M1: </dt><dd className="fig inline">{gain("M2 - M1")}</dd></div>
        </dl>
        <p className="max-w-[70ch] text-[13px] text-muted">
          M1 forecasts live, not M2: no serve statistics are published for ITF matches after June 2026, so the serve
          inputs could not be kept current.
        </p>
        {research.calibration?.held_out.M1 && (
          <p className="max-w-[70ch] text-[13px] text-muted">
            <span className="text-text">Calibration.</span> M1 was checked, not adjusted: its average gap between forecast and
            outcome was {f4(research.calibration.held_out.M1.ece)} on the held-out half-year
            {research.calibration.validation.M1 ? ` (${f4(research.calibration.validation.M1.ece)} on validation)` : ""}, with
            strong favourites winning about two points less often than forecast in 2026.{" "}
            <a href="#calibration" className="link">Calibration chart</a>
          </p>
        )}
      </section>

      {model && men && (
        <section className="grid gap-6 border-t border-border pt-10">
          <SectionHead title="The frozen live model"
                       action={<span className="mono rounded-md border border-border bg-card px-2 py-1 text-muted">{model.version}</span>}>
            {model.description}. Weights per unit of each input, fitted separately for men and women.
          </SectionHead>
          <table className="w-full text-left text-[13px]">
            <thead className="text-dim">
              <tr><th className="py-2 font-normal">Input</th><th className="py-2 text-right font-normal">ITF Men</th><th className="py-2 text-right font-normal">ITF Women</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {Object.entries(men.weights).map(([f, w]) => {
                const other = women?.weights[f];
                return (
                  <tr key={f} className="text-muted">
                    <td className="py-2.5">{featureLabel(f)}</td>
                    <td className="fig py-2.5 text-right">{sgn4(w)}</td>
                    <td className="fig py-2.5 text-right">{other != null ? sgn4(other) : "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mono break-all text-[12px] text-dim">sha256 {model.sha256}</p>
        </section>
      )}
    </div>
  );
}
