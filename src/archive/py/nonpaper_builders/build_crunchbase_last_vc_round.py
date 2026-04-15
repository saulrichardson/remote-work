#!/usr/bin/env python3
"""Crunchbase: last VC fundraising date diagnostics for firms in the sample.

This script answers meeting-style questions like:
  - "For firms in our matched sample (e.g., Facebook), when was the *last* VC
    fundraising round?"
  - "How many firms have had no VC activity in >10 years?"

It is deliberately *artifact-first*: it computes dates directly from the raw
Crunchbase funding rounds export and merges the result onto the firm panel that
already contains the firm↔Crunchbase org_uuid match.

Inputs (expected to exist in this repo layout)
  - data/clean/firm_panel_with_cb.csv
  - data/raw/crunchbase/funding_rounds.csv

Outputs
  - results/raw/crunchbase_funding_recency/last_vc_round_by_firm.csv
  - results/raw/crunchbase_funding_recency/last_vc_round_bins_summary.csv

Notes on definitions
  We implement two VC definitions because "VC round" can be ambiguous:
    - vc_core  : seed/pre-seed/angel/convertible_note + any "series_*" + undisclosed
    - vc_broad : vc_core plus corporate_round/private_equity/equity_crowdfunding/secondary_market

  Post-IPO rounds (investment_type starting with "post_ipo_") are always excluded
  from VC definitions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.py.project_paths import DATA_CLEAN, DATA_RAW, RESULTS_RAW, ensure_dir, require_file


FIRM_PANEL = DATA_CLEAN / "firm_panel_with_cb.csv"
FUNDING_ROUNDS = DATA_RAW / "crunchbase" / "funding_rounds.csv"

DEFAULT_OUT_DIR = RESULTS_RAW / "crunchbase_funding_recency"


VC_CORE_NON_SERIES = {"pre_seed", "seed", "angel", "convertible_note", "undisclosed"}
VC_BROAD_EXTRA = {"corporate_round", "private_equity", "equity_crowdfunding", "secondary_market"}


@dataclass(frozen=True)
class RecencyBins:
    # Upper bounds in years since last VC date (strictly <= bound).
    # Anything above the last bound is grouped as f">{last}".
    cutoffs_years: tuple[float, ...] = (2.0, 5.0, 10.0)

    def label(self, years_since: float) -> str:
        for c in self.cutoffs_years:
            if years_since <= c:
                return f"≤{c:g}y"
        return f">{self.cutoffs_years[-1]:g}y"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--asof",
        type=str,
        default="2020-01-01",
        help="Reference date for 'years since last VC' (YYYY-MM-DD). Default: %(default)s",
    )
    p.add_argument(
        "--sample",
        choices=["all_matched", "matched_private"],
        default="all_matched",
        help="Which firm sample to summarise. Default: %(default)s",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory under results/raw. Default: %(default)s",
    )
    return p.parse_args()


def _parse_date(s: str) -> date | None:
    s = str(s).strip()
    if not s or s.lower() in {"nan", "nat", "none"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def load_firm_panel() -> pd.DataFrame:
    require_file(FIRM_PANEL, nonempty=True, purpose="Firm panel with Crunchbase org_uuid (firm_panel_with_cb.csv)")
    usecols = ["firm_id", "companyname", "org_uuid", "match_type", "public", "age"]
    df = pd.read_csv(FIRM_PANEL, usecols=lambda c: c in set(usecols), low_memory=False)
    # firm_id should exist; others may be missing in older builds.
    if "firm_id" not in df.columns:
        raise RuntimeError(f"Expected firm_id column in {FIRM_PANEL}.")
    # firm-level unique snapshot
    df = df.drop_duplicates(subset=["firm_id"]).copy()
    return df


def load_funding_rounds() -> pd.DataFrame:
    require_file(FUNDING_ROUNDS, nonempty=True, purpose="Crunchbase funding rounds export (funding_rounds.csv)")
    usecols = ["org_uuid", "announced_on", "investment_type"]
    fr = pd.read_csv(FUNDING_ROUNDS, usecols=lambda c: c in set(usecols), low_memory=False)
    missing = set(usecols) - set(fr.columns)
    if missing:
        raise RuntimeError(f"Funding rounds file is missing columns: {sorted(missing)}.")
    fr = fr.rename(columns={"announced_on": "announced_on_raw"}).copy()
    fr["org_uuid"] = fr["org_uuid"].astype(str)
    fr["investment_type"] = fr["investment_type"].astype(str).str.strip().str.lower()
    fr["announced_on"] = fr["announced_on_raw"].apply(_parse_date)
    fr = fr.dropna(subset=["announced_on"]).copy()
    return fr


def classify_vc(fr: pd.DataFrame) -> pd.DataFrame:
    fr = fr.copy()
    post_ipo = fr["investment_type"].str.startswith("post_ipo_")
    is_series = fr["investment_type"].str.startswith("series_")
    vc_core = (~post_ipo) & (is_series | fr["investment_type"].isin(VC_CORE_NON_SERIES))
    vc_broad = vc_core | ((~post_ipo) & fr["investment_type"].isin(VC_BROAD_EXTRA))
    fr["is_vc_core"] = vc_core
    fr["is_vc_broad"] = vc_broad
    return fr


def last_dates_by_org(fr: pd.DataFrame) -> pd.DataFrame:
    """Return last-round dates by org_uuid (any, VC-core, VC-broad).

    Important: *fr* is expected to already be restricted to the desired time window.
    E.g., if you want "last VC round as-of 2020-01-01", filter announced_on <= that
    date before calling this function.
    """
    last_any = fr.groupby("org_uuid")["announced_on"].max().rename("last_round_date_any")
    last_core = (
        fr.loc[fr["is_vc_core"]]
        .groupby("org_uuid")["announced_on"]
        .max()
        .rename("last_vc_date_core")
    )
    last_broad = (
        fr.loc[fr["is_vc_broad"]]
        .groupby("org_uuid")["announced_on"]
        .max()
        .rename("last_vc_date_broad")
    )
    return pd.concat([last_any, last_core, last_broad], axis=1).reset_index()


def years_since(d: date | pd.Timestamp | None, asof: date) -> float | None:
    if d is None or pd.isna(d):
        return None
    if isinstance(d, pd.Timestamp):
        d = d.date()
    return (asof - d).days / 365.25


def main() -> None:
    args = parse_args()
    asof = _parse_date(args.asof)
    if asof is None:
        raise ValueError(f"--asof must be YYYY-MM-DD; got {args.asof!r}.")

    firm = load_firm_panel()
    # Sample definition
    firm["public"] = pd.to_numeric(firm.get("public"), errors="coerce")
    firm["age"] = pd.to_numeric(firm.get("age"), errors="coerce")
    matched = firm[firm["org_uuid"].notna()].copy()
    if args.sample == "matched_private":
        matched = matched[matched["public"] != 1].copy()

    fr = load_funding_rounds()
    fr = classify_vc(fr)
    # Last VC dates overall (full Crunchbase coverage) vs. last VC dates "as-of"
    # the requested reference date. The latter is what we use for recency bins.
    org_last_all = last_dates_by_org(fr).rename(
        columns={
            "last_round_date_any": "last_round_date_any_all",
            "last_vc_date_core": "last_vc_date_core_all",
            "last_vc_date_broad": "last_vc_date_broad_all",
        }
    )
    fr_asof = fr.loc[fr["announced_on"] <= asof].copy()
    org_last_asof = last_dates_by_org(fr_asof).rename(
        columns={
            "last_round_date_any": "last_round_date_any_asof",
            "last_vc_date_core": "last_vc_date_core_asof",
            "last_vc_date_broad": "last_vc_date_broad_asof",
        }
    )

    out = (
        matched.merge(org_last_all, on="org_uuid", how="left")
        .merge(org_last_asof, on="org_uuid", how="left")
    )

    bins = RecencyBins()
    out["years_since_vc_core"] = out["last_vc_date_core_asof"].apply(lambda d: years_since(d, asof))
    out["years_since_vc_broad"] = out["last_vc_date_broad_asof"].apply(lambda d: years_since(d, asof))

    def _bin(val: float | None) -> str:
        if val is None or pd.isna(val):
            return "never"
        return bins.label(float(val))

    out["vc_core_recency_bin"] = out["years_since_vc_core"].apply(_bin)
    out["vc_broad_recency_bin"] = out["years_since_vc_broad"].apply(_bin)

    # Avoid accidental overwrite when running multiple samples: write into a
    # per-sample subdirectory under results/raw/.
    sample_out_dir = args.out_dir / args.sample
    ensure_dir(sample_out_dir)
    out_path = sample_out_dir / "last_vc_round_by_firm.csv"
    out.to_csv(out_path, index=False)

    # Summary tables: counts/shares by recency bin (core + broad).
    ordered_bins = (
        ["never"]
        + [f"≤{c:g}y" for c in RecencyBins().cutoffs_years]
        + [f">{RecencyBins().cutoffs_years[-1]:g}y"]
    )

    summaries: list[pd.DataFrame] = []
    for label, col in [
        ("vc_core", "vc_core_recency_bin"),
        ("vc_broad", "vc_broad_recency_bin"),
    ]:
        tmp = (
            out.groupby(col, dropna=False)
            .size()
            .reset_index(name="n_firms")
            .rename(columns={col: "recency_bin"})
        )
        tmp["definition"] = label
        tmp["share"] = tmp["n_firms"] / tmp["n_firms"].sum()
        tmp["recency_bin"] = pd.Categorical(tmp["recency_bin"], categories=ordered_bins, ordered=True)
        tmp = tmp.sort_values("recency_bin")
        tmp["recency_bin"] = tmp["recency_bin"].astype(str)
        summaries.append(tmp)

    summ = pd.concat(summaries, ignore_index=True)
    summ_path = sample_out_dir / "last_vc_round_bins_summary.csv"
    summ.to_csv(summ_path, index=False)

    print(f"Wrote firm-level VC recency file → {out_path}")
    print(f"Wrote VC recency bin summary     → {summ_path}")
    print(f"Sample: {args.sample} | as-of: {asof.isoformat()} | firms: {len(out):,}")


if __name__ == "__main__":
    main()
