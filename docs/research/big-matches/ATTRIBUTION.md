# Attribution summary: Working Paper 1, version 3.1

Version 3.1 (16 November 2026) is a citation and attribution revision of version 3.0, based on `ORIGINALITY_AUDIT.md`.
The analysis and results are unchanged; `CHANGELOG.md` lists every edit.

Each source below was checked again against the original, not taken from the audit's summaries:
- Full text: the three Sackmann posts, Gorgi et al. (the 2018 discussion paper, and the Grand Slam passage of the
  published 2019 article), Kovalchik & Ingram, Birnbaum, and the first pages of Kovalchik & Reid.
- Abstract or publisher record only: Jetter & Walker, Cohen-Zada et al., James (SABR summary page), and Tango et al.
  (bibliographic record only).

## A. Citations added, and why

| Work | What it established | Relation to this paper | What this paper does differently |
|---|---|---|---|
| Sackmann (2019a), "Dominic Thiem, Tennys Sandgren, and playing your way in" | Results of the ATP top 100 by round (first matches to finals) were compared with Elo. 29 of about 1,043 player-round categories were significant at 5%, no more than chance. | The closest precedent: a similar question with an Elo baseline. | Covers both tours and a defined set of big matches. Adds a contrast with regular matches, calibrated expectations, simulation nulls with Holm correction, out-of-sample tests and bounds. |
| Sackmann (2025), "Matteo Berrettini and best-of-five puzzles" | Men's Slam results against Elo since 2000. Career halves and odd/even matches showed "virtually zero correlation". | A similar persistence check (split halves of Elo residuals). | Splits by tournament edition; adds confidence intervals, a simulation null, the WTA, and out-of-sample forecasting. |
| Sackmann (2019b), "An introduction to tennis Elo" | A 50/50 blend of overall and surface Elo, found by his own testing. | The same weighting idea as the project's surface-blended Elo. | Cited as related work only (see B). |
| Jetter & Walker (2015), already cited | Hot hand. Top-ranked players do better at Grand Slams: a group-level clutch effect. | The Grand Slam finding had been omitted. It bears directly on the question. | Tests for individual player traits, not a top-player group effect. |
| Gorgi, Koopman & Lit (2019) | ATP dynamic model. No Grand Slam widening of the strength gap once best of five is modelled. | A tour-level calibration question for the ATP. | Tests calibration on both tours. The ATP result agrees with theirs; the WTA shows a difference. |
| Kovalchik & Ingram (2016) | Player-specific responses to pressure in about 3 million points. They improved 2015 men's Slam predictions, but not women's beyond average effects. | A player-level pressure effect that helped prediction, which contrasts with this paper's null. | Uses match results, not point data, and a chronological evaluation over 2012–2026. |
| Kovalchik & Reid (2020) | Clutch averages: serve and return statistics weighted by point importance. They predicted the winner from first-set statistics in 2011 Slams. | A point-level measure of clutch performance. | Their measure works within a match. This paper studies a pre-match, persistent trait. |
| James (2004) | A null from a persistence test says little without power. | Motivates the power analysis and bounds. | — |
| Birnbaum (2005; reprinted 2008) | Simulated clutch talent of known size to find the power of Cramer's test. | Similar simulation design for power. | Applies the idea to tennis big matches, with refitted calibration in each simulation. |
| Tango, Lichtman & Dolphin (2007) | Observed variance = true variance + random variance, applied to clutch hitting. | Related to the variance ratio and to "implied k". | — |

Considered but not added, to keep §2 short: Sackmann (2021) on Osaka's second-week results, Bijleveld et al. (2011),
and the less central items listed in the audit. Sackmann (2021) and Bijleveld et al. would be the next to add if a
reviewer asks.

## B. Established techniques used

All of the following are standard: Elo ratings, logistic recalibration by maximum likelihood, residuals against
expectation, fixed and empirical-Bayes shrinkage, variance decomposition against binomial noise, split-half
reliability with Spearman–Brown, the parametric and cluster bootstrap, permutation tests, Holm's correction, power
simulation with an injected effect, fractional logit, and chronological out-of-sample scoring by log loss and Brier
score. The paper now cites a foundational or closely related source for each of them, using neutral wording such as
"related to", "builds on" and "similar simulations were used by". It does not say "adapted from" or "following",
because there is no record that any of them was taken from a particular paper.

**Surface-blended Elo.** `SURFACE_WEIGHT = 0.5` in `matchup_dna/elo.py`. Since its first commit (`6fb84b7`) the
module has said these constants "must match what python -m matchup_dna.evaluate chooses on the tuning period".
`evaluate.py` (`aceac5b`) compares weights of 0.25, 0.5, 0.75 and 1 by log loss on 1990–2009 matches. Rerun on
16 November 2026 without writing any files, the lowest log loss was 0.5967, at K = 48 and weight 0.5, the project's
values.

So the value was selected empirically inside the project. That does not make the idea original: Sackmann published an
equal-weight blend in 2019. The paper therefore describes the implementation, states how the weight was chosen, and
cites Sackmann (2019b) as a similar earlier approach. It neither claims the method nor says it was derived from his.

## C. Contributions of this working paper

These are stated in §2's closing paragraph as an applied contribution, not a methodological one:
- one analysis of 130,460 ATP and WTA matches that combines calibrated Elo residuals, variance and persistence tests,
  simulation-based nulls with multiple-testing correction, and simulated power and bounds;
- a chronological out-of-sample evaluation of big-match and clutch scores on 7,476 big matches;
- a comparison of Elo's calibration in big and regular matches on both tours, with the WTA difference as the clearest
  result;
- a modelling decision for Matchup DNA based on the evidence.

No "first" claim is made. The audit found no tennis precedent for the out-of-sample test or for a WTA calibration
comparison. Its search could not reach Google Scholar or SSRN, and it could not open one possibly close item
(ResearchGate 395539755, "Revisiting Clutch Performance Among Elite Players in Tennis"), so a priority claim would
not be safe.

## D. Evidence of copied code or text

- **Text: none found.** The audit's 46 exact-phrase searches and its n-gram comparison against cited abstracts and
  reference pages found no copied passage. Two sentences followed their abstracts' structure closely (Klaassen &
  Magnus; Cohen-Zada et al.). Both have been rewritten with a different structure and wording, and the same meaning
  and citations.
- **Code: none found.** The code has no third-party files, external URLs or "adapted from" notes, and the formulas
  are standard.
- **Limits of these checks.** No plagiarism database (Turnitin or iThenticate) was used. The code was written with an
  AI coding assistant, and no available check can rule out that such a tool reproduced a fragment of public code.
  These results do not establish that the paper or code is free of plagiarism. They show only that these checks found
  nothing.

## E. Originality claims that remain unsupported

None in the paper as revised. Two things to watch:
- Outside the paper, `SUMMARY.md`'s resume bullet begins "Led an independent statistical study". Make sure that
  wording matches how you describe the role of tools and assistance.
- Tango et al. (2007) is cited for the general variance decomposition. I did not read the chapter itself; the method is
  confirmed from Tango's own published description (tangotiger.net/clutch.html). Check the chapter if you can get a
  copy.

## Corrections made separately, in version 4.0

1. **Split-half intervals made deterministic** (audit C4) with `sorted(...)`. The ATP interval is now −0.03 to +0.26.
2. **§7 code provenance and the "every random seed is fixed" sentence** rewritten. They no longer refer to `4882aa0`.
3. An Acknowledgements section was added in the author's wording. Two wording errors from an external review were
   also corrected: the ATP best-of-five share, and "widened" for the WTA calibration gap.

## Still open

4. **The repository has no LICENSE** (audit P7). Add a code licence that excludes the CC BY-NC-SA data.
5. **Data provenance** (audit P6). The data come from an unofficial mirror. It cannot be checked against Sackmann's
   final upstream commits, which are offline.
6. **Unverified details.** Cramer (1977) page numbers; whether the Kovalchik & Ingram venue is the MIT Sloan Sports
   Analytics Conference (taken from the paper's "2016 Research Papers Competition" footer and secondary records, since
   the conference page returned 404); Paserman (2023) full text.
