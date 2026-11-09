import type { HistoryPlayer } from "@/lib/contract";

/** The attribution a freely licensed (Wikimedia Commons) photo requires: author, licence and source. */
export function PhotoCredit({ credit, className = "" }: { credit: HistoryPlayer["photo_credit"]; className?: string }) {
  if (!credit) return null;
  return (
    <p className={`text-[11px] leading-snug text-dim ${className}`}>
      Photo: {credit.author},{" "}
      {credit.license_url
        ? <a href={credit.license_url} className="underline decoration-border-strong underline-offset-2 hover:text-muted" rel="license noreferrer" target="_blank">{credit.license}</a>
        : credit.license}
      , via{" "}
      <a href={credit.source} className="underline decoration-border-strong underline-offset-2 hover:text-muted" rel="noreferrer" target="_blank">Wikimedia Commons</a>
    </p>
  );
}
