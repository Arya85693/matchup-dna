# Author review checklist

Before you publish version 3, or put it on a resume, you should be able to explain and defend each item below. Tick
items off as you check them.

## Understand the methods

- [ ] **Calibrated Elo (equations 1–2).** Why Elo's log-odds are rescaled per tour, format and match type, and why
      best-of-five matters for a big-match study.
- [ ] **Residuals and shrinkage (equations 3–4).** Why sum/(n + 20) pulls short records toward zero. Why it is *fixed*
      shrinkage, not empirical Bayes. What the empirical Bayes variant does differently (Appendix B.4).
- [ ] **Variance ratio.** Observed variance of players' mean residuals ÷ average binomial variance. Why 1 means "chance
      only". Why it is a ratio of variances, not of standard deviations.
- [ ] **Split-half and Spearman–Brown.** What the reliability estimate means, and why it is a point estimate, not a
      maximum.
- [ ] **Parametric bootstrap null.** What is simulated (one outcome per match from its calibrated probability), what is
      held fixed (the schedule), and what it assumes (no form or other player effects).
- [ ] **Holm's correction.** Which 18 statistics form the family, why the regular-match ratio is excluded, and that the
      family was chosen after earlier results.
- [ ] **Power and upper bounds.** What τ is, how "edge at even odds" is computed, why the bound is conditional on a
      normal, career-constant trait, and why it describes the spread across players, not a maximum for one player.
- [ ] **Out-of-sample design.** For a match in year Y, what is fitted on which years (calibration, scores, β). Why
      evaluation starts in 2012. How players without history are handled (score 0). Why the edition bootstrap is used.
- [ ] **The difference between the retrospective association test and the out-of-sample test**, and why the WTA
      big-match association can be nominally significant retrospectively and still add nothing out of sample.

## Check the conclusions

- [ ] "No player-specific adjustment" follows from the out-of-sample results, not just from the non-significant tests.
- [ ] The paper does **not** claim that clutch traits do not exist, and a modest trait (bounds 7.1 / 4.8 points) is
      acknowledged.
- [ ] The WTA calibration finding is a tour-level calibration pattern, not evidence that WTA players or favourites
      choke. Its explanations are possibilities, not findings.
- [ ] The live model is frozen and has no big-match adjustment, and the paper does not suggest otherwise.

## Check facts that could not be fully verified

- [ ] **WTA tier lists** (`WTA_TOP_TIER` in `matchup_dna/posthoc_big_match.py`), checked against Wikipedia season pages,
      not official WTA records.
- [ ] **References.** Each one was checked against Crossref or publisher metadata, but only abstracts were read for most.
      Before citing a paper's finding in an interview, read at least its abstract yourself. Cramer (1977) page numbers
      could not be verified and are omitted.
- [ ] **Data source.** The Sackmann repositories were offline on 16 November 2026. Confirm the mirror's provenance, and
      that your use is non-commercial under CC BY-NC-SA 4.0.

## Before publishing

- [ ] Read the full PDF once end to end.
- [ ] Rerun the four analysis commands on the committed code (see README) and confirm the publisher prints "every
      headline matches", so the published results are tied to a commit.
- [ ] Add the public repository URL to `SUMMARY.md` if the repository is public.
