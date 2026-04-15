#!/usr/bin/env python3
"""Sample Scoop job postings for manual equity-compensation coding.

Transcript ask (equity incentives from job postings):
  - Filter postings by role (k7 role field; exclude admin/marketing; keep
    engineer/scientist/ops categories).
  - For large employers, sample a fixed number of postings per firm rather than
    labeling all.
  - Classify sampled postings for equity compensation and aggregate to a
    firm-level measure.

This script implements the *sampling + aggregation plumbing* in a way that is
reproducible and fail-fast. It does NOT try to infer equity-compensation from
titles/salary because the in-repo postings extract currently contains no free-
text description/benefits fields.

Inputs
  - data/raw/vacancy/Postings_scoop.csv
  - data/clean/firm_panel_with_cb.csv (used only to map companyname → firm_id)

Outputs
  - results/raw/equity_coding/postings_sample.csv
  - results/raw/equity_coding/firm_equity_measure.csv   (after labeling)

Workflow
  1) Create a sample to label:
       python src/py/sample_vacancy_postings_for_equity_coding.py sample --max-per-firm 50
     → label the `equity_flag` column manually (0/1) in the output CSV
  2) Aggregate to firm-level measure:
       python src/py/sample_vacancy_postings_for_equity_coding.py aggregate --labeled-csv results/raw/equity_coding/postings_sample.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd

from src.py.project_paths import DATA_CLEAN, DATA_RAW, RESULTS_RAW, ensure_dir


POSTINGS_CSV = DATA_RAW / "vacancy" / "Postings_scoop.csv"
FIRM_PANEL_CB = DATA_CLEAN / "firm_panel_with_cb.csv"
OUT_DIR = RESULTS_RAW / "equity_coding"


KEEP_ROLES_K7 = {"Engineer", "Scientist", "Operations"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("sample", help="Create a per-firm postings sample for manual labeling.")
    ps.add_argument("--max-per-firm", type=int, default=50, help="Max postings to keep per firm. Default: %(default)s")
    ps.add_argument("--seed", type=int, default=123, help="Random seed for sampling. Default: %(default)s")
    ps.add_argument(
        "--out-csv",
        type=Path,
        default=OUT_DIR / "postings_sample.csv",
        help="Output sample CSV to label. Default: %(default)s",
    )

    pa = sub.add_parser("aggregate", help="Aggregate a labeled sample to firm-level equity measures.")
    pa.add_argument(
        "--labeled-csv",
        type=Path,
        default=OUT_DIR / "postings_sample.csv",
        help="Labeled CSV produced by the 'sample' command. Default: %(default)s",
    )
    pa.add_argument(
        "--out-csv",
        type=Path,
        default=OUT_DIR / "firm_equity_measure.csv",
        help="Firm-level output CSV. Default: %(default)s",
    )

    return p.parse_args()


def load_postings() -> pd.DataFrame:
    raise RuntimeError(
        "This helper is intentionally unused: the postings file is ~8GB, so we rely on DuckDB to "
        "filter + sample without loading the full CSV into memory."
    )


def load_firm_id_map() -> pd.DataFrame:
    if not FIRM_PANEL_CB.exists():
        raise FileNotFoundError(f"Missing firm panel with IDs: {FIRM_PANEL_CB}")
    df = pd.read_csv(FIRM_PANEL_CB, usecols=["companyname", "firm_id"], low_memory=False)
    df["companyname_norm"] = df["companyname"].astype(str).str.strip().str.lower()
    df = df.dropna(subset=["firm_id"]).drop_duplicates(subset=["companyname_norm"])
    return df[["companyname_norm", "firm_id"]]


def make_sample(*, max_per_firm: int, seed: int) -> pd.DataFrame:
    if max_per_firm <= 0:
        raise ValueError("--max-per-firm must be positive.")

    firm_map = load_firm_id_map()
    if not POSTINGS_CSV.exists():
        raise FileNotFoundError(f"Missing postings extract: {POSTINGS_CSV}")

    # Use DuckDB for memory-safe sampling from a very large CSV.
    con = duckdb.connect()
    con.register("firm_map", firm_map)

    roles = ", ".join(f"'{r}'" for r in sorted(KEEP_ROLES_K7))

    query = f"""
    WITH posts AS (
      SELECT
        row_number() OVER () - 1 AS posting_rowid,
        companyname,
        lower(trim(companyname)) AS companyname_norm,
        post_date,
        postyear,
        title,
        title_cleaned,
        role_k7,
        role_k50,
        role_k150,
        salary,
        location,
        city,
        state,
        industry_cleaned
      FROM read_csv_auto('{POSTINGS_CSV.as_posix()}', SAMPLE_SIZE=-1)
      WHERE role_k7 IN ({roles})
    ),
    mapped AS (
      SELECT
        p.*,
        m.firm_id
      FROM posts p
      LEFT JOIN firm_map m
      ON p.companyname_norm = m.companyname_norm
    ),
    keyed AS (
      SELECT
        *,
        coalesce(cast(firm_id AS varchar), companyname_norm) AS firm_key,
        hash(posting_rowid, {seed}) AS h
      FROM mapped
    ),
    ranked AS (
      SELECT
        *,
        row_number() OVER (PARTITION BY firm_key ORDER BY h) AS rn
      FROM keyed
    )
    SELECT
      firm_id,
      companyname,
      companyname_norm,
      posting_rowid,
      post_date,
      postyear,
      title,
      title_cleaned,
      role_k7,
      role_k50,
      role_k150,
      salary,
      location,
      city,
      state,
      industry_cleaned
    FROM ranked
    WHERE rn <= {max_per_firm}
    """

    try:
        sampled = con.execute(query).fetchdf()
    finally:
        con.close()

    # Parse post_date in pandas (keep failures as NaT).
    if "post_date" in sampled.columns:
        sampled["post_date"] = pd.to_datetime(sampled["post_date"], errors="coerce")

    sampled["equity_flag"] = pd.NA
    sampled = sampled.sort_values(["firm_id", "post_date"], na_position="last")
    return sampled


def aggregate_labeled(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing labeled CSV: {path}")
    df = pd.read_csv(path, low_memory=False)
    required = {"firm_id", "equity_flag"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Labeled file missing required columns: {sorted(missing)}")

    df["equity_flag"] = pd.to_numeric(df["equity_flag"], errors="coerce")
    # Fail-fast: we only accept 0/1 coding.
    bad = df.loc[df["equity_flag"].notna() & ~df["equity_flag"].isin([0, 1]), "equity_flag"]
    if not bad.empty:
        ex = ", ".join(str(x) for x in bad.unique()[:10])
        raise ValueError(f"equity_flag must be coded as 0/1. Found other values (sample): {ex}")

    # Keep only labeled rows.
    labeled = df[df["equity_flag"].isin([0, 1])].copy()
    if labeled.empty:
        raise ValueError("No labeled rows found (equity_flag is all missing).")

    out = (
        labeled.groupby("firm_id", as_index=False)
        .agg(
            n_labeled=("equity_flag", "size"),
            equity_share=("equity_flag", "mean"),
        )
        .sort_values("n_labeled", ascending=False)
    )
    return out


def main() -> None:
    args = parse_args()
    ensure_dir(OUT_DIR)

    if args.cmd == "sample":
        sample = make_sample(max_per_firm=args.max_per_firm, seed=args.seed)
        ensure_dir(args.out_csv.parent)
        sample.to_csv(args.out_csv, index=False)
        print(f"Wrote postings sample → {args.out_csv}")
        print(f"Rows: {len(sample):,} | firms: {sample['firm_id'].nunique(dropna=True):,}")
        print("Next: manually fill equity_flag (0/1), then run 'aggregate'.")
        return

    if args.cmd == "aggregate":
        out = aggregate_labeled(args.labeled_csv)
        ensure_dir(args.out_csv.parent)
        out.to_csv(args.out_csv, index=False)
        print(f"Wrote firm-level equity measure → {args.out_csv}")
        print(f"Firms: {len(out):,} | mean(equity_share): {out['equity_share'].mean():.3f}")
        return

    raise RuntimeError(f"Unhandled cmd: {args.cmd}")


if __name__ == "__main__":
    main()
