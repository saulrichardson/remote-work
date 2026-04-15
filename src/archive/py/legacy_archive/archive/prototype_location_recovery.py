#!/usr/bin/env python3
"""
Prototype pipeline: recover CBSA codes for spells with missing MSA using
user-level location strings.

This script purposefully runs on a small sample so we can validate the
approach before wiring it into the production builders.  It performs:

1. Load the first N rows from the raw spell dump (restricting to columns
   we need) and keep only spells whose LinkedIn MSA is "empty" or tagged
   as NONMETRO.
2. Join on the user-level location file (New/Data/User_location.csv).
3. Attempt to map the location string to an MSA/CBSA using a few simple
   heuristics (alias dictionary + city/state matching backed by the
   existing enriched_msa.csv lookup).
4. Report coverage statistics so we can judge whether the recovery logic
   is worth hardening.

Usage:
    python py/prototype_location_recovery.py --sample 500000
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
NEW = ROOT.parent / "New" / "Data"

SPELL_CSV = RAW / "Scoop_workers_positions.csv"
USER_LOC_CSV = NEW / "User_location.csv"
ENRICH_MSA = PROC / "enriched_msa.csv"


STATE_ABBR = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}

# Manual aliases that cover the modal remote/ambiguous location strings.
ALIASES = {
    "san francisco bay area": "San Francisco-Oakland-Fremont CA MSA",
    "san francisco bay": "San Francisco-Oakland-Fremont CA MSA",
    "san francisco, california, united states": "San Francisco-Oakland-Fremont CA MSA",
    "san francisco, california": "San Francisco-Oakland-Fremont CA MSA",
    "san francisco ca": "San Francisco-Oakland-Fremont CA MSA",
    "new york, new york, united states": "New York-Northern New Jersey-Long Island NY-NJ-PA MSA",
    "new york city metropolitan area": "New York-Northern New Jersey-Long Island NY-NJ-PA MSA",
    "new york city metropolitan": "New York-Northern New Jersey-Long Island NY-NJ-PA MSA",
    "new york ny": "New York-Northern New Jersey-Long Island NY-NJ-PA MSA",
    "greater chicago area": "Chicago-Naperville-Joliet IL-IN-WI MSA",
    "chicago": "Chicago-Naperville-Joliet IL-IN-WI MSA",
    "chicago, illinois, united states": "Chicago-Naperville-Joliet IL-IN-WI MSA",
    "greater boston": "Boston-Cambridge-Quincy MA-NH MSA",
    "boston, massachusetts, united states": "Boston-Cambridge-Quincy MA-NH MSA",
    "dallas-fort worth metroplex": "Dallas-Fort Worth-Arlington TX MSA",
    "dallas, texas, united states": "Dallas-Fort Worth-Arlington TX MSA",
    "houston, texas, united states": "Houston-Sugar Land-Baytown TX MSA",
    "san jose, california, united states": "San Jose-Sunnyvale-Santa Clara CA MSA",
    "seattle, washington, united states": "Seattle-Tacoma-Bellevue WA MSA",
    "los angeles, california, united states": "Los Angeles-Long Beach-Santa Ana CA MSA",
    "san diego, california, united states": "San Diego-Carlsbad-San Marcos CA MSA",
    "austin, texas, united states": "Austin-Round Rock TX MSA",
    "atlanta, georgia, united states": "Atlanta-Sandy Springs-Marietta GA MSA",
    "charlotte, north carolina, united states": "Charlotte-Gastonia-Concord NC-SC MSA",
    "washington dc-baltimore area": "Washington-Arlington-Alexandria DC-VA-MD-WV MSA",
    "washington, district of columbia, united states": "Washington-Arlington-Alexandria DC-VA-MD-WV MSA",
    "greater minneapolis-st. paul area": "Minneapolis-St. Paul-Bloomington MN-WI MSA",
    "minneapolis, minnesota, united states": "Minneapolis-St. Paul-Bloomington MN-WI MSA",
    "st paul, minnesota, united states": "Minneapolis-St. Paul-Bloomington MN-WI MSA",
    "phoenix, arizona, united states": "Phoenix-Mesa-Scottsdale AZ MSA",
    "denver, colorado, united states": "Denver-Aurora CO MSA",
    "miami, florida, united states": "Miami-Fort Lauderdale-Pompano Beach FL MSA",
    "tampa bay": "Tampa-St. Petersburg-Clearwater FL MSA",
    "tampa, florida, united states": "Tampa-St. Petersburg-Clearwater FL MSA",
}


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[-/]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class MsaLookup:
    msa_to_cbsa: dict[str, str]
    normalized_msa: dict[str, str]

    @classmethod
    def from_file(cls, path: Path) -> "MsaLookup":
        df = pd.read_csv(path, usecols=["msa", "cbsacode"])
        df = df.dropna(subset=["cbsacode"])
        msa_to_cbsa = {row.msa: str(int(row.cbsacode)) for row in df.itertuples(index=False)}
        normalized = {_normalize(msa.replace(" msa", "")): msa for msa in msa_to_cbsa}
        return cls(msa_to_cbsa, normalized)

    def alias_to_cbsa(self, alias: str) -> Optional[str]:
        msa_name = ALIASES.get(alias)
        if msa_name is None:
            return None
        return self.msa_to_cbsa.get(msa_name)

    def match_city_state(self, city: str, state: str) -> Optional[str]:
        city_norm = _normalize(city)
        state_norm = _normalize(state)
        state_abbr = STATE_ABBR.get(state_norm)
        if state_abbr is None:
            return None

        candidates = []
        for norm_name, msa in self.normalized_msa.items():
            if city_norm in norm_name and state_abbr in msa:
                candidates.append(msa)

        if len(candidates) == 1:
            return self.msa_to_cbsa[candidates[0]]
        return None

    def fuzzy_match(self, loc_norm: str) -> Optional[str]:
        for norm_name, msa in self.normalized_msa.items():
            if norm_name == loc_norm:
                return self.msa_to_cbsa[msa]
            if loc_norm in norm_name:
                return self.msa_to_cbsa[msa]
        return None


def infer_cbsa(lookup: MsaLookup, location_raw: str) -> tuple[Optional[str], str]:
    """Return (cbsa, reason) for a given location string."""
    if not location_raw or pd.isna(location_raw):
        return None, "missing_user_location"

    loc_norm = _normalize(location_raw)

    alias_cbsa = lookup.alias_to_cbsa(loc_norm)
    if alias_cbsa:
        return alias_cbsa, "alias"
    if alias_cbsa is None and loc_norm in ALIASES and ALIASES[loc_norm] is None:
        return None, "alias_remote"

    parts = [p.strip() for p in location_raw.split(",")]
    if len(parts) >= 3 and parts[-1].strip().lower() == "united states":
        city = parts[0]
        state = parts[1]
        cbsa = lookup.match_city_state(city, state)
        if cbsa:
            return cbsa, "city_state"

    cbsa = lookup.fuzzy_match(loc_norm)
    if cbsa:
        return cbsa, "fuzzy_contains"

    return None, "unmatched"


def sample_spell_user_data(sample_rows: int) -> pd.DataFrame:
    spell_cols = ["user_id", "companyname", "msa", "location"]
    spells = pd.read_csv(
        SPELL_CSV,
        usecols=spell_cols,
        nrows=sample_rows,
    )
    mask = spells["msa"].fillna("").str.contains("empty", case=False) | spells["msa"].fillna("").str.contains("nonmetro", case=False)
    spells = spells.loc[mask].copy()
    spells["msa"] = spells["msa"].fillna("empty")
    return spells


def load_user_locations(user_ids: list[int]) -> pd.DataFrame:
    ids = set(user_ids)
    chunks = []
    reader = pd.read_csv(USER_LOC_CSV, usecols=["user_id", "location"], chunksize=500_000)
    for chunk in reader:
        sub = chunk[chunk["user_id"].isin(ids)]
        if not sub.empty:
            chunks.append(sub)
        ids -= set(sub["user_id"])
        if not ids:
            break
    if not chunks:
        return pd.DataFrame(columns=["user_id", "location"])
    return pd.concat(chunks, ignore_index=True)


def run_pipeline(sample_rows: int) -> None:
    print(f"Sampling first {sample_rows:,} rows from spell file…")
    spells = sample_spell_user_data(sample_rows)
    print(f"  → {len(spells):,} spells with empty/NONMETRO MSA in sample")

    print("Joining user-level locations…")
    user_locs = load_user_locations(spells["user_id"].tolist())
    merged = spells.merge(user_locs, on="user_id", how="left", suffixes=("_raw", "_user"))
    print(f"  → matched user locations for {merged['location_user'].notna().sum():,} spells")

    lookup = MsaLookup.from_file(ENRICH_MSA)

    results = merged.apply(
        lambda row: infer_cbsa(lookup, row["location_user"]),
        axis=1,
        result_type="expand",
    )
    merged["cbsa_recovered"] = results[0]
    merged["recovery_reason"] = results[1]

    summary = merged["recovery_reason"].value_counts(dropna=False).rename_axis("reason").reset_index(name="spells")
    print("\nRecovery reasons:")
    print(summary.to_string(index=False))

    total = len(merged)
    recovered = merged["cbsa_recovered"].notna().sum()
    print(f"\nRecovered CBSA for {recovered:,} of {total:,} spells ({recovered / total:.1%}).")

    print("\nExample recoveries:")
    examples = merged[merged["cbsa_recovered"].notna()].head(10)
    if not examples.empty:
        print(examples[["user_id", "location_user", "cbsa_recovered", "recovery_reason"]].to_string(index=False))
    else:
        print("No recoveries in sample — expand sample size or refine rules.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prototype location recovery pipeline")
    parser.add_argument("--sample", type=int, default=300_000, help="Rows to read from spell CSV (default: 300k)")
    args = parser.parse_args()

    if not SPELL_CSV.exists():
        raise FileNotFoundError(SPELL_CSV)
    if not USER_LOC_CSV.exists():
        raise FileNotFoundError(USER_LOC_CSV)
    if not ENRICH_MSA.exists():
        raise FileNotFoundError(ENRICH_MSA)

    run_pipeline(args.sample)


if __name__ == "__main__":
    main()
