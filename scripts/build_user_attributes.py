#!/usr/bin/env python3
"""
Produce user-level demographic and education attributes for productivity specs.

The script reads the large Scoop education file and the user location file in
chunks, keeps only the user_ids that appear in the processed user panels, and
exports a compact dataset that is easy to merge inside Stata.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, Iterable, List, Set

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
NEW_DATA_DIR = REPO_ROOT.parent / "New" / "Data"

PANEL_PATHS = [
    PROCESSED_DIR / "user_panel_precovid.dta",
    PROCESSED_DIR / "user_panel_unbalanced.dta",
    PROCESSED_DIR / "user_panel_balanced.dta",
]

EDUCATION_PATH = NEW_DATA_DIR / "Scoop_Education.csv"
LOCATION_PATH = NEW_DATA_DIR / "User_location.csv"

OUTPUT_CSV = PROCESSED_DIR / "user_attributes.csv"
OUTPUT_DTA = PROCESSED_DIR / "user_attributes.dta"


def load_panel_user_ids(panel_paths: Iterable[Path]) -> Set[int]:
    user_ids: Set[int] = set()
    for path in panel_paths:
        if not path.exists():
            continue

        df = pd.read_stata(path, columns=["user_id"], convert_categoricals=False)
        vals = df["user_id"].dropna().astype(np.int64)
        user_ids.update(vals.tolist())

    return user_ids


def classify_degree(degree: pd.Series) -> pd.Series:
    text = degree.fillna("").str.lower()
    result = pd.Series(np.full(len(text), "other", dtype=object), index=degree.index)

    def assign(mask: pd.Series, label: str) -> None:
        result.loc[mask] = label

    assign(text.str.contains(r"\b(?:phd|ph\.d|doctor|dphil|scd|sc\.d|edd|ed\.d|dpt|d\.phil)\b", regex=True, na=False), "doctoral")
    assign(text.str.contains(r"\b(?:md|m\.d|jd|j\.d|dvm|d\.v\.m|dds|d\.d\.s|dmd|d\.m\.d|od|o\.d|esq|juris doctor)\b", regex=True, na=False), "professional")
    assign(text.str.contains(r"\bmba\b", regex=True, na=False), "mba")
    assign(text.str.contains(r"\b(?:master|m\.s|msc|m\.sc|ma |m\.a|mfa|m\.f\.a|mph|m\.p\.h)\b", regex=True, na=False), "masters")
    assign(text.str.contains(r"\b(?:bachelor|b\.s|bs |b\.a|ba |bfa|b\.f\.a|beng|b\.eng)\b", regex=True, na=False), "bachelors")
    assign(text.str.contains(r"\b(?:associate|a\.a|aas|a\.a\.s|a\.s|a\.sc)\b", regex=True, na=False), "associate")
    assign(text.str.contains(r"(?:high school|secondary school|h\.s\. diploma|ged|general education)", regex=True, na=False), "high_school")
    assign(text.str.contains(r"(?:certificate|certification|bootcamp|nanodegree|course)", regex=True, na=False), "certificate")

    return result


DEGREE_RANK: Dict[str, int] = {
    "other": 0,
    "certificate": 0,
    "high_school": 1,
    "associate": 2,
    "bachelors": 3,
    "masters": 4,
    "mba": 5,
    "professional": 6,
    "doctoral": 7,
}

DEGREE_FALLBACK = {
    6: "doctoral",
    5: "mba",
    4: "masters",
    3: "masters",
    2: "bachelors",
    1: "high_school",
    0: "other",
}

DEGREE_AGE_GUESS = {
    "doctoral": 30,
    "professional": 28,
    "mba": 28,
    "masters": 24,
    "bachelors": 22,
    "associate": 20,
    "high_school": 18,
    "certificate": 22,
    "other": 22,
}


def process_education(path: Path, user_ids: Set[int]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    usecols = [
        "user_id",
        "campus",
        "startdate",
        "enddate",
        "degree",
        "field",
        "university_priname",
        "university_priname_usa",
        "university_priname_world",
        "degree_level",
        "specialization",
    ]

    chunks: List[pd.DataFrame] = []
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=250_000):
        chunk = chunk[chunk["user_id"].isin(user_ids)]
        if chunk.empty:
            continue

        chunk["user_id"] = chunk["user_id"].astype("int64", copy=False)
        chunk["degree_level"] = pd.to_numeric(chunk["degree_level"], errors="coerce")

        chunk["start_year"] = pd.to_datetime(chunk["startdate"], errors="coerce").dt.year
        chunk["end_year"] = pd.to_datetime(chunk["enddate"], errors="coerce").dt.year
        chunk["grad_year"] = chunk["end_year"].fillna(chunk["start_year"])

        degree_type = classify_degree(chunk["degree"])
        needs_fallback = degree_type.eq("other") & chunk["degree_level"].notna()
        if needs_fallback.any():
            fallback_levels = chunk.loc[needs_fallback, "degree_level"].round().astype("Int64")
            degree_type.loc[needs_fallback] = fallback_levels.map(DEGREE_FALLBACK).fillna("other")

        chunk["degree_type"] = degree_type
        chunk["degree_rank"] = chunk["degree_type"].map(DEGREE_RANK).fillna(0)

        chunks.append(chunk)

    if not chunks:
        raise RuntimeError("No education rows matched the panel user IDs.")

    edu = pd.concat(chunks, ignore_index=True)
    edu = edu.dropna(subset=["user_id"])

    edu["grad_year"] = pd.to_numeric(edu["grad_year"], errors="coerce").round().astype("Int64")

    edu = edu.sort_values(
        by=["user_id", "degree_rank", "grad_year", "end_year", "start_year"],
        ascending=[True, False, False, False, False],
    )
    top = edu.drop_duplicates("user_id", keep="first")

    grouped = edu.groupby("user_id", as_index=True)
    summary = pd.DataFrame(index=grouped.size().index)
    summary["education_records"] = grouped.size()
    summary["grad_year_earliest"] = grouped["grad_year"].min()
    summary["grad_year_latest"] = grouped["grad_year"].max()
    summary["highest_degree_rank"] = grouped["degree_rank"].max()
    summary["has_graduate_degree"] = (summary["highest_degree_rank"] >= DEGREE_RANK["masters"]).astype("Int64")
    summary["has_bachelors_plus"] = (summary["highest_degree_rank"] >= DEGREE_RANK["bachelors"]).astype("Int64")
    summary["has_doctorate"] = (summary["highest_degree_rank"] >= DEGREE_RANK["doctoral"]).astype("Int64")

    summary = summary.merge(
        top[
            [
                "user_id",
                "degree_type",
                "degree",
                "field",
                "grad_year",
                "university_priname",
                "university_priname_usa",
                "university_priname_world",
                "specialization",
                "campus",
            ]
        ],
        left_index=True,
        right_on="user_id",
        how="left",
    )

    summary.rename(
        columns={
            "degree_type": "highest_degree_type",
            "degree": "highest_degree_label",
            "field": "highest_field",
            "grad_year": "highest_degree_grad_year",
            "university_priname": "highest_university_name",
            "university_priname_usa": "highest_university_name_usa",
            "university_priname_world": "highest_university_name_world",
            "specialization": "highest_specialization",
            "campus": "highest_campus",
        },
        inplace=True,
    )

    summary["highest_degree_type"] = summary["highest_degree_type"].fillna("other")

    summary["highest_degree_rank"] = summary["highest_degree_rank"].astype("Int64")
    summary["highest_degree_grad_year"] = summary["highest_degree_grad_year"].astype("Int64")

    assumed_age = summary["highest_degree_type"].map(DEGREE_AGE_GUESS).fillna(22)
    summary["approx_birth_year"] = (
        summary["highest_degree_grad_year"] - assumed_age
    ).round().astype("Int64")
    summary["approx_age_2020"] = (
        2020 - summary["approx_birth_year"]
    ).astype("float64")
    summary.loc[summary["approx_birth_year"].isna(), "approx_age_2020"] = np.nan

    return summary.reset_index(drop=True)


def process_location(path: Path, user_ids: Set[int]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    usecols = [
        "Unnamed: 0",
        "user_id",
        "firstname",
        "lastname",
        "f_prob",
        "m_prob",
        "white_prob",
        "black_prob",
        "api_prob",
        "hispanic_prob",
        "native_prob",
        "multiple_prob",
        "location",
        "currentindustry",
        "title",
    ]

    chunks: List[pd.DataFrame] = []
    for chunk in pd.read_csv(
        path,
        usecols=usecols,
        chunksize=250_000,
        dtype={"Unnamed: 0": "string"},
    ):
        chunk = chunk[chunk["user_id"].isin(user_ids)]
        if chunk.empty:
            continue

        chunk["user_id"] = chunk["user_id"].astype("int64", copy=False)

        chunk["f_prob"] = pd.to_numeric(chunk["f_prob"], errors="coerce")
        chunk["m_prob"] = pd.to_numeric(chunk["m_prob"], errors="coerce")

        gender_max = chunk[["f_prob", "m_prob"]].max(axis=1, skipna=True)
        gender_category = np.where(
            (chunk["f_prob"] >= 0.6) & (chunk["f_prob"] >= chunk["m_prob"].fillna(-1)),
            "female",
            np.where(
                (chunk["m_prob"] >= 0.6) & (chunk["m_prob"] >= chunk["f_prob"].fillna(-1)),
                "male",
                "undetermined",
            ),
        )
        chunk["gender_category"] = gender_category
        chunk["gender_confident"] = (gender_max >= 0.6).astype("Int64")

        race_cols = [
            "white_prob",
            "black_prob",
            "api_prob",
            "hispanic_prob",
            "native_prob",
            "multiple_prob",
        ]
        for col in race_cols:
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce")

        race_probs = chunk[race_cols]
        race_idx = race_probs.idxmax(axis=1, skipna=True)
        race_max = race_probs.max(axis=1, skipna=True)
        race_category = race_idx.str.replace("_prob", "", regex=False)
        race_category = race_category.fillna("unknown")
        race_category.loc[race_max.fillna(0) == 0] = "unknown"
        chunk["race_category"] = race_category
        chunk["race_confident"] = (race_max >= 0.6).astype("Int64")

        split_loc = chunk["location"].fillna("").str.split(",", n=2, expand=True)
        if split_loc.shape[1] < 3:
            split_loc = split_loc.reindex(columns=[0, 1, 2])
        chunk["location_city"] = split_loc[0].str.strip()
        chunk["location_state"] = split_loc[1].str.strip()
        chunk["location_country"] = split_loc[2].str.strip()

        chunks.append(chunk)

    if not chunks:
        raise RuntimeError("No location rows matched the panel user IDs.")

    loc = pd.concat(chunks, ignore_index=True)
    loc["Unnamed: 0"] = pd.to_numeric(loc["Unnamed: 0"], errors="coerce")
    loc = loc.sort_values(["user_id", "Unnamed: 0"])
    loc = loc.drop_duplicates("user_id", keep="first")

    columns_to_keep = [
        "user_id",
        "firstname",
        "lastname",
        "gender_category",
        "gender_confident",
        "f_prob",
        "m_prob",
        "race_category",
        "race_confident",
        "white_prob",
        "black_prob",
        "api_prob",
        "hispanic_prob",
        "native_prob",
        "multiple_prob",
        "location",
        "location_city",
        "location_state",
        "location_country",
        "currentindustry",
        "title",
    ]

    return loc[columns_to_keep].reset_index(drop=True)


def merge_attributes(location: pd.DataFrame, education: pd.DataFrame) -> pd.DataFrame:
    merged = location.merge(education, on="user_id", how="outer", validate="1:1")
    merged.sort_values("user_id", inplace=True)
    merged.reset_index(drop=True, inplace=True)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Build merged user attributes.")
    parser.add_argument(
        "--no-location", action="store_true", help="Skip location processing (debug)."
    )
    parser.add_argument(
        "--no-education", action="store_true", help="Skip education processing (debug)."
    )
    args = parser.parse_args()

    print("→ Loading user IDs from panel variants…")
    user_ids = load_panel_user_ids(PANEL_PATHS)
    if not user_ids:
        raise RuntimeError("No user IDs found in the processed panels.")
    print(f"   Collected {len(user_ids):,} unique user IDs.")

    location_df = None
    if not args.no_location:
        print("→ Processing user location file…")
        location_df = process_location(LOCATION_PATH, user_ids)
        print(f"   Location attributes retained for {len(location_df):,} users.")

    education_df = None
    if not args.no_education:
        print("→ Processing Scoop education file…")
        education_df = process_education(EDUCATION_PATH, user_ids)
        print(f"   Education attributes retained for {len(education_df):,} users.")

    if location_df is None:
        merged = education_df
    elif education_df is None:
        merged = location_df
    else:
        merged = merge_attributes(location_df, education_df)

    merged = merged.sort_values("user_id").reset_index(drop=True)

    print(f"→ Writing attributes to {OUTPUT_CSV} and {OUTPUT_DTA} …")
    merged.to_csv(OUTPUT_CSV, index=False)
    merged.to_stata(OUTPUT_DTA, write_index=False, version=117)
    print("✓ Done.")


if __name__ == "__main__":
    main()
