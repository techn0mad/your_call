#!/usr/bin/env python3

# Copyright (c) 2026 Larry Gadallah
# SPDX-License-Identifier: ISC

"""
your_call.py

Rank amateur-radio callsigns using measurable CW and voice criteria.

Input:
    Text file containing one callsign per line.

Example:
    python3 your_call.py bc_calls.txt --prefix VE7 -n 25
"""

import argparse
import re
from dataclasses import dataclass


# ----------------------------------------------------------------------
# Morse and phonetic data
# ----------------------------------------------------------------------

MORSE = {
    "A": ".-",    "B": "-...",  "C": "-.-.",  "D": "-..",
    "E": ".",     "F": "..-.",  "G": "--.",   "H": "....",
    "I": "..",    "J": ".---",  "K": "-.-",   "L": ".-..",
    "M": "--",    "N": "-.",    "O": "---",   "P": ".--.",
    "Q": "--.-",  "R": ".-.",   "S": "...",   "T": "-",
    "U": "..-",   "V": "...-",  "W": ".--",   "X": "-..-",
    "Y": "-.--",  "Z": "--..",

    "0": "-----", "1": ".----", "2": "..---", "3": "...--",
    "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.",
}


PHONETICS = {
    "A": ("Alpha", 2),
    "B": ("Bravo", 2),
    "C": ("Charlie", 2),
    "D": ("Delta", 2),
    "E": ("Echo", 2),
    "F": ("Foxtrot", 2),
    "G": ("Golf", 1),
    "H": ("Hotel", 2),
    "I": ("India", 3),
    "J": ("Juliett", 3),
    "K": ("Kilo", 2),
    "L": ("Lima", 2),
    "M": ("Mike", 1),
    "N": ("November", 3),
    "O": ("Oscar", 2),
    "P": ("Papa", 2),
    "Q": ("Quebec", 2),
    "R": ("Romeo", 3),
    "S": ("Sierra", 3),
    "T": ("Tango", 2),
    "U": ("Uniform", 3),
    "V": ("Victor", 2),
    "W": ("Whiskey", 2),
    "X": ("X-ray", 2),
    "Y": ("Yankee", 2),
    "Z": ("Zulu", 2),
}


# ----------------------------------------------------------------------
# Weights
# ----------------------------------------------------------------------

WEIGHTS = {
    "suffix_length":       0.20,
    "cw_time":             0.15,
    "cw_elements":         0.10,
    "boundary_contrast":   0.10,
    "boundary_runs":       0.05,
    "cw_rhythm":           0.10,
    "phonetic_length":     0.10,
    "phonetic_contrast":   0.08,
    "prefix_uniqueness":   0.07,
    "adjacent_duplicates": 0.03,
    "memorability":        0.02,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


# ----------------------------------------------------------------------
# Result object
# ----------------------------------------------------------------------

@dataclass
class Result:  # pylint: disable=too-many-instance-attributes
    """Scoring measurements and results for a single callsign."""

    callsign: str
    prefix: str
    suffix: str

    suffix_morse: str
    phonetics: str

    elements: int
    cw_units: int
    syllables: int

    boundary_contrast: float
    boundary_run_penalty: int
    prefix_repeats: int
    adjacent_duplicates: int

    scores: dict
    score: float


# ----------------------------------------------------------------------
# Callsign parsing
# ----------------------------------------------------------------------

def split_callsign(callsign):
    """Split callsign into prefix and suffix."""
    """
    Split VE7HTE -> ("VE7", "HTE").

    Assumes the prefix terminates with the first digit.
    """

    match = re.fullmatch(r"([A-Z]+\d)([A-Z]+)", callsign)

    if not match:
        raise ValueError(f"Cannot parse callsign: {callsign}")

    return match.group(1), match.group(2)


# ----------------------------------------------------------------------
# Basic Morse measurements
# ----------------------------------------------------------------------

def morse_elements(text):
    """Number of dots and dashes."""

    return sum(len(MORSE[c]) for c in text)


def morse_character_units(c):
    """Calculate CW character element lengths."""
    """
    Morse duration of one character.

    dot                = 1 unit
    dash               = 3 units
    intra-element gap  = 1 unit
    """

    code = MORSE[c]

    keying = sum(
        1 if element == "." else 3
        for element in code
    )

    internal_gaps = len(code) - 1

    return keying + internal_gaps


def morse_units(text):
    """Calculate total CW duration, including inter-character gaps."""
    """
    Total Morse duration including 3-unit inter-character gaps.
    """

    if not text:
        return 0

    character_units = sum(
        morse_character_units(c)
        for c in text
    )

    inter_character_gaps = 3 * (len(text) - 1)

    return character_units + inter_character_gaps


# ----------------------------------------------------------------------
# CW boundary analysis
# ----------------------------------------------------------------------

def leading_run(code):
    """Length of the identical-element run at start of Morse code."""

    first = code[0]
    count = 0

    for element in code:
        if element != first:
            break
        count += 1

    return count


def trailing_run(code):
    """Length of the identical-element run at end of Morse code."""

    last = code[-1]
    count = 0

    for element in reversed(code):
        if element != last:
            break
        count += 1

    return count


def boundary_contrast(suffix):
    """Calculate CW polarity changes."""
    """
    Fraction of character boundaries where Morse polarity changes.

    HTE:
        .... | -    contrast
        -    | .    contrast
        => 1.0

    IMT:
        .. | --     contrast
        -- | -      no contrast
        => 0.5

    ESI:
        .   | ...   no contrast
        ... | ..    no contrast
        => 0.0
    """

    if len(suffix) < 2:
        return 1.0

    good = 0

    for left, right in zip(suffix, suffix[1:]):
        if MORSE[left][-1] != MORSE[right][0]:
            good += 1

    return good / (len(suffix) - 1)


def boundary_run_penalty(suffix):
    """Calculate runs of identical CW elements crossing character boundaries."""

    Example:

        MT = -- | -

    produces a run of three dashes whose correct interpretation
    depends heavily on detecting the character gap.

    Zero is ideal.
    """

    penalty = 0

    for left, right in zip(suffix, suffix[1:]):
        a = MORSE[left]
        b = MORSE[right]

        if a[-1] == b[0]:
            run = trailing_run(a) + leading_run(b)

            # A run of two is the minimum possible bad boundary.
            # Penalize increasingly long runs.
            penalty += run - 1

    return penalty


# ----------------------------------------------------------------------
# General Morse-character contrast
# ----------------------------------------------------------------------

def morse_distance(a, b):
    """Calculate structual distance between two morse characters."""
    """
    Simple structural distance between two Morse characters.

    This is not yet a true Morse edit-distance model.
    """

    a = MORSE[a]
    b = MORSE[b]

    length_difference = abs(len(a) - len(b))

    differing_elements = sum(
        x != y
        for x, y in zip(a, b)
    )

    return length_difference + differing_elements


def cw_rhythm_raw(suffix):
    """Calculate CW 'rhythm'."""
    """
    Average structural contrast between adjacent Morse characters.
    """

    if len(suffix) < 2:
        return 1.0

    distances = [
        morse_distance(a, b)
        for a, b in zip(suffix, suffix[1:])
    ]

    # Normalize roughly against a strong four-element difference.

    return min(
        sum(distances) / (4.0 * len(distances)),
        1.0
    )


# ----------------------------------------------------------------------
# Voice analysis
# ----------------------------------------------------------------------

def phonetic_syllables(text):
    """Return the total NATO phonetic syllable count for text."""
    return sum(PHONETICS[c][1] for c in text)


def phonetic_string(text):
    """Return text represented using NATO phonetic words."""
    return " ".join(PHONETICS[c][0] for c in text)


def phonetic_contrast_raw(suffix):
    """Calculate the phonetic distinctiveness of a call."""
    """
    V1 phonetic-distinctiveness heuristic.

    Reward different phonetic words and penalize repeated letters.

    This intentionally remains simple until we have a defensible
    acoustic-distance model.
    """

    if len(suffix) <= 1:
        return 1.0

    unique = len(set(suffix))

    return unique / len(suffix)


# ----------------------------------------------------------------------
# Repetition / uniqueness
# ----------------------------------------------------------------------

def prefix_repeats(prefix, suffix):
    """Return the number of suffix characters also present in the prefix."""
    """
    Number of suffix characters also appearing in the prefix.

    VE7OL -> 0
    VE7LV -> 1
    """

    prefix_chars = set(prefix)

    return sum(
        c in prefix_chars
        for c in suffix
    )


def count_adjacent_duplicates(text):
    """Return the number of adjacent duplicate-character boundaries."""
    """
    UEE -> one adjacent duplicate.
    EEE -> two adjacent duplicate boundaries.
    """

    return sum(
        a == b
        for a, b in zip(text, text[1:])
    )


# ----------------------------------------------------------------------
# Normalization
# ----------------------------------------------------------------------

def lower_is_better(value, minimum, maximum):
    """Normalize a value to 0..100 where lower is better."""
    """
    Convert a metric where lower is better into 0..100.
    """

    if maximum == minimum:
        return 100.0

    return 100.0 * (
        (maximum - value) /
        (maximum - minimum)
    )


def higher_is_better(value, minimum, maximum):
    """Normalize a value to 0..100 where higher is better."""
    """
    Convert a metric where higher is better into 0..100.
    """

    if maximum == minimum:
        return 100.0

    return 100.0 * (
        (value - minimum) /
        (maximum - minimum)
    )


# ----------------------------------------------------------------------
# Memorability
# ----------------------------------------------------------------------

def memorability_raw(suffix):
    """Generate a memorability heuristic value."""
    """
    Conservative V1 memorability heuristic.

    Rewards:
        - unique characters
        - symmetry

    This intentionally carries little weight because aesthetics
    are inherently subjective.
    """

    if not suffix:
        return 0.0

    uniqueness = len(set(suffix)) / len(suffix)

    symmetry = (
        1.0
        if len(suffix) > 1 and suffix == suffix[::-1]
        else 0.0
    )

    return 0.8 * uniqueness + 0.2 * symmetry


# ----------------------------------------------------------------------
# Raw analysis
# ----------------------------------------------------------------------

def raw_analysis(callsign):
    """Perform the raw analysis of a callsign."""

    prefix, suffix = split_callsign(callsign)

    return {
        "callsign": callsign,
        "prefix": prefix,
        "suffix": suffix,

        "suffix_length": len(suffix),

        "suffix_morse":
            " ".join(MORSE[c] for c in suffix),

        "phonetics":
            phonetic_string(suffix),

        "elements":
            morse_elements(suffix),

        "cw_units":
            morse_units(suffix),

        "syllables":
            phonetic_syllables(suffix),

        "boundary_contrast":
            boundary_contrast(suffix),

        "boundary_runs":
            boundary_run_penalty(suffix),

        "cw_rhythm":
            cw_rhythm_raw(suffix),

        "phonetic_contrast":
            phonetic_contrast_raw(suffix),

        "prefix_repeats":
            prefix_repeats(prefix, suffix),

        "adjacent_duplicates":
            count_adjacent_duplicates(suffix),

        "memorability":
            memorability_raw(suffix),
    }


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------

def analyze(callsigns):
    """Analyze a set of callsigns."""

    raw = [
        raw_analysis(call)
        for call in callsigns
    ]

    if not raw:
        return []

    def limits(field):
        values = [r[field] for r in raw]
        return min(values), max(values)

    ranges = {
        field: limits(field)
        for field in (
            "suffix_length",
            "cw_units",
            "elements",
            "boundary_runs",
            "syllables",
        )
    }

    results = []

    for r in raw:

        scores = {}

        scores["suffix_length"] = lower_is_better(
            r["suffix_length"],
            *ranges["suffix_length"]
        )

        scores["cw_time"] = lower_is_better(
            r["cw_units"],
            *ranges["cw_units"]
        )

        scores["cw_elements"] = lower_is_better(
            r["elements"],
            *ranges["elements"]
        )

        scores["boundary_contrast"] = (
            100.0 * r["boundary_contrast"]
        )

        scores["boundary_runs"] = lower_is_better(
            r["boundary_runs"],
            *ranges["boundary_runs"]
        )

        scores["cw_rhythm"] = (
            100.0 * r["cw_rhythm"]
        )

        scores["phonetic_length"] = lower_is_better(
            r["syllables"],
            *ranges["syllables"]
        )

        scores["phonetic_contrast"] = (
            100.0 * r["phonetic_contrast"]
        )

        if r["suffix_length"]:
            scores["prefix_uniqueness"] = max(
                0.0,
                100.0 * (
                    1.0 -
                    r["prefix_repeats"] /
                    r["suffix_length"]
                )
            )
        else:
            scores["prefix_uniqueness"] = 0.0

        if r["suffix_length"] <= 1:
            scores["adjacent_duplicates"] = 100.0
        else:
            scores["adjacent_duplicates"] = max(
                0.0,
                100.0 * (
                    1.0 -
                    r["adjacent_duplicates"] /
                    (r["suffix_length"] - 1)
                )
            )

        scores["memorability"] = (
            100.0 * r["memorability"]
        )

        total = sum(
            scores[name] * weight
            for name, weight in WEIGHTS.items()
        )

        results.append(
            Result(
                callsign=r["callsign"],
                prefix=r["prefix"],
                suffix=r["suffix"],
                suffix_morse=r["suffix_morse"],
                phonetics=r["phonetics"],
                elements=r["elements"],
                cw_units=r["cw_units"],
                syllables=r["syllables"],
                boundary_contrast=r["boundary_contrast"],
                boundary_run_penalty=r["boundary_runs"],
                prefix_repeats=r["prefix_repeats"],
                adjacent_duplicates=r["adjacent_duplicates"],
                scores=scores,
                score=total,
            )
        )

    return sorted(
        results,
        key=lambda r: (
            -r.score,
            r.cw_units,
            r.elements,
            r.callsign,
        )
    )


# ----------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------

def print_summary(results, count):
    """Print the analysis summary for a set of callsigns."""

    print(
        f"{'#':>3} "
        f"{'Call':<8} "
        f"{'Score':>6} "
        f"{'CW':>4} "
        f"{'Elem':>4} "
        f"{'BCon':>5} "
        f"{'BRun':>4} "
        f"{'Syl':>3} "
        f"{'Pfx':>3} "
        f"{'Dup':>3} "
        f"{'Morse':<18}"
    )

    for rank, r in enumerate(results[:count], 1):

        print(
            f"{rank:3d} "
            f"{r.callsign:<8} "
            f"{r.score:6.2f} "
            f"{r.cw_units:4d} "
            f"{r.elements:4d} "
            f"{100*r.boundary_contrast:5.0f} "
            f"{r.boundary_run_penalty:4d} "
            f"{r.syllables:3d} "
            f"{r.prefix_repeats:3d} "
            f"{r.adjacent_duplicates:3d} "
            f"{r.suffix_morse:<18}"
        )


def print_detail(result):
    """Print the detailed analysis of a callsign."""

    print()
    print(result.callsign)
    print("-" * len(result.callsign))

    print(f"Suffix:              {result.suffix}")
    print(f"Morse:               {result.suffix_morse}")
    print(f"Phonetics:           {result.phonetics}")
    print(f"CW elements:         {result.elements}")
    print(f"CW time units:       {result.cw_units}")
    print(f"Phonetic syllables:  {result.syllables}")
    print(
        f"Boundary contrast:   "
        f"{100 * result.boundary_contrast:.0f}%"
    )
    print(
        f"Boundary run penalty:"
        f" {result.boundary_run_penalty}"
    )
    print(
        f"Prefix repetitions:  "
        f"{result.prefix_repeats}"
    )
    print(
        f"Adjacent duplicates: "
        f"{result.adjacent_duplicates}"
    )

    print()
    print("Component scores:")

    for name, weight in WEIGHTS.items():

        value = result.scores[name]

        print(
            f"  {name:<22}"
            f"{value:6.1f}"
            f"   weight={100*weight:4.1f}%"
        )

    print()
    print(f"Overall score: {result.score:.2f}/100")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
   """Mainline."""
    parser = argparse.ArgumentParser(
        description=(
            "Rank amateur-radio callsigns for CW and voice."
        )
    )

    parser.add_argument(
        "file",
        help="Text file containing one callsign per line"
    )

    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=25,
        help="Number of ranked results to display"
    )

    parser.add_argument(
        "--prefix",
        help="Restrict results to a prefix, e.g. VE7"
    )

    parser.add_argument(
        "--detail",
        metavar="CALLSIGN",
        help="Show detailed scoring for one callsign"
    )

    args = parser.parse_args()

    with open(args.file) as f:

        callsigns = [
            line.strip().upper()
            for line in f
            if line.strip()
        ]

    if args.prefix:

        prefix = args.prefix.upper()

        callsigns = [
            call
            for call in callsigns
            if call.startswith(prefix)
        ]

    results = analyze(callsigns)

    print_summary(
        results,
        args.number
    )

    if args.detail:

        wanted = args.detail.upper()

        match = next(
            (
                r for r in results
                if r.callsign == wanted
            ),
            None
        )

        if match is None:
            raise SystemExit(
                f"{wanted} is not in the candidate set"
            )

        print_detail(match)


if __name__ == "__main__":
    main()
