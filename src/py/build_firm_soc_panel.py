"""Build company × SOC-4 × half-year panel for regressions.

This is the *fine-grain* counterpart to *build_firm_panel.py*: we keep the
occupation dimension (`soc4`) so every observation is a firm–occupation–time
cell.  The panel includes the same outcome variables and static firm
attributes as the original Stata pipeline, plus `tight_wavg`.

Inputs
------
1. data/clean/firm_occ_panel_enriched.parquet  (already built)
2. Static firm attributes (same as firm_panel script)

Outputs
-------
data/clean/firm_soc_panel_enriched.parquet
data/clean/firm_soc_panel_enriched.dta

Variables
---------
key ids      : companyname, soc4, yh, firm_id, soc_id
outcomes     : growth_rate_we, join_rate_we, leave_rate_we
attributes   : remote, teleworkable, startup, covid, tight_wavg, etc.

All names match those expected by *spec/stata/firm_scaling.do*, so you can adapt the
Stata code by absorbing `firm_id yh` (or add `soc_id` if desired).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Fallback engine for parquet if pyarrow missing
import duckdb as dk

from project_paths import DATA_PROCESSED, DATA_RAW

PROC = DATA_PROCESSED
RAW = DATA_RAW

# Input occupation panel (already enriched with tightness)
# The build_firm_occ_tightness.py script now writes only CSV.  We first look
# for the CSV file; if it is absent we fall back to the legacy Parquet path.
PANEL_OCC_CSV = PROC / "firm_occ_panel_enriched.csv"
PANEL_OCC_PARQ = PROC / "firm_occ_panel_enriched.parquet"

# Static firm attributes
PATH_TELE = PROC / "scoop_firm_tele_2.dta"
PATH_REMOTE = RAW / "Scoop_clean_public.dta"
PATH_FOUND = RAW / "Scoop_founding.dta"

# Output
OUT_CSV = PROC / "firm_soc_panel_enriched.csv"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------


def _read_occ_panel() -> pd.DataFrame:
    """Load the occupation panel regardless of whether it is stored as CSV or Parquet."""

    if PANEL_OCC_CSV.exists():
        return pd.read_csv(PANEL_OCC_CSV)

    if PANEL_OCC_PARQ.exists():
        # Parquet via pandas first, fallback to DuckDB if pyarrow missing
        try:
            return pd.read_parquet(PANEL_OCC_PARQ)
        except Exception:
            con = dk.connect()
            return con.execute(
                f"SELECT * FROM parquet_scan('{PANEL_OCC_PARQ.as_posix()}')"
            ).fetch_df()

    raise FileNotFoundError(
        "Occupation panel not found – expected CSV or Parquet in data/clean."
    )


def _winsor(s: pd.Series, p: float = 0.01) -> pd.Series:
    lo, hi = s.quantile([p, 1 - p])
    return s.clip(lo, hi)


def _prep_static(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df[cols].drop_duplicates().copy()
    out["companyname"] = out["companyname"].str.lower()
    return out


# ---------------------------------------------------------------------------
# Build routine
# ---------------------------------------------------------------------------


def build() -> None:  # noqa: C901
    occ = _read_occ_panel()
    occ["companyname"] = occ["companyname"].str.lower()

    # --- Year & lagged headcount within firm-SOC --------------------------
    occ = occ.sort_values(["companyname", "soc4", "yh"]).reset_index(drop=True)
    occ["year"] = (occ["yh"] // 2).astype(int)

    occ["headcount_lag"] = occ.groupby(["companyname", "soc4"])["headcount"].shift(1)

    # Outcomes
    occ["growth_rate"] = (occ["headcount"] / occ["headcount_lag"] - 1).replace([np.inf, -np.inf], np.nan)
    occ["join_rate"] = (occ["joins"] / occ["headcount_lag"]).replace([np.inf, -np.inf], np.nan)
    occ["leave_rate"] = (occ["leaves"] / occ["headcount_lag"]).replace([np.inf, -np.inf], np.nan)

    # Winsorise
    for var in ("growth_rate", "join_rate", "leave_rate"):
        occ[f"{var}_we"] = _winsor(occ[var])

    # --- Merge static firm attributes ------------------------------------
    tele = _prep_static(pd.read_stata(PATH_TELE), ["companyname", "teleworkable"])
    remote = _prep_static(pd.read_stata(PATH_REMOTE), ["companyname", "flexibility_score2"]).rename(
        columns={"flexibility_score2": "remote"}
    )
    found = _prep_static(pd.read_stata(PATH_FOUND), ["companyname", "founded"])

    panel = occ.merge(tele, on="companyname", how="left").merge(remote, on="companyname", how="left").merge(
        found, on="companyname", how="left"
    )

    # Derived flags --------------------------------------------------------
    panel["age"] = 2020 - panel["founded"]
    panel["startup"] = panel["age"] <= 10
    panel["covid"] = panel["year"] >= 2020

    panel["var3"] = panel["remote"] * panel["covid"]
    panel["var4"] = panel["covid"] * panel["startup"]
    panel["var5"] = panel["remote"] * panel["covid"] * panel["startup"]
    panel["var6"] = panel["covid"] * panel["teleworkable"]
    panel["var7"] = panel["startup"] * panel["covid"] * panel["teleworkable"]

    # Numeric ids
    panel = panel.sort_values(["companyname", "soc4", "yh"]).reset_index(drop=True)
    panel["firm_id"] = pd.factorize(panel["companyname"])[0] + 1
    panel["soc_id"] = pd.factorize(panel["soc4"])[0] + 1

    # Drop rows with missing core vars (same rule as Stata pipeline)
    keep_vars = [
        "firm_id",
        "soc4",
        "yh",
        "covid",
        "remote",
        "startup",
        "teleworkable",
        "growth_rate_we",
        "join_rate_we",
        "leave_rate_we",
        "var3",
        "var4",
        "var5",
        "var6",
        "var7",
    ]
    panel = panel.dropna(subset=keep_vars)

    # Persist --------------------------------------------------------------
    panel.to_csv(OUT_CSV, index=False)

    print(
        f"✓ firm_soc_panel_enriched written → {OUT_CSV.name}\n  rows: {len(panel):,}"
    )


if __name__ == "__main__":
    build()
