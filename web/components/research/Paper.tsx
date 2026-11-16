/**
 * Building blocks for the Research tab's papers, laid out like a journal article: a masthead, a metadata column beside
 * the title, a structured abstract, one continuous column of body text, numbered sections, tables with dark header
 * rows, boxed numbered figures, and an author-year reference list. The sheet uses the site's palette (.paper in
 * globals.css). Server-rendered.
 */
import Link from "next/link";
import { IconLogo } from "@/components/icons";
import { paperDate, type Paper } from "@/lib/papers";

/** The paper sheet. `fontClass` carries the serif face's CSS variable from the page. */
export function Sheet({ fontClass, children }: { fontClass: string; children: React.ReactNode }) {
  return (
    <article className={`paper ${fontClass} -mx-4 border-y border-[var(--p-rule)] px-5 pb-14 pt-8 sm:mx-auto sm:max-w-[980px] sm:rounded-lg sm:border sm:px-10 lg:px-14`}>
      {children}
    </article>
  );
}

export function Masthead({ paper }: { paper: Paper }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-6 border-b border-[var(--p-rule)] pb-6">
      <Link href="/research" className="flex items-center gap-3 text-[var(--p-text)]">
        <IconLogo />
        <span className="border-l border-[var(--p-rule)] pl-3 leading-tight">
          <span className="block text-[15px] font-semibold">Matchup DNA</span>
          <span className="block text-[15px] text-[var(--p-muted)]">Research</span>
        </span>
      </Link>
      <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5 border-l border-[var(--p-rule)] pl-4 text-[11px] text-[var(--p-text)]">
        <dt className="uppercase tracking-[0.08em] text-[var(--p-dim)]">Type</dt><dd>Working paper</dd>
        <dt className="uppercase tracking-[0.08em] text-[var(--p-dim)]">Published</dt><dd>{paperDate(paper.date)}</dd>
        <dt className="uppercase tracking-[0.08em] text-[var(--p-dim)]">Number</dt><dd>Matchup DNA WP {paper.number}, v{paper.version}</dd>
      </dl>
    </header>
  );
}

export type MetaItem = { label: string; value: React.ReactNode };

/** The front page: a narrow metadata column at the left and the title block at the right, as in a journal. */
export function FrontMatter({ meta, children }: { meta: MetaItem[]; children: React.ReactNode }) {
  return (
    <div className="mt-10 grid gap-10 lg:grid-cols-[210px_minmax(0,1fr)] lg:gap-12">
      <aside className="order-2 min-w-0 lg:order-1">
        <dl className="grid gap-4 text-[11.5px] leading-snug text-[var(--p-text)]">
          {meta.map((m) => (
            <div key={m.label}>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--p-dim)]">{m.label}</dt>
              <dd className="mt-1">{m.value}</dd>
            </div>
          ))}
        </dl>
      </aside>
      <div className="order-1 min-w-0 lg:order-2">{children}</div>
    </div>
  );
}

export function TitleBlock({ paper, authors, affiliation }: { paper: Paper; authors: string; affiliation: string }) {
  return (
    <div>
      <h1 className="text-[32px] font-normal leading-[1.12] tracking-[-0.015em] sm:text-[42px]">
        {paper.title}<span className="mt-2 block text-[20px] leading-snug text-[var(--p-muted)] sm:text-[24px]">{paper.subtitle}</span>
      </h1>
      <p className="mt-6 text-[17px] text-[var(--p-muted)]">{authors}</p>
      <p className="mt-1 text-[12px] text-[var(--p-dim)]">{affiliation}</p>
    </div>
  );
}

/** A structured abstract under a visible heading: each part starts with its label in bold, as in the journal format. */
export function Abstract({ parts, keywords }: { parts: { label: string; text: React.ReactNode }[]; keywords: string[] }) {
  return (
    <section aria-labelledby="abstract" className="mt-8">
      <h2 id="abstract" className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--p-dim)]">Abstract</h2>
      <div className="mt-3 grid gap-3 text-[15px] leading-[1.65]">
        {parts.map((p) => <p key={p.label}><strong className="font-semibold">{p.label}:</strong> {p.text}</p>)}
      </div>
      <p className="mt-6 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--p-dim)]">Keywords</p>
      <p className="mt-1 text-[13px] font-semibold text-[var(--p-muted)]">{keywords.join(", ")}</p>
    </section>
  );
}

export function Body({ children }: { children: React.ReactNode }) {
  return <div className="mt-12 grid gap-12">{children}</div>;
}

export function Section({ id, number, title, children }: { id: string; number?: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="grid scroll-mt-24 gap-5">
      <h2 id={`${id}-h`} className="text-[24px] font-normal leading-tight text-[var(--p-head)] sm:text-[27px]">
        {number && <span className="mr-3">{number}</span>}{title}
      </h2>
      {children}
    </section>
  );
}

export function Subsection({ number, title, children }: { number: string; title: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-4">
      <h3 className="text-[19px] font-normal leading-tight text-[var(--p-text)]">
        <span className="mr-2.5">{number}</span>{title}
      </h3>
      {children}
    </div>
  );
}

/** Body prose: serif, justified, one continuous column (about 95 characters a line at full width), each paragraph after
 *  the first indented, as in a single-column preprint. */
export function Cols({ children }: { children: React.ReactNode }) {
  return <div className="cols serif text-[17px] leading-[1.75]">{children}</div>;
}

/** A display equation, centred, with its number at the right. */
export function Eq({ number, children }: { number: number | string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4 overflow-x-auto py-1" role="math">
      <p className="serif min-w-0 flex-1 whitespace-nowrap text-center text-[17px] italic">{children}</p>
      <span className="serif shrink-0 text-[15px]">({number})</span>
    </div>
  );
}

/** A boxed figure with its label and caption below, as in the journal format. */
export function Figure({ number, caption, children }: { number: number | string; caption: React.ReactNode; children: React.ReactNode }) {
  return (
    <figure className="m-0 border border-[var(--p-rule-strong)] px-4 pb-4 pt-6 sm:px-7">
      {children}
      <figcaption className="mt-6 text-[12.5px] leading-snug">
        <span className="block text-[11px] font-semibold uppercase tracking-[0.08em]">Figure {number}</span>
        <span className="text-[var(--p-muted)]">{caption}</span>
      </figcaption>
    </figure>
  );
}

export type Align = "left" | "right" | "center";

/** A table with its caption above and a dark header row, as in the journal format. */
export function Table({ number, caption, head, rows, align, note }: {
  number: number | string; caption: React.ReactNode; head: string[]; rows: React.ReactNode[][]; align?: Align[]; note?: React.ReactNode;
}) {
  const side = (i: number) => ({ left: "text-left", right: "text-right", center: "text-center" })[align?.[i] ?? (i === 0 ? "left" : "right")];
  return (
    <figure className="m-0 grid gap-2.5">
      <figcaption className="text-[12.5px] leading-snug">
        <span className="font-semibold uppercase tracking-[0.06em]">Table {number}</span>{" "}
        <span className="text-[var(--p-muted)]">{caption}</span>
      </figcaption>
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`Table ${number}`}>
        <table className="serif w-full min-w-[520px] border-collapse border border-[var(--p-rule)] text-[14px]">
          <thead>
            <tr className="bg-[var(--p-th)] text-[var(--p-text)]">
              {head.map((h, i) => <th key={h} scope="col" className={`px-3.5 py-2.5 font-sans text-[13px] font-medium ${side(i)}`}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri} className="border-t border-[var(--p-rule)]">
                {r.map((c, i) => <td key={i} className={`whitespace-nowrap border-l border-[var(--p-rule)] px-3.5 py-2 first:border-l-0 ${side(i)}`}>{c}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {note && <p className="text-[12px] leading-snug text-[var(--p-dim)]">{note}</p>}
    </figure>
  );
}

/** An inline author-year citation linking to the reference list. */
export function Cite({ id, children }: { id: string; children: React.ReactNode }) {
  return <a href={`#ref-${id}`} className="ref">{children}</a>;
}

/** Back matter in the journal's style: short headed statements. */
export function Statements({ items }: { items: { title: string; text: React.ReactNode }[] }) {
  return (
    <div className="grid gap-8">
      {items.map((s) => (
        <section key={s.title} className="grid gap-2">
          <h2 className="text-[22px] font-normal text-[var(--p-head)]">{s.title}</h2>
          <div className="serif text-[15px] leading-[1.65]">{s.text}</div>
        </section>
      ))}
    </div>
  );
}

export function References({ items }: { items: { id: string; text: React.ReactNode }[] }) {
  return (
    <section aria-labelledby="references-h" className="grid gap-4 border-t border-[var(--p-rule)] pt-8">
      <h2 id="references-h" className="text-[22px] font-normal">References</h2>
      <ol className="serif grid gap-2.5 text-[14px] leading-snug">
        {items.map((r) => (
          <li key={r.id} id={`ref-${r.id}`} className="scroll-mt-24 pl-5 -indent-5">{r.text}</li>
        ))}
      </ol>
    </section>
  );
}

/** The running footer of the sheet. */
export function Footer({ paper }: { paper: Paper }) {
  return (
    <footer className="mt-12 flex flex-wrap justify-between gap-3 border-t border-[var(--p-rule)] pt-4 text-[11px] text-[var(--p-dim)]">
      <span>Matchup DNA Research · Working paper {paper.number}</span>
      <span>Not peer reviewed · version {paper.version}</span>
    </footer>
  );
}
