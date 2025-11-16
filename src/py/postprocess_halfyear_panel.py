#!/usr/bin/env python3
"""
Postprocess merged half-year panel with guardrails and winsorization.

Inputs
  --input: merged CSV from merge_halfyear_with_firm_panel.py
  --output: path for augmented CSV

Adds columns:
  - hires_to_vacancies_raw  (computed as join/vacancies when defined)
  - hires_to_vacancies_guarded_min{1..5}
  - hires_to_vacancies_winsor_min{1..5}    (winsor 1/99)
  - hires_to_vacancies_winsor95_min{1..5}  (winsor 5/95)
  - hires_to_vacancies_winsor (alias of hires_to_vacancies_winsor_min5)
  - vpe_pc_guarded (vacancies per pre-COVID employees; denominator firm employment in 2019H2)
  - upe_pc_guarded (unfilled per pre-COVID employees)
  - vpe_pc_winsor
  - upe_pc_winsor

Guardrails (defaults):
  - Pre-COVID per-employee ratios only if pre-COVID (2019H2) employees >= 100
  - Hires-to-vacancies series constructed from raw join/vacancies; for each k in {1..5},
    the guarded sample requires vacancies >= k (and join, vacancies nonnegative; divide-by-zero avoided).
  - Blank ratios if inputs missing or negative
  - For pre-COVID ratios, use firm total_employees in 2019H2 (year=2019, half=2) and require it >= 100

Winsorization:
  - Apply to guarded values only
  - For per-employee ratios, cap at CLI-provided percentiles (defaults: 1/99)
  - For hires-to-vacancies, emit two sets per cutoff: 1/99 and 5/95

Example
  python py/postprocess_halfyear_panel.py \
    --input data/cleaned/vacancy/firm_halfyear_panel_MERGED.csv \
    --output data/cleaned/vacancy/firm_halfyear_panel_MERGED_POST.csv \
    --min-lag-employees 100 --winsor-low 1 --winsor-high 99
"""
from __future__ import annotations

import argparse
import csv
import math
import os
from typing import List, Tuple


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply guardrails and winsorization to merged panel")
    p.add_argument("--input", required=True, help="Input merged CSV path")
    p.add_argument("--output", required=True, help="Output CSV path")
    p.add_argument("--min-lag-employees", type=float, default=100.0, help="Minimum pre-COVID employees (2019H2) to compute per-employee ratios")
    p.add_argument("--winsor-low", type=float, default=1.0, help="Lower percentile for winsorization (0-100)")
    p.add_argument("--winsor-high", type=float, default=99.0, help="Upper percentile for winsorization (0-100)")
    return p.parse_args()


def to_float(x: str) -> float | None:
    x = (x or '').strip()
    if x == '':
        return None
    try:
        v = float(x)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return v


def pctile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return float('nan')
    n = len(sorted_vals)
    i = int(round(p * (n - 1)))
    i = max(0, min(i, n - 1))
    return sorted_vals[i]


def main() -> None:
    args = parse_args()
    inp = args.input
    outp = args.output
    os.makedirs(os.path.dirname(outp), exist_ok=True)

    min_emp = float(args.min_lag_employees)
    lo = float(args.winsor_low) / 100.0
    hi = float(args.winsor_high) / 100.0
    if not (0.0 <= lo < hi <= 1.0):
        raise SystemExit("Invalid winsor percentiles; require 0 <= low < high <= 100")

    # First pass: collect key fields and pre-COVID denominators
    rows = []
    # For HTV, we will collect per-cutoff values separately for 1/99 and 5/95 later
    # Pre-COVID baseline employment by firm (2019H2)
    precovid_emp_by_firm: dict[str, float] = {}

    with open(inp, 'r', encoding='utf-8', errors='replace', newline='') as fi:
        r = csv.DictReader(fi)
        fields = r.fieldnames or []
        # Fail fast: verify required input columns exist
        required_inputs = [
            'companyname', 'year', 'half', 'yh',
            'vacancies', 'filled_<=3mo', 'unfilled', 'join', 'total_employees',
        ]
        missing_in = [c for c in required_inputs if c not in fields]
        if missing_in:
            raise SystemExit(f"Missing required input columns: {missing_in}")
        for row in r:
            vac = to_float(row.get('vacancies'))
            emp_lag = to_float(row.get('total_employees_lag'))
            unfilled = to_float(row.get('unfilled'))
            join = to_float(row.get('join'))
            # Rebuild hires_to_vacancies from raw components to avoid upstream pre-cuts
            htv_raw = None
            if join is not None and join >= 0 and vac is not None and vac > 0:
                htv_raw = join / vac

            # Capture pre-COVID employment per firm (2019H2)
            firm = (row.get('companyname') or '').strip()
            try:
                year = int(row.get('year')) if row.get('year') else None
                half = int(row.get('half')) if row.get('half') else None
            except Exception:
                year = half = None
            if firm and year == 2019 and half == 2:
                emp_now = to_float(row.get('total_employees'))
                if emp_now is not None and emp_now >= 0:
                    precovid_emp_by_firm[firm] = emp_now

            # Stash row and HTV raw for multi-cutoff processing later
            rows.append((row, htv_raw, vac, join))

    # No prev-emp winsor thresholds; we compute pre-COVID thresholds later
    # For HTV we compute per-cutoff (1..5) and per-winsor setting (1/99 and 5/95)
    # Prepare containers: for each k, collect guarded values
    from collections import defaultdict
    htv_guarded_by_k: dict[int, List[float]] = {k: [] for k in range(1, 6)}
    # We will also count raw eligibility and guarded counts per k
    htv_counts = {k: {'raw': 0, 'guarded': 0} for k in range(1, 6)}

    for _row, htv_raw, vac, join in rows:
        # raw-defined if we could compute join/vac with vac>0 and join>=0
        raw_defined = htv_raw is not None
        for k in range(1, 6):
            if raw_defined:
                htv_counts[k]['raw'] += 1
                # Guarded if vacancies >= k and nonnegative components already ensured in raw
                if vac is not None and vac >= k and join is not None and join >= 0:
                    htv_counts[k]['guarded'] += 1
                    htv_guarded_by_k[k].append(htv_raw)

    # Winsor thresholds for HTV per k for two settings
    def winsor_thresholds(sorted_vals: List[float], lo_p: float, hi_p: float) -> tuple[float|None, float|None]:
        if not sorted_vals:
            return (None, None)
        return (pctile(sorted_vals, lo_p), pctile(sorted_vals, hi_p))

    htv_thresh_01_99 = {}
    htv_thresh_05_95 = {}
    for k in range(1, 6):
        vals_sorted = sorted(htv_guarded_by_k[k])
        lo01, hi99 = winsor_thresholds(vals_sorted, 0.01, 0.99)
        lo05, hi95 = winsor_thresholds(vals_sorted, 0.05, 0.95)
        htv_thresh_01_99[k] = (lo01, hi99)
        htv_thresh_05_95[k] = (lo05, hi95)

    def winsor(val: float | None, lo_v: float | None, hi_v: float | None) -> float | None:
        if val is None or lo_v is None or hi_v is None:
            return None
        if val < lo_v:
            return lo_v
        if val > hi_v:
            return hi_v
        return val

    # Second pass: write output with guarded and winsorized columns
    out_fields = list(rows[0][0].keys()) if rows else []
    # Drop legacy prev-emp and upstream raw HTV columns from output to avoid confusion
    for legacy_col in (
        'vacancies_per_prev_emp',
        'unfilled_per_prev_emp',
        'hires_to_vacancies',
    ):
        if legacy_col in out_fields:
            out_fields.remove(legacy_col)
    out_fields += [
        'hires_to_vacancies_raw',
        'vpe_pc_guarded',
        'upe_pc_guarded',
        'vpe_pc_winsor',
        'upe_pc_winsor',
    ]
    # Fill-rate variants
    out_fields.append('fill_rate_raw')
    for k in range(1, 6):
        out_fields.append(f'fill_rate_min{k}')
    out_fields.append('fill_rate')  # alias = min5
    # Add HTV guarded/winsor columns for k=1..5
    for k in range(1, 6):
        out_fields.append(f'hires_to_vacancies_guarded_min{k}')
    for k in range(1, 6):
        out_fields.append(f'hires_to_vacancies_winsor_min{k}')
    for k in range(1, 6):
        out_fields.append(f'hires_to_vacancies_winsor95_min{k}')
    # Back-compat alias (min5 1/99)
    out_fields.append('hires_to_vacancies_winsor')
    # Fail fast: ensure required outputs will be present in header
    required_outputs = [
        'vpe_pc_winsor', 'upe_pc_winsor',
        'fill_rate',
        *[f'fill_rate_min{k}' for k in range(1, 6)],
        'hires_to_vacancies_winsor',
        *[f'hires_to_vacancies_winsor_min{k}' for k in range(1, 6)],
        *[f'hires_to_vacancies_winsor95_min{k}' for k in range(1, 6)],
    ]
    missing_out = [c for c in required_outputs if c not in out_fields]
    if missing_out:
        raise SystemExit(f"Internal error: required outputs missing from header: {missing_out}")

    with open(outp, 'w', encoding='utf-8', newline='') as fo:
        w = csv.DictWriter(fo, fieldnames=out_fields)
        w.writeheader()
        # Compute winsor thresholds for pre-COVID ratios by first scanning all rows
        vpe_pc_vals: List[float] = []
        upe_pc_vals: List[float] = []
        for row, htv_raw, vac, join in rows:
            firm = (row.get('companyname') or '').strip()
            emp_pc = precovid_emp_by_firm.get(firm)
            if emp_pc is not None and emp_pc >= min_emp:
                vac2 = to_float(row.get('vacancies'))
                unfilled2 = to_float(row.get('unfilled'))
                if vac2 is not None and vac2 >= 0:
                    vpe_pc_vals.append(vac2 / emp_pc)
                if unfilled2 is not None and unfilled2 >= 0:
                    upe_pc_vals.append(unfilled2 / emp_pc)
        vpe_pc_vals_sorted = sorted(vpe_pc_vals)
        upe_pc_vals_sorted = sorted(upe_pc_vals)
        vpe_pc_lo = pctile(vpe_pc_vals_sorted, lo) if vpe_pc_vals_sorted else None
        vpe_pc_hi = pctile(vpe_pc_vals_sorted, hi) if vpe_pc_vals_sorted else None
        upe_pc_lo = pctile(upe_pc_vals_sorted, lo) if upe_pc_vals_sorted else None
        upe_pc_hi = pctile(upe_pc_vals_sorted, hi) if upe_pc_vals_sorted else None

        # Now write rows with both prev-emp and pre-COVID variants
        for row, htv_raw, vac, join in rows:
            # Prepare output dict limited to declared out_fields
            row_out = {k: (row.get(k, '') if row.get(k, '') is not None else '') for k in out_fields}

            # Emit HTV raw
            row_out['hires_to_vacancies_raw'] = '' if htv_raw is None else f"{htv_raw}"

            # Pre-COVID per-employee ratios
            firm = (row.get('companyname') or '').strip()
            emp_pc = precovid_emp_by_firm.get(firm)
            vac2 = to_float(row.get('vacancies'))
            unfilled2 = to_float(row.get('unfilled'))
            vpe_pc_g = None
            if emp_pc is not None and emp_pc >= min_emp and vac2 is not None and vac2 >= 0:
                vpe_pc_g = vac2 / emp_pc
            upe_pc_g = None
            if emp_pc is not None and emp_pc >= min_emp and unfilled2 is not None and unfilled2 >= 0:
                upe_pc_g = unfilled2 / emp_pc
            row_out['vpe_pc_guarded'] = '' if vpe_pc_g is None else f"{vpe_pc_g}"
            row_out['upe_pc_guarded'] = '' if upe_pc_g is None else f"{upe_pc_g}"
            row_out['vpe_pc_winsor'] = '' if vpe_pc_g is None else f"{winsor(vpe_pc_g, vpe_pc_lo, vpe_pc_hi)}"
            row_out['upe_pc_winsor'] = '' if upe_pc_g is None else f"{winsor(upe_pc_g, upe_pc_lo, upe_pc_hi)}"

            # Per-cutoff guarded and winsorized values
            min5_01_99_value = ''
            for k in range(1, 6):
                # guarded
                if htv_raw is not None and vac is not None and vac >= k and join is not None and join >= 0:
                    row_out[f'hires_to_vacancies_guarded_min{k}'] = f"{htv_raw}"
                    lo01, hi99 = htv_thresh_01_99[k]
                    lo05, hi95 = htv_thresh_05_95[k]
                    # winsor 1/99
                    row_out[f'hires_to_vacancies_winsor_min{k}'] = f"{winsor(htv_raw, lo01, hi99)}"
                    # winsor 5/95
                    row_out[f'hires_to_vacancies_winsor95_min{k}'] = f"{winsor(htv_raw, lo05, hi95)}"
                    if k == 5:
                        min5_01_99_value = row_out[f'hires_to_vacancies_winsor_min{k}']
                else:
                    row_out[f'hires_to_vacancies_guarded_min{k}'] = ''
                    row_out[f'hires_to_vacancies_winsor_min{k}'] = ''
                    row_out[f'hires_to_vacancies_winsor95_min{k}'] = ''

            # Legacy alias: hires_to_vacancies_winsor = min5 (1/99)
            row_out['hires_to_vacancies_winsor'] = min5_01_99_value

            # Fill rate computations
            vac2 = to_float(row.get('vacancies'))
            filled2 = to_float(row.get('filled_<=3mo'))
            fr_raw = None
            if filled2 is not None and filled2 >= 0 and vac2 is not None and vac2 > 0:
                fr_raw = filled2 / vac2
            row_out['fill_rate_raw'] = '' if fr_raw is None else f"{fr_raw}"

            fr_min5_val = ''
            for k in range(1, 6):
                if fr_raw is not None and vac2 is not None and vac2 >= k:
                    row_out[f'fill_rate_min{k}'] = f"{fr_raw}"
                    if k == 5:
                        fr_min5_val = row_out[f'fill_rate_min{k}']
                else:
                    row_out[f'fill_rate_min{k}'] = ''
            row_out['fill_rate'] = fr_min5_val

            w.writerow(row_out)

    # Print summary
    def fmt(x):
        return 'n/a' if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x}"
    print('Guardrails: min_preCOVID_employees=', min_emp, ' (HTV cutoffs emitted for k=1..5)')
    print('Winsorization percentiles: low=', args.winsor_low, ' high=', args.winsor_high)
    print('Pre-COVID ratios thresholds: vpe_pc_lo=', fmt(vpe_pc_lo), ' vpe_pc_hi=', fmt(vpe_pc_hi), ' n=', len(vpe_pc_vals))
    print('Pre-COVID ratios thresholds: upe_pc_lo=', fmt(upe_pc_lo), ' upe_pc_hi=', fmt(upe_pc_hi), ' n=', len(upe_pc_vals))
    for k in range(1, 6):
        lo01, hi99 = htv_thresh_01_99[k]
        lo05, hi95 = htv_thresh_05_95[k]
        print(f'HTV k={k}: raw={htv_counts[k]["raw"]} guarded={htv_counts[k]["guarded"]} | p01/99 lo={fmt(lo01)} hi={fmt(hi99)} | p05/95 lo={fmt(lo05)} hi={fmt(hi95)}')

    # Fill rate counts
    fill_counts = {k: 0 for k in range(1, 6)}
    fill_raw_n = 0
    for row, htv_raw, vac, join in rows:
        vac2 = to_float(row.get('vacancies'))
        filled2 = to_float(row.get('filled_<=3mo'))
        fr_raw = filled2 is not None and filled2 >= 0 and vac2 is not None and vac2 > 0
        if fr_raw:
            fill_raw_n += 1
            for k in range(1, 6):
                if vac2 is not None and vac2 >= k:
                    fill_counts[k] += 1
    for k in range(1, 6):
        print(f'FillRate k={k}: raw={fill_raw_n} guarded={fill_counts[k]}')

    # Fail fast: basic monotonicity and positivity checks
    def is_monotone_desc(vals: List[int]) -> bool:
        return all(vals[i] >= vals[i+1] for i in range(len(vals)-1))

    htv_guarded_seq = [htv_counts[k]['guarded'] for k in range(1, 6)]
    if any(v <= 0 for v in htv_guarded_seq):
        raise SystemExit(f"HTV guarded counts must be positive for all cutoffs; got {htv_guarded_seq}")
    if not is_monotone_desc(htv_guarded_seq):
        raise SystemExit(f"HTV guarded counts must be monotonically non-increasing with k; got {htv_guarded_seq}")

    fill_guarded_seq = [fill_counts[k] for k in range(1, 6)]
    if fill_raw_n <= 0 or any(v <= 0 for v in fill_guarded_seq):
        raise SystemExit(f"Fill-rate counts must be positive; raw={fill_raw_n}, guarded={fill_guarded_seq}")
    if not is_monotone_desc(fill_guarded_seq):
        raise SystemExit(f"Fill-rate guarded counts must be monotonically non-increasing with k; got {fill_guarded_seq}")


if __name__ == '__main__':
    main()
