"""Phase 6: the production forecasting engine.

Two frozen Phase 4 models, run forward on fixtures that have not been played yet, with every forecast stored before
the match and never changed afterwards:

    Model A, tournament start (P4-refit)   uses only information from before the tournament started
    Model B, round-aware (R0)               also uses the completed earlier rounds of the same tournament

Layers, each in its own module:

    records.py        provider-neutral match records with their four timestamps
    providers.py      provider adapters (TennisData.app file snapshots, recorded JSON, authenticated HTTP probes)
    history.py        the canonical completed-match history: Sackmann + TennisIsMyLife + TennisData.app, one record
                      per real match, one identity per real player (Phase 4 erratum 1's version-2 rules)
    canonical.py      provider fixtures -> canonical editions, matches and player identities
    frozen_models.py  the frozen models exported once from the Phase 4 procedure, and their reproduction check
    engine.py         point-in-time features for unplayed fixtures, eligibility, inference
    store.py          SQLite storage; predictions and outcomes are append-only, with a hash-chained ledger
    pipeline.py       ingest -> forecast -> settle, idempotent
    prospective.py    the prospective evaluation, under experiments/phase6_prospective_protocol.json
    api.py            the read-only JSON interface the website will use

Nothing here changes a Phase 1-5 module, file or result. The research code is imported, not copied, wherever the
production path must compute exactly what the research measured.
"""
