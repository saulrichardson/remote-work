#!/usr/bin/env python3
"""
Merge vacancy half-year panel with firm_panel.csv to compute requested ratios.

Inputs
  --vacancy-panel: CSV from build_halfyear_panel.py
  --firm-panel: CSV containing columns: companyname, yh, total_employees, join, leave

Outputs
  CSV with merged metrics and ratios:
   - vacancies, filled_<=3mo, prop_filled_<=3mo, unfilled, avg_gap_days
   - total_employees (current), join, leave
   - total_employees_lag (previous available period for firm)
   - vacancies_per_prev_emp = vacancies / total_employees_lag
   - unfilled_per_prev_emp = unfilled / total_employees_lag
   - hires_to_vacancies = join / vacancies

Notes
  - 'yh' in firm panel should look like '2020h2'.
  - If no lag employees for a firm-period, ratios to employees are left blank.
  - hires_to_vacancies is blank when vacancies==0.
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from typing import Dict, Tuple, List


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge vacancy half-year panel with firm panel and compute ratios")
    p.add_argument("--vacancy-panel", required=True, help="Path to vacancy half-year panel CSV")
    p.add_argument("--firm-panel", required=True, help="Path to firm_panel.csv")
    p.add_argument("--output", required=True, help="Output merged CSV path")
    return p.parse_args()


def parse_yh(s: str) -> Tuple[int, int] | None:
    # Expected like '2021h1' or '2021H2'
    s = s.strip()
    if len(s) < 6 or 'h' not in s.lower():
        return None
    s_low = s.lower()
    try:
        year = int(s_low[:4])
        half = int(s_low.split('h')[1])
        if half not in (1, 2):
            return None
        return year, half
    except Exception:
        return None


def main() -> None:
    args = parse_args()
    vp = args.vacancy_panel
    fp = args.firm_panel
    outp = args.output

    os.makedirs(os.path.dirname(outp), exist_ok=True)

    # Load firm panel into dict and prepare employee time series per firm
    firm_data: Dict[Tuple[str, int, int], dict] = {}
    periods_by_firm: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    emp_series: Dict[str, List[Tuple[int, int, float]]] = defaultdict(list)

    with open(fp, 'r', newline='', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        needed = {"companyname", "yh"}
        missing = needed - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Firm panel missing columns: {sorted(missing)}")

        # Choose employee and join/leave columns if present
        # Prefer 'total_employees' (time-varying panel measure) over 'employeecount' (static)
        emp_cols = [c for c in ("total_employees", "employeecount") if c in reader.fieldnames]
        join_col = "join" if "join" in reader.fieldnames else None
        leave_col = "leave" if "leave" in reader.fieldnames else None
        firm_id_col = "firm_id" if "firm_id" in reader.fieldnames else None
        if not emp_cols:
            raise SystemExit("Firm panel must contain total_employees or employeecount column")

        for row in reader:
            firm = row.get("companyname", "").strip()
            yh = row.get("yh", "").strip()
            if not firm or not yh:
                continue
            parsed = parse_yh(yh)
            if parsed is None:
                continue
            year, half = parsed

            def to_float(x: str) -> float | None:
                x = (x or "").strip()
                if x == "":
                    return None
                try:
                    return float(x)
                except Exception:
                    return None

            emp = None
            for c in emp_cols:
                emp = to_float(row.get(c, ""))
                if emp is not None:
                    break
            j = to_float(row.get(join_col, "")) if join_col else None
            l = to_float(row.get(leave_col, "")) if leave_col else None

            key = (firm, year, half)
            firm_data[key] = {
                "total_employees": emp,
                "join": j,
                "leave": l,
                "firm_id": (row.get(firm_id_col) if firm_id_col else None),
            }
            periods_by_firm[firm].append((year, half))
            if emp is not None:
                emp_series[firm].append((year, half, emp))

    # Sort employee series for quick previous lookup
    for firm in list(emp_series.keys()):
        emp_series[firm].sort()

    # Merge with vacancy panel
    with open(vp, 'r', newline='', encoding='utf-8', errors='replace') as f_in, \
         open(outp, 'w', newline='', encoding='utf-8') as f_out:
        r = csv.DictReader(f_in)
        needed_v = {"companyname", "year", "half", "period", "vacancies", "filled_<=3mo", "prop_filled_<=3mo", "unfilled", "avg_gap_days"}
        missing_v = needed_v - set(r.fieldnames or [])
        if missing_v:
            raise SystemExit(f"Vacancy panel missing columns: {sorted(missing_v)}")

        fieldnames = [
            "companyname", "companyname_c", "year", "half", "period", "yh", "firm_id",
            "vacancies", "filled_<=3mo", "prop_filled_<=3mo", "unfilled", "avg_gap_days",
            "total_employees", "join", "leave", "total_employees_lag",
            "vacancies_per_prev_emp", "unfilled_per_prev_emp", "hires_to_vacancies",
        ]
        w = csv.DictWriter(f_out, fieldnames=fieldnames)
        w.writeheader()

        unmatched_firms = 0
        matched_rows = 0

        for row in r:
            firm = row.get("companyname", "").strip()
            try:
                year = int(row["year"]) if row.get("year") else None
                half = int(row["half"]) if row.get("half") else None
            except Exception:
                year = None
                half = None
            if not firm or year is None or half is None:
                continue

            key = (firm, year, half)
            fd = firm_data.get(key, {})
            emp = fd.get("total_employees")
            j = fd.get("join")
            l = fd.get("leave")
            # Strict immediate previous half-year employees (as of last half)
            if half == 1:
                prev_y, prev_h = year - 1, 2
            else:
                prev_y, prev_h = year, 1
            emp_prev = None
            prev_key = (firm, prev_y, prev_h)
            if prev_key in firm_data:
                emp_prev = firm_data[prev_key].get("total_employees")

            # Parse numeric vacancy stats
            def to_float(x: str) -> float | None:
                x = (x or "").strip()
                if x == "":
                    return None
                try:
                    return float(x)
                except Exception:
                    return None

            vac = to_float(row.get("vacancies", "")) or 0.0
            unfilled = to_float(row.get("unfilled", "")) or 0.0

            if emp_prev and emp_prev != 0:
                vac_per_emp_prev = vac / emp_prev
                unfilled_per_emp_prev = unfilled / emp_prev
            else:
                vac_per_emp_prev = ""
                unfilled_per_emp_prev = ""

            if vac and vac != 0 and j is not None:
                hires_to_vac = j / vac
            else:
                hires_to_vac = ""

            out_row = {
                "companyname": firm,
                "companyname_c": firm.lower(),
                "year": year,
                "half": half,
                "period": row.get("period", ""),
                "yh": f"{year}h{half}",
                "firm_id": fd.get("firm_id") if fd else "",
                "vacancies": row.get("vacancies", "0"),
                "filled_<=3mo": row.get("filled_<=3mo", "0"),
                "prop_filled_<=3mo": row.get("prop_filled_<=3mo", "0"),
                "unfilled": row.get("unfilled", "0"),
                "avg_gap_days": row.get("avg_gap_days", ""),
                "total_employees": emp if emp is not None else "",
                "join": j if j is not None else "",
                "leave": l if l is not None else "",
                "total_employees_lag": emp_prev if emp_prev is not None else "",
                "vacancies_per_prev_emp": vac_per_emp_prev if vac_per_emp_prev != "" else "",
                "unfilled_per_prev_emp": unfilled_per_emp_prev if unfilled_per_emp_prev != "" else "",
                "hires_to_vacancies": hires_to_vac if hires_to_vac != "" else "",
            }
            if fd:
                matched_rows += 1
            else:
                unmatched_firms += 1
            w.writerow(out_row)

    print(f"Merged. Vacancy rows: {matched_rows + unmatched_firms:,}; with firm data: {matched_rows:,}; without: {unmatched_firms:,}. Output: {outp}")


if __name__ == "__main__":
    main()
