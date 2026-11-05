"""Serve statistics for one player in one match, and the rules that decide whether they can be used.

Sackmann and TennisIsMyLife store, for the winner (prefix "w") and the loser ("l"):

    ace      aces                          svpt     service points played
    df       double faults                 1stIn    first serves in
    1stWon   points won on first serve     2ndWon   points won on second serve
    SvGms    service games                 bpSaved  break points saved
    bpFaced  break points faced

A blank cell is missing, never zero. A line is checked rule by rule, so a line with one bad field can still be
used for the statistics its other fields support.
"""
STAT_FIELDS = ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")


def to_count(value):
    """An integer count, None when blank, or the string "invalid" when the cell is not a whole number."""
    value = (value or "").strip()
    if value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return "invalid"
    return int(number) if number.is_integer() else "invalid"


def stat_line(row, prefix):
    """{field: count} for one side ("w" or "l") of a Sackmann-layout row."""
    return {field: to_count(row[f"{prefix}_{field}"]) for field in STAT_FIELDS}


# Each rule: (name, fields it needs, test). A rule is checked only when all its fields are whole numbers.
RULES = (
    ("serve points above zero", ("svpt",), lambda s: s["svpt"] > 0),
    ("first serves in within serve points", ("1stIn", "svpt"), lambda s: 0 <= s["1stIn"] <= s["svpt"]),
    ("first-serve points won within first serves in", ("1stWon", "1stIn"), lambda s: 0 <= s["1stWon"] <= s["1stIn"]),
    ("second-serve points won within second-serve points", ("2ndWon", "svpt", "1stIn"),
     lambda s: 0 <= s["2ndWon"] <= s["svpt"] - s["1stIn"]),
    ("double faults within second-serve points", ("df", "svpt", "1stIn"),
     lambda s: 0 <= s["df"] <= s["svpt"] - s["1stIn"]),
    ("aces within points won on serve", ("ace", "1stWon", "2ndWon"),
     lambda s: 0 <= s["ace"] <= s["1stWon"] + s["2ndWon"]),
    ("break points saved within break points faced", ("bpSaved", "bpFaced"),
     lambda s: 0 <= s["bpSaved"] <= s["bpFaced"]),
    ("service games not negative", ("SvGms",), lambda s: s["SvGms"] >= 0),
)


def line_problems(line):
    """Every problem with a stat line: "missing <field>", "invalid <field>", and each broken rule by name.
    An empty list means every field is present and every rule holds."""
    problems = [f"missing {field}" for field, value in line.items() if value is None]
    problems += [f"invalid {field}" for field, value in line.items() if value == "invalid"]
    for name, fields, test in RULES:
        if all(isinstance(line[field], int) for field in fields) and not test(line):
            problems.append(name)
    return problems


def serve_points_won(line):
    """(points won on serve, serve points played), or None when they cannot be used."""
    problems = line_problems(line)
    needed = ("svpt", "1stIn", "1stWon", "2ndWon")
    if any(f"missing {field}" in problems or f"invalid {field}" in problems for field in needed):
        return None
    if any(name in problems for name, fields, _ in RULES if set(fields) <= set(needed)):
        return None
    return line["1stWon"] + line["2ndWon"], line["svpt"]
