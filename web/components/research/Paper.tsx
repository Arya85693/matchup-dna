/**
 * Building blocks for the Research tab's papers, laid out as a plain single-column working paper: a title block, an
 * abstract, numbered sections, tables with a light header row, boxed figures with captions below, and an author-year
 * reference list. One serif face throughout. The same markup prints to the PDF (print rules in globals.css,
 * web/scripts/paper-pdf.mjs). Server-rendered.
 */
import Link from "next/link";
import { paperDate, type Paper } from "@/lib/papers";

/** The paper sheet. `fontClass` carries the serif face's CSS variable from the page. */
export function Sheet({ fontClass, children }: { fontClass: string; children: React.ReactNode }) {
  return (
    <article className={`paper serif ${fontClass} -mx-4 border-y border-[var(--p-rule)] px-5 pb-14 pt-8 sm:mx-auto sm:max-w-[900px] sm:rounded-lg sm:border sm:px-10 lg:px-16`}>
      {children}
    </article>
  );
}

/** A small link back to the Research tab; not printed. */
export function BackLink() {
  return (
    <p className="print-hide text-[13px] text-[var(--p-muted)]">
      <Link href="/research" className="ref">← Research</Link>
    </p>
  );
}

export function TitleBlock({ paper, author, affiliation }: { paper: Paper; author: string; affiliation: string }) {
  return (
    <header className="title-block mt-8 text-center">
      <h1 className="text-[34px] font-semibold leading-[1.15] tracking-[-0.01em] sm:text-[40px]">{paper.title}</h1>
      <p className="mt-3 text-[19px] leading-snug text-[var(--p-muted)] sm:text-[21px]">{paper.subtitle}</p>
      <p className="mt-7 text-[17px]">{author}</p>
      <p className="mt-1 text-[14px] text-[var(--p-muted)]">{affiliation}</p>
      <p className="mt-4 text-[13px] text-[var(--p-dim)]">
        {paperDate(paper.date)} · Version {paper.version} · Working paper, not peer reviewed
      </p>
    </header>
  );
}

export function Abstract({ children, keywords }: { children: React.ReactNode; keywords: string[] }) {
  return (
    <section aria-labelledby="abstract" className="abstract mx-auto mt-10 max-w-[680px]">
      <h2 id="abstract" className="text-center text-[15px] font-semibold uppercase tracking-[0.08em]">Abstract</h2>
      <div className="mt-3 text-justify text-[15.5px] leading-[1.6]">{children}</div>
      <p className="mt-4 text-[14px] text-[var(--p-muted)]"><i>Keywords:</i> {keywords.join(", ")}</p>
    </section>
  );
}

export function Body({ children }: { children: React.ReactNode }) {
  return <div className="paper-body mt-12 grid gap-11">{children}</div>;
}

export function Section({ id, number, title, className = "", children }: {
  id: string; number?: string; title: string; className?: string; children: React.ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className={`grid scroll-mt-24 gap-5 ${className}`}>
      <h2 id={`${id}-h`} className="text-[23px] font-semibold leading-tight sm:text-[25px]">
        {number && <span className="mr-3">{number}</span>}{title}
      </h2>
      {children}
    </section>
  );
}

export function Subsection({ number, title, children }: { number: string; title: string; children: React.ReactNode }) {
  return (
    <div className="subsection grid gap-4">
      <h3 className="text-[18px] font-semibold leading-tight">
        <span className="mr-2.5">{number}</span>{title}
      </h3>
      {children}
    </div>
  );
}

/** Body prose: justified, one column, each paragraph after the first indented. */
export function Cols({ children }: { children: React.ReactNode }) {
  return <div className="cols text-[17px] leading-[1.7]">{children}</div>;
}

/** A display equation, centred on the text column, with its number at the right. Function names (logit, σ) are set
 *  upright by the page and variables in italic, as in typeset mathematics. */
export function Eq({ number, children }: { number: number | string; children: React.ReactNode }) {
  return (
    <div className="eq grid grid-cols-[3rem_minmax(0,1fr)_3rem] items-center overflow-x-auto py-1.5" role="math">
      <span aria-hidden="true" />
      <p className="whitespace-nowrap text-center text-[17px] [word-spacing:0.12em]">{children}</p>
      <span className="text-right text-[15px]">({number})</span>
    </div>
  );
}

/** A built-up fraction for display equations. */
export function Frac({ num, den }: { num: React.ReactNode; den: React.ReactNode }) {
  return (
    <span className="mx-1 inline-flex flex-col items-stretch text-center align-middle leading-[1.3]">
      <span className="px-1.5 pb-1">{num}</span>
      <span className="px-1.5 pt-0.5" style={{ borderTop: "1px solid currentColor" }}>{den}</span>
    </span>
  );
}

/** A figure with its label and caption below, set between hairline rules rather than in a box. */
export function Figure({ number, caption, children }: { number: number | string; caption: React.ReactNode; children: React.ReactNode }) {
  return (
    <figure className="m-0 border-y border-[var(--p-rule)] px-1 pb-4 pt-5 sm:px-2">
      {children}
      <figcaption className="mt-4 text-[14px] leading-snug">
        <span className="font-semibold">Figure {number}.</span>{" "}
        <span className="text-[var(--p-muted)]">{caption}</span>
      </figcaption>
    </figure>
  );
}

export type Align = "left" | "right" | "center";
/** A header that spans columns `from` to `to` (inclusive), drawn with a short rule beneath it. */
export type Span = { label: React.ReactNode; from: number; to: number };
/** A row group: starts before row `at`, with an optional label row (e.g. the tour). */
export type RowGroup = { at: number; label?: React.ReactNode };

/** A table in the conventional academic (booktabs) style: caption above, rules only at the top, under the header and
 *  at the bottom, optional spanning headers over column groups, optional labelled row groups, and numbers in tabular
 *  figures, right-aligned so that decimals line up. Short tables are kept on one page when printed; long ones may
 *  break between rows, and the browser repeats the header. */
export function Table({ number, caption, head, rows, align, note, spans, groups, keep }: {
  number: number | string; caption: React.ReactNode; head: React.ReactNode[]; rows: React.ReactNode[][]; align?: Align[];
  note?: React.ReactNode; spans?: Span[]; groups?: RowGroup[]; keep?: boolean;
}) {
  const side = (i: number) => ({ left: "text-left", right: "text-right", center: "text-center" })[align?.[i] ?? (i === 0 ? "left" : "right")];
  const groupAt = new Map((groups ?? []).map((g) => [g.at, g]));
  const indent = (groups ?? []).some((g) => g.label);  // labelled groups: indent the row labels beneath them
  const spanCells: React.ReactNode[] = [];
  for (let i = 0; i < head.length;) {
    const s = spans?.find((x) => x.from === i);
    if (s) {
      spanCells.push(
        <th key={i} scope="colgroup" colSpan={s.to - s.from + 1} className="px-3 pb-0 pt-2 text-center font-semibold">
          <span className="block border-b border-[var(--p-rule-strong)] pb-1">{s.label}</span>
        </th>);
      i = s.to + 1;
    } else {
      spanCells.push(<th key={i} aria-hidden="true" />);
      i += 1;
    }
  }
  return (
    <figure className={`ptable m-0 grid gap-2.5 ${keep ?? rows.length + (groups?.length ?? 0) <= 18 ? "keep" : ""}`}>
      <figcaption className="text-[14px] leading-snug">
        <span className="font-semibold">Table {number}.</span>{" "}
        <span className="text-[var(--p-muted)]">{caption}</span>
      </figcaption>
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`Table ${number}`}>
        <table className="w-full min-w-[520px] border-collapse border-y-[1.5px] border-[var(--p-text)] text-[14.5px]">
          <thead>
            {spans && <tr>{spanCells}</tr>}
            <tr className="border-b border-[var(--p-text)]">
              {head.map((h, i) => <th key={i} scope="col" className={`px-3 pb-1.5 pt-2 align-bottom font-semibold leading-tight ${side(i)}`}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => {
              const g = groupAt.get(ri);
              const gap = g && ri > 0 ? "pt-3" : ri === 0 ? "pt-2" : "pt-[3px]";
              return [
                g?.label ? (
                  <tr key={`g${ri}`} className="group-row">
                    <th scope="colgroup" colSpan={head.length} className={`px-3 pb-0.5 text-left font-semibold italic ${ri > 0 ? "pt-3" : "pt-2"}`}>{g.label}</th>
                  </tr>
                ) : null,
                <tr key={ri} className={g?.label ? "" : g ? "group-start" : ""}>
                  {r.map((c, i) => (
                    <td key={i} className={`whitespace-nowrap px-3 ${ri === rows.length - 1 ? "pb-2" : "pb-[3px]"} tabular-nums ${g?.label ? "pt-[3px]" : gap} ${side(i)} ${indent && i === 0 ? "pl-6" : ""}`}>{c}</td>
                  ))}
                </tr>,
              ];
            })}
          </tbody>
        </table>
      </div>
      {note && <p className="text-[13px] leading-snug text-[var(--p-dim)]">{note}</p>}
    </figure>
  );
}

/** An inline author-year citation linking to the reference list. */
export function Cite({ id, children }: { id: string; children: React.ReactNode }) {
  return <a href={`#ref-${id}`} className="ref">{children}</a>;
}

/** End matter: short headed statements (availability, disclosure, version history). */
export function Statements({ items }: { items: { title: string; text: React.ReactNode }[] }) {
  return (
    <div className="statements grid gap-6">
      {items.map((s) => (
        <section key={s.title} className="grid gap-2">
          <h3 className="text-[18px] font-semibold">{s.title}</h3>
          <div className="text-[15.5px] leading-[1.6]">{s.text}</div>
        </section>
      ))}
    </div>
  );
}

export function References({ items }: { items: { id: string; text: React.ReactNode }[] }) {
  return (
    <section aria-labelledby="references-h" className="references grid gap-4">
      <h2 id="references-h" className="text-[23px] font-semibold sm:text-[25px]">References</h2>
      <ol className="grid gap-2.5 text-[15px] leading-snug">
        {items.map((r) => (
          <li key={r.id} id={`ref-${r.id}`} className="scroll-mt-24 pl-6 -indent-6 [overflow-wrap:anywhere]">{r.text}</li>
        ))}
      </ol>
    </section>
  );
}

/** The closing line of the sheet; the PDF prints its own running footer instead. */
export function Footer({ paper, author }: { paper: Paper; author: string }) {
  return (
    <footer className="print-hide mt-12 flex flex-wrap justify-between gap-3 border-t border-[var(--p-rule)] pt-4 text-[13px] text-[var(--p-dim)]">
      <span>{author} · {paper.title}</span>
      <span>Working paper, version {paper.version} · not peer reviewed</span>
    </footer>
  );
}
