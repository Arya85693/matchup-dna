# Change log — working paper 1, version 3.1 → 4.0 (16 November 2026)

These are the corrections that `ATTRIBUTION.md` left for a separate step, plus two wording errors found in an external
review.

- **Split-half intervals made deterministic (audit C4).** `matchup_dna/posthoc_big_match.py` now iterates over
  `sorted(...)` players. Before, the order of the bootstrap draws depended on `PYTHONHASHSEED`.
  - Rerun under hash seeds 1 and 7, the main analysis gave byte-identical output.
  - Against v3.1, only the split-half interval bounds changed: ATP −0.02 to +0.27 → **−0.03 to +0.26**; WTA −0.143 to
    +0.228 → −0.138 to +0.226, still −0.14 to +0.23 when rounded. r and Spearman–Brown differ only in the 16th
    decimal place.
  - The robustness, player and forecast scripts were not rerun. They do not use this function, and the audit found
    their outputs byte-identical on rerun.
  - The publisher re-exported `big-match.json` and confirmed every headline figure. The 32 analysis tests pass.
- **§7 reproducibility statement.** It no longer refers to uncommitted code on `4882aa0`. It now says the code is in
  the same commit as the paper, with fixed seeds and no dependence on set ordering.
- **§4.7 format sentence corrected.** It said "ATP big matches are mostly best of five", which was wrong: 22% of ATP
  big matches are best of five, against 18% of regular matches. The sentence now gives these shares, and a build check
  enforces them.
- **WTA calibration over time.** "Has widened since 2018" (abstract) and "the widening since 2018" (§5.2) became
  "largest in 2018–2026", because the paper reports three period estimates, not a trend test.
- **Acknowledgements section added** before the References, in the author's wording.
- **Editorial fixes, all in v4.0, from an external review:**
  - The introduction says "Version 3.0 corrected…" instead of "This version (3.0) also corrects…".
  - Running-text p-values now read "p < 0.001", not "p = < 0.001". A `pEq` helper applies this to all 14 places.
  - §4.4 says "no player score produced a statistically reliable improvement", because some variants have tiny
    favourable point estimates.
  - No number changed.
- **§7 version history shortened** to a correction note: what v3.0 fixed, what changed in 3.1 and 4.0, and a pointer to
  this file. The detailed per-version list now lives only here. The disclosures in the text about when each test was
  added stay.
- **Version** 4.0. PDF regenerated: 19 pages.

# Change log — working paper 1, version 3.0 → 3.1 (16 November 2026)

An attribution revision based on `ORIGINALITY_AUDIT.md`; see `ATTRIBUTION.md` for the reasoning and the sources checked.
No analysis was rerun and no reported number changed. A comparison of every number in the v3.0 and v3.1 PDFs found
only three new values: Sackmann's 1,043 categories and two DOIs.

- **§2 Related Research.**
  - Klaassen & Magnus (2001) and Cohen-Zada et al. (2017) are summarised in new wording, because the old sentences
    followed the abstracts too closely.
  - New paragraph on player-level pressure measures: Kovalchik & Ingram (2016) and Kovalchik & Reid (2020).
  - Jetter & Walker (2015) now include their group-level Grand Slam ("clutch-player") finding.
  - Gorgi et al. (2019) added (no Grand Slam widening of the ATP strength gap).
  - New paragraph on the closest precedents: Sackmann (2019a) on round-by-round results against Elo, and Sackmann
    (2025) on split-half persistence in best-of-five matches.
  - The baseball paragraph adds James (2004), Birnbaum (2005) and Tango et al. (2007), and now says the framework
    "builds on established approaches" instead of "the closest methodological precedent".
  - Efron & Morris: "error" is now "mean squared error".
  - New closing paragraph stating the paper's applied contribution.
- **§3.3 Expected results.** Describes the blend: overall and surface ratings weighted equally, the weight being the
  best of 0.25/0.5/0.75/1 by 1990–2009 log loss in the project's model development. A similar blend was described by
  Sackmann (2019b).
- **§3.4** cites Efron & Morris (1975) for empirical Bayes. **§3.5** relates the variance ratio to Tango et al.
  (2007). **§3.7** notes that Birnbaum (2005) used similar power simulations.
- **References.**
  - Nine added.
  - URLs or DOIs added for Cramer, Holm and Papke & Wooldridge.
  - Brown, L. D. now comes before Brown, W.
  - The Sackmann data entry uses the licensor's attribution title and links the licence.
- **Version** 3.1 (`web/lib/papers.ts`), with a version-history line in §7. PDF regenerated.

# Change log — working paper 1, version 2.2 → 3.0 (16 November 2026)

See `AUDIT.md` for the reasons behind each change.

## Statistical changes

- **Sample.** Roland Garros 2026 removed (its later rounds were played in the sealed June period). ATP Cup, United Cup,
  World Team Cup, Laver Cup, Next Gen Finals and WTA 125 events removed. Finals identified by name; the second-tier WTA
  year-end events treated as ordinary events. The WTA top tier assigned by event and year.
- **Multiple testing.** Holm's correction now covers the 18 trait statistics (nine per tour), not only the eight
  variance ratios. The family was defined after earlier results were known, and the paper says so.
- **Out-of-sample evaluation (new).** Chronological, year-by-year: calibration, scores and β fitted on earlier years
  only. Models M0 (pooled calibration), M1 (big/regular calibration), and M1 + big-match or clutch score (fixed
  shrinkage, empirical Bayes, last five years). Paired log-loss and Brier differences with an edition-cluster bootstrap.
- **Calibration (new).** Edition-cluster bootstrap for the big-minus-regular slope difference; slopes by period.
- **Bounds.** τ = 0.35 added to the grid; Monte Carlo range for each bound.
- **Game margins.** Permutations stratified by closeness, with stratum-level noise variance.
- **Old "forecast test".** Unchanged in computation, renamed "retrospective association".

## Numerical changes (headline figures)

| Figure | v2.2 | v3.0 |
|---|---|---|
| Matches / big matches | 131,649 / 14,071 | 130,460 / 14,086 |
| Big-match variance ratios (range) | 0.92–1.17 | 0.93–1.16 |
| Split-half r, ATP / WTA | +0.094 / +0.064 | +0.121 / +0.044 |
| Players in the period split, ATP / WTA | 29 / 32 | 26 / 32 |
| ATP clutch spread (wins) | 1.20, p = 0.044, no adjusted p | 1.14, p = 0.108, Holm 1.000 |
| WTA clutch spread (wins) | 0.98 | 0.97 |
| WTA regular-match variance ratio | 1.29 | 1.30 |
| WTA big-match association (permutation p) | 0.114 | 0.026 (simulation p 0.006, Holm 0.108) |
| Smallest Holm-adjusted p for a trait statistic | 0.437 (only the big-match variance ratios were corrected) | 0.108 (all 18 trait statistics) |
| Clutch-spread 95% bound, ATP / WTA (points at evens) | 7.9 / 5.0 | 7.1 / 4.8 |
| WTA calibration slopes, big vs regular | 0.75 vs 0.82, Wald p = 0.006 | 0.755 vs 0.821, Wald p = 0.014, cluster p = 0.016 |
| ATP game-margin clutch spread | 1.23, p = 0.022 | 1.23, p = 0.027 |
| ATP best-of-three clutch spread, wins / games | 1.19 (p 0.042) / 1.28 (p 0.010) | 1.18 (p 0.048) / 1.30 (p 0.008) |
| Out-of-sample Δ log loss, big-match / clutch score (both tours) | — | +0.00003 / +0.00007, intervals include 0 |
| Out-of-sample Δ log loss, pooled vs big/regular calibration (WTA) | — | +0.00089 (0.00030 to 0.00148) |

The direction of the conclusions did not change, but two things did. The ATP clutch excess, the "one finding worth
following up" in v2, is no longer nominally significant on its main statistic. The WTA calibration finding is now the
paper's clearest result.

## Editorial changes

- New title-case title and subtitle ("Evidence from 26 Years of Professional Tennis"); author and "Independent
  Research · Matchup DNA" affiliation; no journal-style masthead, metadata block or sidebar.
- Structure: Abstract; 1 Introduction; 2 Related Research; 3 Data and Methods; 4 Results; 5 Discussion and
  Limitations; 6 Conclusion; 7 Data and Code Availability (with the version history);
  References; Appendix A (tables A1–A8); Appendix B (technical details).
- Introduction shortened and opened with the forecasting question; repeated explanations of noise and small samples
  removed; the losing-run section and Figure 6 of v2.2 removed.
- Findings separated from explanations; the WTA calibration explanations are labelled as possibilities.
- Variance ratios named as such; point estimates no longer described as maxima; bounds described as conditional,
  population-level quantities.
- Live-model statement corrected: the live model has no big-match adjustment.
- References checked and corrected; DOIs added; three directly relevant tennis studies added; five less relevant ones
  removed.
- Every number rendered from the export, with build-time checks on qualitative claims.
- New PDF layout: plain A4 working paper, one serif face, simple running footer, references and appendices on new
  pages.
