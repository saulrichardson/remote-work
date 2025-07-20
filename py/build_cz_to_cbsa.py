"""Build county→CZ→CBSA cross-walks (largest-population and fractional)

Inputs (all already in the repo)
--------------------------------
data/raw/Data for labor market concentration using Lightcast (formerly Burning Glass Technologies)-2/
    • county_cz_xwalk.dta       (county → CZ)
    • list1_2023.xlsx           (OMB CBSA delineations, county → CBSA)
    • co-est2020-alldata.csv    (Census 2020 county population)

Outputs written to data/processed/
---------------------------------
cz_to_cbsa_largest.csv       cz → cbsa  (1-to-1, pick CBSA with largest 2020 pop share)
cz_to_cbsa_fractional.csv    cz → cbsa, weight  (many-to-many, population shares)

These artefacts are the only ingredient missing to aggregate the Lightcast
HHI panel from commuting-zone to CBSA level.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent  # project root
RAW  = ROOT / "data" / "raw" / "Data for labor market concentration using Lightcast (formerly Burning Glass Technologies)-2"
PROC = ROOT / "data" / "processed"


CZ_DTA   = RAW / "county_cz_xwalk.dta"
CBSA_XLS = RAW / "list1_2023.xlsx"
POP_CSV  = RAW / "co-est2020-alldata.csv"

OUT_LARGEST   = PROC / "cz_to_cbsa_largest.csv"
OUT_FRACTION  = PROC / "cz_to_cbsa_fractional.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    PROC.mkdir(parents=True, exist_ok=True)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (county→CZ, county→CBSA, county population) dataframes."""

    cz = pd.read_stata(CZ_DTA, columns=["fips", "cz"])
    cz["fips"] = cz["fips"].astype(int).astype(str).str.zfill(5)

    # OMB List1 – county → CBSA
    cbsa = pd.read_excel(CBSA_XLS, header=2, dtype=str)
    cbsa["state_fips"] = cbsa["FIPS State Code"].str.zfill(2)
    cbsa["county_fips"] = cbsa["FIPS County Code"].str.zfill(3)
    cbsa["fips"] = cbsa["state_fips"] + cbsa["county_fips"]
    cbsa = cbsa[["fips", "CBSA Code"]].rename(columns={"CBSA Code": "cbsa"})

    # Census county population – 2020 estimate
    pop = pd.read_csv(POP_CSV, encoding="latin1")
    pop_col = "POPESTIMATE2020" if "POPESTIMATE2020" in pop.columns else None
    if pop_col is None:
        # find first column that contains 2020 population
        pop_col = next(c for c in pop.columns if c.startswith("POPESTIMATE2020"))

    pop["STATE"] = pop["STATE"].astype(str).str.zfill(2)
    pop["COUNTY"] = pop["COUNTY"].astype(str).str.zfill(3)
    pop["fips"] = pop["STATE"] + pop["COUNTY"]
    pop = pop[["fips", pop_col]].rename(columns={pop_col: "pop2020"})

    return cz, cbsa, pop


def _build_largest(cz: pd.DataFrame, cbsa: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    """Return 1-to-1 mapping cz → cbsa using largest 2020 population share."""

    df = cz.merge(cbsa, on="fips", how="left").merge(pop, on="fips", how="left")

    # total pop per cz for share calculation
    df["pop2020"] = df["pop2020"].fillna(0)
    # Sum population by cz & cbsa (some cbsa nan for non-metro counties)
    agg = df.groupby(["cz", "cbsa"], as_index=False)["pop2020"].sum()

    # for each cz pick cbsa with max pop
    idx = agg.groupby("cz")["pop2020"].idxmax()
    largest = agg.loc[idx, ["cz", "cbsa"]].copy()

    # some cz may have cbsa = NaN (purely rural). Drop them.
    largest = largest.dropna(subset=["cbsa"])

    # ensure types
    largest["cz"] = largest["cz"].astype(int)
    largest["cbsa"] = largest["cbsa"].astype(str).str.zfill(5)

    return largest.sort_values("cz").reset_index(drop=True)


def _build_fractional(cz: pd.DataFrame, cbsa: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    """Return mapping with weight = population share of the CZ that lies in the CBSA."""

    df = cz.merge(cbsa, on="fips", how="left").merge(pop, on="fips", how="left")
    df["pop2020"] = df["pop2020"].fillna(0)

    agg = df.groupby(["cz", "cbsa"], as_index=False)["pop2020"].sum()

    # total pop per cz for denominator
    total = agg.groupby("cz", as_index=False)["pop2020"].sum().rename(
        columns={"pop2020": "total_pop"}
    )
    frac = agg.merge(total, on="cz", how="left")
    frac = frac[frac["total_pop"] > 0].copy()
    frac["weight"] = frac["pop2020"] / frac["total_pop"]

    # clean up
    frac = frac.drop(columns=["pop2020", "total_pop"])
    frac = frac.dropna(subset=["cbsa"])  # keep only metro overlaps

    frac["cz"] = frac["cz"].astype(int)
    frac["cbsa"] = frac["cbsa"].astype(str).str.zfill(5)

    return frac.sort_values(["cz", "weight"], ascending=[True, False]).reset_index(drop=True)


def main() -> None:
    _ensure_dirs()

    cz, cbsa, pop = _load_inputs()

    largest = _build_largest(cz, cbsa, pop)
    largest.to_csv(OUT_LARGEST, index=False)
    print(f"✓ {OUT_LARGEST.name} written  ({len(largest):,} CZs)")

    frac = _build_fractional(cz, cbsa, pop)
    frac.to_csv(OUT_FRACTION, index=False)
    print(
        f"✓ {OUT_FRACTION.name} written  ({frac['cz'].nunique():,} CZs, {len(frac):,} rows)"
    )


if __name__ == "__main__":
    main()

