"use client";

import { useEffect, useRef, useState } from "react";
import { compact } from "@/lib/format";

/**
 * Counts up to `value` when it scrolls into view. `short` shows it with compact() instead of in full. The server renders the final number, so the page is correct before
 * any script runs and stays static for visitors who prefer reduced motion.
 */
export function CountUp({ value, duration = 1200, short = false }: { value: number; duration?: number; short?: boolean }) {
  const [shown, setShown] = useState(value);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || value <= 0 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      observer.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / duration);
        setShown(Math.round(value * (1 - (1 - t) ** 3)));
        if (t < 1) frame = requestAnimationFrame(tick);
      };
      setShown(0);
      frame = requestAnimationFrame(tick);
    }, { threshold: 0.4 });
    observer.observe(el);
    return () => { observer.disconnect(); cancelAnimationFrame(frame); };
  }, [value, duration]);
  return <span ref={ref} className="num">{short ? compact(shown) : shown.toLocaleString("en-GB")}</span>;
}
