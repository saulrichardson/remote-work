"""Build a firm–level Herfindahl–Hirschman Index that captures how
geographically concentrated each firm is across U.S. metropolitan areas
(CBSA codes) in the baseline period 2019-H2.

Input
-----
data/processed/firm_occ_msa_heads_2019H2.csv
    Columns required: companyname, cbsa, heads

Output
------
data/processed/firm_hhi_msa.csv
    Columns: companyname (lower-case), hhi_msa_2019

HHI definition
--------------
For firm *f* with employment shares *s*\_{f,m} across metros *m*

    HHI_f = Σ_m  s_{f,m}² ,    where  s_{f,m} = heads_{f,m} / heads_{f,•}

The index equals 1 when every employee sits in a single metro and tends
towards 0 as the footprint becomes more evenly spread over many metros.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

PATH_HEADS = PROC / "firm_occ_msa_heads_2019H2.csv"
OUT_CSV = PROC / "firm_hhi_msa.csv"


# ---------------------------------------------------------------------------
# Build routine
# ---------------------------------------------------------------------------


def build() -> None:
    if not PATH_HEADS.exists():
        raise FileNotFoundError(
            "firm_occ_msa_heads_2019H2.csv not found – run build_firm_occ_tightness.py first."
        )

    # Load company × CBSA head-counts (collapse over occupations)
    cols = ["companyname", "cbsa", "heads"]
    df = pd.read_csv(PATH_HEADS, usecols=cols)

    # Normalise keys -----------------------------------------------------
    df["companyname"] = df["companyname"].str.lower()

    # Total heads per firm ----------------------------------------------
    tot = df.groupby("companyname", as_index=False)["heads"].sum().rename(
        columns={"heads": "tot_heads"}
    )
    df = df.merge(tot, on="companyname", how="left")

    # Shares per metro ---------------------------------------------------
    df["share"] = df["heads"] / df["tot_heads"]

    # HHI per firm -------------------------------------------------------
    hhi = (
        df.groupby("companyname")["share"].apply(lambda s: np.square(s).sum()).reset_index()
    )
    hhi = hhi.rename(columns={"share": "hhi_msa_2019"})

    # Persist -----------------------------------------------------------
    hhi.to_csv(OUT_CSV, index=False)

    print(f"✓ {OUT_CSV.name} written  ({len(hhi):,} firms)")
    q = hhi["hhi_msa_2019"].describe()
    print(
        "HHI distribution – min: %.3f | median: %.3f | max: %.3f"
        % (q["min"], q["50%"], q["max"])
    )


if __name__ == "__main__":
    build()
