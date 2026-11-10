"use client";

import Link from "next/link";
import type { MatchPage } from "@/lib/contract";
import { LocalTime } from "../LocalTime";
import { MODEL } from "./ForecastSummary";

/**
 * Integrity, compact by default: was each forecast stored before the match, by the frozen code, and chained into the
 * ledger? Expanding shows every hash, the decision log and the result sources. Integrity is not accuracy.
 */
export function Verification({ page }: { page: MatchPage }) {
  const versions = (["tournament_start", "round_aware"] as const).flatMap((k) => page.versions[k].map((v) => ({ k, v })));
  const start = page.match.start;
  const beforeStart = versions.every(({ v }) => !start || v.issued_at < start);
  const frozen = versions.every(({ v }) => v.integrity.code_matches_protocol);
  const pilot = versions.some(({ v }) => v.pilot);
  const ledger = pilot ? "pilot ledger" : "ledger";
  return (
    <details className="group min-w-0 rounded-xl border border-border bg-card">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4 text-[13px]">
        <span className="font-medium">Verification</span>
        {versions.length === 0 ? <span className="text-dim">Result records</span> : (
          <>
            <Check ok={beforeStart}>{beforeStart ? "Stored before the scheduled start" : "Check issue times"}</Check>
            <Check ok={frozen}>{frozen ? "Code matches the frozen protocol" : pilot ? "Pilot run, before the protocol was frozen" : "Code differs from the frozen protocol"}</Check>
            <span className="mono text-dim">{versions.map(({ v }) => `#${v.integrity.ledger_position}`).join(", ")} in the {ledger}</span>
          </>
        )}
        <span className="ml-auto text-[12px] text-muted"><span className="group-open:hidden">Show records</span><span className="hidden group-open:inline">Hide records</span></span>
      </summary>
      <div className="grid gap-6 border-t border-border px-5 py-5 text-[12px]">
        {versions.map(({ k, v }) => (
          <dl key={v.prediction_id} className="grid gap-x-6 gap-y-1.5 sm:grid-cols-[150px_minmax(0,1fr)]">
            <dt className="text-[13px] font-medium text-text sm:col-span-2">{MODEL[k].label} · issued <LocalTime iso={v.issued_at} style="datetime" /></dt>
            <dt className="text-dim">Prediction id</dt><dd className="mono break-all">{v.prediction_id}</dd>
            <dt className="text-dim">Inputs (SHA-256)</dt><dd className="mono break-all text-muted">{v.integrity.input_sha256}</dd>
            <dt className="text-dim">Model artifact</dt><dd className="mono break-all text-muted">{v.integrity.model_sha256}</dd>
            <dt className="text-dim">Code</dt><dd className="mono break-all text-muted">{v.integrity.code_sha256 ?? (v.pilot ? "pilot run (uncommitted code, before the protocol freeze)" : "not recorded")}</dd>
            <dt className="text-dim">{v.pilot ? "Pilot ledger" : "Ledger"}</dt><dd className="mono break-all text-muted">position {v.integrity.ledger_position}, chain hash {v.integrity.record_hash}</dd>
            {v.supersedes && <><dt className="text-dim">Supersedes</dt><dd className="mono break-all text-muted">{v.supersedes}</dd></>}
          </dl>
        ))}
        {page.decisions.length > 0 && (
          <div>
            <p className="mb-2 text-[13px] font-medium">Decision log</p>
            <ul className="grid gap-1.5">
              {page.decisions.map((d, i) => (
                <li key={i} className="grid gap-x-4 sm:grid-cols-[150px_minmax(0,1fr)]">
                  <span className="fig text-dim"><LocalTime iso={d.first_at} style="datetime" />{d.times > 1 ? ` (${d.times} runs)` : ""}</span>
                  <span className="text-muted"><span className="text-text">{MODEL[d.kind as keyof typeof MODEL]?.label ?? d.kind}:</span> {d.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {page.outcomes.length > 0 && (
          <p className="text-muted">Result reported by {[...new Set(page.outcomes.map((o) => o.source.toUpperCase()))].join(" and ")}; each source is stored separately and a disagreement is never scored.</p>
        )}
        <p className="text-dim">
          These checks show that a forecast was recorded before the match and has not changed since. They say nothing about
          whether it was right; that is what the <Link href="/lab" className="link">Model Lab</Link> measures. Every forecast is also listed in the{" "}
          <Link href="/archive" className="link">Forecast Archive</Link>.
        </p>
      </div>
    </details>
  );
}

function Check({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[12px] ${ok ? "text-muted" : "text-warn"}`}>
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        {ok ? <path d="M2.5 6.2 5 8.5l4.5-5" fill="none" stroke="var(--color-pos)" strokeWidth="1.6" strokeLinecap="round" />
            : <path d="M6 2.5v4M6 9h.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />}
      </svg>
      {children}
    </span>
  );
}
