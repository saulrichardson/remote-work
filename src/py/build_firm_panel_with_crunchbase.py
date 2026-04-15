#!/usr/bin/env python3
"""Build the firm panel with Crunchbase match metadata.

This is the explicit upstream step that turns:

- ``data/clean/firm_panel.dta``
- ``data/clean/crunchbase_crosswalk.csv``

into:

- ``data/clean/firm_panel_with_cb.csv``

The output keeps the canonical firm-panel columns and adds the Crunchbase
match fields used by downstream funding builders:

- ``org_uuid``
- ``match_type``

The current crosswalk exports a labeled ``firm_id`` column rather than the
numeric firm-panel identifier, so the stable join key here is ``companyname``.
This is grounded in the current files under ``data/clean/``:

- every crosswalk row has a unique ``companyname``
- those company names align with the active ``firm_panel.dta`` company names
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.py.project_paths import DATA_CLEAN, ensure_dir, require_file

DEFAULT_FIRM_PANEL = DATA_CLEAN / "firm_panel.dta"
DEFAULT_CROSSWALK = DATA_CLEAN / "crunchbase_crosswalk.csv"
DEFAULT_OUT = DATA_CLEAN / "firm_panel_with_cb.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--firm-panel",
        type=Path,
        default=DEFAULT_FIRM_PANEL,
        help="Canonical firm panel input (default: %(default)s).",
    )
    parser.add_argument(
        "--crosswalk",
        type=Path,
        default=DEFAULT_CROSSWALK,
        help="Firm-to-Crunchbase crosswalk CSV (default: %(default)s).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output CSV path (default: %(default)s).",
    )
    return parser.parse_args()


def load_firm_panel(path: Path) -> pd.DataFrame:
    require_file(path, nonempty=True, purpose="canonical firm panel")
    if path.suffix.lower() == ".dta":
        return pd.read_stata(path, convert_categoricals=False)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported firm panel extension: {path.suffix}")


def load_crosswalk(path: Path) -> pd.DataFrame:
    require_file(path, nonempty=True, purpose="Crunchbase crosswalk")
    df = pd.read_csv(path)
    required = {"companyname", "org_uuid", "match_type"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise RuntimeError(
            f"Crosswalk is missing required columns: {missing}. "
            "Expected at least companyname, org_uuid, and match_type."
        )

    if df["companyname"].duplicated().any():
        dupes = (
            df.loc[df["companyname"].duplicated(keep=False), "companyname"]
            .drop_duplicates()
            .head(10)
            .tolist()
        )
        raise RuntimeError(
            "Crosswalk must have one row per companyname before merging into the "
            f"firm panel. Duplicate companyname values include: {dupes}"
        )

    return df[["companyname", "org_uuid", "match_type"]].copy()


def main() -> None:
    args = parse_args()

    firm = load_firm_panel(args.firm_panel)
    crosswalk = load_crosswalk(args.crosswalk)

    if "companyname" not in firm.columns:
        raise RuntimeError(
            f"{args.firm_panel} is missing companyname, which is required for the "
            "Crunchbase merge."
        )

    merged = firm.merge(crosswalk, on="companyname", how="left")
    ensure_dir(args.out.parent)
    merged.to_csv(args.out, index=False)

    matched_rows = int(merged["org_uuid"].notna().sum()) if "org_uuid" in merged.columns else 0
    total_rows = len(merged)
    matched_firms = int(merged.loc[merged["org_uuid"].notna(), "companyname"].nunique())
    total_firms = int(merged["companyname"].nunique())

    print(f"Wrote {args.out}")
    print(
        "Matched rows:",
        f"{matched_rows:,}/{total_rows:,}",
        f"({matched_rows / total_rows:.1%})" if total_rows else "(n/a)",
    )
    print(
        "Matched firms:",
        f"{matched_firms:,}/{total_firms:,}",
        f"({matched_firms / total_firms:.1%})" if total_firms else "(n/a)",
    )


if __name__ == "__main__":
    main()
