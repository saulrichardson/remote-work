#!/usr/bin/env python3
"""
Build firm-by-half-year panels for multiple fill thresholds in a single pass.

This streams Postings_scoop.csv once and produces, for each threshold in
--thresholds, an output CSV identical in schema to build_halfyear_panel.py:

  companyname, year, half, period, vacancies,
  filled_<=3mo, prop_filled_<=3mo, unfilled, avg_gap_days

Notes
  - Column names retain '3mo' for compatibility, but counts reflect the
    provided threshold (in days).
  - Unfilled gaps are treated as 365 days when averaging (same as single build).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import os
from collections import defaultdict
from typing import Dict, Tuple, List


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build multi-threshold vacancy panels in one pass")
    p.add_argument("--input", required=True, help="Path to Postings_scoop.csv")
    p.add_argument("--outdir", required=True, help="Base directory to write per-threshold panels")
    p.add_argument("--thresholds", nargs="+", type=int, required=True, help="Day thresholds, e.g., 30 60 90 120 150")
    p.add_argument("--min-year-valid", type=int, default=1900)
    p.add_argument("--max-year-valid", type=int, default=2100)
    p.add_argument("--limit", type=int, default=0, help="Optional row cap for testing")
    p.add_argument("--progress-every", type=int, default=1_000_000, help="Print progress every N rows (0 to disable)")
    return p.parse_args()


def to_half_year(d: dt.date) -> Tuple[int, int]:
    return (d.year, 1 if d.month <= 6 else 2)


def parse_date(s: str) -> dt.date | None:
    s = (s or '').strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    if " " in s:
        try:
            return dt.datetime.fromisoformat(s.split(" ")[0]).date()
        except Exception:
            pass
    try:
        return dt.date.fromisoformat(s[:10])
    except Exception:
        return None


def safe_float(s: str) -> float | None:
    s = (s or '').strip()
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
    outdir = args.outdir
    thr_list: List[int] = [int(t) for t in args.thresholds]
    min_year_valid = int(args.min_year_valid)
    max_year_valid = int(args.max_year_valid)

    os.makedirs(outdir, exist_ok=True)

    # Aggregators
    agg_common: Dict[Tuple[str, int, int], List[float]] = defaultdict(lambda: [0, 0, 0.0])
    # vacancies, unfilled, gap_sum_with_fill
    agg_thr: Dict[int, Dict[Tuple[str, int, int], int]] = {t: defaultdict(int) for t in thr_list}

    firms = set()
    min_yh: Tuple[int, int] | None = None
    max_yh: Tuple[int, int] | None = None

    total_rows = 0

    with open(inp, "r", newline="", encoding="utf-8", errors="replace") as f:
        r = csv.reader(f)
        headers = next(r)
        col_idx = {}
        for i, h in enumerate(headers):
            hh = (h or '').strip()
            if not hh:
                continue
            if hh not in col_idx:
                col_idx[hh] = i
        for req in ("companyname", "post_date", "gap"):
            if req not in col_idx:
                raise SystemExit(f"Input missing required column: {req}")

        def get(row, name: str) -> str:
            i = col_idx.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        for row in r:
            total_rows += 1
            if args.limit and total_rows > args.limit:
                break

            firm = get(row, "companyname")
            if not firm:
                continue
            d = parse_date(get(row, "post_date"))
            if d is None or d.year < min_year_valid or d.year > max_year_valid:
                continue
            year, half = to_half_year(d)
            yh = (year, half)
            if min_yh is None or yh < min_yh:
                min_yh = yh
            if max_yh is None or yh > max_yh:
                max_yh = yh
            firms.add(firm)

            gap_val = safe_float(get(row, "gap"))
            is_unfilled = gap_val is None
            gap_for_avg = 365.0 if gap_val is None else float(gap_val)

            key = (firm, year, half)
            acc = agg_common[key]
            acc[0] += 1  # vacancies
            acc[1] += 1 if is_unfilled else 0
            acc[2] += gap_for_avg

            if gap_val is not None:
                g = float(gap_val)
                for t in thr_list:
                    if g <= t:
                        agg_thr[t][key] += 1

            if args.progress_every and (total_rows % args.progress_every == 0):
                print(f"Processed {total_rows:,} rows...", flush=True)

    if min_yh is None or max_yh is None:
        raise SystemExit("No valid rows found.")

    # Build global periods list
    (min_y, min_h) = min_yh
    (max_y, max_h) = max_yh
    periods: List[Tuple[int, int]] = []
    y, h = min_y, min_h
    while True:
        periods.append((y, h))
        if (y, h) == (max_y, max_h):
            break
        if h == 1:
            h = 2
        else:
            y += 1
            h = 1

    # Write one panel per threshold
    for t in thr_list:
        out_dir_t = os.path.join(outdir, f"t{t}")
        os.makedirs(out_dir_t, exist_ok=True)
        path_out = os.path.join(out_dir_t, "firm_halfyear_panel.csv")
        with open(path_out, "w", newline="", encoding="utf-8") as fo:
            w = csv.writer(fo)
            w.writerow([
                "companyname", "year", "half", "period",
                "vacancies", "filled_<=3mo", "prop_filled_<=3mo",
                "unfilled", "avg_gap_days",
            ])
            for firm in sorted(firms):
                for (year, half) in periods:
                    key = (firm, year, half)
                    vac, unfilled, gap_sum = agg_common.get(key, [0, 0, 0.0])
                    filled_le = agg_thr[t].get(key, 0)
                    if vac > 0:
                        prop = filled_le / vac
                        avg_gap = gap_sum / vac
                    else:
                        prop = ""
                        avg_gap = ""
                    period_label = f"{year}H{half}"
                    w.writerow([
                        firm, year, half, period_label,
                        vac, filled_le, (round(prop, 6) if prop != "" else ""), unfilled,
                        round(avg_gap, 6) if avg_gap != "" else "",
                    ])
        print(f"✓ Wrote {path_out}")

    print(
        f"Done. Processed {total_rows:,} rows across {len(firms):,} firms. "
        f"Periods {min_yh} to {max_yh}. Thresholds: {thr_list}"
    )


if __name__ == "__main__":
    main()
