"use client";

import { useState } from "react";
import { Segmented } from "./lab/parts";

/** Main tour | ITF, used on the Players, Matches and Archive pages. The two have different models, ratings and
 * records, so they are shown side by side, never mixed. */
export function CircuitTabs({ main, itf, label = "Circuit" }: { main: React.ReactNode; itf: React.ReactNode; label?: string }) {
  const [view, setView] = useState<"main" | "itf">("main");
  return (
    <>
      <div className="mb-6">
        <Segmented label={label} value={view} onChange={setView} options={[["main", "Main tour"], ["itf", "ITF"]]} />
      </div>
      <div hidden={view !== "main"}>{main}</div>
      <div hidden={view !== "itf"}>{itf}</div>
    </>
  );
}
