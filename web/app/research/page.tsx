import type { Metadata } from "next";
import Link from "next/link";
import { EvidenceTag } from "@/components/lab/parts";
import { PageHeader } from "@/components/ui";
import { PAPERS, paperDate } from "@/lib/papers";

export const metadata: Metadata = {
  title: "Research",
  description: "Working papers from Matchup DNA: questions about tennis tested against the data, written up in full.",
};

export default function Research() {
  return (
    <>
      <PageHeader title="Research"
                  description="Questions about tennis tested against the data and written up in full, with their methods, figures and limits. Each paper says whether its analysis was fixed in advance." />

      <ol className="grid max-w-[860px] gap-5">
        {PAPERS.map((p) => (
          <li key={p.slug}>
            <Link href={`/research/${p.slug}`}
                  className="group block rounded-lg border border-border bg-card px-6 py-6 transition-colors hover:border-border-strong hover:bg-card-hover sm:px-8 sm:py-7">
              <p className="flex flex-wrap items-center gap-2.5 text-[12px] text-muted">
                Working paper · {paperDate(p.date)} · {p.readingMinutes} min read <EvidenceTag kind={p.evidence} />
              </p>
              <h2 className="mt-3 text-[22px] font-semibold leading-tight text-text sm:text-[26px]">{p.title}</h2>
              <p className="mt-1.5 text-[15px] text-muted">{p.subtitle}</p>
              <p className="mt-4 max-w-[72ch] text-[14px] leading-relaxed text-muted">{p.abstract}</p>
              <p className="mt-5 text-[13px] font-medium text-accent">
                Read the paper <span aria-hidden="true" className="inline-block transition-transform group-hover:translate-x-0.5">→</span>
              </p>
            </Link>
          </li>
        ))}
      </ol>

      <p className="mt-10 max-w-[72ch] text-[13px] text-dim">
        Papers marked post-hoc were run after the data had been seen and are descriptive only; none of them changes a
        frozen model or the live forecast record. How the forecasts themselves are made is on the{" "}
        <Link href="/methodology" className="link">Methodology</Link> page.
      </p>
    </>
  );
}
