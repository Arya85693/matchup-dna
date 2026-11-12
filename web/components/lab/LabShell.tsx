"use client";

import { useEffect, useRef, useState } from "react";
import type { Itf, Models, TrackRecord } from "@/lib/contract";
import type { LedgerEntry } from "@/lib/ledger";
import type { HISTORICAL as H, MARKET as M } from "@/lib/research";
import { BenchmarksTab } from "./BenchmarksTab";
import { CalibrationTab } from "./CalibrationTab";
import { LiveTab, type ItfLive } from "./LiveTab";
import { MarketTab } from "./MarketTab";
import { ModelsTab } from "./ModelsTab";

const TABS = [
  { id: "live", label: "Live record" },
  { id: "benchmarks", label: "Benchmarks" },
  { id: "calibration", label: "Calibration" },
  { id: "market", label: "Market" },
  { id: "models", label: "Models" },
] as const;
type TabId = (typeof TABS)[number]["id"];

/** Tabs with shareable addresses (/lab#market) and arrow-key navigation, as the WAI-ARIA tabs pattern describes. */
export function LabShell({ record, archive, historical, market, models, itfResearch, itfRecord, itfLive }: {
  record: TrackRecord | null; archive: LedgerEntry[]; historical: typeof H; market: typeof M; models: Models | null;
  itfResearch: Itf["research"]; itfRecord: Itf["record"] | null; itfLive: ItfLive;
}) {
  const [tab, setTab] = useState<TabId>("live");
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    const read = () => {
      const id = window.location.hash.slice(1);
      if (TABS.some((t) => t.id === id)) setTab(id as TabId);
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);

  const select = (id: TabId, focus = false) => {
    setTab(id);
    window.history.replaceState(null, "", `#${id}`);
    if (focus) refs.current[TABS.findIndex((t) => t.id === id)]?.focus();
  };
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : null;
    if (next === null) return;
    e.preventDefault();
    select(TABS[(next + TABS.length) % TABS.length]!.id, true);
  };

  return (
    <div className="grid gap-10">
      <div role="tablist" aria-label="Model Lab sections" className="-mx-1 flex gap-1 overflow-x-auto border-b border-border px-1">
        {TABS.map((t, i) => (
          <button key={t.id} ref={(el) => { refs.current[i] = el; }} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id}
                  aria-controls={`panel-${t.id}`} tabIndex={tab === t.id ? 0 : -1} onClick={() => select(t.id)} onKeyDown={(e) => onKey(e, i)}
                  className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] transition-colors ${tab === t.id ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div key={tab} role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="anim-fade">
        {tab === "live" && <LiveTab record={record} entries={archive} itf={itfLive} itfRecord={itfRecord} />}
        {tab === "benchmarks" && <BenchmarksTab h={historical} m={market} itf={itfResearch} />}
        {tab === "calibration" && <CalibrationTab h={historical} record={record} itf={itfResearch} itfRecord={itfRecord} />}
        {tab === "market" && <MarketTab m={market} />}
        {tab === "models" && <ModelsTab models={models} itf={itfResearch} />}
      </div>
    </div>
  );
}
