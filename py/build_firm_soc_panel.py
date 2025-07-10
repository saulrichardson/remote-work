"""Build company × SOC-4 × half-year panel for regressions.

This is the *fine-grain* counterpart to *build_firm_panel.py*: we keep the
occupation dimension (`soc4`) so every observation is a firm–occupation–time
cell.  The panel includes the same outcome variables and static firm
attributes as the original Stata pipeline, plus `tight_wavg`.

Inputs
------
1. data/processed/firm_occ_panel_enriched.parquet  (already built)
2. Static firm attributes (same as firm_panel script)

Outputs
-------
data/processed/firm_soc_panel_enriched.parquet
data/processed/firm_soc_panel_enriched.dta

Variables
---------
key ids      : companyname, soc4, yh, firm_id, soc_id
outcomes     : growth_rate_we, join_rate_we, leave_rate_we
attributes   : remote, teleworkable, startup, covid, tight_wavg, etc.

All names match those expected by *spec/firm_scaling.do*, so you can adapt the
Stata code by absorbing `firm_id yh` (or add `soc_id` if desired).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Fallback engine for parquet if pyarrow missing
import duckdb as dk


ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

# Input occupation panel (already enriched with tightness)
PANEL_OCC = PROC / "firm_occ_panel_enriched.parquet"

# Static firm attributes
PATH_TELE = PROC / "scoop_firm_tele_2.dta"
PATH_REMOTE = RAW / "Scoop_clean_public.dta"
PATH_FOUND = RAW / "Scoop_founding.dta"

# Outputs
OUT_PARQ = PROC / "firm_soc_panel_enriched.parquet"
OUT_DTA = PROC / "firm_soc_panel_enriched.dta"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _read_parquet(path: Path) -> pd.DataFrame:
    """Read parquet via pandas (pyarrow) or fallback to DuckDB."""

    try:
        return pd.read_parquet(path)
    except Exception:  # pyarrow missing → duckdb fallback
        con = dk.connect()
        return con.execute(f"SELECT * FROM parquet_scan('{path.as_posix()}')").fetchdf()


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
    occ = _read_parquet(PANEL_OCC)
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
    try:
        panel.to_parquet(OUT_PARQ, index=False)
    except Exception:
        con = dk.connect(); con.register("_tmp", panel)
        con.execute(f"COPY _tmp TO '{OUT_PARQ.as_posix()}' (FORMAT 'parquet')")

    try:
        panel.to_stata(OUT_DTA, write_index=False, version=117)
    except Exception:
        pass

    print(f"✓ firm_soc_panel_enriched written → {OUT_PARQ.name}\n  rows: {len(panel):,}")


if __name__ == "__main__":
    build()
