"""Create a *firm-level* half-year panel that mirrors the variables used in
Stata's  *build_firm_panel.do*, but starting from the *Python*-generated
firm_occ_panel_enriched.parquet (company × SOC-4 × half-year).

The goal is to make the resulting dataset usable directly with the existing
`spec/firm_scaling.do` regression script – i.e., provide the same variable
names and transformations that the Stata code constructs, while also carrying
the new `tight_wavg` field for future heterogeneous analyses.

Key steps
----------
1. Collapse the occupation-level panel to firm × half-year, aggregating
   `headcount`, `joins`, `leaves`, and (for now) taking the *headcount-weighted*
   mean of `tight_wavg` so every firm–time record has a single tightness.
2. Compute growth_rate, join_rate, leave_rate using the previous half-year's
   headcount (same formula as the Stata code).
3. Merge the *static* firm attributes used by the original Stata pipeline:
     • teleworkable            (processed/scoop_firm_tele_2.dta)
     • flexibility_score2      (raw/Scoop_clean_public.dta → renamed → remote)
     • founding year           (raw/Scoop_founding.dta)  → age / startup
4. Winsorise growth_rate / join_rate / leave_rate to the [1,99] percentiles
   (suffix *_we*) to match Stata's `winsor2` defaults.

The script **does not merge** any Scoop attributes (teleworkable, remote,
founding year).  Those merges—and any derived interaction dummies—can be
replicated in Stata, matching the original workflow.

Output
------

    data/processed/firm_panel_enriched.csv

ready for `import delimited` in Stata.

Implementation notes
--------------------
• Requires pandas & pyarrow for fast parquet I/O; statsmodels used only for
  winsorisation quantiles (optional fallback to numpy).
• All merges are case-insensitive on `companyname` to mimic Stata behaviour.
"""

from __future__ import annotations

import datetime as _dt
import numpy as np
import pandas as pd
import duckdb as dk  # fallback reader *and* writer when pyarrow unavailable

from project_paths import DATA_PROCESSED, DATA_RAW

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROC = DATA_PROCESSED
RAW = DATA_RAW

# Occupation-level panel (CSV produced by build_firm_occ_tightness.py)
PANEL_OCC_CSV = PROC / "firm_occ_panel_enriched.csv"

# Static firm attributes
PATH_TELE = PROC / "scoop_firm_tele_2.dta"
PATH_REMOTE = RAW / "Scoop_clean_public.dta"
PATH_FOUND = RAW / "Scoop_founding.dta"


# Output (CSV only)
OUT_CSV = PROC / "firm_panel_enriched.csv"
# Also output the static firm-level tightness (2019-H2 weights)
TIGHT_STATIC_CSV = PROC / "firm_tightness_static.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _winsorise_series(s: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    lo, hi = s.quantile([lower, upper]).values
    return s.clip(lo, hi)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build() -> None:  # noqa: C901 – procedural
    # 1) Load occupation-level panel (CSV) ----------------------------------------
    if PANEL_OCC_CSV.exists():
        df_occ = pd.read_csv(PANEL_OCC_CSV)
    else:
        raise FileNotFoundError(
            "Occupation-level panel CSV not found. Run build_firm_occ_tightness.py first."
        )

    # company names to lower-case for robust merges
    df_occ["companyname"] = df_occ["companyname"].str.lower()

    # add year for later dummies
    df_occ["year"] = (df_occ["yh"] // 2).astype(int)

    # Head-count weighted tightness so that firm-level panel retains the info
    # ------------------------------------------------------------------
    # 1) Aggregate flows & headcounts to firm × yh
    # ------------------------------------------------------------------

    grouped = (
        df_occ
        .groupby(["companyname", "yh"], as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "headcount": g["headcount"].sum(),
                    "joins": g["joins"].sum(),
                    "leaves": g["leaves"].sum(),
                }
            )
        )
        .reset_index()
    )

    # ------------------------------------------------------------------
    # 2) Firm-level tightness – fixed at 2019-H2 occupational mix
    # ------------------------------------------------------------------

    YH_2019H2 = 4039  # 2019 second half (used in build_firm_occ_tightness)

    base = (
        df_occ[df_occ["yh"] == YH_2019H2]
        .groupby("companyname")
        .apply(
            lambda g: (
                np.average(
                    g.loc[g["tight_wavg"].notna(), "tight_wavg"],
                    weights=g.loc[g["tight_wavg"].notna(), "headcount"],
                )
                if g["tight_wavg"].notna().any()
                else np.nan
            )
        )
        .reset_index(name="tight_wavg")
    )

    # Persist the static firm-level tightness for downstream merges
    base.to_csv(TIGHT_STATIC_CSV, index=False)
    print(f"✓ firm_tightness_static written → {TIGHT_STATIC_CSV.name}\n  rows: {len(base):,}")

    grouped = grouped.merge(base, on="companyname", how="left")

    # Drop artefact columns that groupby.apply may create ("level_0" / "index")
    for col in ("level_0", "index"):
        if col in grouped.columns:
            grouped = grouped.drop(columns=col)

    # Year for covid flag
    grouped["year"] = (grouped["yh"] // 2).astype(int)

    # 2) Growth & flow rates --------------------------------------------------------
    grouped.sort_values(["companyname", "yh"], inplace=True)
    grouped["headcount_lag"] = grouped.groupby("companyname")["headcount"].shift(1)

    grouped["growth_rate"] = (grouped["headcount"] / grouped["headcount_lag"] - 1).replace([np.inf, -np.inf], np.nan)
    grouped["join_rate"] = (grouped["joins"] / grouped["headcount_lag"]).replace([np.inf, -np.inf], np.nan)
    grouped["leave_rate"] = (grouped["leaves"] / grouped["headcount_lag"]).replace([np.inf, -np.inf], np.nan)

    # Winsorise to [1,99] pct and add *_we columns
    for var in ("growth_rate", "join_rate", "leave_rate"):
        grouped[f"{var}_we"] = _winsorise_series(grouped[var])

    # 3) Persist – CSV only -------------------------------------------------------
    grouped.to_csv(OUT_CSV, index=False)

    print(f"✓ firm_panel_enriched written → {OUT_CSV.name}\n  rows: {len(grouped):,}")


if __name__ == "__main__":
    build()
