#!/usr/bin/env python3
"""Build the final vacancy outcomes panel used by the active paper lane.

This is the only active downstream vacancy builder. It reads the canonical
vacancy half-year counts and the canonical firm panel, merges current-half
join counts onto the vacancy panel, and emits the hires-per-vacancy outcome
family that the active Stata specs consume.

Inputs
------
- data/clean/vacancy/firm_halfyear_panel.csv
- data/clean/firm_panel.dta

Output
------
- data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv

Columns emitted
---------------
- companyname
- companyname_c
- year
- half
- period
- yh
- firm_id
- vacancies
- hires_to_vacancies_raw
- hires_to_vacancies_guarded_min{1..5}
- hires_to_vacancies_winsor_min{1..5}
- hires_to_vacancies_winsor95_min{1..5}
- hires_to_vacancies_winsor  (alias of hires_to_vacancies_winsor_min5)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.py.project_paths import DATA_CLEAN, ensure_dir, require_file


DEFAULT_VACANCY_PANEL = DATA_CLEAN / "vacancy" / "firm_halfyear_panel.csv"
DEFAULT_FIRM_PANEL = DATA_CLEAN / "firm_panel.dta"
DEFAULT_OUTPUT = DATA_CLEAN / "vacancy" / "firm_halfyear_panel_MERGED_POST.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vacancy-panel",
        type=Path,
        default=DEFAULT_VACANCY_PANEL,
        help=f"Canonical vacancy half-year panel (default: {DEFAULT_VACANCY_PANEL})",
    )
    parser.add_argument(
        "--firm-panel",
        type=Path,
        default=DEFAULT_FIRM_PANEL,
        help=f"Canonical firm panel (default: {DEFAULT_FIRM_PANEL})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Final vacancy outcomes CSV (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def parse_firm_panel(path: Path) -> pd.DataFrame:
    require_file(path, nonempty=True, purpose="canonical firm panel")
    if path.suffix.lower() == ".dta":
        frame = pd.read_stata(path, convert_categoricals=False)
    elif path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, low_memory=False)
    else:
        raise ValueError(f"Unsupported firm panel extension: {path.suffix}")

    required = {"companyname", "yh", "join"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise RuntimeError(
            f"Firm panel is missing required columns: {missing}. "
            "Expected at least companyname, yh, and join."
        )

    frame = frame.copy()
    frame["yh"] = coerce_halfyear_string(frame["yh"])
    frame["join"] = pd.to_numeric(frame["join"], errors="coerce")
    if "firm_id" not in frame.columns:
        frame["firm_id"] = pd.NA
    frame = frame[["companyname", "yh", "join", "firm_id"]]
    frame = frame.dropna(subset=["companyname", "yh"])
    frame = frame.drop_duplicates(subset=["companyname", "yh"], keep="first")
    return frame


def coerce_halfyear_string(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        dt = pd.to_datetime(series, errors="coerce")
        half = np.where(dt.dt.month <= 6, 1, 2)
        return pd.Series(
            np.where(dt.notna(), dt.dt.year.astype("Int64").astype(str) + "h" + pd.Series(half, index=series.index).astype(str), pd.NA),
            index=series.index,
            dtype="string",
        ).replace("<NA>h1", pd.NA).replace("<NA>h2", pd.NA)

    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce")
        year = 1960 + np.floor_divide(numeric.fillna(-1).astype("Int64"), 2)
        half = np.mod(numeric.fillna(-1).astype("Int64"), 2) + 1
        out = pd.Series(pd.NA, index=series.index, dtype="string")
        valid = numeric.notna()
        out.loc[valid] = year.loc[valid].astype(str) + "h" + half.loc[valid].astype(str)
        return out

    text = series.astype("string").str.strip()
    out = pd.Series(pd.NA, index=series.index, dtype="string")

    iso_mask = text.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
    if iso_mask.any():
        dt = pd.to_datetime(text.loc[iso_mask], errors="coerce")
        half = np.where(dt.dt.month <= 6, 1, 2)
        out.loc[iso_mask] = dt.dt.year.astype("Int64").astype(str) + "h" + pd.Series(half, index=dt.index).astype(str)

    yh_mask = text.str.match(r"^\d{4}[hH][12]$", na=False)
    if yh_mask.any():
        out.loc[yh_mask] = text.loc[yh_mask].str.lower()

    invalid = text.notna() & text.ne("") & out.isna()
    if invalid.any():
        bad = text.loc[invalid].drop_duplicates().head(10).tolist()
        raise RuntimeError(
            "Encountered unsupported yh values in firm panel. "
            f"Examples: {bad}. Expected datetime-like values, ISO dates, or YYYYh1/2 strings."
        )

    return out


def parse_vacancy_panel(path: Path) -> pd.DataFrame:
    require_file(path, nonempty=True, purpose="canonical vacancy half-year panel")
    frame = pd.read_csv(path, low_memory=False)
    required = {"companyname", "year", "half", "vacancies"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise RuntimeError(
            f"Vacancy panel is missing required columns: {missing}. "
            "Rebuild it with src/py/build_vacancy_halfyear_panel.py."
        )

    frame = frame.copy()
    if "companyname_c" not in frame.columns:
        frame["companyname_c"] = frame["companyname"].astype(str).str.lower()
    frame["vacancies"] = pd.to_numeric(frame["vacancies"], errors="coerce").fillna(0.0)
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    frame["half"] = pd.to_numeric(frame["half"], errors="coerce").astype("Int64")
    if "period" not in frame.columns:
        frame["period"] = frame["year"].astype(str) + "H" + frame["half"].astype(str)
    if "yh" not in frame.columns:
        frame["yh"] = frame["year"].astype(str) + "h" + frame["half"].astype(str)
    frame["yh"] = frame["yh"].astype("string").str.strip().str.lower()
    return frame


def winsorise(series: pd.Series, lower: float, upper: float) -> pd.Series:
    valid = series.dropna()
    if valid.empty:
        return series
    lo, hi = valid.quantile([lower, upper]).tolist()
    return series.clip(lower=lo, upper=hi)


def build_outcomes(vacancy: pd.DataFrame, firm: pd.DataFrame) -> pd.DataFrame:
    merged = vacancy.merge(firm, on=["companyname", "yh"], how="left", validate="1:1")

    join = pd.to_numeric(merged["join"], errors="coerce")
    vacancies = pd.to_numeric(merged["vacancies"], errors="coerce")
    raw = pd.Series(np.nan, index=merged.index, dtype="float64")
    valid_raw = join.notna() & (join >= 0) & vacancies.notna() & (vacancies > 0)
    raw.loc[valid_raw] = join.loc[valid_raw] / vacancies.loc[valid_raw]
    merged["hires_to_vacancies_raw"] = raw

    for minimum_vacancies in range(1, 6):
        guarded_name = f"hires_to_vacancies_guarded_min{minimum_vacancies}"
        winsor_0199_name = f"hires_to_vacancies_winsor_min{minimum_vacancies}"
        winsor_0595_name = f"hires_to_vacancies_winsor95_min{minimum_vacancies}"

        guarded = raw.where(vacancies >= minimum_vacancies)
        merged[guarded_name] = guarded
        merged[winsor_0199_name] = winsorise(guarded, 0.01, 0.99)
        merged[winsor_0595_name] = winsorise(guarded, 0.05, 0.95)

    merged["hires_to_vacancies_winsor"] = merged["hires_to_vacancies_winsor_min5"]

    output_columns = [
        "companyname",
        "companyname_c",
        "year",
        "half",
        "period",
        "yh",
        "firm_id",
        "vacancies",
        "hires_to_vacancies_raw",
    ]
    output_columns += [f"hires_to_vacancies_guarded_min{k}" for k in range(1, 6)]
    output_columns += [f"hires_to_vacancies_winsor_min{k}" for k in range(1, 6)]
    output_columns += [f"hires_to_vacancies_winsor95_min{k}" for k in range(1, 6)]
    output_columns.append("hires_to_vacancies_winsor")

    return merged[output_columns].copy()


def main() -> None:
    args = parse_args()
    vacancy = parse_vacancy_panel(args.vacancy_panel.expanduser().resolve())
    firm = parse_firm_panel(args.firm_panel.expanduser().resolve())
    outcomes = build_outcomes(vacancy, firm)

    ensure_dir(args.output.expanduser().resolve().parent)
    outcomes.to_csv(args.output.expanduser().resolve(), index=False)

    matched_rows = int(outcomes["firm_id"].notna().sum())
    total_rows = len(outcomes)
    raw_defined = int(outcomes["hires_to_vacancies_raw"].notna().sum())
    min3_defined = int(outcomes["hires_to_vacancies_winsor95_min3"].notna().sum())
    min5_defined = int(outcomes["hires_to_vacancies_winsor"].notna().sum())

    print(f"Wrote {args.output}")
    print(f"Rows with firm matches: {matched_rows:,}/{total_rows:,}")
    print(f"Rows with raw hires/vacancies defined: {raw_defined:,}")
    print(f"Rows with min3 5/95 series defined: {min3_defined:,}")
    print(f"Rows with min5 1/99 series defined: {min5_defined:,}")


if __name__ == "__main__":
    main()
