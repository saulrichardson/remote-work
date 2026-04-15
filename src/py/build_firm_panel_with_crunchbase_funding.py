#!/usr/bin/env python3
"""
Build Crunchbase-derived firm scaling outcomes on the *same firm×half-year panel*
and with the *same RHS variables* used by `spec/stata/firm_scaling.do`.

What this script does
---------------------
1) Reads the processed firm panel that already includes a Crunchbase org UUID:
     data/clean/firm_panel_with_cb.csv
   (This file has the canonical `var3 var4 var5 var6 var7` interaction bundle
   plus `org_uuid`.)

2) Reads Crunchbase funding rounds (untracked raw input):
     data/raw/crunchbase/funding_rounds.csv

3) Collapses funding rounds to org_uuid × half-year start date (Jan 1 / Jul 1),
   then merges those outcomes onto the firm panel via `org_uuid` and `yh`.

4) Writes an augmented panel back to data/clean/.

The intent is to let you run regressions with the *exact same RHS and FE*
as firm_scaling, swapping only the dependent variable to Crunchbase outcomes.

Outputs
-------
  - data/clean/firm_panel_with_cb_funding.csv

Added outcome columns (when available)
--------------------------------------
Always (requires only org_uuid + announced_on):
  - cb_round_count          : # funding rounds announced in the half-year
  - cb_any_round            : 1{cb_round_count>0}

If investment_type (or funding_round_type) exists:
  - cb_seriesAplus_round    : 1{any “Series A+” style round in the half-year}
  - cb_seriesAplus_cum      : ever reached Series A+ by that half-year (cummax)

If a USD amount column exists:
  - cb_raised_usd           : sum of USD raised in the half-year
  - cb_log1p_raised_usd     : log(1 + cb_raised_usd)
  - cb_cum_raised_usd       : cumulative USD raised up to that half-year
  - cb_log1p_cum_raised_usd : log(1 + cb_cum_raised_usd)
  - cb_dlog_cum_raised      : log(1+cum) - log(1+lag(cum))
  - cb_dlog_cum_raised_we   : winsorised cb_dlog_cum_raised to [1,99] pct

Important sample note
---------------------
For firms that have a valid `org_uuid` but no rounds in a half-year, outcomes are
filled with 0 (interpreted as “no round” / “$0 raised”).

For firms with missing `org_uuid` (not matched to Crunchbase), outcomes are left
missing by default (to avoid silently treating missing coverage as “zero”).
Use `--drop-unmatched` to restrict to matched firms only.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Iterable

import duckdb
import numpy as np
import pandas as pd

from src.py.project_paths import DATA_CLEAN, DATA_RAW, ensure_dir, require_file


DEFAULT_FIRM_PANEL = DATA_CLEAN / "firm_panel_with_cb.csv"
DEFAULT_FUNDING_ROUNDS = DATA_RAW / "crunchbase" / "funding_rounds.csv"
DEFAULT_OUT = DATA_CLEAN / "firm_panel_with_cb_funding.csv"


def _pick_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lower_to_actual = {c.lower(): c for c in columns}
    for cand in candidates:
        key = cand.lower()
        if key in lower_to_actual:
            return lower_to_actual[key]
    return None


def _date_to_stata_yh(d: date) -> int:
    half = 1 if d.month <= 6 else 2
    return (d.year - 1960) * 2 + (half - 1)


def _coerce_panel_yh_to_date(yh: pd.Series) -> pd.Series:
    """Parse a firm-panel half-year column into `datetime.date` objects.

    Supports:
      - ISO dates: '2021-07-01'
      - Stata half-year numeric codes: 120 == 2020h1 (floats/ints)
      - Compact strings: '2020h2' / '2020H1'
    """
    if pd.api.types.is_numeric_dtype(yh):
        # Stata half-year date: (year-1960)*2 + (half-1)
        # year = 1960 + floor(yh/2); half = mod(yh,2)+1
        s = yh.dropna().astype(int)
        year = 1960 + (s // 2)
        half = (s % 2) + 1
        month = np.where(half.to_numpy() == 1, 1, 7)
        d = pd.to_datetime(
            {
                "year": year.to_numpy(),
                "month": month,
                "day": np.ones(len(s), dtype=int),
            },
            errors="coerce",
        ).dt.date
        out = pd.Series(pd.NaT, index=yh.index, dtype="object")
        out.loc[s.index] = d
        return out

    # Strings: either ISO date or 'YYYYh{1,2}'
    s = yh.astype(str).str.strip()
    iso_mask = s.str.match(r"^\d{4}-\d{2}-\d{2}$")
    yh_mask = s.str.match(r"^\d{4}[hH][12]$")

    out = pd.Series(pd.NaT, index=yh.index, dtype="object")
    if iso_mask.any():
        out.loc[iso_mask] = pd.to_datetime(s.loc[iso_mask], errors="coerce").dt.date
    if yh_mask.any():
        years = s.loc[yh_mask].str.slice(0, 4).astype(int)
        halves = s.loc[yh_mask].str[-1].astype(int)
        months = np.where(halves.to_numpy() == 1, 1, 7)
        out.loc[yh_mask] = pd.to_datetime(
            {"year": years.to_numpy(), "month": months, "day": np.ones(len(years), dtype=int)},
            errors="coerce",
        ).dt.date

    if out.isna().any():
        bad = s[out.isna() & s.ne("")].unique().tolist()[:10]
        if bad:
            raise ValueError(
                "Unrecognised yh values in firm panel (showing up to 10): "
                f"{bad}. Expected ISO 'YYYY-MM-DD', 'YYYYh1/2', or numeric Stata yh codes."
            )
    return out


def _winsorise(s: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Winsorise to match Stata winsor2 cuts(1 99) at the sample level."""
    x = s.astype(float)
    mask = x.notna() & np.isfinite(x)
    if mask.sum() == 0:
        return s
    lo, hi = x.loc[mask].quantile([lower, upper]).tolist()
    return x.clip(lo, hi)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build Crunchbase funding outcomes on the firm_scaling panel."
    )
    p.add_argument(
        "--firm-panel",
        type=Path,
        default=DEFAULT_FIRM_PANEL,
        help="Firm×half-year panel with org_uuid (default: %(default)s).",
    )
    p.add_argument(
        "--funding-rounds",
        type=Path,
        default=DEFAULT_FUNDING_ROUNDS,
        help="Crunchbase funding_rounds.csv (default: %(default)s).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output CSV path (default: %(default)s).",
    )
    p.add_argument(
        "--drop-unmatched",
        action="store_true",
        help="Drop firms without org_uuid (default: keep but outcomes missing).",
    )
    return p.parse_args()


def read_firm_panel(path: Path) -> pd.DataFrame:
    require_file(path, nonempty=True, purpose="Firm panel with Crunchbase org_uuid (firm_panel_with_cb)")
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() == ".dta":
        df = pd.read_stata(path)
    else:
        raise ValueError(f"Unsupported firm panel extension: {path.suffix}")

    required = {"yh", "org_uuid", "var3", "var4", "var5", "var6", "var7"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            f"Firm panel is missing required columns: {sorted(missing)}. "
            "Use data/clean/firm_panel_with_cb.csv which already contains org_uuid and var3–var7."
        )

    df["yh_date"] = _coerce_panel_yh_to_date(df["yh"])
    df["yh_num"] = df["yh_date"].apply(lambda d: _date_to_stata_yh(d) if isinstance(d, date) else np.nan)
    return df


def read_funding_rounds(path: Path) -> tuple[pd.DataFrame, dict]:
    require_file(path, nonempty=True, purpose="Crunchbase funding rounds export (funding_rounds.csv)")

    con = duckdb.connect()
    try:
        cols = con.execute(
            f"SELECT * FROM read_csv_auto('{path.as_posix()}', SAMPLE_SIZE=-1) LIMIT 0"
        ).fetchdf().columns.tolist()
    finally:
        con.close()

    org_col = _pick_column(cols, ["org_uuid", "organization_uuid"])
    date_col = _pick_column(cols, ["announced_on", "announced_on_date", "announced_date"])
    stage_col = _pick_column(cols, ["investment_type", "funding_round_type"])
    amount_col = _pick_column(
        cols,
        [
            "raised_amount_usd",
            "money_raised_usd",
            "raised_amount",
            "money_raised",
        ],
    )

    if org_col is None or date_col is None:
        raise RuntimeError(
            "Crunchbase funding_rounds is missing required columns. "
            f"Found columns: {cols[:25]}... "
            "Need at least org_uuid + announced_on (or equivalents)."
        )

    # Parse dates with a small set of common formats; null if unparseable.
    date_expr = (
        f"COALESCE("
        f"try_strptime(CAST(\"{date_col}\" AS VARCHAR), '%Y-%m-%d'), "
        f"try_strptime(CAST(\"{date_col}\" AS VARCHAR), '%Y-%m-%d %H:%M:%S'), "
        f"try_strptime(CAST(\"{date_col}\" AS VARCHAR), '%m/%d/%Y')"
        f")::DATE"
    )

    yh_expr = (
        "CASE WHEN EXTRACT('month' FROM announced_date) <= 6 "
        "THEN make_date(EXTRACT('year' FROM announced_date)::INT, 1, 1) "
        "ELSE make_date(EXTRACT('year' FROM announced_date)::INT, 7, 1) END"
    )

    # Build query parts conditionally so we don't assume amount/stage columns exist.
    select_fr = [
        f"\"{org_col}\" AS org_uuid",
        f"{date_expr} AS announced_date",
    ]
    if stage_col is not None:
        select_fr.append(f"lower(trim(\"{stage_col}\")) AS stage_l")
    if amount_col is not None:
        # Crunchbase exports often store numeric fields as strings with commas or currency symbols.
        # Strip all non-numeric characters except '.' and '-' before casting.
        cleaned_amount = (
            f"regexp_replace(CAST(\"{amount_col}\" AS VARCHAR), '[^0-9.-]', '', 'g')"
        )
        select_fr.append(f"try_cast({cleaned_amount} AS DOUBLE) AS raised_usd")

    agg_parts = ["COUNT(*) AS cb_round_count"]
    if stage_col is not None:
        series_expr = (
            "(regexp_matches(stage_l, '^series_[a-i]') "
            "OR stage_l IN ('venture_round','growth_equity','private_equity','series_unknown'))"
        )
        agg_parts.append(
            "MAX(CASE WHEN is_seriesAplus THEN 1 ELSE 0 END) AS cb_seriesAplus_round"
        )
    if amount_col is not None:
        agg_parts.append("SUM(COALESCE(raised_usd, 0.0)) AS cb_raised_usd")

    query = f"""
    WITH fr AS (
      SELECT {", ".join(select_fr)}
      FROM read_csv_auto('{path.as_posix()}', SAMPLE_SIZE=-1)
      WHERE "{org_col}" IS NOT NULL
    ),
    fr2 AS (
      SELECT
        org_uuid,
        {yh_expr} AS yh_date
        {"," if stage_col is not None else ""} {(" " + series_expr + " AS is_seriesAplus") if stage_col is not None else ""}
        {"," if amount_col is not None else ""} {(" raised_usd") if amount_col is not None else ""}
      FROM fr
      WHERE announced_date IS NOT NULL
    )
    SELECT
      org_uuid,
      yh_date,
      {", ".join(agg_parts)}
    FROM fr2
    GROUP BY org_uuid, yh_date
    """

    con = duckdb.connect()
    try:
        out = con.execute(query).fetchdf()
    finally:
        con.close()

    if "yh_date" in out.columns:
        out["yh_date"] = pd.to_datetime(out["yh_date"], errors="coerce").dt.date

    meta = {
        "org_col": org_col,
        "date_col": date_col,
        "stage_col": stage_col,
        "amount_col": amount_col,
    }
    return out, meta


def build_panel(firm: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    firm = firm.copy()
    firm["cb_matched"] = firm["org_uuid"].notna().astype(int)

    merged = firm.merge(funding, on=["org_uuid", "yh_date"], how="left")

    # Fill zeros only for matched orgs: "no round" should be 0; unmatched stays missing.
    matched = merged["cb_matched"] == 1
    for col in ["cb_round_count", "cb_seriesAplus_round", "cb_raised_usd"]:
        if col in merged.columns:
            merged.loc[matched, col] = merged.loc[matched, col].fillna(0)

    if "cb_round_count" in merged.columns:
        merged["cb_any_round"] = np.where(
            merged["cb_matched"] == 1, (merged["cb_round_count"] > 0).astype(int), np.nan
        )

    # Cumulative outcomes by org_uuid (requires complete half-year grid, which firm panel provides)
    merged = merged.sort_values(["org_uuid", "yh_date"], na_position="last")
    if "cb_seriesAplus_round" in merged.columns:
        merged["cb_seriesAplus_cum"] = merged.groupby("org_uuid", dropna=True)[
            "cb_seriesAplus_round"
        ].cummax()

    if "cb_raised_usd" in merged.columns:
        merged["cb_log1p_raised_usd"] = np.log1p(merged["cb_raised_usd"])
        merged["cb_cum_raised_usd"] = merged.groupby("org_uuid", dropna=True)[
            "cb_raised_usd"
        ].cumsum()
        merged["cb_log1p_cum_raised_usd"] = np.log1p(merged["cb_cum_raised_usd"])
        merged["cb_log1p_cum_raised_usd_lag"] = merged.groupby("org_uuid", dropna=True)[
            "cb_log1p_cum_raised_usd"
        ].shift(1)
        merged["cb_dlog_cum_raised"] = (
            merged["cb_log1p_cum_raised_usd"] - merged["cb_log1p_cum_raised_usd_lag"]
        )
        merged["cb_dlog_cum_raised_we"] = _winsorise(merged["cb_dlog_cum_raised"])

    return merged


def main() -> None:
    args = parse_args()

    ensure_dir(args.out.parent)

    firm = read_firm_panel(args.firm_panel)
    funding, meta = read_funding_rounds(args.funding_rounds)

    panel = build_panel(firm, funding)

    if args.drop_unmatched:
        before = len(panel)
        panel = panel[panel["cb_matched"] == 1].copy()
        dropped = before - len(panel)
        print(f"Applied --drop-unmatched: dropped {dropped:,} firm×period rows.")

    panel.to_csv(args.out, index=False)

    # Lightweight diagnostics
    n_rows = len(panel)
    n_firms = panel["firm_id"].nunique(dropna=True) if "firm_id" in panel.columns else None
    n_matched_firms = (
        panel.loc[panel["cb_matched"] == 1, "firm_id"].nunique(dropna=True) if "firm_id" in panel.columns else None
    )
    print("Wrote:", args.out)
    print("Firm panel rows:", f"{n_rows:,}")
    if n_firms is not None:
        print("Firms:", f"{n_firms:,}", "| matched firms:", f"{n_matched_firms:,}")
    print("Funding-rounds columns used:", meta)
    print(
        "Outcome columns present:",
        [c for c in panel.columns if c.startswith("cb_") and c not in ("cb_matched",)],
    )


if __name__ == "__main__":
    main()
