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
