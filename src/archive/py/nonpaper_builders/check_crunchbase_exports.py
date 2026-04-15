#!/usr/bin/env python3
"""Validate Crunchbase raw exports used by the paper pipeline.

This repo's Crunchbase workflow relies on two raw CSVs:
  - data/raw/crunchbase/organizations.csv
  - data/raw/crunchbase/funding_rounds.csv

Those are often stored in a Dropbox-synced folder (sometimes as symlinks from
data/raw/crunchbase/*). If the files are cloud-only placeholders, they may
appear as zero-byte CSVs and downstream scripts will fail in confusing ways.

This script is a lightweight, artifact-first preflight check. It verifies:
  - the files exist and are non-empty
  - key columns expected by the builders are present

It does *not* attempt to download Crunchbase data.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.py.project_paths import DATA_CLEAN, DATA_RAW, require_file


DEFAULT_ORGS = DATA_RAW / "crunchbase" / "organizations.csv"
DEFAULT_FUNDING = DATA_RAW / "crunchbase" / "funding_rounds.csv"


def _read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        return next(reader)


def _pick_column(columns: list[str], candidates: list[str]) -> str | None:
    lower_to_actual = {c.lower(): c for c in columns}
    for cand in candidates:
        key = cand.lower()
        if key in lower_to_actual:
            return lower_to_actual[key]
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--organizations",
        type=Path,
        default=DEFAULT_ORGS,
        help="Path to organizations.csv (default: %(default)s).",
    )
    p.add_argument(
        "--funding-rounds",
        type=Path,
        default=DEFAULT_FUNDING,
        help="Path to funding_rounds.csv (default: %(default)s).",
    )
    p.add_argument(
        "--firm-panel-with-cb",
        type=Path,
        default=DATA_CLEAN / "firm_panel_with_cb.csv",
        help="Path to firm_panel_with_cb.csv (default: %(default)s).",
    )
    return p.parse_args()


def check_funding_rounds(path: Path) -> None:
    require_file(path, nonempty=True, purpose="Crunchbase funding rounds export (funding_rounds.csv)")
    cols = _read_header(path)
    print("\n[funding_rounds.csv]")
    print("path:", path)
    print("columns:", len(cols))

    org_col = _pick_column(cols, ["org_uuid", "organization_uuid"])
    date_col = _pick_column(cols, ["announced_on", "announced_on_date", "announced_date"])
    stage_col = _pick_column(cols, ["investment_type", "funding_round_type"])
    amount_col = _pick_column(
        cols,
        ["raised_amount_usd", "money_raised_usd", "raised_amount", "money_raised"],
    )

    if org_col is None or date_col is None:
        raise RuntimeError(
            "funding_rounds.csv is missing required columns.\n"
            f"Found org column: {org_col!r}; date column: {date_col!r}.\n"
            "Expected at least org_uuid + announced_on (or equivalents)."
        )

    print("detected org_uuid column:", org_col)
    print("detected announced_on column:", date_col)
    print("detected stage column:", stage_col)
    print("detected amount column:", amount_col)

    # For the Overleaf main table (firm_scaling_crunchbase_fundraising_core4),
    # we need both stage + amount-derived outcomes.
    missing_for_core4 = []
    if stage_col is None:
        missing_for_core4.append("investment_type / funding_round_type")
    if amount_col is None:
        missing_for_core4.append("raised_amount_usd / money_raised_usd")
    if missing_for_core4:
        print("WARNING: core4 table needs:", ", ".join(missing_for_core4))


def check_organizations(path: Path) -> None:
    require_file(path, nonempty=True, purpose="Crunchbase organizations export (organizations.csv)")
    cols = _read_header(path)
    print("\n[organizations.csv]")
    print("path:", path)
    print("columns:", len(cols))

    required = ["uuid", "permalink", "name", "country_code", "state_code", "rank"]
    missing = [c for c in required if c not in cols]
    if missing:
        print("WARNING: organizations.csv missing columns expected by build_crunchbase_crosswalk.py:", missing)
        print("First 30 columns:", cols[:30])
    else:
        print("OK: has required columns for crosswalk builder.")


def check_firm_panel_with_cb(path: Path) -> None:
    require_file(path, nonempty=True, purpose="Firm panel with Crunchbase org_uuid (firm_panel_with_cb.csv)")
    cols = _read_header(path)
    print("\n[firm_panel_with_cb.csv]")
    print("path:", path)
    print("columns:", len(cols))
    required = ["firm_id", "yh", "org_uuid", "var3", "var4", "var5", "var6", "var7"]
    missing = [c for c in required if c not in cols]
    if missing:
        print("WARNING: firm_panel_with_cb.csv missing required columns for CB outcomes builder:", missing)
    else:
        print("OK: has required columns for src/py/build_firm_scaling_crunchbase_outcomes.py.")


def main() -> None:
    args = parse_args()
    try:
        check_organizations(args.organizations)
        check_funding_rounds(args.funding_rounds)
        check_firm_panel_with_cb(args.firm_panel_with_cb)
    except Exception as e:
        raise SystemExit(f"\n✖ Crunchbase preflight failed:\n{e}")

    print("\n✓ Crunchbase preflight completed.")


if __name__ == "__main__":
    main()
