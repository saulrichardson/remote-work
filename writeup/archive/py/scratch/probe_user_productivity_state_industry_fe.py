#!/usr/bin/env python3
"""Scratch probe: validate columns for user-productivity FE robustness.

Goal
----
We want to add robustness columns that include:
  • Industry × Year FE
  • Industry × Half-Year FE
  • HQ State × Year FE
  • HQ State × Half-Year FE

Before touching any production Stata specs or writeup table builders, this
script loads an existing user panel (default: user_panel_precovid.dta) and:
  1) Confirms the relevant columns exist and what they represent.
  2) Verifies core constructed variables (var3–var7) match their definitions.
  3) Reports FE “cell counts” (unique combinations) to gauge dimensionality.
  4) Prints suggested Stata `reghdfe` absorb() strings for each robustness.

This file is intentionally placed under writeup/py/scratch/ and should not be
treated as part of the main pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import DATA_CLEAN  # type: ignore


def _max_abs_diff(lhs: pd.Series, rhs: pd.Series) -> float:
    aligned = pd.concat([lhs, rhs], axis=1)
    aligned = aligned.dropna()
    if aligned.empty:
        return float("nan")
    return float((aligned.iloc[:, 0] - aligned.iloc[:, 1]).abs().max())


def _mismatch_share(lhs: pd.Series, rhs: pd.Series) -> float:
    aligned = pd.concat([lhs, rhs], axis=1)
    aligned = aligned.dropna()
    if aligned.empty:
        return float("nan")
    return float((aligned.iloc[:, 0] != aligned.iloc[:, 1]).mean())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe which columns to use for Industry/State×(Year/Half-Year) FE robustness."
    )
    parser.add_argument(
        "--panel",
        default="user_panel_precovid.dta",
        help="Filename under data/clean/ (or an absolute path). Default: %(default)s",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    panel_path = Path(args.panel)
    if not panel_path.is_absolute():
        panel_path = DATA_CLEAN / panel_path
    if not panel_path.exists():
        raise SystemExit(f"Panel not found: {panel_path}")

    # Only load the columns we need for this probe (faster than loading the full panel).
    wanted_cols = [
        # IDs and time
        "user_id",
        "firm_id",
        "yh",
        "year",
        "half",
        "y",
        # Core covariates / constructions
        "covid",
        "startup",
        "remote",
        "flexibility_score2",
        "company_teleworkable",
        "var3",
        "var4",
        "var5",
        "var6",
        "var7",
        # FE candidates
        "industry_id",
        "industry",
        "hqstate",
        # Location columns we should *not* use for HQ state (included for contrast)
        "state",
        "user_state_assigned",
        # Startup construction inputs (optional)
        "founded",
    ]

    cols_present = pd.read_stata(panel_path, iterator=True).read(1).columns
    use_cols = [c for c in wanted_cols if c in cols_present]
    missing_cols = [c for c in wanted_cols if c not in cols_present]
    if missing_cols:
        print("NOTE: requested-but-missing columns (ok for scratch):")
        for c in missing_cols:
            print(f"  - {c}")

    df = pd.read_stata(panel_path, columns=use_cols)

    print(f"\nPanel: {panel_path}")
    print(f"Rows: {len(df):,}")
    if "user_id" in df.columns:
        print(f"Unique users: {df['user_id'].nunique(dropna=True):,}")
    if "firm_id" in df.columns:
        print(f"Unique firms: {df['firm_id'].nunique(dropna=True):,}")
    if "yh" in df.columns:
        print(f"Unique half-years (yh): {df['yh'].nunique(dropna=True):,}")
        if pd.api.types.is_datetime64_any_dtype(df["yh"]):
            print(f"yh range: {df['yh'].min()} → {df['yh'].max()}")

    print("\nKey column meanings (as observed in data):")
    if "industry_id" in df.columns:
        nunq = df["industry_id"].nunique(dropna=True)
        miss = df["industry_id"].isna().mean()
        print(f"  - industry_id: encoded industry category (nunique={nunq}, missing_share={miss:.4f})")
    if "industry" in df.columns:
        nunq = df["industry"].nunique(dropna=True)
        miss = df["industry"].isna().mean()
        print(f"  - industry: industry label string (nunique={nunq}, missing_share={miss:.4f})")
    if "hqstate" in df.columns:
        nunq = df["hqstate"].nunique(dropna=True)
        miss = df["hqstate"].isna().mean()
        print(f"  - hqstate: firm HQ state (2-letter) (nunique={nunq}, missing_share={miss:.4f})")
    if "state" in df.columns:
        nunq = df["state"].nunique(dropna=True)
        print(f"  - state: worker/user location state (varies within firm) (nunique={nunq})")
    if "user_state_assigned" in df.columns:
        nunq = df["user_state_assigned"].nunique(dropna=True)
        print(f"  - user_state_assigned: worker/user inferred state (nunique={nunq})")

    # ------------------------------------------------------------------
    # Sanity-check core constructions (grounding which columns mean what)
    # ------------------------------------------------------------------
    print("\nSanity checks of constructed variables:")

    if {"remote", "flexibility_score2"}.issubset(df.columns):
        diff = _max_abs_diff(df["remote"], df["flexibility_score2"])
        print(f"  - remote == flexibility_score2: max_abs_diff={diff:g}")

    if {"covid", "year"}.issubset(df.columns):
        covid_from_year = (df["year"] >= 2020).astype(df["covid"].dtype)
        mismatch = _mismatch_share(df["covid"], covid_from_year)
        print(f"  - covid == 1(year>=2020): mismatch_share={mismatch:.6f}")

    if {"startup", "founded"}.issubset(df.columns):
        # founded can be missing; treat as mismatch only when both defined
        age = 2020 - df["founded"]
        startup_from_founded = (age <= 10).astype(df["startup"].dtype)
        mismatch = _mismatch_share(df["startup"], startup_from_founded)
        print(f"  - startup == 1(2020-founded<=10): mismatch_share={mismatch:.6f}")

    if {"var3", "remote", "covid"}.issubset(df.columns):
        diff = _max_abs_diff(df["var3"], df["remote"] * df["covid"])
        print(f"  - var3 == remote*covid: max_abs_diff={diff:g}")

    if {"var4", "startup", "covid"}.issubset(df.columns):
        diff = _max_abs_diff(df["var4"], df["startup"] * df["covid"])
        print(f"  - var4 == startup*covid: max_abs_diff={diff:g}")

    if {"var5", "remote", "startup", "covid"}.issubset(df.columns):
        diff = _max_abs_diff(df["var5"], df["remote"] * df["startup"] * df["covid"])
        print(f"  - var5 == remote*startup*covid: max_abs_diff={diff:g}")

    if {"var6", "company_teleworkable", "covid"}.issubset(df.columns):
        diff = _max_abs_diff(df["var6"], df["company_teleworkable"] * df["covid"])
        print(f"  - var6 == company_teleworkable*covid: max_abs_diff={diff:g}")

    if {"var7", "company_teleworkable", "startup", "covid"}.issubset(df.columns):
        diff = _max_abs_diff(df["var7"], df["company_teleworkable"] * df["startup"] * df["covid"])
        print(f"  - var7 == company_teleworkable*startup*covid: max_abs_diff={diff:g}")

    # ------------------------------------------------------------------
    # Stability checks (to choose HQ vs user location columns)
    # ------------------------------------------------------------------
    if "firm_id" in df.columns:
        print("\nWithin-firm stability checks:")
        for col in ["hqstate", "industry_id", "state", "user_state_assigned"]:
            if col not in df.columns:
                continue
            # NOTE: pandas' SeriesGroupBy.nunique() has produced incorrect results on some
            # large Stata-imported categoricals in this repo. The explicit agg(lambda)
            # version matches manual spot-checks.
            nunique_by_firm = df.groupby("firm_id", observed=True)[col].agg(
                lambda s: s.nunique(dropna=True)
            )
            share_multi = float((nunique_by_firm > 1).mean())
            share_none = float((nunique_by_firm == 0).mean())
            print(
                f"  - {col:18s}: firms with >1 distinct value = {share_multi:.3f}, firms with 0 non-missing = {share_none:.3f}"
            )

    # ------------------------------------------------------------------
    # FE cell counts (how many absorb categories each interaction implies)
    # ------------------------------------------------------------------
    print("\nFE cell counts (unique combinations, excluding missing):")
    fe_defs: dict[str, list[str]] = {
        "industry×year": ["industry_id", "year"],
        "industry×yh": ["industry_id", "yh"],
        "hqstate×year": ["hqstate", "year"],
        "hqstate×yh": ["hqstate", "yh"],
    }
    for name, keys in fe_defs.items():
        if not all(k in df.columns for k in keys):
            continue
        n_cells = df[keys].dropna().drop_duplicates().shape[0]
        print(f"  - {name:14s}: {n_cells:,}")

    # ------------------------------------------------------------------
    # Suggested Stata absorb() strings
    # ------------------------------------------------------------------
    print("\nSuggested Stata FE variants (absorb strings):")
    if "year" not in df.columns:
        print("  (Panel lacks `year`; in Stata you can generate it via: gen int year = year(dofh(yh)))")
    print("  Base (existing): absorb(user_id firm_id yh)")
    print("  + Industry×Year: absorb(user_id firm_id yh industry_id#year)")
    print("  + Industry×YH:   absorb(user_id firm_id industry_id#yh)")
    print("  + State×Year:    encode hqstate, gen(hqstate_id)  // once per run")
    print("                  absorb(user_id firm_id yh hqstate_id#year)")
    print("  + State×YH:      encode hqstate, gen(hqstate_id)  // once per run")
    print("                  absorb(user_id firm_id hqstate_id#yh)")

    if "industry_id" in df.columns:
        n_drop = int(df["industry_id"].isna().sum())
        if n_drop:
            print(
                f"\nSample note: industry_id is missing on {n_drop:,} rows; "
                "decide whether robustness columns should enforce a common sample "
                "by dropping these rows up front."
            )


if __name__ == "__main__":
    main()
