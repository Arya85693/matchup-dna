"use client";

import { useId } from "react";

/**
 * A small "i" that explains a term on hover or keyboard focus. The text is linked with aria-describedby, so screen
 * readers announce it with the button even though it is only shown visually on hover or focus.
 */
export function InfoTip({ label, children, align = "center" }: { label: string; children: React.ReactNode; align?: "center" | "end" | "start" }) {
  const id = useId();
  const position = align === "end" ? "right-0" : align === "start" ? "left-0" : "left-1/2 -translate-x-1/2";
  return (
    <span className="group/tip relative inline-flex align-middle">
      <button type="button" aria-label={`About ${label}`} aria-describedby={id} onClick={(e) => e.stopPropagation()}
              className="inline-flex size-3.5 items-center justify-center rounded-full border border-border-strong text-[9px] font-semibold leading-none text-dim transition-colors hover:border-muted hover:text-text focus-visible:text-text">
        i
      </button>
      <span id={id} role="tooltip"
            className={`pointer-events-none invisible absolute top-full z-30 mt-2 w-[240px] rounded-md border border-border-strong bg-bg px-3 py-2 text-left text-[12px] font-normal leading-snug text-muted opacity-0 shadow-lg transition-opacity group-hover/tip:visible group-hover/tip:opacity-100 group-focus-within/tip:visible group-focus-within/tip:opacity-100 ${position}`}>
        {children}
      </span>
    </span>
  );
}
