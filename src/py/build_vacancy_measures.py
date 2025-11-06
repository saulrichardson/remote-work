"""Build vacancy-based firm-level variables requested by professor.

Inputs
------
data/raw/scoop_vacancy.csv
    Columns: companyname, vacancy, gap (plus an unnamed index column)

data/processed/Scoop_Positions_Firm_Collapse2.csv
    Firm × date panel with total_employees and join counts.

Outputs
-------
data/processed/vacancy_measures_2020.csv with columns
    companyname          – lower-case firm key
    vacancy              – raw vacancy postings (open postings)
    gap                  – vacancy gap (vacancies vs hires) – copied from
                           the source CSV without modification
    size_2019H2          – employment size (max total_employees, Jul–Dec 2019)
    hires_2019H2         – total hires (joins) during Jul–Dec 2019
    vacancy_per_size     – vacancy ÷ size_2019H2
    vacancy_per_hire     – vacancy ÷ hires_2019H2
"""

from __future__ import annotations

import pandas as pd

from project_paths import DATA_PROCESSED, DATA_RAW, ensure_dir

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RAW = DATA_RAW
PROC = DATA_PROCESSED

PATH_VACANCY = RAW / "scoop_vacancy.csv"
PATH_POS = PROC / "Scoop_Positions_Firm_Collapse2.csv"

OUT_CSV = PROC / "vacancy_measures_2020.csv"


# ---------------------------------------------------------------------------
# Helper loaders
# ---------------------------------------------------------------------------


def _read_vacancy() -> pd.DataFrame:
    """Return vacancy dataset with companyname normalised to lower-case."""

    df = pd.read_csv(PATH_VACANCY)

    # Drop export index column if present
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    df["companyname"] = df["companyname"].str.lower().str.strip()
    return df


def _read_size_hires() -> pd.DataFrame:
    """Compute size_2020 (max headcount) and hires_2020 (sum joins) per firm."""

    cols = ["companyname", "total_employees", "join", "date"]
    df = pd.read_csv(PATH_POS, usecols=cols, parse_dates=["date"])

    df["companyname"] = df["companyname"].str.lower().str.strip()

    # Filter to 2019-H2 (July–December)
    mask_2019h2 = (df["date"].dt.year == 2019) & (df["date"].dt.month >= 7)
    df_2019h2 = df.loc[mask_2019h2].copy()

    # Employment size – maximum stock during 2019-H2
    size = (
        df_2019h2.groupby("companyname", as_index=False)["total_employees"].max()
        .rename(columns={"total_employees": "size_2019H2"})
    )

    # Hiring flow – sum of joins during 2019-H2
    hires = (
        df_2019h2.groupby("companyname", as_index=False)["join"].sum()
        .rename(columns={"join": "hires_2019H2"})
    )

    return size.merge(hires, on="companyname", how="outer")


# ---------------------------------------------------------------------------
# Build routine
# ---------------------------------------------------------------------------


def build() -> None:
    if not PATH_VACANCY.exists():
        raise FileNotFoundError("scoop_vacancy.csv not found in data/raw")
    if not PATH_POS.exists():
        raise FileNotFoundError("Scoop_Positions_Firm_Collapse2.csv not found in data/processed")

    vac = _read_vacancy()
    firm_2020 = _read_size_hires()

    df = vac.merge(firm_2020, on="companyname", how="left")

    # Ratios ------------------------------------------------------------
    df["vacancy_per_size"] = df["vacancy"] / df["size_2019H2"]
    df.loc[df["size_2019H2"] <= 0, "vacancy_per_size"] = pd.NA

    df["vacancy_per_hire"] = df["vacancy"] / df["hires_2019H2"]
    df.loc[df["hires_2019H2"] <= 0, "vacancy_per_hire"] = pd.NA

    # Save --------------------------------------------------------------
    ensure_dir(OUT_CSV.parent)
    df.to_csv(OUT_CSV, index=False)

    print(
        f"✓ {OUT_CSV.name} written  ({len(df):,} firms)"\
        f" – per-size avail: {(df['vacancy_per_size'].notna()).sum():,};"\
        f" per-hire avail: {(df['vacancy_per_hire'].notna()).sum():,}"
    )


if __name__ == "__main__":
    build()
