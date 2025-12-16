"""Build both firm-level tightness metrics (static metro-weighted and
HQ-based) in a *single pass* over the 2019-H2 head-count file.

Outputs – written to data/clean/
------------------------------------
firm_tightness_static.csv   • columns: companyname, tight_wavg
firm_tightness_hq.csv       • columns: companyname, tight_hq

The script replaces the combination of
    build_firm_occ_tightness.py   (for the static measure) and
    build_firm_hq_tightness.py    (for the HQ measure)
for workflows that need only the firm-level aggregates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from project_paths import DATA_PROCESSED, DATA_RAW
# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROC = DATA_PROCESSED
RAW = DATA_RAW

# Inputs
PATH_HEADS = PROC / "firm_occ_msa_heads_2019H2.csv"
PATH_HQ_DTA = PROC / "modal_msa_per_firm.dta"
PATH_MSA_MAP = PROC / "enriched_msa.csv"  # maps msa string → cbsacode
PATH_OEWS = RAW / "oews" / "processed_data" / "tight_occ_msa_y.csv"

# Outputs
OUT_STATIC = PROC / "firm_tightness_static.csv"
OUT_HQ = PROC / "firm_tightness_hq.csv"


# ---------------------------------------------------------------------------
# Helper loaders
# ---------------------------------------------------------------------------


def _read_heads() -> pd.DataFrame:
    """Return DataFrame companyname, soc4, cbsa (str 5), heads."""

    cols = ["companyname", "soc4", "cbsa", "heads"]
    heads = pd.read_csv(PATH_HEADS, usecols=cols)
    heads["companyname"] = heads["companyname"].str.lower()
    heads["cbsa"] = heads["cbsa"].astype(str).str.zfill(5)
    return heads


def _read_oews() -> pd.DataFrame:
    df = pd.read_csv(PATH_OEWS, usecols=["soc4", "msa", "year", "tight_occ"])
    df = df[df["year"] == 2019].copy()
    df["msa"] = df["msa"].astype(int).astype(str).str.zfill(5)
    return df[["soc4", "msa", "tight_occ"]]


def _read_hq_lookup() -> pd.DataFrame:
    """Return DataFrame with columns companyname, cbsacode (str 5)."""

    if not PATH_HQ_DTA.exists():
        raise FileNotFoundError("modal_msa_per_firm.dta missing. Build it first.")

    hq = pd.read_stata(PATH_HQ_DTA)[["companyname", "msa"]]
    hq["companyname"] = hq["companyname"].str.lower()

    # Map MSA string to code
    msa_map = (
        pd.read_csv(PATH_MSA_MAP, usecols=["msa", "cbsacode"]).drop_duplicates()
    )
    hq = hq.merge(msa_map, on="msa", how="left")
    hq = hq.dropna(subset=["cbsacode"]).drop_duplicates("companyname")
    hq["cbsacode"] = hq["cbsacode"].astype(int).astype(str).str.zfill(5)
    return hq[["companyname", "cbsacode"]]


# ---------------------------------------------------------------------------
# Core build
# ---------------------------------------------------------------------------


def build() -> None:  # noqa: C901 – procedural
    print("Building firm-level tightness metrics (single pass)…")

    heads = _read_heads()
    oews = _read_oews()
    hq_lookup = _read_hq_lookup()

    # ------------------------------------------------------------------
    #   Static metro-weighted tightness (tight_wavg)
    # ------------------------------------------------------------------

    # Merge OEWS tightness onto heads per metro
    df = heads.merge(
        oews, left_on=["soc4", "cbsa"], right_on=["soc4", "msa"], how="left"
    )

    # Occupation-level weighted average across metros per firm
    def _occ_wavg(g: pd.DataFrame) -> float:
        mask = g["tight_occ"].notna()
        return (
            np.average(g.loc[mask, "tight_occ"], weights=g.loc[mask, "heads"])
            if mask.any() else np.nan
        )

    occ_tight = (
        df.groupby(["companyname", "soc4"]).apply(_occ_wavg).reset_index(name="tight_hat")
    )

    # Occupation totals H_{f,o}
    occ_tot = heads.groupby(["companyname", "soc4"], as_index=False)["heads"].sum()
    occ = occ_tight.merge(occ_tot, on=["companyname", "soc4"], how="left")

    # Firm-level aggregation with beta weights
    def _static_wavg(g: pd.DataFrame) -> float:
        mask = g["tight_hat"].notna()
        return (
            np.average(g.loc[mask, "tight_hat"], weights=g.loc[mask, "heads"])
            if mask.any() else np.nan
        )

    tight_static = (
        occ.groupby("companyname").apply(_static_wavg).reset_index(name="tight_wavg")
    )

    tight_static.to_csv(OUT_STATIC, index=False)
    print(f"✓ {OUT_STATIC.name} written  ({len(tight_static):,} firms)")

    # ------------------------------------------------------------------
    #   HQ tightness (tight_hq)
    # ------------------------------------------------------------------

    # Merge HQ cbsa into heads and keep rows located in HQ metro
    df_hq = heads.merge(hq_lookup, on="companyname", how="left")
    df_hq = df_hq[df_hq["cbsa"] == df_hq["cbsacode"]].copy()

    if df_hq.empty:
        print("[warn] No HQ head-counts found; tight_hq will be empty.")
        tight_hq = hq_lookup[["companyname"]].copy()
        tight_hq["tight_hq"] = np.nan
    else:
        # Occupation totals within HQ
        occ_hq_tot = df_hq.groupby(["companyname", "soc4"], as_index=False)["heads"].sum()

        # Merge OEWS tightness for HQ metro
        occ_hq = occ_hq_tot.merge(
            hq_lookup, on="companyname", how="left"
        ).merge(
            oews, left_on=["soc4", "cbsacode"], right_on=["soc4", "msa"], how="left"
        )

        def _hq_wavg(g: pd.DataFrame) -> float:
            mask = g["tight_occ"].notna()
            return (
                np.average(g.loc[mask, "tight_occ"], weights=g.loc[mask, "heads"])
                if mask.any() else np.nan
            )

        tight_hq = (
            occ_hq.groupby("companyname").apply(_hq_wavg).reset_index(name="tight_hq")
        )

    tight_hq.to_csv(OUT_HQ, index=False)
    print(f"✓ {OUT_HQ.name} written  ({len(tight_hq):,} firms)")

    # QA summary
    q1 = tight_static["tight_wavg"].describe()
    q2 = tight_hq["tight_hq"].describe()
    print("Static tightness   – min: %.3f | median: %.3f | max: %.3f" % (q1["min"], q1["50%"], q1["max"]))
    print("HQ tightness       – min: %.3f | median: %.3f | max: %.3f" % (q2["min"], q2["50%"], q2["max"]))


if __name__ == "__main__":
    build()
