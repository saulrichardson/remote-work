#!/usr/bin/env python3
"""Build the canonical top-14 CSA mapping used by the active top-metro table.

The paper's top-metro scenarios depend on a fixed 14-CSA definition recovered
from the archived CSA-analysis branch. That recovered source-of-truth lives in
``data/raw/paper_aux/csa_top14_definition.csv``. This builder materializes the
cleaned mapping consumed by the active Stata top-metro spec.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.py.project_paths import DATA_CLEAN, DATA_RAW, ensure_dir, require_file

DEFAULT_SOURCE = DATA_RAW / "paper_aux" / "csa_top14_definition.csv"
DEFAULT_OUTPUT = DATA_CLEAN / "csa_msa_top14_mapping.csv"
EXPECTED_COLUMNS = ("csa_rank", "csa_name", "msa", "cbsacode")
EXPECTED_RANKS = tuple(range(1, 15))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Recovered raw CSA definition (defaults to data/raw/paper_aux/csa_top14_definition.csv).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination cleaned mapping (defaults to data/clean/csa_msa_top14_mapping.csv).",
    )
    return parser.parse_args()


def _trim(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def load_definition(path: Path) -> pd.DataFrame:
    require_file(path, nonempty=True, purpose="recovered top-14 CSA definition")
    df = pd.read_csv(path)

    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise KeyError(f"Definition file missing required columns: {sorted(missing)}")

    df = df.loc[:, EXPECTED_COLUMNS].copy()
    df["csa_name"] = _trim(df["csa_name"])
    df["msa"] = _trim(df["msa"])
    df["csa_rank"] = pd.to_numeric(df["csa_rank"], errors="coerce")
    df["cbsacode"] = pd.to_numeric(df["cbsacode"], errors="coerce")

    if df["csa_name"].isna().any() or (df["csa_name"] == "").any():
        raise ValueError("Recovered CSA definition contains blank csa_name values.")
    if df["msa"].isna().any() or (df["msa"] == "").any():
        raise ValueError("Recovered CSA definition contains blank msa values.")
    if df["csa_rank"].isna().any():
        raise ValueError("Recovered CSA definition contains non-numeric csa_rank values.")
    if df["cbsacode"].isna().any():
        raise ValueError("Recovered CSA definition contains non-numeric cbsacode values.")

    df["csa_rank"] = df["csa_rank"].astype(int)
    df["cbsacode"] = df["cbsacode"].astype(int)

    observed_ranks = tuple(sorted(df["csa_rank"].unique().tolist()))
    if observed_ranks != EXPECTED_RANKS:
        raise ValueError(
            "Recovered CSA definition must contain exactly ranks 1 through 14. "
            f"Found {observed_ranks}."
        )

    if df.duplicated(["csa_rank", "cbsacode"]).any():
        dupes = df.loc[df.duplicated(["csa_rank", "cbsacode"], keep=False), ["csa_rank", "cbsacode"]]
        raise ValueError(
            "Recovered CSA definition has duplicate rank/CBSA rows:\n"
            f"{dupes.to_string(index=False)}"
        )

    if df.groupby("csa_rank")["cbsacode"].nunique().min() < 1:
        raise ValueError("Every CSA rank must include at least one CBSA member.")

    return df.reset_index(drop=True)


def main() -> None:
    args = parse_args()
    definition = load_definition(args.source.expanduser().resolve())
    output = args.output.expanduser().resolve()
    ensure_dir(output.parent)
    definition.to_csv(output, index=False)
    print(f"Wrote canonical top-14 CSA mapping to {output}")


if __name__ == "__main__":
    main()
