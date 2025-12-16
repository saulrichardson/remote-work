#!/usr/bin/env python3
"""
Build a firm-by-half-year (H1/H2) panel from a large vacancy-level CSV.

Inputs
  - A CSV like Postings_scoop.csv with at least: companyname, post_date, gap
    • post_date: timestamp or date string
    • gap: days between posting and filling; NaN/blank if never filled (expired)

Outputs
  - CSV with metrics by firm and half-year, including zero-filled periods for
    firms present anywhere in the file.

Metrics per firm x half-year:
  - vacancies: number of vacancies posted in that half-year
  - filled_<=3mo: count of vacancies with gap <= threshold_days (default 90)
  - prop_filled_<=3mo: filled_<=3mo / vacancies (blank when vacancies==0)
  - unfilled: count of vacancies with missing gap
  - avg_gap_days: average of gap with missing treated as 365 days; NaN if vacancies==0

Notes
  - This script streams the CSV to handle very large files.
  - The first unnamed index column (if present) is ignored.
  - Half-year is based on post_date month: H1=Jan–Jun, H2=Jul–Dec.

Example
  python py/build_halfyear_panel.py \
    --input data/raw/vacancy/Postings_scoop.csv \
    --output data/clean/vacancy/firm_halfyear_panel.csv \
    --threshold-days 90
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import os
from collections import defaultdict
from typing import Dict, Tuple


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build firm-by-half-year panel from vacancy CSV")
    p.add_argument("--input", required=True, help="Path to Postings_scoop.csv")
    p.add_argument("--output", required=True, help="Output CSV path for panel")
    p.add_argument("--threshold-days", type=int, default=90, help="Days cutoff for 'filled within 3 months'")
    p.add_argument("--min-year-valid", type=int, default=1900, help="Skip rows with post_date year below this")
    p.add_argument("--max-year-valid", type=int, default=2100, help="Skip rows with post_date year above this")
    p.add_argument("--limit", type=int, default=0, help="Optional row limit for sampling/testing")
    p.add_argument("--progress-every", type=int, default=1_000_000, help="Log progress every N rows (0 to disable)")
    return p.parse_args()


def to_half_year(d: dt.date) -> Tuple[int, int]:
    """Return (year, half) where half is 1 or 2."""
    half = 1 if d.month <= 6 else 2
    return d.year, half


def parse_date(s: str) -> dt.date | None:
    s = s.strip()
    if not s:
        return None
    # Try common formats quickly without full dateutil dependency
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%Y/%m/%d",
    ):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    # Fallback: attempt to split at space and parse date part
    if " " in s:
        try:
            return dt.datetime.fromisoformat(s.split(" ")[0]).date()
        except Exception:
            pass
    # Last resort: try fromisoformat
    try:
        return dt.date.fromisoformat(s[:10])
    except Exception:
        return None


def safe_float(s: str) -> float | None:
    s = s.strip()
    if not s or s.lower() in {"na", "n/a", "null", "none"}:
        return None
    try:
        v = float(s)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return v


def main() -> None:
    args = parse_args()
    inp = args.input
    outp = args.output
    thr = int(args.threshold_days)
    min_year_valid = int(args.min_year_valid)
    max_year_valid = int(args.max_year_valid)

    os.makedirs(os.path.dirname(outp), exist_ok=True)

    # Aggregation dict: (company, year, half) -> metrics accumulators
    # Each value: [vacancies, filled_le_thr, unfilled, gap_sum_with_fill]
    agg: Dict[Tuple[str, int, int], list] = defaultdict(lambda: [0, 0, 0, 0.0])

    firms = set()
    min_year_half: Tuple[int, int] | None = None
    max_year_half: Tuple[int, int] | None = None

    # Column name map
    needed_cols = {"companyname", "post_date", "gap"}

    total_rows = 0

    with open(inp, "r", newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        headers = next(reader)
        # Build mapping from header to index, ignoring duplicate/blank first column
        col_idx = {}
        for i, h in enumerate(headers):
            hh = h.strip()
            if hh == "":
                # likely an unnamed index column; skip
                continue
            # only keep first occurrence for any duplicate names
            if hh not in col_idx:
                col_idx[hh] = i

        missing = needed_cols - set(col_idx.keys())
        if missing:
            raise SystemExit(f"Input missing required columns: {sorted(missing)}")

        def get(row, name: str) -> str:
            i = col_idx.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        for row in reader:
            total_rows += 1
            if args.limit and total_rows > args.limit:
                break

            company = get(row, "companyname")
            if not company:
                # Skip rows without firm name
                continue

            pd_str = get(row, "post_date")
            d = parse_date(pd_str)
            if d is None:
                # If no valid date, skip row
                continue
            if d.year < min_year_valid or d.year > max_year_valid:
                # Skip obviously invalid years (e.g., year=2)
                continue
            year, half = to_half_year(d)

            # Track global min/max year-half
            yh = (year, half)
            if min_year_half is None or yh < min_year_half:
                min_year_half = yh
            if max_year_half is None or yh > max_year_half:
                max_year_half = yh

            firms.add(company)

            gap_val = safe_float(get(row, "gap"))
            is_unfilled = gap_val is None
            filled_le_thr = (gap_val is not None) and (gap_val <= thr)
            gap_for_avg = 365.0 if gap_val is None else float(gap_val)

            key = (company, year, half)
            acc = agg[key]
            acc[0] += 1  # vacancies
            acc[1] += 1 if filled_le_thr else 0
            acc[2] += 1 if is_unfilled else 0
            acc[3] += gap_for_avg

            if args.progress_every and (total_rows % args.progress_every == 0):
                print(f"Processed {total_rows:,} rows...", flush=True)

    if min_year_half is None or max_year_half is None:
        raise SystemExit("No valid rows found in input.")

    # Build full index of (year, half) across global range
    (min_y, min_h) = min_year_half
    (max_y, max_h) = max_year_half

    periods: list[Tuple[int, int]] = []
    y, h = min_y, min_h
    while True:
        periods.append((y, h))
        if (y, h) == (max_y, max_h):
            break
        # advance half-year
        if h == 1:
            h = 2
        else:
            y += 1
            h = 1

    # Write output CSV
    with open(outp, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow([
            "companyname",
            "year",
            "half",
            "period",
            "vacancies",
            "filled_<=3mo",
            "prop_filled_<=3mo",
            "unfilled",
            "avg_gap_days",
        ])

        # deterministically order firms
        for company in sorted(firms):
            for (year, half) in periods:
                key = (company, year, half)
                vac, filled_le, unfilled, gap_sum = agg.get(key, [0, 0, 0, 0.0])
                if vac > 0:
                    prop = filled_le / vac
                    avg_gap = gap_sum / vac
                else:
                    prop = ""
                    avg_gap = ""
                period_label = f"{year}H{half}"
                w.writerow([
                    company,
                    year,
                    half,
                    period_label,
                    vac,
                    filled_le,
                    (round(prop, 6) if prop != "" else ""),
                    unfilled,
                    round(avg_gap, 6) if avg_gap != "" else "",
                ])

    print(
        f"Done. Processed {total_rows:,} rows across {len(firms):,} firms, "
        f"periods {min_year_half} to {max_year_half}. Output: {outp}")


if __name__ == "__main__":
    main()
