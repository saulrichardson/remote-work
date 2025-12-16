"""Build a static firm-level tightness measure based on the firm‘s
head-quarters (HQ) metro.

Steps (data flow)
-----------------
1. Headquarters lookup      • modal_msa_per_firm.dta  ⇒ companyname → msa
2. Map MSA → CBSA code      • enriched_msa.csv         ⇒ msa → cbsacode
3. 2019-H2 occupation mix   • firm_occ_msa_heads_2019H2.csv ⇒ heads per company×SOC
4. OEWS tightness           • tight_occ_msa_y.csv (year=2019)

5. For every firm–occupation pair attach the tightness of the HQ metro.
6. Head-count-weight over occupations to obtain one scalar per firm.

Output
------
data/clean/firm_tightness_hq.csv  (columns: companyname, tight_hq)

The resulting CSV can be merged in Stata:

    import delimited "firm_tightness_hq.csv", clear
    merge 1:1 companyname using my_panel.csv, keep(3) nogen
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
PATH_HQ_DTA = PROC / "modal_msa_per_firm.dta"
PATH_MSA_MAP = PROC / "enriched_msa.csv"  # msa → cbsacode
PATH_HEADS = PROC / "firm_occ_msa_heads_2019H2.csv"
PATH_OEWS = RAW / "oews" / "processed_data" / "tight_occ_msa_y.csv"

# Output
OUT_CSV = PROC / "firm_tightness_hq.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_hq_lookup() -> pd.DataFrame:
    """Return DataFrame with columns companyname (lower-case) and cbsacode (str)."""

    if not PATH_HQ_DTA.exists():
        raise FileNotFoundError("modal_msa_per_firm.dta not found – run HQ extraction first.")

    hq = pd.read_stata(PATH_HQ_DTA)[["companyname", "msa"]]
    hq["companyname"] = hq["companyname"].str.lower()

    # Map MSA string → CBSA code using the enriched lookup
    msa_map = pd.read_csv(PATH_MSA_MAP)[["msa", "cbsacode"]].drop_duplicates()
    hq = hq.merge(msa_map, on="msa", how="left")

    missing = hq["cbsacode"].isna().sum()
    if missing:
        print(f"[warn] {missing:,} HQ rows without CBSA code – will be dropped")
        hq = hq.dropna(subset=["cbsacode"])

    # keep first occurrence if duplicates (due to multiple modal ties)
    hq = hq.drop_duplicates("companyname")

    # ensure 5-digit zero-padded string for join with OEWS file
    hq["cbsacode"] = hq["cbsacode"].astype(int).astype(str).str.zfill(5)

    return hq[["companyname", "cbsacode"]]


def _read_heads() -> pd.DataFrame:
    """Load 2019-H2 head-counts at company × SOC4 × CBSA granularity."""

    heads = pd.read_csv(PATH_HEADS)[["companyname", "soc4", "cbsa", "heads"]]
    heads["companyname"] = heads["companyname"].str.lower()
    # zero-pad cbsa to 5 chars for joins
    heads["cbsa"] = heads["cbsa"].astype(str).str.zfill(5)
    return heads


def _read_oews() -> pd.DataFrame:
    df = pd.read_csv(PATH_OEWS, usecols=["msa", "soc4", "year", "tight_occ"])
    df = df[df["year"] == 2019].copy()
    df["msa"] = df["msa"].astype(int).astype(str).str.zfill(5)
    return df[["soc4", "msa", "tight_occ"]]


# ---------------------------------------------------------------------------
# Build routine
# ---------------------------------------------------------------------------


def build() -> None:
    print("Building HQ-based firm tightness …")

    hq = _read_hq_lookup()
    heads_full = _read_heads()
    oews = _read_oews()

    # Restrict to heads located in the HQ metro --------------------------------

    df = heads_full.merge(hq, on="companyname", how="left")
    df = df[df["cbsa"] == df["cbsacode"]].copy()

    # Collapse to company × SOC4 (heads within HQ only)
    df = (
        df.groupby(["companyname", "soc4"], as_index=False)["heads"].sum()
    )

    # Merge OEWS tightness for the HQ metro -------------------------------------

    df = df.merge(
        hq, on="companyname", how="left"
    ).merge(
        oews,
        left_on=["soc4", "cbsacode"],
        right_on=["soc4", "msa"],
        how="left",
    )

    # Weighted average across occupations per firm
    def _wavg(g: pd.DataFrame) -> float:
        mask = g["tight_occ"].notna()
        if mask.any():
            return np.average(g.loc[mask, "tight_occ"], weights=g.loc[mask, "heads"])
        return np.nan

    if df.empty:
        raise SystemExit("No matching HQ heads after filtering—check inputs.")

    tight_hq = (
        df.groupby("companyname").apply(_wavg).reset_index(name="tight_hq")
    )

    tight_hq.to_csv(OUT_CSV, index=False)

    print(f"✓ {OUT_CSV.name} written  ({len(tight_hq):,} firms)")

    # QA summary
    q = tight_hq["tight_hq"].describe()
    print(
        f"Distribution — min: {q['min']:.3f} | median: {q['50%']:.3f} | max: {q['max']:.3f}"
    )


if __name__ == "__main__":
    build()
