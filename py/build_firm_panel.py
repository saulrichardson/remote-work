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
4. Build COVID / interaction dummies exactly as in the Stata script, but with
   our own `yh` convention (year*2 + half):
       covid    = (year >= 2020)
       startup  = (age  <= 10)   where age is as of 2020
       var3     = remote * covid
       var4     = covid  * startup
       var5     = remote * covid * startup
       var6     = covid * teleworkable
       var7     = startup * covid * teleworkable
5. Winsorise growth_rate / join_rate / leave_rate to the [1,99] percentiles
   (suffix *_we*) to match Stata's `winsor2` defaults.

The script writes

    data/processed/firm_panel_enriched.dta  (Stata-13)
    data/processed/firm_panel_enriched.parquet

so downstream Stata do-files can simply replace the earlier `use` command with

    use "$processed_data/firm_panel_enriched.dta", clear

Implementation notes
--------------------
• Requires pandas & pyarrow for fast parquet I/O; statsmodels used only for
  winsorisation quantiles (optional fallback to numpy).
• All merges are case-insensitive on `companyname` to mimic Stata behaviour.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np
import pandas as pd
import duckdb as dk  # fallback reader *and* writer when pyarrow unavailable


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

PANEL_OCC_PATH = PROC / "firm_occ_panel_enriched.parquet"

# Static firm attributes
PATH_TELE = PROC / "scoop_firm_tele_2.dta"
PATH_REMOTE = RAW / "Scoop_clean_public.dta"
PATH_FOUND = RAW / "Scoop_founding.dta"


# Output
OUT_PARQUET = PROC / "firm_panel_enriched.parquet"
OUT_DTA = PROC / "firm_panel_enriched.dta"


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
    # 1) Load occupation-level panel ------------------------------------------------
    try:
        df_occ = pd.read_parquet(PANEL_OCC_PATH)
    except Exception:
        # fallback via DuckDB's parquet reader (no pyarrow dependency)
        con = dk.connect()
        df_occ = con.execute(f"SELECT * FROM parquet_scan('{PANEL_OCC_PATH.as_posix()}')").fetchdf()

    # company names to lower-case for robust merges
    df_occ["companyname"] = df_occ["companyname"].str.lower()

    # add year for later dummies
    df_occ["year"] = (df_occ["yh"] // 2).astype(int)

    # Head-count weighted tightness so that firm-level panel retains the info
    grouped = (
        df_occ
        .groupby(["companyname", "yh"], as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "headcount": g["headcount"].sum(),
                    "joins": g["joins"].sum(),
                    "leaves": g["leaves"].sum(),
                    "tight_wavg": np.average(g["tight_wavg"], weights=g["headcount"],) if g["tight_wavg"].notna().any() else np.nan,
                }
            )
        )
        .reset_index()
    )

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

    # 3) Merge static firm attributes ---------------------------------------------
    def _prep(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        return df[cols].drop_duplicates().assign(companyname=lambda d: d["companyname"].str.lower())

    tele = _prep(pd.read_stata(PATH_TELE), ["companyname", "teleworkable"])
    remote = _prep(pd.read_stata(PATH_REMOTE), ["companyname", "flexibility_score2"]).rename(
        columns={"flexibility_score2": "remote"}
    )
    founding = _prep(pd.read_stata(PATH_FOUND), ["companyname", "founded"])

    panel = grouped.merge(tele, on="companyname", how="left").merge(remote, on="companyname", how="left").merge(
        founding, on="companyname", how="left"
    )

    # 4) Derived firm-level dummies -------------------------------------------------
    panel["age"] = 2020 - panel["founded"]
    panel["startup"] = panel["age"] <= 10

    panel["covid"] = panel["year"] >= 2020

    # remote  ∈ [0,1]  → hybrid / full remote dummies if needed later
    panel["hybrid"] = (panel["remote"] > 0) & (panel["remote"] < 1)
    panel["fullrem"] = panel["remote"] == 1

    # interactions exactly as in Stata
    panel["var3"] = panel["remote"] * panel["covid"]
    panel["var4"] = panel["covid"] * panel["startup"]
    panel["var5"] = panel["remote"] * panel["covid"] * panel["startup"]
    panel["var6"] = panel["covid"] * panel["teleworkable"]
    panel["var7"] = panel["startup"] * panel["covid"] * panel["teleworkable"]

    # firm_id (numeric)
    panel = panel.sort_values(["companyname", "yh"]).reset_index(drop=True)
    panel["firm_id"] = pd.factorize(panel["companyname"])[0] + 1  # 1-based like Stata encode

    # 5) Drop rows with missing core vars to mimic Stata filtering ---------------
    keep_vars = [
        "firm_id",
        "yh",
        "covid",
        "remote",
        "startup",
        "teleworkable",
        "growth_rate_we",
        "leave_rate_we",
        "join_rate_we",
        "var3",
        "var4",
        "var5",
        "var6",
        "var7",
    ]
    panel = panel.dropna(subset=keep_vars)

    # 6) Persist ---------------------------------------------------------------
    # Persist: If pyarrow not present, fall back to DuckDB for parquet write
    try:
        panel.to_parquet(OUT_PARQUET, index=False)
    except Exception as exc:
        try:
            con = dk.connect()
            con.register("_tmp_df", panel)
            con.execute(f"COPY _tmp_df TO '{OUT_PARQUET.as_posix()}' (FORMAT 'parquet');")
        except Exception as exc2:  # pragma: no cover
            print("⚠ Failed to write parquet via pandas & duckdb:", exc, exc2)

    try:
        panel.to_stata(OUT_DTA, write_index=False, version=117)
    except Exception as exc:  # pragma: no cover
        print("⚠ Could not write .dta (", exc, ") – continuing.")

    print(f"✓ firm_panel_enriched written → {OUT_PARQUET.name} & .dta\n  rows: {len(panel):,}")


if __name__ == "__main__":
    build()
