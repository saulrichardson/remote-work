"""Build a single consolidated CSV that contains several head-quarters (HQ)
based labour-market concentration measures for every firm.

Outputs  (written to data/cleaned/firm_hq_concentration.csv)
----------------------------------------------------------------
companyname (lower-case)  |  hhi_hq_fw  |  hhi_hq_hq  |  hhi_hq_eq  |
hq_heads  |  any_hq_heads

Definitions
-----------
hhi_hq_fw   – HQ-metro HHI, **firm-wide occupation weights** (baseline).
hhi_hq_hq   – HQ-metro HHI, **HQ-only occupation weights**, computed only
              for firms with ≥ MIN_HQ_HEADS employees in the HQ metro; else
              missing.
hhi_hq_eq   – simple **unweighted average** of HHIs across all SOCs in the
              HQ metro (same for every firm located in that CBSA).
hq_heads    – number of LinkedIn heads located in the HQ metro (2019-H2).
any_hq_heads– 1 if hq_heads>0, 0 otherwise (can be used as control).

All HHIs come from 2019-Q4 (baseline, pre-COVID) and use the 1-to-1 CZ→CBSA
mapping (‘hhi_cbsa_largest.dta’).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from project_paths import DATA_PROCESSED, DATA_RAW

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

MIN_HQ_HEADS = 20  # threshold for hhi_hq_hq


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROC = DATA_PROCESSED
RAW = DATA_RAW / "Data for labor market concentration using Lightcast (formerly Burning Glass Technologies)-2"

# Inputs
PATH_HEADS = PROC / "firm_occ_msa_heads_2019H2.csv"  # firm × soc4 × cbsa × heads
PATH_HQ    = PROC / "modal_msa_per_firm.dta"         # firm → HQ msa
MSA_MAP    = PROC / "enriched_msa.csv"               # msa → cbsacode
# CBSA-level HHIs (two mapping schemes)
PATH_HHI_LG = PROC / "hhi_cbsa_largest.dta"   # largest-population mapping
PATH_HHI_FR = PROC / "hhi_cbsa_weighted.dta"  # fractional mapping

# Output
OUT_CSV    = PROC / "firm_hq_concentration.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_hq_lookup() -> pd.DataFrame:
    hq = pd.read_stata(PATH_HQ)[["companyname", "msa"]]
    hq["companyname"] = hq["companyname"].str.lower()

    msa_map = pd.read_csv(MSA_MAP)[["msa", "cbsacode"]].drop_duplicates()
    hq = hq.merge(msa_map, on="msa", how="left")
    hq = hq.rename(columns={"cbsacode": "cbsa_hq"})

    # Drop rows without CBSA code (empty / unmatched MSAs)
    hq = hq.dropna(subset=["cbsa_hq"])
    hq["cbsa_hq"] = hq["cbsa_hq"].astype(int).astype(str).str.zfill(5)
    return hq[["companyname", "cbsa_hq"]]


def _read_heads() -> pd.DataFrame:
    cols = ["companyname", "soc4", "cbsa", "heads"]
    df = pd.read_csv(PATH_HEADS, usecols=cols)
    df["companyname"] = df["companyname"].str.lower()
    df["soc4"] = df["soc4"].astype(str).str.zfill(4)
    df["cbsa"] = df["cbsa"].astype(str).str.zfill(5)
    return df


def _load_hhi_table(path: Path) -> pd.DataFrame:
    """Return cbsa×soc4 HHI DataFrame for 2019-Q4 from the given path."""

    # We need only one quarter (2019-Q4).  Loading the entire file
    # (~17 M rows for the weighted mapping) is slow and memory-heavy, so we
    # stream in chunks and keep only the rows we need.

    quarter = pd.Timestamp("2019-10-01")  # 2019-Q4 in the Lightcast file

    cols = ["cbsa", "soc", "yq", "hhi_lower"]

    # Newer pandas allows iterator/chunksize for read_stata.  Fallback to
    # full read if that fails (small files <1 M rows are fine).
    try:
        reader = pd.read_stata(path, columns=cols, iterator=True, chunksize=1_000_000)
        pieces = []
        for chunk in reader:
            chunk = chunk[chunk["yq"] == quarter]
            if not chunk.empty:
                pieces.append(chunk)
        hhi = pd.concat(pieces, ignore_index=True)
    except (TypeError, ValueError):
        # iterator argument unsupported (older pandas) – fall back
        hhi = pd.read_stata(path, columns=cols)
        hhi = hhi[hhi["yq"] == quarter].copy()

    # Harmonise SOC-4
    hhi["soc4"] = hhi["soc"].str.replace("-", "", regex=False).str.slice(0, 4)
    return hhi[["cbsa", "soc4", "hhi_lower"]].rename(columns={"hhi_lower": "hhi"})


def _read_hhi() -> dict:
    """Return dict with keys 'lg', 'fr', each mapping to (hhi_soc, hhi_eq)."""

    out = {}
    for key, p in {"lg": PATH_HHI_LG, "fr": PATH_HHI_FR}.items():
        if not p.exists():
            continue
        soc_tbl = _load_hhi_table(p)
        eq_tbl = soc_tbl.groupby("cbsa", as_index=False)["hhi"].mean().rename(
            columns={"hhi": "hhi_eq"}
        )
        out[key] = (soc_tbl, eq_tbl)
    return out


# ---------------------------------------------------------------------------
# Build routine
# ---------------------------------------------------------------------------


def build() -> None:  # noqa: C901
    if not PATH_HEADS.exists():
        raise FileNotFoundError("firm_occ_msa_heads_2019H2.csv not found – run build_firm_occ_tightness.py first.")

    hq = _read_hq_lookup()
    heads = _read_heads()
    hhi_dict = _read_hhi()  # keys 'lg', 'fr'

    # attach HQ cbsa to each head row
    df_base = heads.merge(hq, on="companyname", how="left").dropna(subset=["cbsa_hq"])

    # helper for weighted average
    def _wavg(g):
        mask = g["hhi"].notna() & (g["heads"] > 0)
        return np.average(g.loc[mask, "hhi"], weights=g.loc[mask, "heads"]) if mask.any() else np.nan

    # prepare containers
    out = hq.copy()

    # compute HQ head counts once
    df_hqonly_base = df_base[df_base["cbsa"] == df_base["cbsa_hq"]].copy()
    hq_heads = df_hqonly_base.groupby("companyname", as_index=False)["heads"].sum().rename(columns={"heads": "hq_heads"})

    out = out.merge(hq_heads, on="companyname", how="left")

    for key, (hhi_soc, hhi_eq) in hhi_dict.items():
        suffix = "_lg" if key == "lg" else "_fr"

        # firm-wide HQ weighted
        df_fw = df_base.merge(hhi_soc, left_on=["cbsa_hq", "soc4"], right_on=["cbsa", "soc4"], how="left")
        h_fw = df_fw.groupby("companyname").apply(_wavg).reset_index(name=f"hhi_hq_fw{suffix}")

        # HQ-only weighted
        df_hqonly = df_hqonly_base.merge(hhi_soc, left_on=["cbsa_hq", "soc4"], right_on=["cbsa", "soc4"], how="left")
        h_hq = df_hqonly.groupby("companyname").apply(_wavg).reset_index(name=f"hhi_hq_hq{suffix}")

        # equal-weight HQ
        h_eq = hq.merge(hhi_eq, left_on="cbsa_hq", right_on="cbsa", how="left").drop(columns=["cbsa"]).rename(columns={"hhi_eq": f"hhi_hq_eq{suffix}"})

        # full-footprint weighted
        df_fwavg = heads.merge(hhi_soc, on=["cbsa", "soc4"], how="left")
        h_fwavg = df_fwavg.groupby("companyname").apply(_wavg).reset_index(name=f"hhi_fwavg{suffix}")

        # merge into out
        for tbl in (h_fw, h_hq, h_eq[["companyname", f"hhi_hq_eq{suffix}" ]], h_fwavg):
            out = out.merge(tbl, on="companyname", how="left")

    out["hq_heads"] = out["hq_heads"].fillna(0).astype(int)
    out["any_hq_heads"] = (out["hq_heads"] > 0).astype(int)

    # apply minimum-headcount threshold for hhi_hq_hq
    mask = out["hq_heads"] < MIN_HQ_HEADS
    out.loc[mask, "hhi_hq_hq"] = np.nan

    # drop legacy columns without suffix if any (from earlier versions)
    for col in list(out.columns):
        if col.startswith("hhi_") and (col.endswith("_lg") is False and col.endswith("_fr") is False) and col not in ("hhi_hq_eq_lg","hhi_hq_eq_fr"):
            out.drop(columns=[col], inplace=True)

    # tidy and save -----------------------------------------------------
    # 'out' already contains all dynamically generated columns plus hq_heads flags.

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    cols_info = ", ".join(
        f"{c}: {(out[c].notna()).sum():,}" for c in out.columns if c.startswith("hhi_")
    )
    print(f"✓ {OUT_CSV.name} written  ({len(out):,} firms)\n   • non-missing counts → {cols_info}")


if __name__ == "__main__":
    build()
