# Originality, citation and attribution audit: Working Paper 1, version 3.0

"Do Players Choke in Big Matches?" (16 November 2026). Audit run on 16 November 2026 against the PDF
`web/public/research/big-matches.pdf`, which is byte-identical to the downloaded copy. The code audited is commit
`c051088`, with a clean working tree.

This audit is separate from `AUDIT.md`, which covered statistical errors in v2.2. This one covers four things:
- whether any text is copied or too closely paraphrased;
- whether the references and the claims attributed to them are correct;
- whether the research question and methods are original;
- whether code and data are properly credited and the results reproduce from the committed code.

## How far this audit can be trusted

- **No plagiarism database.** I had no access to Turnitin, iThenticate or any other plagiarism database. The text
  screen used:
  - 46 quoted exact-phrase web searches;
  - word n-gram matching (runs of 4 and 5 words) of the full body text against 11 cited abstracts and 35 reference
    pages, including the relevant Wikipedia method pages, Tennis Abstract, Tango and FiveThirtyEight.

  "No match" only means no indexed page turned up. No similarity percentage is given, because none could be measured
  honestly. This audit does not certify the paper as plagiarism-free.
- **Mostly abstracts, not full texts.** Elsevier, APA, JASA, De Gruyter and JSTOR blocked automated access. Claims were
  checked against full text only for:
  - Efron & Morris (1975);
  - Cramer (1977);
  - Jetter & Walker (2015), via the IZA discussion-paper version;
  - Kovalchik & Reid (2020);
  - Gorgi et al. (2018 discussion paper).

  The rest were checked against abstracts and publisher or Crossref records.
- **Literature search.** It covered web search, RePEc/IDEAS, OpenAlex, Semantic Scholar, SABR and the Tennis Abstract
  blog. Google Scholar, SSRN and the MIT Sloan archive could not be queried directly, and theses were not searched
  systematically. Relevant work may have been missed.
- **Model-generated code.** No automated tool can rule out that a model reproduced a snippet of public code from its
  training data. The check here was manual reading for copied code and attribution markers.

## Findings by category

| Class | Count | Items |
|---|---|---|
| Confirmed concern | 4 | C1 the closest prior work, Sackmann's Tennis Abstract analyses, is not cited. C2 the surface-blended Elo method (Tennis Abstract's 50/50 blend) is not credited. C3 the paper does not disclose AI assistance. C4 the split-half confidence intervals cannot be reproduced exactly. |
| Potential concern | 7 | P1 the Jetter & Walker summary leaves out its "clutch-player" finding. P2 relevant academic work is uncited (Gorgi et al.; Kovalchik & Reid; Kovalchik & Ingram; Bijleveld et al.). P3 the methods come from the baseball clutch literature (Tango et al.; Birnbaum; James), which is uncited. P4 the Cohen-Zada et al. sentence is a close paraphrase of its abstract. P5 so is the Klaassen & Magnus sentence. P6 the data are read from an unofficial mirror. P7 the repository has no code licence. |
| Verified acceptable | — | No copied text found. All 19 references exist, and all 14 printed DOIs resolve to the cited work. Every attributed claim is accurate or largely accurate. No third-party code was found. The licences of the dependencies and fonts are satisfied. Sackmann credit and licence appear in the paper and on the site. Every table and figure is generated from the analysis outputs. All four analysis scripts reproduce the paper from the committed code, apart from C4. The robustness, player and out-of-sample outputs are byte-identical, and the tests pass. |
| Unable to verify | — | Cramer (1977) page numbers. Paserman's (2023) exact gender comparison (full text blocked). Whether the mirror matches Sackmann's final upstream commit. ResearchGate item 395539755 ("Revisiting Clutch Performance Among Elite Players in Tennis"), blocked. Whether the repository is public. |

---

## 1. Text originality

**No confirmed copying.** None of the 46 exact-phrase searches matched another page. No run of 5 or more words is
shared with any cited abstract or reference page, apart from bibliography entries, proper nouns and standard terms.

| # | Location | Possible source | Overlap | Class | Recommended fix |
|---|---|---|---|---|---|
| P4 | §2, p. 2: "Cohen-Zada et al. (2017) report that men's performance falls at the more important stages of matches, while the evidence for women is mixed and the declines they do find are smaller." | Abstract, [IDEAS](https://ideas.repec.org/a/eee/joepsy/v61y2017icp176-190.html): men "consistently choke"; for women "the results are mixed"; women's drop in "the more crucial stages of the match" is about half as large. | Three clauses in the same order, with words swapped ("crucial"→"important", "results"→"evidence"). No run is longer than 4 words. | Potential, low | "In Cohen-Zada et al. (2017), men perform worse when more is at stake within a match; the results for women are inconsistent, and where women do decline the drop is about half the size of men's." |
| P5 | §2, p. 2: the Klaassen & Magnus sentence ("…not exactly independent and identically distributed (servers win slightly fewer important points, and winning the previous point helps), but that the departures are small enough for an i.i.d. model to remain a good approximation"). | Abstract, [DOI 10.1198/016214501753168217](https://doi.org/10.1198/016214501753168217): not i.i.d.; the previous point helps; servers struggle on important points; deviations small, so i.i.d. is "a good approximation". | It follows the abstract's argument step by step, sharing "winning the previous point" and "a good approximation". "Independent and identically distributed" is a technical term and their title. | Potential, low (borderline acceptable) | "Klaassen and Magnus (2001) reject the i.i.d. hypothesis for Wimbledon points (servers do worse on important points, and a point won raises the chance of winning the next) but find the effects small enough that i.i.d. models are usually adequate." |
| — | §2: González-Díaz et al., Paserman, Harris et al., Jetter & Walker, Efron & Morris, Brown, Kovalchik, Baumeister, Cramer | Their abstracts, and the SABR full text for Cramer | Shared words are technical terms ("double faults and unforced errors", "important points") or title echoes. Sentence structure differs. | Acceptable | None needed. |
| — | §3.3–3.7, Appendix B | Wikipedia method pages; Tango; Tennis Abstract; FiveThirtyEight | No shared run of 4 or more words, apart from the cited "Spearman–Brown formula (Spearman, 1910; Brown, 1910)". | Acceptable | None. |
| — | §3.1 and B.1, data description | Sackmann README and data dictionary | "other tour-level events" (the gloss for code A) and event names only. | Acceptable | None. |

The full list of searched phrases and the n-gram script are in the session scratchpad. Ask for them if you want them
kept.

## 2. Citation verification

"Abstract" means the claim was checked against the abstract only.

| Reference | Metadata | Claim in the paper | Claim status | Notes and evidence |
|---|---|---|---|---|
| Baumeister (1984), JPSP 46(3) 610–620, [doi](https://doi.org/10.1037/0022-3514.46.3.610) | Verified | Competition, money or an audience worsened skilled performance | Accurate (abstract) | The abstract lists implicit competition, a cash incentive and audience-induced pressure. |
| Brown, W. (1910), BJP 3(3) 296–322, [doi](https://doi.org/10.1111/j.2044-8295.1910.tb00207.x) | Verified | Half of the Spearman–Brown formula | Accurate | The standard attribution. |
| Brown, L. D. (2008), AOAS 2(1) 113–152, [doi](https://doi.org/10.1214/07-AOAS138) | Verified | Compared empirical Bayes methods for within-season batting averages | Accurate (abstract) | Under APA ordering, "Brown, L. D." should come before "Brown, W." |
| Cohen-Zada et al. (2017), JEP 61 176–190, [doi](https://doi.org/10.1016/j.joep.2017.04.005) | Verified | Men decline at important stages; women mixed and smaller | Accurate (abstract) | Close paraphrase, see P4. |
| Cramer (1977), BRJ 6 | Partly verified | 1969 clutch hitting did not predict 1970 | Accurate (full text) | r² = .038 (NL) and .055 (AL). Pages not verified. Add the [SABR URL](https://sabr.org/journal/article/do-clutch-hitters-exist/). |
| Efron (1979), Ann. Stat. 7(1) 1–26, [doi](https://doi.org/10.1214/aos/1176344552) | Verified | Bootstrap | Appropriate | The general citation. The cluster and parametric variants are later developments, which is fine. |
| Efron & Morris (1975), JASA 70(350) 311–319, [doi](https://doi.org/10.1080/01621459.1975.10479864) | Verified | Shrinkage predicted the rest of the season with "less than half the error" | Accurate, but understated (full text) | The total squared error ratio is 0.285 (5.01 against 17.56, transformed scale). "Half" matches the abstract. Better to say "mean squared error". |
| Elo (1978), Arco, New York | Verified | Elo ratings | Appropriate | First edition 1978; ISBN 0-668-04721-6. |
| González-Díaz, Gossner & Rogers (2012), JEBO 84(3) 767–781, [doi](https://doi.org/10.1016/j.jebo.2012.09.021) | Verified | Persistent player differences on important points at the US Open, linked to career success | Accurate (abstract) | — |
| Harris, Vine, Eysenck & Wilson (2021), PSE 56 101987, [doi](https://doi.org/10.1016/j.psychsport.2021.101987) | Verified | Double faults and unforced errors more likely as pressure rises | Accurate (abstract) | The study combines the two into one "performance error" outcome. |
| Holm (1979), SJS 6(2) 65–70 | Verified (secondary records) | Holm correction | Appropriate | No DOI. Add [JSTOR 4615733](https://www.jstor.org/stable/4615733), taken from bibliographic records; the JSTOR page itself did not load. |
| Jetter & Walker (2015), JEBO 119 96–108, [doi](https://doi.org/10.1016/j.jebo.2015.07.017) | Verified (title correct) | Recent wins predict the next match | Accurate but incomplete (full working-paper text) | Each extra win in the last ten matches adds about 3 points of win probability, for both men and women. The paper leaves out their clutch-player finding: top players do better at Grand Slams. That finding bears directly on this paper's question. See P1. |
| Klaassen & Magnus (2001), JASA 96(454) 500–509, [doi](https://doi.org/10.1198/016214501753168217) | Verified | Not i.i.d., but i.i.d. is a good approximation | Accurate (abstract) | Close paraphrase, see P5. |
| Kovalchik (2016), JQAS 12(3) 127–138, [doi](https://doi.org/10.1515/jqas-2015-0059) | Verified | Elo among the more accurate published methods for ATP | Accurate (abstract) | Ranking-based regression and FiveThirtyEight's Elo were the most accurate of 11 models. |
| Lakens (2017), SPPS 8(4) 355–362, [doi](https://doi.org/10.1177/1948550617697177) | Verified | "In the spirit of" equivalence tests | Appropriate | The hedge is correct: the bounds come from simulation, not from two one-sided tests. |
| Papke & Wooldridge (1996), JAE 11(6) 619–632 | Verified; DOI missing | Fractional logit | Appropriate | Add [doi:10.1002/(SICI)1099-1255(199611)11:6<619::AID-JAE418>3.0.CO;2-1](https://doi.org/10.1002/(SICI)1099-1255(199611)11:6%3C619::AID-JAE418%3E3.0.CO;2-1). |
| Paserman (2023), JEBO 212 590–609, [doi](https://doi.org/10.1016/j.jebo.2023.05.042) | Verified (the title's "?" is correct) | Both sexes play less aggressively on important points | Accurate (abstract) | Optional: add that he argues this lowers their chances of winning. The exact gender comparison in the 2023 full text was not verified. |
| Sackmann (2026), tennis_atp / tennis_wta | Partly verified | Data source, CC BY-NC-SA 4.0 | Accurate | The original repositories return 404 today, as the paper says. The mirror exists (created 25 June 2026) and keeps Sackmann's READMEs and licence, but it is unofficial and not endorsed. Use Sackmann's own attribution title (correction 8). |
| Spearman (1910), BJP 3(3) 271–295, [doi](https://doi.org/10.1111/j.2044-8295.1910.tb00206.x) | Verified | Half of the Spearman–Brown formula | Accurate | — |

**No invented references, no wrong years or co-authors, and no two works run together.** Version 2's misdescriptions,
recorded in `AUDIT.md` item 17, have been fixed.

## 3. Research originality

### Closest existing work

| Work | Question, data and method | Finding | How WP1 differs |
|---|---|---|---|
| **Sackmann, J. (2025). "Matteo Berrettini and Best-of-Five Puzzles." Tennis Abstract**, [link](https://www.tennisabstract.com/blog/2025/01/17/matteo-berrettini-and-best-of-five-puzzles/) | Is there a persistent best-of-five (Slam) skill? ATP Slam matches since 2000; actual wins against Elo-expected wins; persistence checked with career halves and odd/even matches. | "Virtually zero correlation": mostly luck, Djokovic and Nadal possibly excepted. | **Same template: Elo residuals plus a split-half test.** WP1 adds the WTA, a defined big-match set, a big-minus-regular contrast, simulation nulls with Holm correction, an out-of-sample test and power bounds. |
| **Sackmann, J. (2019). "Dominic Thiem, Tennys Sandgren, and Playing Your Way In." Tennis Abstract**, [link](https://www.tennisabstract.com/blog/2019/02/20/dominic-thiem-tennys-sandgren-and-playing-your-way-in/) | ATP top 100; wins by round, finals included, against Elo expectation. | 29 of 1,043 player-categories significant at 5%, about what chance gives. Monfils's poor finals record is consistent with chance. | Same question and baseline, done descriptively and for the ATP only. |
| Sackmann, J. (2021). "How Much Does Naomi Osaka Raise Her Game?" Tennis Abstract, [link](https://www.tennisabstract.com/blog/?p=4201) | Second-week Slam results against Elo for women who won a Slam. | Osaka, Serena Williams and Seles beat Elo. | The "big-match players exist" side, for the WTA. WP1 should address it. |
| Jetter & Walker (2015), JEBO (cited) | More than 100,000 matches; logits with ranking controls; top players interacted with Grand Slam events. | Hot hand; top players do better at Slams ("clutch-player effect"). | A group effect for top-ranked players, not an individual trait, and with no out-of-sample test. |
| Gorgi, Koopman & Lit (2019), JRSS A 182(4) 1393–1409, [doi](https://doi.org/10.1111/rssa.12464); [discussion paper](https://papers.tinbergen.nl/18009.pdf) | Dynamic ATP model with a Grand Slam amplification parameter γ on the strength gap. | γ is not significantly different from 1: the Grand Slam effect is "most likely a statistical effect" of format. | Essentially a tour-level calibration test for ATP big matches. It anticipates WP1's ATP null; the WTA is not covered. |
| González-Díaz et al. (2012), JEBO (cited) | Point-level data, US Open. | Persistent differences in critical ability. | Point-level. Its persistence contrasts with WP1's weak match-level persistence, which deserves a sentence. |
| Kovalchik, S. & Reid, M. (2020). "Measuring clutch performance in professional tennis." Stat. Applicata–IJAS 30(2) 255–268, [doi](https://doi.org/10.26398/IJAS.0030-011) | Weights serve and return statistics by point importance, using Slam point data. | "Clutch averages" improve prediction. | Point-level, with no persistence or chance-variance test. |
| Kovalchik, S. & Ingram, M. (2016). "Hot heads, cool heads, and tacticians." MIT SSAC, [pdf](https://martiningram.github.io/papers/hot-heads-cool-heads.pdf) | Player random effects for pressure situations, about 3 million points. | Players differ under pressure, and this improves match prediction. | Claims a player-specific pressure effect that helps prediction, which contrasts with WP1's out-of-sample null. Worth discussing. |
| Bijleveld, Custers & Aarts (2011), J. Sports Sci. 29(13), [doi](https://doi.org/10.1080/02640414.2011.604679) | Tennis finals with trophy cues. | Favourites' advantage shrinks in high-prize finals. | A tour-level "favourites fail in finals" result, relevant to WP1's WTA calibration finding. Full text not read. |
| Birnbaum (2005/2008). "Clutch Hitting and the Cramer Test," [SABR](https://sabr.org/?p=76765); James (2004). "Underestimating the Fog," [SABR](https://sabr.org/research/article/underestimating-the-fog/) | Power of persistence tests for clutch hitting; simulated normal talent at given standard deviations. | A null is uninformative without power (James). Bounds on clutch talent (Birnbaum). | **WP1's power-and-bounds design follows Birnbaum's approach.** Neither is cited. |
| Tango, Lichtman & Dolphin (2007). *The Book*, ch. "Clutch" | Observed variance against random variance; regression constants. | — | The source of the variance-ratio and "implied k" ideas. Chapter text not read. |

Also related but less central (records seen, mostly not read in full):
- Lahvička (2014, Applied Economics Letters): favourite-longshot bias by round.
- Gilsdorf & Sukhatme (2008, Applied Economics): WTA prize spreads.
- Brown & Minor (2014, Management Science): spillovers in elimination tournaments.
- Paine (2013, Football Perspective): NFL playoff results against Vegas expectations.
- Cao, Price & Stone (2011): NBA free throws.
- Hickman & Metz (2015): PGA putting.

### Assessment

No study I found answers WP1's question with WP1's combination of methods, so no paper pre-empts it. But the question is
not new. Sackmann's Tennis Abstract analyses already asked it informally, with Elo-expected wins and split-half
persistence, and reached the same answer: mostly luck. Each method component is also established: Cramer and James
(persistence), Tango et al. (variance against chance), Birnbaum (power bounds), and Efron & Morris (shrinkage).

**Supported contributions, all modest:**
1. A formal test on both tours, with a calibrated expectation, a parametric-bootstrap null and multiple-testing
   correction.
2. A chronological out-of-sample log-loss test of whether past big-match records improve an Elo forecast. I found no
   tennis precedent.
3. Simulation-based upper bounds on the size of the trait, applied to tennis.
4. The tour-level WTA finding that the big-match calibration slope is lower, is widening, and gives a small
   out-of-sample gain. I found no WTA precedent; Gorgi et al. tested the ATP case and found nothing.

**Not supported:** calling the question new, or calling WP1 the first test of clutch performance in tennis. The paper
does not currently make either claim, which is right. Describe it on your resume and website as "a pre-specified,
forecast-oriented test of whether big-match records add information to Elo", not as a discovery.

## 4. Code and data attribution checklist

| Item | Status | Evidence |
|---|---|---|
| Third-party code copied into analysis scripts | ✅ None found | Read the four `posthoc_big_match*.py` scripts, `elo.py`, `load.py`, `experiment.py` and `round_aware.py`, and the publisher. There are no external URLs, no "adapted from" notes and no vendored files. Elo, logistic MLE, Holm, the bootstraps and empirical Bayes are written in-house from standard formulas. (See the caveat on model-generated code above.) |
| Python dependencies | ✅ | Python standard library (PSF licence). numpy 2.3.0 (BSD-3). Tests only: scikit-learn (BSD-3). lightgbm (MIT) is not used by this paper. None requires a credit in the paper. |
| Website and PDF dependencies | ✅ | next, react, zod, aws4fetch, tailwindcss (all MIT); playwright (Apache-2.0); @axe-core/playwright (MPL-2.0, dev only). Their licence notices ship inside the packages. No in-paper credit needed. |
| Fonts in the PDF and site | ✅ | Source Serif 4, Geist and IBM Plex Mono, all under the SIL Open Font License, which allows embedding in PDFs. |
| Elo algorithm | ✅ Cited | Elo (1978). |
| **Surface-blended Elo (50/50 overall and surface)** | ❌ **C2, not credited** | `SURFACE_WEIGHT = 0.5` in `matchup_dna/elo.py`. This is the blend Sackmann published in ["An Introduction to Tennis Elo" (2019)](https://www.tennisabstract.com/blog/2019/12/03/an-introduction-to-tennis-elo/). The paper calls it "the project's surface-blended Elo". Add a citation (correction 2). |
| Decaying K-factor `value/(n+5)**0.4` in `elo.py` | ⚠️ Optional | This is FiveThirtyEight's K rule. WP1 uses the fixed K rule (48), so it does not affect the paper. A one-line credit in the code comment is good practice. |
| Variance ratio, "implied k", power bounds | ⚠️ P3 | The ideas come from Tango et al. (2007) and Birnbaum (2005/2008). Cite them (correction 3). |
| Holm, bootstrap, Spearman–Brown, fractional logit, shrinkage | ✅ Cited | — |
| Sackmann credit in the paper | ✅ | §3.1, §7, the reference list and Figure 1. |
| Sackmann credit on the website | ✅ | Site footer (`web/app/layout.tsx:31`) and the paper page. |
| CC BY-NC-SA: attribution | ✅, wording can improve | Use the licensor's title, "Tennis databases, files, and algorithms by Jeff Sackmann / Tennis Abstract", and link the licence (correction 8). |
| CC BY-NC-SA: non-commercial | ✅ for portfolio and resume use | The site says "Non-commercial research. Not betting advice." This holds only while the site carries no ads, paid tiers, sponsorship or betting affiliate links. Recheck if any are added. |
| CC BY-NC-SA: share-alike | ⚠️ Low risk | Raw data are not redistributed (checked: `data/` is untracked, and `big-match.json` holds only aggregate statistics). If any derived match-level file is ever published (for example, ratings), label it CC BY-NC-SA 4.0. Adding a licence note to `big-match.json`'s `sources` is cheap insurance. |
| Data provenance | ⚠️ P6 | The data were read from an unofficial mirror; the README and the paper already say so. File SHA-256 values are recorded, but I could not check that the mirror matches Sackmann's final upstream commit. |
| **Code licence** | ⚠️ P7 | There is no LICENSE file in the repository, so legally the code is all-rights-reserved. Before public release, add a code licence (for example MIT) that explicitly excludes the Sackmann-derived data, which stay CC BY-NC-SA 4.0. |
| **AI-assistance disclosure** | ❌ **C3** | Nothing in the paper, README or docs says that Claude Code helped write the code and text, and the commits carry no co-author lines. Most universities and journals now require disclosure, and a resume reviewer who learns of it later could treat silence as misrepresentation. Add an acknowledgement (correction 1). |

## 5. Result integrity and reproducibility

The rerun used commit `c051088` (clean tree), Python 3.13.7 and numpy 2.3.0, on the same 118 input files. The combined
SHA-256 begins `3910dc82…`. The outputs that existed before the rerun were backed up first.

| Script | Result |
|---|---|
| `posthoc_big_match_players` | ✅ Byte-identical (Tables 6–7). |
| `posthoc_big_match_forecast` | ✅ Identical in every number (Tables 2, 5, A3, A4; Figures 2, 5). Only the provenance fields differ: they now record commit `c051088` with `analysis_code_committed: true`, where the paper's run recorded `4882aa0` with uncommitted code. |
| `posthoc_big_match` | ⚠️ Every number identical except the **split-half 95% intervals** (C4). |
| `posthoc_big_match_robustness` | ✅ Byte-identical, JSON and text (Tables 3, A1, A2, A5–A8; Figures 3, 6). Run time 30 minutes. |
| Unit tests (`tests/test_posthoc_big_match*.py`) | ✅ 32 passed. |

After the comparison, the original output files were put back, so `results/` again matches the committed export. The
rerun's outputs are kept in the session scratchpad.

**Provenance of the published figures.** The SHA-256 of each analysis output on disk before the rerun matches the
hashes recorded in `web/content/research/big-match.json` → `sources`. The page renders every result from that file.
Apart from thresholds and seeds, the page source contains no typed-in result numbers. Nothing in the tables or figures
is copied from another publication: every value traces to an analysis output.

**C4: split-half intervals cannot be reproduced exactly.** `matchup_dna/posthoc_big_match.py:325` loops over
`set(halves[0]) & set(halves[1])`. The player keys are `(tour, id)` tuples, whose string part is hashed with Python's
per-process random seed. So the order of players, and with it which players each bootstrap draw selects, changes from
run to run, even though the numpy seed is fixed. I confirmed this by running with three different `PYTHONHASHSEED`
values:

| Run | ATP 95% interval | WTA 95% interval |
|---|---|---|
| Paper (v3.0) | −0.02 to +0.27 | −0.14 to +0.23 |
| Rerun, today | −0.04 to +0.26 | −0.12 to +0.22 |
| Hash seeds 1 / 2 / 3, unsorted | −0.031/−0.027/−0.016 to +0.257/+0.260/+0.263 | −0.130/−0.131/−0.124 to +0.216/+0.218/+0.213 |
| **Sorted (`sorted(...)`), any hash seed** | **−0.03 to +0.26** | **−0.14 to +0.23** |

The point estimates (r = +0.12 and +0.04) and the conclusions are unaffected, and no other statistic depends on set
order. But §7's statement that the results reproduce "because every random seed is fixed" is not quite true for these
two intervals.
**Fix:** wrap the loop in `sorted(...)`. Then rerun the main analysis and the publisher, which changes the ATP interval
in §4.3 and Figure 4 to −0.03 to +0.26. Then rebuild the PDF.

**§7 is now out of date.** It says the results came from code "not yet committed, on top of commit 4882aa0". The code
is now committed in `c051088`, and that commit reproduces the results apart from C4. Update the sentence (correction 7).

## 6. Recommended manuscript corrections

Ordered by importance. Each one is targeted; no section needs a rewrite.

1. **Disclose AI assistance (C3).** Add before the References:
   > **Acknowledgements.** The analysis code, the website and drafts of the text were developed with the assistance of
   > Claude Code (Anthropic), an AI coding assistant. The author specified the research question and design, reviewed
   > the code and every reported result, and is responsible for the content.

   Adjust the wording so it accurately describes what you did yourself.
2. **Credit the surface-blended Elo (C2).** §3.3, first sentence: "Each player's strength is a surface-blended Elo
   rating, an equal-weight average of the overall and surface-specific ratings following Sackmann (2019), taken at the
   start of each tournament week, …". Add to the references: *Sackmann, J. (2019, December 3). An introduction to tennis
   Elo. Tennis Abstract. https://www.tennisabstract.com/blog/2019/12/03/an-introduction-to-tennis-elo/*
3. **Cite the closest prior work (C1) and the methodological sources (P3).** In §2, after the Cramer, Efron–Morris and
   Brown paragraph:
   > The tennis version of this question has been examined informally: Sackmann (2019) found that players' records in
   > particular rounds, including finals, depart from Elo expectations about as often as chance predicts, and Sackmann
   > (2025) found almost no correlation between the two halves of players' best-of-five records. I extend these
   > analyses to both tours, a defined set of big matches, formal null distributions, out-of-sample forecasts and bounds
   > on effect size. The variance-ratio approach follows Tango, Lichtman and Dolphin (2007), and the power analysis
   > follows Birnbaum (2005), who simulated clutch talent to measure the power of Cramer's test after James (2004)
   > argued that a null result from persistence tests says little without an estimate of power.

   Add the matching references. Birnbaum, P. (2005). Clutch hitting and the Cramer test. *By the Numbers*, 15(1),
   reprinted in the 2008 *Baseball Research Journal*, https://sabr.org/?p=76765 (venue and year checked on that
   page). James, B. (2004). Underestimating the fog. *Baseball Research Journal*, 33. Tango, T., Lichtman, M., &
   Dolphin, A. (2007). *The Book: Playing the Percentages in Baseball*. Potomac Books.
4. **Complete Jetter & Walker (P1).** §2, replace "Jetter and Walker (2015) find that recent wins predict the next
   match," with: "Jetter and Walker (2015) find that recent wins predict the next match and that top-ranked players
   perform better at Grand Slams, a group-level 'clutch' effect;". Optionally add one sentence on Gorgi, Koopman and
   Lit (2019), who found no Grand Slam amplification of the strength gap once the format is modelled, which matches
   the ATP calibration result in §4.1.
5. **Point-level clutch measures (P2, optional).** One sentence in §2: "Kovalchik and Ingram (2016) and Kovalchik and
   Reid (2020) estimate player-specific performance on important points from point-level data." In §5.2, consider
   citing Bijleveld et al. (2011) as one candidate explanation for favourites underperforming in finals.
6. **Rephrase two summaries (P4, P5).** Use the rewrites in the table in section 1.
7. **§7 provenance.** Replace "The results in this version were produced from analysis code that had not yet been
   committed, on top of commit 4882aa0; rerunning … because every random seed is fixed." with: "The analysis code is
   in commit c051088; rerunning the commands on that commit reproduces the reported results, with fixed random
   seeds." Do this only after applying the C4 fix and re-exporting.
8. **Reference details.**
   - Add the Papke & Wooldridge DOI.
   - Add the Holm JSTOR URL.
   - Add the Cramer SABR URL.
   - Put Brown, L. D. (2008) before Brown, W. (1910).
   - Replace the Sackmann entry with: *Sackmann, J. (2026). Tennis databases, files, and algorithms: tennis_atp and
     tennis_wta [Data sets]. Jeff Sackmann / Tennis Abstract. Licensed CC BY-NC-SA 4.0
     (https://creativecommons.org/licenses/by-nc-sa/4.0/). Read from a June 2026 snapshot via the unofficial archive
     mirror github.com/Aneeshers/tennis-sackmann-archive; the original repositories at github.com/JeffSackmann were
     unavailable on 16 November 2026.*
9. **Efron & Morris wording (optional).** "with less than half the mean squared error of the raw averages".

Outside the paper:
- Add a LICENSE for the code (P7).
- Optionally credit FiveThirtyEight in the `k_factor` comment in `elo.py`.
- Recheck the NonCommercial condition if the site ever adds advertising or affiliate links.

## 7. Could not be verified

- Cramer (1977) page numbers. No SABR page gives them.
- The exact gender comparison in Paserman (2023). The full text was blocked, and the abstract reports no gender gap.
- Whether the mirror's June 2026 snapshot matches Sackmann's final upstream commits. The upstream repositories are
  offline.
- ResearchGate item 395539755, "Revisiting Clutch Performance Among Elite Players in Tennis" (blocked). Check it by
  hand: it may be close prior work.
- Whether the GitHub repository is public (`gh` is not installed here).
- Full texts of the uncited related papers, beyond those listed under "How far this audit can be trusted".
