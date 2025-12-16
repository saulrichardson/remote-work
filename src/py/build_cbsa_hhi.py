"""Aggregate Lightcast labour-market concentration (HHI) from commuting-zone
level to CBSA (metro) level.

Inputs
------
1. data/raw/Data …/hhis_pub_revised.dta         • HHI per CZ×SOC×quarter
2. data/clean/cz_to_cbsa_largest.csv        • 1-to-1 CZ→CBSA mapping
3. data/clean/cz_to_cbsa_fractional.csv     • fractional mapping with
                                                 `weight` = pop share of CZ in CBSA

Outputs (written to data/clean/)
------------------------------------
hhi_cbsa_largest.dta      • CBSA×SOC×quarter, inherits HHI from dominant CZ
hhi_cbsa_weighted.dta     • population-weighted avg across all CZ portions

Both files contain variables: cbsa (str5), soc, yq (Stata quarterly),
hhi_lower, hhi_higher.
"""

from __future__ import annotations

import pandas as pd

from project_paths import DATA_PROCESSED, DATA_RAW

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RAW = DATA_RAW / "Data for labor market concentration using Lightcast (formerly Burning Glass Technologies)-2"
PROC = DATA_PROCESSED

PATH_HHI = RAW / "hhis_pub_revised.dta"

MAP_LARGEST  = PROC / "cz_to_cbsa_largest.csv"
MAP_FRACTION = PROC / "cz_to_cbsa_fractional.csv"

OUT_LARGEST  = PROC / "hhi_cbsa_largest.dta"
OUT_WEIGHTED = PROC / "hhi_cbsa_weighted.dta"


# ---------------------------------------------------------------------------
# Build routines
# ---------------------------------------------------------------------------


def _load_hhi() -> pd.DataFrame:
    cols = ["cz", "soc", "yq", "hhi_lower", "hhi_higher"]
    hhi = pd.read_stata(PATH_HHI, columns=cols)
    hhi["cz"] = hhi["cz"].astype(int)
    return hhi


def _cbsa_largest(hhi: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """1-to-1 mapping: inherit HHI from the CZ that dominates the CBSA."""

    df = hhi.merge(mapping, on="cz", how="inner")
    df = df.drop(columns=["cz"])

    # If multiple CZs map to the same CBSA we simply take the mean (equal weight).
    grp = df.groupby(["cbsa", "soc", "yq"], as_index=False)
    res = grp[["hhi_lower", "hhi_higher"]].mean()

    # Ensure CBSA is 5-digit str (Stata likes str)
    res["cbsa"] = res["cbsa"].astype(str).str.zfill(5)
    return res


def _cbsa_weighted(hhi: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Population-weighted average HHI across all CZ pieces within a CBSA."""

    df = hhi.merge(mapping, on="cz", how="inner")

    # multiply HHI by weight, then sum and divide by Σweight
    for col in ("hhi_lower", "hhi_higher"):
        df[f"{col}_w"] = df[col] * df["weight"]

    grp = df.groupby(["cbsa", "soc", "yq"], as_index=False)

    res = grp.apply(
        lambda g: pd.Series({
            "hhi_lower": g["hhi_lower_w"].sum() / g["weight"].sum(),
            "hhi_higher": g["hhi_higher_w"].sum() / g["weight"].sum(),
        })
    ).reset_index()

    res["cbsa"] = res["cbsa"].astype(str).str.zfill(5)
    return res


def main() -> None:
    if not PATH_HHI.exists():
        raise FileNotFoundError("hhis_pub_revised.dta not found – ensure raw data present.")

    hhi = _load_hhi()

    # ------------------------------------------------------------------
    # Largest-population mapping
    # ------------------------------------------------------------------
    map_largest = pd.read_csv(MAP_LARGEST)
    cbsa_largest = _cbsa_largest(hhi, map_largest)
    cbsa_largest.to_stata(OUT_LARGEST, write_index=False)
    print(f"✓ {OUT_LARGEST.name} written  ({len(cbsa_largest):,} rows)")

    # ------------------------------------------------------------------
    # Fractional population-weighted mapping
    # ------------------------------------------------------------------
    map_frac = pd.read_csv(MAP_FRACTION)
    cbsa_weighted = _cbsa_weighted(hhi, map_frac)
    cbsa_weighted.to_stata(OUT_WEIGHTED, write_index=False)
    print(f"✓ {OUT_WEIGHTED.name} written  ({len(cbsa_weighted):,} rows)")


if __name__ == "__main__":
    main()
