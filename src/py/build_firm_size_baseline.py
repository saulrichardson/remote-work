#!/usr/bin/env python3
"""Create firm-level size baseline (employees as of 2019H2) for size-based startup specs.

- Reads data/clean/firm_panel.dta
- Prefers total_employees at 2019H2 (2019-07-01); if missing, falls back to the last pre-COVID half-year (date < 2020-01-01)
- Writes data/clean/firm_size_2019h2.dta and CSV mirror under data/samples/
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

from project_paths import DATA_CLEAN, DATA_SAMPLES, ensure_dir

INPUT = DATA_CLEAN / "firm_panel.dta"
OUTPUT_DTA = DATA_CLEAN / "firm_size_2019h2.dta"
OUTPUT_CSV = DATA_SAMPLES / "firm_size_2019h2.csv"
TARGET_DATE = pd.Timestamp("2019-07-01")  # 2019H2 in this panel
COVID_CUTOFF = pd.Timestamp("2020-01-01")  # 2020H1 boundary


def main() -> int:
    if not INPUT.exists():
        print(f"Missing input {INPUT}; run src/stata/build_firm_panel.do first.", file=sys.stderr)
        return 1

    df = pd.read_stata(INPUT)
    if "total_employees" not in df.columns:
        print("firm_panel.dta is missing `total_employees`", file=sys.stderr)
        return 1

    df["yh_dt"] = pd.to_datetime(df["yh"])
    pre = df[df["yh_dt"] < COVID_CUTOFF].copy()
    if pre.empty:
        print("No pre-COVID observations found (yh < 2020-01-01)", file=sys.stderr)
        return 1

    target = pre[pre["yh_dt"] == TARGET_DATE]
    size_at_target = target.set_index("companyname")["total_employees"]

    pre_sorted = pre.sort_values(["companyname", "yh_dt"])
    size_last_pre = pre_sorted.groupby("companyname")['total_employees'].last()

    size = size_at_target.combine_first(size_last_pre)

    out = pd.DataFrame({"companyname": size.index.astype(str), "size_2019h2": size.values})
    out = out.dropna(subset=["size_2019h2"]).copy()

    ensure_dir(DATA_CLEAN)
    ensure_dir(DATA_SAMPLES)

    out.to_stata(OUTPUT_DTA, write_index=False, version=118)
    out.to_csv(OUTPUT_CSV, index=False)

    print(f"✓ Wrote {len(out):,} firm sizes → {OUTPUT_DTA}")
    print(f"✓ CSV mirror → {OUTPUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
