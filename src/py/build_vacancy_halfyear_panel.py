#!/usr/bin/env python3
"""Build the canonical vacancy half-year panel used by the active paper lane.

This builder keeps the vacancy branch narrow. It reads the raw postings file,
counts postings by firm and half-year, and zero-fills missing firm-periods
across the observed global date range so zero-vacancy periods survive the later
merge into the firm panel.

Input
-----
- data/raw/vacancy/Postings_scoop.csv
  Required columns: companyname, post_date

Output
------
- data/clean/vacancy/firm_halfyear_panel.csv
  Columns:
    - companyname
    - companyname_c
    - year
    - half
    - period   (e.g. 2020H2)
    - yh       (e.g. 2020h2)
    - vacancies
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path

from src.py.project_paths import DATA_CLEAN, DATA_RAW, ensure_dir, require_file


DEFAULT_INPUT = DATA_RAW / "vacancy" / "Postings_scoop.csv"
DEFAULT_OUTPUT = DATA_CLEAN / "vacancy" / "firm_halfyear_panel.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Raw vacancy postings CSV (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output vacancy panel CSV (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--min-year-valid",
        type=int,
        default=1900,
        help="Skip rows with post_date year below this value.",
    )
    parser.add_argument(
        "--max-year-valid",
        type=int,
        default=2100,
        help="Skip rows with post_date year above this value.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit for sampling or smoke tests.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1_000_000,
        help="Log progress every N input rows (0 disables progress logs).",
    )
    return parser.parse_args()


def parse_date(value: str) -> dt.date | None:
    text = value.strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    if " " in text:
        try:
            return dt.datetime.fromisoformat(text.split(" ")[0]).date()
        except ValueError:
            pass

    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def to_half_year(date_value: dt.date) -> tuple[int, int]:
    return date_value.year, 1 if date_value.month <= 6 else 2


def iter_periods(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    periods: list[tuple[int, int]] = []
    year, half = start
    while True:
        periods.append((year, half))
        if (year, half) == end:
            break
        if half == 1:
            half = 2
        else:
            year += 1
            half = 1
    return periods


def main() -> None:
    args = parse_args()
    input_path = require_file(
        args.input.expanduser().resolve(),
        nonempty=True,
        purpose="raw vacancy postings CSV",
    )
    output_path = args.output.expanduser().resolve()

    counts: dict[tuple[str, int, int], int] = defaultdict(int)
    firms: set[str] = set()
    min_period: tuple[int, int] | None = None
    max_period: tuple[int, int] | None = None
    total_rows = 0

    with input_path.open("r", newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration as exc:
            raise RuntimeError(f"Vacancy CSV is empty: {input_path}") from exc

        col_idx: dict[str, int] = {}
        for index, header in enumerate(headers):
            name = header.strip()
            if name and name not in col_idx:
                col_idx[name] = index

        required = {"companyname", "post_date"}
        missing = sorted(required.difference(col_idx))
        if missing:
            raise RuntimeError(
                f"Vacancy input is missing required columns: {missing}. "
                f"Expected at least companyname and post_date in {input_path}."
            )

        def get(row: list[str], name: str) -> str:
            idx = col_idx[name]
            return row[idx].strip() if idx < len(row) else ""

        for row in reader:
            total_rows += 1
            if args.limit and total_rows > args.limit:
                break

            company = get(row, "companyname")
            if not company:
                continue

            post_date = parse_date(get(row, "post_date"))
            if post_date is None:
                continue
            if post_date.year < args.min_year_valid or post_date.year > args.max_year_valid:
                continue

            year, half = to_half_year(post_date)
            period_key = (year, half)
            if min_period is None or period_key < min_period:
                min_period = period_key
            if max_period is None or period_key > max_period:
                max_period = period_key

            firms.add(company)
            counts[(company, year, half)] += 1

            if args.progress_every and total_rows % args.progress_every == 0:
                print(f"Processed {total_rows:,} vacancy rows...", flush=True)

    if min_period is None or max_period is None or not firms:
        raise RuntimeError(f"No valid vacancy rows were found in {input_path}.")

    ensure_dir(output_path.parent)
    periods = iter_periods(min_period, max_period)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["companyname", "companyname_c", "year", "half", "period", "yh", "vacancies"])
        for company in sorted(firms):
            companyname_c = company.lower()
            for year, half in periods:
                writer.writerow(
                    [
                        company,
                        companyname_c,
                        year,
                        half,
                        f"{year}H{half}",
                        f"{year}h{half}",
                        counts.get((company, year, half), 0),
                    ]
                )

    print(
        f"Wrote {output_path} with {len(firms):,} firms across "
        f"{len(periods):,} half-year periods ({min_period} to {max_period})."
    )


if __name__ == "__main__":
    main()
