/**
 * Building blocks for the Research tab's papers: numbered sections with anchors, numbered figures and tables with
 * captions, display equations, and a reference list. Server-rendered and in the site's palette; the reading column
 * stays near 70 characters so long prose is comfortable.
 */
import Link from "next/link";
import { EvidenceTag } from "@/components/lab/parts";
import { paperDate, type Paper } from "@/lib/papers";

export function PaperHeader({ paper, authors }: { paper: Paper; authors: string }) {
  return (
    <header className="anim-rise max-w-[760px]">
      <nav aria-label="Breadcrumb" className="text-[12px] text-muted">
        <Link href="/research" className="hover:text-text">Research</Link>
        <span className="px-2 text-dim" aria-hidden="true">/</span>
        <span className="text-text">Working paper</span>
      </nav>
      <p className="mt-10 flex flex-wrap items-center gap-2.5 text-[12px] text-muted">
        Working paper · Version {paper.version} · {paperDate(paper.date)} <EvidenceTag kind={paper.evidence} />
      </p>
      <h1 className="mt-4 text-[32px] font-semibold leading-[1.1] tracking-[-0.02em] sm:text-[44px]">{paper.title}</h1>
      <p className="mt-3 text-[17px] leading-snug text-muted sm:text-[20px]">{paper.subtitle}</p>
      <p className="mt-6 text-[13px] text-text">{authors}</p>
    </header>
  );
}

export function Abstract({ children, keywords }: { children: React.ReactNode; keywords: string[] }) {
  return (
    <section aria-labelledby="abstract" className="mt-12 max-w-[760px] rounded-lg border border-border bg-card px-6 py-6 sm:px-8 sm:py-7">
      <h2 id="abstract" className="text-[12px] font-medium uppercase tracking-[0.12em] text-accent">Abstract</h2>
      <div className="mt-3 text-[15px] leading-[1.75] text-text">{children}</div>
      <p className="mt-5 text-[12px] text-muted"><span className="text-dim">Keywords:</span> {keywords.join(" · ")}</p>
    </section>
  );
}

export type TocEntry = { id: string; number: string; title: string };

export function Contents({ entries }: { entries: TocEntry[] }) {
  return (
    <nav aria-label="Contents" className="mt-10 max-w-[760px]">
      <p className="text-[12px] font-medium uppercase tracking-[0.12em] text-dim">Contents</p>
      <ol className="mt-3 grid gap-x-8 gap-y-1.5 text-[13px] sm:grid-cols-2">
        {entries.map((e) => (
          <li key={e.id}>
            <a href={`#${e.id}`} className="group inline-flex gap-3 text-muted hover:text-text">
              <span className="fig w-5 text-dim group-hover:text-accent">{e.number}</span>{e.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** The reading column: prose sections sit at about 70 characters; figures and tables may use the wider column. */
export function Body({ children }: { children: React.ReactNode }) {
  return <div className="mt-14 grid max-w-[760px] gap-14 text-[15px] leading-[1.8] text-muted">{children}</div>;
}

export function Section({ id, number, title, children }: { id: string; number: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="grid scroll-mt-24 gap-5 border-t border-border pt-10">
      <h2 id={`${id}-h`} className="flex items-baseline gap-4 text-[22px] font-semibold leading-tight text-text sm:text-[24px]">
        <span className="fig text-[15px] font-medium text-accent">{number}</span>{title}
      </h2>
      {children}
    </section>
  );
}

export function Subsection({ number, title, children }: { number: string; title: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-4">
      <h3 className="flex items-baseline gap-3 text-[16px] font-medium text-text">
        <span className="fig text-[13px] text-dim">{number}</span>{title}
      </h3>
      {children}
    </div>
  );
}

export function P({ children }: { children: React.ReactNode }) {
  return <p className="max-w-[68ch]">{children}</p>;
}

/** A display equation with its number at the right. */
export function Eq({ number, children }: { number: number; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4 overflow-x-auto rounded-md border border-border bg-card px-5 py-4" role="math">
      <p className="fig min-w-0 flex-1 whitespace-nowrap text-[14px] text-text">{children}</p>
      <span className="fig shrink-0 text-[12px] text-dim">({number})</span>
    </div>
  );
}

export function Figure({ number, caption, children }: { number: number; caption: React.ReactNode; children: React.ReactNode }) {
  return (
    <figure className="m-0 grid gap-5 rounded-lg border border-border px-5 py-6 sm:px-7">
      {children}
      <figcaption className="max-w-[72ch] text-[13px] leading-relaxed text-muted">
        <span className="font-medium text-text">Figure {number}.</span> {caption}
      </figcaption>
    </figure>
  );
}

export type Align = "left" | "right";

export function Table({ number, caption, head, rows, align, note }: {
  number: number; caption: React.ReactNode; head: string[]; rows: React.ReactNode[][]; align?: Align[]; note?: React.ReactNode;
}) {
  const side = (i: number) => ((align?.[i] ?? (i === 0 ? "left" : "right")) === "right" ? "text-right" : "text-left");
  return (
    <figure className="m-0 grid gap-3">
      <figcaption className="max-w-[72ch] text-[13px] leading-relaxed text-muted">
        <span className="font-medium text-text">Table {number}.</span> {caption}
      </figcaption>
      <div className="overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={`Table ${number}`}>
        <table className="w-full min-w-[480px] text-[13px]">
          <thead>
            <tr className="border-b border-border-strong bg-card text-[11px] uppercase tracking-[0.06em] text-dim">
              {head.map((h, i) => <th key={h} scope="col" className={`px-4 py-2.5 font-medium ${side(i)}`}>{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r, ri) => (
              <tr key={ri}>
                {r.map((c, i) => <td key={i} className={`px-4 py-2.5 ${side(i)} ${i === 0 ? "text-text" : "fig whitespace-nowrap text-[12px] text-muted"}`}>{c}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {note && <p className="text-[12px] leading-relaxed text-dim">{note}</p>}
    </figure>
  );
}

/** An inline citation that links to its entry in the reference list. */
export function Cite({ id, children }: { id: string; children: React.ReactNode }) {
  return <a href={`#ref-${id}`} className="text-text underline decoration-border-strong underline-offset-2 hover:decoration-accent">{children}</a>;
}

export function References({ items }: { items: { id: string; text: React.ReactNode }[] }) {
  return (
    <ol className="grid gap-3 text-[13px] leading-relaxed">
      {items.map((r) => (
        <li key={r.id} id={`ref-${r.id}`} className="scroll-mt-24 pl-6 -indent-6">{r.text}</li>
      ))}
    </ol>
  );
}
