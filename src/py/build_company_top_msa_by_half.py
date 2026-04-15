#!/usr/bin/env python3
"""Build the most-popular company MSA by half-year.

This is the canonical upstream producer for `data/clean/company_top_msa_by_half.csv`.
It reads the raw worker-spell export and counts every spell in each half-year,
keeping only spells whose MSA can be mapped to a valid CBSA code.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from src.py.project_paths import DATA_CLEAN, DATA_RAW, require_file


DEFAULT_SPELLS = DATA_RAW / "Scoop_workers_positions.csv"
DEFAULT_MSA_CBSA = DATA_RAW / "linkedin_msa_with_cbsa.csv"
DEFAULT_OUTPUT = DATA_CLEAN / "company_top_msa_by_half.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spells",
        type=Path,
        default=DEFAULT_SPELLS,
        help="Path to the raw worker-spell extract.",
    )
    parser.add_argument(
        "--msa-cbsa",
        type=Path,
        default=DEFAULT_MSA_CBSA,
        help="Path to the raw MSA→CBSA lookup export.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination cleaned CSV.",
    )
    parser.add_argument("--test-rows", type=int, default=None, help="Process only the first N rows.")
    parser.add_argument("--chunk-rows", type=int, default=1_000_000, help="Rows per pandas chunk.")
    return parser.parse_args()


def load_cbsa_lookup(path: Path) -> dict[str, int]:
    require_file(path, nonempty=True, purpose="MSA to CBSA lookup")
    lookup = pd.read_csv(path, dtype={"msa": str})
    lookup.columns = [col.strip() for col in lookup.columns]
    if "msa" not in lookup.columns or "CBSA Code" not in lookup.columns:
        raise RuntimeError(
            f"{path} must contain columns 'msa' and 'CBSA Code'; found {lookup.columns.tolist()}"
        )
    lookup["cbsacode"] = pd.to_numeric(lookup["CBSA Code"], errors="coerce").astype("Int64")
    lookup = lookup.dropna(subset=["msa", "cbsacode"])
    return {row.msa: int(row.cbsacode) for row in lookup.itertuples(index=False)}


def half_span(start: pd.Timestamp, end: pd.Timestamp):
    """Yield `(year, half)` for each half-year overlapping `[start, end]`."""
    year, half = start.year, 1 if start.month <= 6 else 2
    while True:
        yield year, half
        if half == 1:
            boundary = pd.Timestamp(year, 7, 1)
            if boundary > end:
                break
            half = 2
        else:
            boundary = pd.Timestamp(year + 1, 1, 1)
            if boundary > end:
                break
            year, half = year + 1, 1


def main() -> None:
    args = parse_args()
    spells_path = require_file(args.spells, nonempty=True, purpose="worker spell input")
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cbsa_lookup = load_cbsa_lookup(args.msa_cbsa)

    invalid_date_rows = 0
    filled_end_rows = 0
    unknown_msa_rows = 0

    presence: dict[tuple[str, int, int], Counter[tuple[int, str]]] = defaultdict(Counter)
    reader = pd.read_csv(
        spells_path,
        usecols=["companyname", "msa", "start_date", "end_date"],
        parse_dates=["start_date", "end_date"],
        chunksize=args.chunk_rows,
        nrows=args.test_rows,
    )

    total_chunks = (
        (args.test_rows + args.chunk_rows - 1) // args.chunk_rows if args.test_rows else None
    )

    for chunk in tqdm(reader, unit="chunk", total=total_chunks, desc="Reading"):
        chunk = chunk.dropna(subset=["companyname", "msa", "start_date"])
        chunk["start_date"] = pd.to_datetime(chunk["start_date"], errors="coerce")
        chunk["end_date"] = pd.to_datetime(chunk["end_date"], errors="coerce")

        bad_mask = chunk["start_date"].isna()
        if bad_mask.any():
            invalid_date_rows += int(bad_mask.sum())
            chunk = chunk.loc[~bad_mask]

        end_missing = chunk["end_date"].isna()
        if end_missing.any():
            filled_end_rows += int(end_missing.sum())
            chunk.loc[end_missing, "end_date"] = chunk.loc[end_missing, "start_date"]

        for row in chunk.itertuples(index=False):
            cbsa = cbsa_lookup.get(row.msa)
            if cbsa is None:
                unknown_msa_rows += 1
                continue

            start = row.start_date
            end = row.end_date if row.end_date >= row.start_date else row.start_date
            for year, half in half_span(start, end):
                presence[(row.companyname, year, half)][(cbsa, row.msa)] += 1

    rows: list[tuple[str, int, int, int, str, int]] = []
    for (company, year, half), counter in tqdm(presence.items(), desc="Selecting", unit="cmp"):
        (cbsa, msa), count = counter.most_common(1)[0]
        rows.append((company, year, half, cbsa, msa, count))

    pd.DataFrame(
        rows,
        columns=["companyname", "year", "half", "cbsacode", "msa", "spell_count"],
    ).to_csv(output_path, index=False)

    print(f"Wrote {output_path} (rows={len(rows):,})")
    print("\nSummary of skipped/fixed rows:")
    print(f"  invalid start_date rows dropped: {invalid_date_rows:,}")
    print(f"  end_date filled with start_date: {filled_end_rows:,}")
    print(f"  unknown MSA rows skipped:       {unknown_msa_rows:,}")


if __name__ == "__main__":
    main()
