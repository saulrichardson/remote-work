"""Compute a static firm-level labour-market concentration measure based on the
firm’s head-quarters (HQ) metro.

Method: population-weighted HHI across occupations in 2019-Q4 (baseline
pre-COVID quarter) for the CBSA where the HQ is located.

Inputs
------
PROC/enriched_msa.csv              • map ‘msa’ text → cbsa code
PROC/modal_msa_per_firm.dta        • firm → HQ msa
PROC/firm_occ_msa_heads_2019H2.csv • firm × SOC4 head-counts (2019-H2)
PROC/hhi_cbsa_largest.dta          • CBSA × SOC6 × quarter HHI (lower bound)

Output
------
PROC/firm_hhi_hq.csv      • columns: companyname (lower), hhi_hq
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from project_paths import DATA_PROCESSED

PROC = DATA_PROCESSED

# paths
HQ_DTA   = PROC / "modal_msa_per_firm.dta"
MSA_CSV  = PROC / "enriched_msa.csv"
HEADS_CSV = PROC / "firm_occ_msa_heads_2019H2.csv"
HHI_DTA   = PROC / "hhi_cbsa_largest.dta"

OUT_CSV   = PROC / "firm_hhi_hq.csv"


def _read_hq() -> pd.DataFrame:
    hq = pd.read_stata(HQ_DTA)[["companyname", "msa"]]
    hq["companyname"] = hq["companyname"].str.lower()

    msa = pd.read_csv(MSA_CSV)[["msa", "cbsacode"]].drop_duplicates()
    hq = hq.merge(msa, on="msa", how="left")
    hq = hq.dropna(subset=["cbsacode"]).drop_duplicates("companyname")
    hq["cbsa"] = hq["cbsacode"].astype(int).astype(str).str.zfill(5)
    hq = hq.rename(columns={"cbsa": "cbsa_hq"})
    return hq


def _read_heads() -> pd.DataFrame:
    heads = pd.read_csv(HEADS_CSV, usecols=["companyname", "soc4", "cbsa", "heads"])
    heads["companyname"] = heads["companyname"].str.lower()
    heads["soc4"] = heads["soc4"].astype(str).str.zfill(4)
    heads["cbsa"] = heads["cbsa"].astype(str).str.zfill(5)
    return heads


def _read_hhi() -> pd.DataFrame:
    cols = ["cbsa", "soc", "yq", "hhi_lower"]
    hhi = pd.read_stata(HHI_DTA, columns=cols)
    # keep 2019-Q4  (Stata quarterly date 2019q4 = 2019-10-01)
    hhi = hhi[hhi["yq"] == pd.Timestamp("2019-10-01")]
    # Harmonise SOC codes: strip the dash before taking the first four digits so
    # that they line up with the 4-digit format used in the LinkedIn head-count
    # table (e.g.  "11-1011" → "1110", "15-1121" → "1511").  Omitting the dash
    # previously produced values such as "11-1" which never matched, causing the
    # downstream merge to drop every observation and ultimately write an empty
    # output file.
    hhi["soc4"] = (
        hhi["soc"].str.replace("-", "", regex=False).str.slice(0, 4)
    )
    hhi = hhi[["cbsa", "soc4", "hhi_lower"]]
    hhi["cbsa"] = hhi["cbsa"].astype(str).str.zfill(5)
    return hhi


def build() -> None:
    hq = _read_hq()
    heads = _read_heads()
    hhi = _read_hhi()

    # keep only heads in HQ metro
    df = heads.merge(hq, on="companyname", how="left")
    df = df.dropna(subset=["cbsa_hq"])
    # keep only heads located in the HQ metro
    df = df[df["cbsa"] == df["cbsa_hq"]].copy()

    # merge HHI per occupation
    df = df.merge(hhi, on=["cbsa", "soc4"], how="left")
    df = df.dropna(subset=["hhi_lower"])

    def _wavg(g: pd.DataFrame) -> float:
        return np.average(g["hhi_lower"], weights=g["heads"]) if len(g) else np.nan

    res = []
    for comp, g in df.groupby("companyname"):
        wavg = (g["hhi_lower"] * g["heads"]).sum() / g["heads"].sum()
        res.append((comp, wavg))

    res = pd.DataFrame(res, columns=["companyname", "hhi_hq"])
    res.to_csv(OUT_CSV, index=False)

    print(f"✓ {OUT_CSV.name} written  ({len(res):,} firms)")


if __name__ == "__main__":
    build()
