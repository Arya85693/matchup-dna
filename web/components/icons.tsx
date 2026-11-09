/** 16px line icons, 1.5 stroke, drawn for this product (consistent geometry, currentColor). */
type P = { className?: string };
const base = { width: 16, height: 16, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const IconOverview = (p: P) => <svg {...base} {...p}><rect x="2" y="2" width="5" height="5" rx="1" /><rect x="9" y="2" width="5" height="5" rx="1" /><rect x="2" y="9" width="5" height="5" rx="1" /><rect x="9" y="9" width="5" height="5" rx="1" /></svg>;
export const IconMatches = (p: P) => <svg {...base} {...p}><rect x="1.5" y="3" width="13" height="10" rx="1" /><path d="M8 3v10M4 6h8M4 10h8" /></svg>;
export const IconPlayers = (p: P) => <svg {...base} {...p}><circle cx="8" cy="5.5" r="2.5" /><path d="M3 14c.6-2.6 2.6-4 5-4s4.4 1.4 5 4" /></svg>;
export const IconLab = (p: P) => <svg {...base} {...p}><path d="M2 13.5h12" /><path d="M3.5 11 6.5 7l2.5 2.5L13 4" /></svg>;
export const IconArchive = (p: P) => <svg {...base} {...p}><rect x="2" y="2.5" width="12" height="3" rx="0.8" /><path d="M3 5.5v7.5h10V5.5M6.5 8.5h3" /></svg>;
export const IconMethod = (p: P) => <svg {...base} {...p}><path d="M3 2.5h7l3 3v8H3z" /><path d="M5.5 8h5M5.5 10.5h5" /></svg>;
export const IconStatus = (p: P) => <svg {...base} {...p}><path d="M1.5 8h3l1.5-4 3 8 1.5-4h4" /></svg>;
export const IconChevron = (p: P) => <svg {...base} {...p}><path d="M6 4l4 4-4 4" /></svg>;
export const IconLogo = (p: P) => (
  <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" {...p}>
    <rect x="1.5" y="3.5" width="17" height="13" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M10 3.5v13" stroke="var(--color-accent)" strokeWidth="1.8" />
    <path d="M5 7.5h10M5 12.5h10" stroke="currentColor" strokeWidth="1" opacity=".6" />
  </svg>
);
