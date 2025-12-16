#!/usr/bin/env python3
"""
Build a firm→Crunchbase org crosswalk using Scoop's LinkedIn export and
Crunchbase organizations.

Priority of matches per firm_id:
 1) Direct org UUID from scoop `crunchbase_url`.
 2) name_norm + state match to Crunchbase.
 3) name_norm only match.
Within each tier, pick the lowest Crunchbase `rank`.

Outputs:
  - data/clean/crunchbase_crosswalk.parquet
  - data/clean/crunchbase_crosswalk.dta (small, for Stata)
  - results/raw/crunchbase_merge/summary.json (coverage + diagnostics)
  - results/raw/crunchbase_merge/unmatched_top.csv (top unmatched by row weight)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import duckdb
import pandas as pd

from project_paths import DATA_CLEAN, DATA_RAW, RESULTS_RAW, ensure_dir

# Locations ---------------------------------------------------------------
FIRM_PANEL = DATA_CLEAN / "firm_panel.dta"
SCOOP_LINKEDIN = DATA_RAW / "Scoop_Linkedin.csv"
CRUNCHBASE_ORGS = DATA_RAW / "crunchbase" / "organizations.csv"
OUT_CROSSWALK_CSV = DATA_CLEAN / "crunchbase_crosswalk.csv"
OUT_SUMMARY = RESULTS_RAW / "crunchbase_merge" / "summary.json"
OUT_UNMATCHED = RESULTS_RAW / "crunchbase_merge" / "unmatched_top.csv"
OVERRIDES = DATA_RAW / "crunchbase_manual_overrides.csv"

# Helpers ----------------------------------------------------------------

def normalize_name(name: str | None) -> str | None:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return None
    s = name.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(
        r"\b(inc|incorporated|llc|ltd|corp|corporation|company|co|plc|ag|sa|gmbh|bv|limited|the)\b",
        " ",
        s,
    )
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def load_firm_panel() -> pd.DataFrame:
    if not FIRM_PANEL.exists():
        raise FileNotFoundError(f"Missing firm panel: {FIRM_PANEL}")
    df = pd.read_stata(FIRM_PANEL, columns=["firm_id", "companyname", "hqstate", "hqcity", "yh"])
    df["name_norm"] = df["companyname"].apply(normalize_name)
    return df


def load_scoop_linkedin() -> pd.DataFrame:
    if not SCOOP_LINKEDIN.exists():
        raise FileNotFoundError(
            f"Missing Scoop LinkedIn export: {SCOOP_LINKEDIN}. "
            "Place it under data/raw/Scoop_Linkedin.csv (untracked)."
        )
    df = pd.read_csv(SCOOP_LINKEDIN)
    df["name_norm"] = df["Company Name (CLEAN)"].apply(normalize_name)
    # Parse org UUID from crunchbase_url
    def parse_uuid(url: str | None) -> str | None:
        if isinstance(url, str):
            m = re.search(r"organization/([^/?#]+)", url)
            if m:
                return m.group(1)
        return None

    df["org_uuid_cburl"] = df["crunchbase_url"].apply(parse_uuid)
    return df


def load_crunchbase_orgs() -> pd.DataFrame:
    if not CRUNCHBASE_ORGS.exists():
        raise FileNotFoundError(
            f"Missing Crunchbase organizations export: {CRUNCHBASE_ORGS}. "
            "Place it under data/raw/crunchbase/organizations.csv (untracked)."
        )
    # Use DuckDB to efficiently read selected columns
    con = duckdb.connect()
    con.execute(
        f"""
        SELECT uuid, permalink, name, state_code, country_code, rank,
               TRIM(REGEXP_REPLACE(REGEXP_REPLACE(lower(name), '[^a-z0-9 ]', ' ', 'g'),
                   '\\b(inc|incorporated|llc|ltd|corp|corporation|company|co|plc|ag|sa|gmbh|bv|limited|the)\\b', ' ', 'g')) AS name_norm
        FROM read_csv_auto('{CRUNCHBASE_ORGS}', SAMPLE_SIZE=-1)
        WHERE country_code = 'USA' OR country_code IS NULL
        """
    )
    df = con.fetch_df()
    con.close()
    return df


def load_overrides() -> pd.DataFrame:
    if not OVERRIDES.exists():
        return pd.DataFrame(columns=["firm_id", "org_uuid", "source"])
    df = pd.read_csv(OVERRIDES)
    return df


# Matching ----------------------------------------------------------------

def build_candidates(
    firm: pd.DataFrame, scoop: pd.DataFrame, orgs: pd.DataFrame, overrides: pd.DataFrame
) -> pd.DataFrame:
    org_rank: Dict[str, float] = orgs.set_index("uuid")["rank"].to_dict()
    slug_to_uuid: Dict[str, str] = orgs.set_index("permalink")["uuid"].to_dict()

    candidates: List[pd.DataFrame] = []

    # Manual overrides (priority 0)
    if not overrides.empty:
        overrides = overrides.merge(firm[["firm_id", "companyname"]], on="firm_id", how="left")
        overrides = overrides.rename(columns={"org_uuid": "org_uuid"})
        overrides["match_type"] = "manual_override"
        overrides["priority"] = 0
        overrides["rank"] = overrides["org_uuid"].map(org_rank)
        candidates.append(overrides[["firm_id", "companyname", "org_uuid", "match_type", "priority", "rank"]])

    # Direct via crunchbase_url provided in Scoop
    direct = (
        firm.merge(
            scoop[["name_norm", "org_uuid_cburl"]], on="name_norm", how="left"
        )
        .dropna(subset=["org_uuid_cburl"])
        .rename(columns={"org_uuid_cburl": "slug"})
    )
    # map slug to canonical uuid if present
    direct["org_uuid"] = direct["slug"].map(slug_to_uuid)
    direct = direct.dropna(subset=["org_uuid"])
    direct["match_type"] = "direct_cb_url"
    direct["priority"] = 1
    direct["rank"] = direct["org_uuid"].map(org_rank)
    candidates.append(direct[["firm_id", "companyname", "org_uuid", "match_type", "priority", "rank"]])

    # Name + state
    name_state = firm.merge(
        orgs[["uuid", "name_norm", "state_code", "rank"]],
        left_on=["name_norm", "hqstate"],
        right_on=["name_norm", "state_code"],
        how="inner",
    )
    name_state = name_state.rename(columns={"uuid": "org_uuid"})
    name_state["match_type"] = "name_state"
    name_state["priority"] = 2
    candidates.append(name_state[["firm_id", "companyname", "org_uuid", "match_type", "priority", "rank"]])

    # Name only
    name_only = firm.merge(
        orgs[["uuid", "name_norm", "rank"]], on="name_norm", how="inner"
    ).rename(columns={"uuid": "org_uuid"})
    name_only["match_type"] = "name_only"
    name_only["priority"] = 3
    candidates.append(name_only[["firm_id", "companyname", "org_uuid", "match_type", "priority", "rank"]])

    return pd.concat(candidates, ignore_index=True)


def pick_best_per_firm(candidates: pd.DataFrame) -> pd.DataFrame:
    # Sort by priority then rank (ascending rank = higher prominence)
    sorted_cand = candidates.sort_values(
        by=["priority", "rank"], na_position="last"
    )
    best = sorted_cand.drop_duplicates(subset=["firm_id"], keep="first")
    return best


def compute_summary(firm: pd.DataFrame, best: pd.DataFrame, candidates: pd.DataFrame) -> dict:
    total_firms = firm["firm_id"].nunique()
    matched_firms = best["firm_id"].nunique()
    row_cov = firm.merge(best[["firm_id", "org_uuid"]], on="firm_id", how="left")
    row_coverage = float(row_cov["org_uuid"].notna().mean())

    # Ambiguity: unique org candidates per firm
    dedup_cand = candidates.drop_duplicates(subset=["firm_id", "org_uuid"])
    cand_counts = dedup_cand.groupby("firm_id")["org_uuid"].nunique()
    ambiguous_firms = int((cand_counts > 1).sum())

    summary = {
        "total_firms": total_firms,
        "matched_firms": matched_firms,
        "firm_coverage": round(matched_firms / total_firms, 4),
        "row_coverage": round(row_coverage, 4),
        "ambiguous_firms": ambiguous_firms,
        "candidates_gt1_share": round(ambiguous_firms / total_firms, 4),
        "match_type_counts": candidates.groupby("match_type")["firm_id"].nunique().to_dict(),
    }
    return summary


def top_unmatched(firm: pd.DataFrame, best: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    matched_ids = set(best["firm_id"])
    unmatched = firm[~firm["firm_id"].isin(matched_ids)]
    return (
        unmatched.groupby("companyname").size().sort_values(ascending=False).head(n).reset_index(name="rows")
    )


# Main -------------------------------------------------------------------

def main() -> None:
    ensure_dir(DATA_CLEAN)
    ensure_dir(RESULTS_RAW / "crunchbase_merge")

    firm = load_firm_panel()
    scoop = load_scoop_linkedin()
    orgs = load_crunchbase_orgs()
    overrides = load_overrides()

    candidates = build_candidates(firm, scoop, orgs, overrides)
    best = pick_best_per_firm(candidates)

    # Save crosswalk
    best.to_csv(OUT_CROSSWALK_CSV, index=False)

    # Summary + unmatched
    summary = compute_summary(firm, best, candidates)
    with open(OUT_SUMMARY, "w") as f:
        json.dump(summary, f, indent=2)

    unmatched = top_unmatched(firm, best)
    unmatched.to_csv(OUT_UNMATCHED, index=False)

    print("Crosswalk saved:", OUT_CROSSWALK_CSV)
    print("Summary:", summary)
    print("Top unmatched saved:", OUT_UNMATCHED)


if __name__ == "__main__":
    main()
