#!/usr/bin/env python3
"""
Design Criterion 5: Usability — median SUS score ≈ 70.

After human participants use the tool, they complete the System Usability Scale (SUS).
This script reads collected SUS responses from a CSV and checks whether the median
SUS score meets the target (≥ 70). No product code; metric only.

Usage:
  python metric/criterion_05_usability.py --input PATH [--target 70]

  Required:
    --input PATH   CSV file with one row per participant and columns Q1..Q10 (1–5 each).

  Optional:
    --target N     Target median SUS score (default: 70).
    --delimiter C  CSV delimiter (default: comma).

CSV format (standard 10-item SUS):
  Header row with columns: Q1, Q2, Q3, ... Q10 (or Participant,Q1,Q2,...).
  Each row = one participant. Each Q is 1–5 (Strongly disagree .. Strongly agree).
  Odd items are positive, even items negative; script applies standard SUS scoring.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Standard 10-item SUS: odd items contrib = (score - 1), even = (5 - score); sum * 2.5 → 0–100.
TARGET_MEDIAN_DEFAULT = 70
SUS_ITEMS = 10


def sus_score_for_row(values: list[int]) -> float:
    """Compute SUS score (0–100) for one participant from 10 item responses (1–5)."""
    if len(values) < SUS_ITEMS:
        raise ValueError(f"Need {SUS_ITEMS} item scores, got {len(values)}")
    contrib = 0.0
    for i, v in enumerate(values[:SUS_ITEMS]):
        if not (1 <= v <= 5):
            raise ValueError(f"Item {i + 1} must be 1–5, got {v}")
        if (i + 1) % 2 == 1:  # odd: 1,3,5,7,9
            contrib += (v - 1)
        else:  # even: 2,4,6,8,10
            contrib += (5 - v)
    return contrib * 2.5


def load_sus_scores(csv_path: Path, delimiter: str) -> list[float]:
    """Load CSV and return list of SUS scores (one per row with Q1..Q10)."""
    scores: list[float] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        headers = reader.fieldnames or []
        # Find Q1..Q10 (allow Participant or other leading columns)
        qcols = [f"Q{i}" for i in range(1, SUS_ITEMS + 1)]
        if not all(q in headers for q in qcols):
            raise ValueError(
                f"CSV must have columns {qcols}. Found: {headers}"
            )
        for row in reader:
            raw = [row.get(q, "").strip() for q in qcols]
            if not all(r.isdigit() for r in raw):
                continue  # skip blank or non-numeric rows
            values = [int(r) for r in raw]
            scores.append(sus_score_for_row(values))
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Criterion 5: median SUS score ≥ target (default 70)"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        metavar="PATH",
        help="CSV file with Q1..Q10 columns (one row per participant)",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=TARGET_MEDIAN_DEFAULT,
        metavar="N",
        help=f"Target median SUS score (default: {TARGET_MEDIAN_DEFAULT})",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        metavar="C",
        help="CSV delimiter (default: ,)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        return 2

    try:
        scores = load_sus_scores(args.input, args.delimiter)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if not scores:
        print("Error: no valid participant rows in CSV.", file=sys.stderr)
        return 2

    n = len(scores)
    median_score = sorted(scores)[n // 2] if n % 2 == 1 else (
        (sorted(scores)[n // 2 - 1] + sorted(scores)[n // 2]) / 2
    )
    mean_score = sum(scores) / n
    min_score = min(scores)
    max_score = max(scores)

    print("Criterion 5: Usability (median SUS ≥ target)")
    print(f"  Input file: {args.input}")
    print(f"  Participants: {n}")
    print(f"  Target median: {args.target}")
    print()
    print("  SUS scores:")
    print(f"    Median: {median_score:.1f}")
    print(f"    Mean:   {mean_score:.1f}")
    print(f"    Min:    {min_score:.1f}")
    print(f"    Max:    {max_score:.1f}")
    print()

    passed = median_score >= args.target
    print(f"  Criterion 5 (median SUS ≥ {args.target}): {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
