"""Chronological periods, by tourney_date (YYYYMMDD). Each period starts on its date and ends where the next begins.

Ratings are replayed through every period. What changes between periods is only which matches may be scored,
trained on, or used for choices.
"""

TUNING_START = 19900101
TRAIN_START = 20100101
VALIDATION_START = 20210101
RESERVED_START = 20240101

PERIODS = (
    ("warmup", None, TUNING_START),
    ("tuning", TUNING_START, TRAIN_START),
    ("train", TRAIN_START, VALIDATION_START),
    ("validation", VALIDATION_START, RESERVED_START),
    ("reserved", RESERVED_START, None),
)

# Phase 2's revised report scores Elo on train and validation together. Reserved outcomes are not scored
# until Phase 3's final model and evaluation protocol are frozen.
DEVELOPMENT_START = TRAIN_START
DEVELOPMENT_END = RESERVED_START


def period(date):
    for name, start, end in PERIODS:
        if (start is None or date >= start) and (end is None or date < end):
            return name
    raise ValueError(f"No period contains {date}")
