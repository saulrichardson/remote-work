#!/usr/bin/env python3
"""
Create a user-level location lookup with CBSA assignments and coordinates.

Input
-----
    External raw `User_location.csv` export
    data/clean/gazetteer_cities.csv
    data/clean/cbsa_city_lookup.csv

Output
------
    data/clean/user_location_lookup.csv

The output includes columns:
    user_id, location_raw, country, state, city, cbsa, cbsa_title,
    latitude, longitude, is_remote, match_quality

The mapping logic proceeds in tiers:
    1. Alias lookup for common strings (e.g., "San Francisco Bay Area").
    2. Exact city+state match against CBSA principal cities.
    3. City+state geocoding via Gazetteer lat/lon and nearest CBSA
       principal city (within a configurable distance threshold).
    4. Residual classification as remote or unmatched.

Usage
-----
    python src/py/build_user_location_lookup.py --input /path/to/User_location.csv --sample 1000000
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import pandas as pd

from src.py.project_paths import DATA_CLEAN, DATA_RAW, ensure_dir, require_file

DEFAULT_INPUT = DATA_RAW / "User_location.csv"
GAZETTEER_CSV = DATA_CLEAN / "gazetteer_cities.csv"
CBSA_LOOKUP_CSV = DATA_CLEAN / "cbsa_city_lookup.csv"
DEFAULT_OUTPUT = DATA_CLEAN / "user_location_lookup.csv"

# Threshold (km) to accept nearest-CBSA assignment for non-principal cities.
NEAREST_CBSA_THRESHOLD_KM = 80.0

# Hard-coded alias map for frequent strings.
ALIASES: dict[str, Tuple[Optional[str], Optional[str]]] = {
    # alias -> (cbsa code, cbsa title). None cbsa -> remote classification.
    "san francisco bay area": ("41860", "San Francisco-Oakland-Berkeley, CA"),
    "san francisco bay": ("41860", "San Francisco-Oakland-Berkeley, CA"),
    "san francisco, california, united states": ("41860", "San Francisco-Oakland-Berkeley, CA"),
    "san francisco, california": ("41860", "San Francisco-Oakland-Berkeley, CA"),
    "san jose, california, united states": ("41940", "San Jose-Sunnyvale-Santa Clara, CA"),
    "new york city metropolitan area": ("35620", "New York-Newark-Jersey City, NY-NJ-PA"),
    "new york city metropolitan": ("35620", "New York-Newark-Jersey City, NY-NJ-PA"),
    "new york, new york, united states": ("35620", "New York-Newark-Jersey City, NY-NJ-PA"),
    "greater new york city area": ("35620", "New York-Newark-Jersey City, NY-NJ-PA"),
    "chicago, illinois, united states": ("16980", "Chicago-Naperville-Elgin, IL-IN-WI"),
    "greater chicago area": ("16980", "Chicago-Naperville-Elgin, IL-IN-WI"),
    "chicago": ("16980", "Chicago-Naperville-Elgin, IL-IN-WI"),
    "los angeles, california, united states": ("31080", "Los Angeles-Long Beach-Anaheim, CA"),
    "greater los angeles area": ("31080", "Los Angeles-Long Beach-Anaheim, CA"),
    "dallas-fort worth metroplex": ("19100", "Dallas-Fort Worth-Arlington, TX"),
    "dallas, texas, united states": ("19100", "Dallas-Fort Worth-Arlington, TX"),
    "houston, texas, united states": ("26420", "Houston-The Woodlands-Sugar Land, TX"),
    "seattle, washington, united states": ("42660", "Seattle-Tacoma-Bellevue, WA"),
    "greater seattle area": ("42660", "Seattle-Tacoma-Bellevue, WA"),
    "san diego, california, united states": ("41740", "San Diego-Chula Vista-Carlsbad, CA"),
    "boston, massachusetts, united states": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "greater boston": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "austin, texas, united states": ("12420", "Austin-Round Rock-Georgetown, TX"),
    "greater austin area": ("12420", "Austin-Round Rock-Georgetown, TX"),
    "washington, district of columbia, united states": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "washington dc-baltimore area": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "washington dc metro area": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "atlanta, georgia, united states": ("12060", "Atlanta-Sandy Springs-Alpharetta, GA"),
    "denver, colorado, united states": ("19740", "Denver-Aurora-Lakewood, CO"),
    "phoenix, arizona, united states": ("38060", "Phoenix-Mesa-Chandler, AZ"),
    "miami, florida, united states": ("33100", "Miami-Fort Lauderdale-Pompano Beach, FL"),
    "tampa bay": ("45300", "Tampa-St. Petersburg-Clearwater, FL"),
    "tampa, florida, united states": ("45300", "Tampa-St. Petersburg-Clearwater, FL"),
    "salt lake city, utah, united states": ("41620", "Salt Lake City-Murray, UT"),
    "brooklyn, new york, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "brooklyn, new york": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "queens, new york, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "queens, new york": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "queens county, new york, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "staten island, new york, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "bronx, new york, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "indianapolis, indiana, united states": ("26900", "Indianapolis-Carmel-Greenwood, IN"),
    "st louis, missouri, united states": ("41180", "St. Louis, MO-IL"),
    "saint louis, missouri, united states": ("41180", "St. Louis, MO-IL"),
    "nashville, tennessee, united states": ("34980", "Nashville-Davidson--Murfreesboro--Franklin, TN"),
    "st paul, minnesota, united states": ("33460", "Minneapolis-St. Paul-Bloomington, MN-WI"),
    "saint paul, minnesota, united states": ("33460", "Minneapolis-St. Paul-Bloomington, MN-WI"),
    "baltimore city county, maryland, united states": ("12580", "Baltimore-Columbia-Towson, MD"),
    "boise, idaho, united states": ("14260", "Boise City, ID"),
    "st petersburg, florida, united states": ("45300", "Tampa-St. Petersburg-Clearwater, FL"),
    "honolulu, hawaii, united states": ("26180", "Urban Honolulu, HI"),
    "honolulu county, hawaii, united states": ("26180", "Urban Honolulu, HI"),
    "port st lucie, florida, united states": ("38940", "Port St. Lucie, FL"),
    "lees summit, missouri, united states": ("28140", "Kansas City, MO-KS"),
    "st charles, missouri, united states": ("41180", "St. Louis, MO-IL"),
    "st cloud, minnesota, united states": ("41060", "St. Cloud, MN"),
    "norfolk city county, virginia, united states": ("47260", "Virginia Beach-Norfolk-Newport News, VA-NC"),
    "edison, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "greater philadelphia": ("37980", "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD"),
    "greater houston": ("26420", "Houston-The Woodlands-Sugar Land, TX"),
    "los angeles metropolitan area": ("31080", "Los Angeles-Long Beach-Anaheim, CA"),
    "los angeles metropolitan": ("31080", "Los Angeles-Long Beach-Anaheim, CA"),
    "atlanta metropolitan area": ("12060", "Atlanta-Sandy Springs-Alpharetta, GA"),
    "atlanta metropolitan": ("12060", "Atlanta-Sandy Springs-Alpharetta, GA"),
    "washington dc-baltimore": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "seattle": ("42660", "Seattle-Tacoma-Bellevue, WA"),
    "charlotte metro": ("16740", "Charlotte-Concord-Gastonia, NC-SC"),
    "greater minneapolis-st. paul area": ("33460", "Minneapolis-St. Paul-Bloomington, MN-WI"),
    "louisville, kentucky, united states": ("31140", "Louisville/Jefferson County, KY-IN"),
    "lexington, kentucky, united states": ("30460", "Lexington-Fayette, KY"),
    "littleton, colorado, united states": ("19740", "Denver-Aurora-Lakewood, CO"),
    "katy, texas, united states": ("26420", "Houston-The Woodlands-Sugar Land, TX"),
    "frisco, texas, united states": ("19100", "Dallas-Fort Worth-Arlington, TX"),
    "spring, texas, united states": ("26420", "Houston-The Woodlands-Sugar Land, TX"),
    "mckinney, texas, united states": ("19100", "Dallas-Fort Worth-Arlington, TX"),
    "garland, texas, united states": ("19100", "Dallas-Fort Worth-Arlington, TX"),
    "cypress, texas, united states": ("26420", "Houston-The Woodlands-Sugar Land, TX"),
    "hollywood, florida, united states": ("33100", "Miami-Fort Lauderdale-Pompano Beach, FL"),
    "lake worth, florida, united states": ("33100", "Miami-Fort Lauderdale-Pompano Beach, FL"),
    "newark, delaware, united states": ("37980", "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD"),
    "augusta, georgia, united states": ("12260", "Augusta-Richmond County, GA-SC"),
    "somerville, massachusetts, united states": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "suffolk county, massachusetts, united states": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "amherst, massachusetts, united states": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "lowell, massachusetts, united states": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "brookline, massachusetts, united states": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "stafford, virginia, united states": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "fairfax county, virginia, united states": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "woodbridge, virginia, united states": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "ashburn, virginia, united states": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "chesterfield, virginia, united states": ("40060", "Richmond, VA"),
    "new alexandria, virginia, united states": ("47900", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    "ventura, california, united states": ("37100", "Oxnard-Thousand Oaks-Ventura, CA"),
    "glendale, arizona, united states": ("38060", "Phoenix-Mesa-Chandler, AZ"),
    "peoria, arizona, united states": ("38060", "Phoenix-Mesa-Chandler, AZ"),
    "bothell, washington, united states": ("42660", "Seattle-Tacoma-Bellevue, WA"),
    "bridgewater, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "lawrenceville, georgia, united states": ("12060", "Atlanta-Sandy Springs-Alpharetta, GA"),
    "greenville-spartanburg-anderson, south carolina": ("24860", "Greenville-Anderson-Greer, SC"),
    "hawaii, united states": (None, None),
    "macon, georgia, united states": ("31420", "Macon-Bibb County, GA"),
    "cherry hill, new jersey, united states": ("37980", "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD"),
    "macomb township, michigan, united states": ("19820", "Detroit-Warren-Dearborn, MI"),
    "clinton township, michigan, united states": ("19820", "Detroit-Warren-Dearborn, MI"),
    "fort bragg, north carolina, united states": ("22180", "Fayetteville, NC"),
    "fort campbell north, kentucky, united states": ("17300", "Clarksville, TN-KY"),
    "ventura county, california, united states": ("37100", "Oxnard-Thousand Oaks-Ventura, CA"),
    "st cloud, florida, united states": ("36740", "Orlando-Kissimmee-Sanford, FL"),
    "fairfield, connecticut, united states": ("14860", "Bridgeport-Stamford-Norwalk, CT"),
    "hamden, connecticut, united states": ("35300", "New Haven-Milford, CT"),
    "st augustine, florida, united states": ("27260", "Jacksonville, FL"),
    "east brunswick, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "wayne, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "elk grove village, illinois, united states": ("16980", "Chicago-Naperville-Elgin, IL-IN-WI"),
    "natick, massachusetts, united states": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "shrewsbury, massachusetts, united states": ("14460", "Boston-Cambridge-Newton, MA-NH"),
    "northridge, california, united states": ("31080", "Los Angeles-Long Beach-Anaheim, CA"),
    "ponte vedra beach, florida, united states": ("27260", "Jacksonville, FL"),
    "west bloomfield township, michigan, united states": ("19820", "Detroit-Warren-Dearborn, MI"),
    "livingston, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "bloomfield, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "milford, connecticut, united states": ("35300", "New Haven-Milford, CT"),
    "stratford, connecticut, united states": ("14860", "Bridgeport-Stamford-Norwalk, CT"),
    "north bergen, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "henrico, virginia, united states": ("40060", "Richmond, VA"),
    "plainsboro, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "windsor mill, maryland, united states": ("12580", "Baltimore-Columbia-Towson, MD"),
    "montclair, new jersey, united states": ("35620", "New York-Newark-Jersey City, NY-NJ"),
    "lewis center, ohio, united states": ("18140", "Columbus, OH"),
    "st charles, illinois, united states": ("16980", "Chicago-Naperville-Elgin, IL-IN-WI"),
    "travis county, texas, united states": ("12420", "Austin-Round Rock-Georgetown, TX"),
    "tompkins county, new york, united states": ("27060", "Ithaca, NY"),
    "greater phoenix area": ("38060", "Phoenix-Mesa-Chandler, AZ"),
    "greater phoenix": ("38060", "Phoenix-Mesa-Chandler, AZ"),
    "phoenix metropolitan area": ("38060", "Phoenix-Mesa-Chandler, AZ"),
    "phoenix metro area": ("38060", "Phoenix-Mesa-Chandler, AZ"),
    "phoenix metro": ("38060", "Phoenix-Mesa-Chandler, AZ"),
    "massachusetts, united states": (None, None),
    "missouri, united states": (None, None),
    "ohio, united states": (None, None),
    "new york, united states": (None, None),
    "georgia, united states": (None, None),
    "puerto rico": (None, None),
    "united states": (None, None),
    "remote": (None, None),
    "worldwide": (None, None),
}

# Common suffixes to strip when normalising.
SUFFIX_PATTERNS = [
    r"\barea\b",
    r"\bregion\b",
    r"\bmetropolitan\b",
    r"\bmetro area\b",
    r"\bgreater\b",
    r"\bmetro\b",
    r"\bcounty\b",
]

STATE_NAME_TO_ABBR = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "washington, district of columbia": "DC",
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
    "puerto rico": "PR",
}


US_STATE_NAME_LOWER = set(STATE_NAME_TO_ABBR.keys())
US_STATE_ABBR_LOWER = {abbr.lower() for abbr in STATE_NAME_TO_ABBR.values()}

# Countries considered domestic.
US_NAMES = {
    "united states",
    "usa",
    "us",
    "u.s.",
    "u.s.a",
    "statele unite ale americii",
    "statelor unite ale americii",
    "estados unidos",
}

FOREIGN_US_PATTERNS = [
    r"\bstatele unite ale americii\b",
    r"\bstatelor unite ale americii\b",
    r"\bestados unidos\b",
    r"\bestados unidos de am[eé]rica\b",
    r"\betats-unis\b",
    r"\bunited states of america\b",
]

def strip_us_terms(text: str) -> str:
    for pattern in FOREIGN_US_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text

def standardize_city_name(name: Optional[str]) -> Optional[str]:
    if not isinstance(name, str):
        return None
    name = strip_us_terms(name)
    name = name.strip().lower()
    name = re.sub(r"\b(county|township|parish|village|municipality|borough|cdp|town)\b", "", name)
    name = re.sub(r"\bcity\b", "", name)
    name = name.replace("saint ", "st ")
    name = name.replace("santa fé", "santa fe")
    name = re.sub(r"\s+-\s+", "-", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip() or None


@dataclass
class GazetteerEntry:
    lat: float
    lon: float


@dataclass
class CbsaEntry:
    cbsa: str
    title: str
    state: str
    lat: float
    lon: float


def load_gazetteer(path: Path) -> tuple[dict[str, GazetteerEntry], dict[str, list[str]]]:
    df = pd.read_csv(path)
    df["city_norm"] = df["city_clean"].apply(standardize_city_name)
    df["state_norm"] = df["state"].str.lower()
    gaz_map: dict[str, GazetteerEntry] = {}
    city_to_states: dict[str, list[str]] = {}
    for row in df.itertuples(index=False):
        base = row.city_norm
        keys = {base}
        if base and base.endswith(" city"):
            keys.add(base[: -len(" city")])
        for key in keys:
            composite = f"{key}, {row.state_norm}"
            gaz_map[composite] = GazetteerEntry(lat=float(row.INTPTLAT), lon=float(row.INTPTLONG))
            city_to_states.setdefault(key, []).append(row.state.upper())
    return gaz_map, city_to_states


def load_cbsa_lookup(
    path: Path,
    gaz_map: dict[str, GazetteerEntry],
) -> tuple[dict[str, CbsaEntry], dict[str, list[CbsaEntry]], dict[str, CbsaEntry]]:
    df = pd.read_csv(path)
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    df["city_state_key"] = (df["principal_city_clean"].str.lower() + ", " + df["usps"].str.lower())

    direct: dict[str, CbsaEntry] = {}
    cbsa_by_state: dict[str, list[CbsaEntry]] = {}
    cbsa_primary: dict[str, CbsaEntry] = {}
    for row in df.itertuples(index=False):
        data = row._asdict()
        lat = data["intptlat"]
        lon = data["intptlong"]
        if pd.isna(lat) or pd.isna(lon):
            city_norm = standardize_city_name(data["principal_city_clean"])
            state_norm = str(data["usps"]).lower()
            gaz_entry = None
            if city_norm:
                key = f"{city_norm}, {state_norm}"
                gaz_entry = gaz_map.get(key)
                if not gaz_entry:
                    key = f"{city_norm} city, {state_norm}"
                    gaz_entry = gaz_map.get(key)
                if not gaz_entry:
                    key = f"{city_norm} city city, {state_norm}"
                    gaz_entry = gaz_map.get(key)
            if gaz_entry:
                lat, lon = gaz_entry.lat, gaz_entry.lon
        entry = CbsaEntry(
            cbsa=str(data["cbsa_code"]),
            title=data["cbsa_title"],
            state=str(data["usps"]).upper(),
            lat=float(lat) if not pd.isna(lat) else float("nan"),
            lon=float(lon) if not pd.isna(lon) else float("nan"),
        )
        direct[data["city_state_key"]] = entry
        cbsa_by_state.setdefault(data["usps"].upper(), []).append(entry)
        if not math.isnan(entry.lat) and not math.isnan(entry.lon):
            cbsa_primary.setdefault(entry.cbsa, entry)
    return direct, cbsa_by_state, cbsa_primary


def normalize(text: str) -> str:
    text = strip_us_terms(text)
    text = text.strip().lower()
    text = re.sub(r"[\\./]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def strip_suffixes(text: str) -> str:
    result = strip_us_terms(text)
    for pattern in SUFFIX_PATTERNS:
        result = re.sub(pattern, "", result).strip()
    return re.sub(r"\s+", " ", result).strip()


def haversine_km(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    # Convert to radians
    rlat1 = math.radians(lat1)
    rlon1 = math.radians(lon1)
    rlat2 = np.radians(lat2)
    rlon2 = np.radians(lon2)

    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = np.sin(dlat / 2) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    return 6371.0 * c


def alias_lookup(name_norm: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
    return ALIASES.get(name_norm)


def detect_remote(raw_norm: str) -> bool:
    if "remote" in raw_norm:
        return True
    if raw_norm in {"", "worldwide"}:
        return True
    if raw_norm in US_STATE_NAME_LOWER or raw_norm in US_STATE_ABBR_LOWER:
        return True
    return False


def parse_location(raw: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return (city, state_abbr, country_lower) for a raw location string.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None, None, None

    raw_norm = normalize(raw)
    parts = [p.strip() for p in raw_norm.split(",") if p.strip()]

    # Country detection
    country = None
    if parts and parts[-1] in US_NAMES:
        country = "united states"
        parts = parts[:-1]
    elif parts:
        tail = parts[-1]
        if tail in STATE_NAME_TO_ABBR:
            country = "united states"
        elif len(tail) == 2 and tail.isalpha():
            country = "united states"
        else:
            country = tail

    # Attempt to parse state
    state_abbr = None
    city = None

    if parts:
        last = parts[-1]
        if len(last) == 2 and last.isalpha():
            state_abbr = last.upper()
            city = ", ".join(parts[:-1]).strip() or None
        elif last in STATE_NAME_TO_ABBR:
            state_abbr = STATE_NAME_TO_ABBR[last]
            city = ", ".join(parts[:-1]).strip() or None
        elif len(parts) >= 2 and parts[-2] in STATE_NAME_TO_ABBR:
            state_abbr = STATE_NAME_TO_ABBR[parts[-2]]
            city = ", ".join(parts[:-2] + [parts[-1]]).strip() or None
        elif len(parts) >= 2 and parts[-2] == last:
            state_abbr = STATE_NAME_TO_ABBR.get(parts[-1], None)
            city = ", ".join(parts[:-2]).strip() or None
        elif len(parts) == 1:
            city = strip_suffixes(parts[0])
        else:
            city = strip_suffixes(parts[0])
    else:
        city = None

    if city:
        city = strip_suffixes(city)
    return city or None, state_abbr, country


class LocationMapper:
    def __init__(self, gaz_path: Path, cbsa_path: Path) -> None:
        self.gaz_map, self.city_to_states = load_gazetteer(gaz_path)
        self.cbsa_direct, self.cbsa_by_state, self.cbsa_primary = load_cbsa_lookup(cbsa_path, self.gaz_map)
        self.cache: dict[
            tuple[str, Optional[str], Optional[str], Optional[str]],
            tuple[Optional[str], Optional[str], Optional[str], Optional[float], Optional[float], str],
        ] = {}

    def resolve(
        self,
        raw: str,
        city: Optional[str],
        state_abbr: Optional[str],
        country: Optional[str],
    ) -> tuple[Optional[str], Optional[str], Optional[str], Optional[float], Optional[float], str]:
        """
        Return cbsa, cbsa_title, state, lat, lon, qualityFlag for a single location.
        """
        city_norm = standardize_city_name(city)
        cache_key = (raw, city_norm, state_abbr, country)
        if cache_key in self.cache:
            return self.cache[cache_key]

        if not isinstance(raw, str) or not raw.strip():
            result = (None, None, state_abbr, None, None, "missing")
            self.cache[cache_key] = result
            return result

        raw_norm = normalize(raw)
        if detect_remote(raw_norm):
            result = (None, None, state_abbr, None, None, "remote_keyword")
            self.cache[cache_key] = result
            return result

        alias_match = alias_lookup(raw_norm)
        if alias_match is not None:
            cbsa_code, cbsa_title = alias_match
            state = None
            lat = lon = None
            if cbsa_code:
                entry = self.cbsa_primary.get(cbsa_code)
                if entry:
                    state = entry.state
                    lat = entry.lat if not math.isnan(entry.lat) else None
                    lon = entry.lon if not math.isnan(entry.lon) else None
                if state is None:
                    # Attempt to infer state from CBSA title (last token)
                    title_parts = cbsa_title.split(",")
                    if title_parts:
                        state = title_parts[-1].strip().split("-")[0].upper()
            result = (cbsa_code, cbsa_title, state or state_abbr, lat, lon, "alias")
            self.cache[cache_key] = result
            return result

        if country and country not in US_NAMES and (state_abbr is None or state_abbr not in self.cbsa_by_state):
            result = (None, None, state_abbr, None, None, "non_us")
            self.cache[cache_key] = result
            return result

        state_abbr_upper = state_abbr.upper() if state_abbr else None

        if city_norm is None and state_abbr_upper and (country in US_NAMES or country is None):
            result = (None, None, state_abbr_upper, None, None, "state_only")
            self.cache[cache_key] = result
            return result

        if city_norm and state_abbr_upper:
            state_key = state_abbr_upper.lower()
            key = f"{city_norm}, {state_key}"
            # Tier 1: direct CBSA principal city match
            if key in self.cbsa_direct:
                entry = self.cbsa_direct[key]
                result = (entry.cbsa, entry.title, state_abbr_upper, entry.lat, entry.lon, "principal_city")
                self.cache[cache_key] = result
                return result

            if "-" in city_norm:
                for part in city_norm.split("-"):
                    part = part.strip()
                    if not part:
                        continue
                    key_part = f"{part}, {state_key}"
                    if key_part in self.cbsa_direct:
                        entry = self.cbsa_direct[key_part]
                        result = (entry.cbsa, entry.title, state_abbr_upper, entry.lat, entry.lon, "principal_city")
                        self.cache[cache_key] = result
                        return result

            # Tier 2: Gazetteer geocode + nearest CBSA in state
            gaz_entry = self.gaz_map.get(key)
            if gaz_entry:
                cbsa_entry, reason = self._nearest_cbsa(state_abbr_upper, gaz_entry.lat, gaz_entry.lon)
                if cbsa_entry:
                    result = (
                        cbsa_entry.cbsa,
                        cbsa_entry.title,
                        state_abbr_upper,
                        gaz_entry.lat,
                        gaz_entry.lon,
                        reason,
                    )
                    self.cache[cache_key] = result
                    return result

            # Tier 3: consider all states that city appears in (ambiguity resolution)
            possible_states = self.city_to_states.get(city_norm, [])
            for other_state in possible_states:
                key_alt = f"{city_norm}, {other_state.lower()}"
                if key_alt in self.cbsa_direct:
                    entry = self.cbsa_direct[key_alt]
                    result = (entry.cbsa, entry.title, other_state, entry.lat, entry.lon, "principal_city_altstate")
                    self.cache[cache_key] = result
                    return result

        elif city_norm and not state_abbr_upper:
            # Attempt to infer state when unique city name in gazetteer
            possible_states = self.city_to_states.get(city_norm, [])
            if len(possible_states) == 1:
                state_guess = possible_states[0]
                key = f"{city_norm}, {state_guess.lower()}"
                if key in self.cbsa_direct:
                    entry = self.cbsa_direct[key]
                    result = (entry.cbsa, entry.title, state_guess, entry.lat, entry.lon, "principal_city_state_guess")
                    self.cache[cache_key] = result
                    return result
                gaz_entry = self.gaz_map.get(key)
                if gaz_entry:
                    cbsa_entry, reason = self._nearest_cbsa(state_guess, gaz_entry.lat, gaz_entry.lon)
                    if cbsa_entry:
                        result = (cbsa_entry.cbsa, cbsa_entry.title, state_guess, gaz_entry.lat, gaz_entry.lon, reason)
                        self.cache[cache_key] = result
                        return result

        result = (None, None, state_abbr_upper, None, None, "unmatched")
        self.cache[cache_key] = result
        return result

    def _nearest_cbsa(self, state: str, lat: float, lon: float) -> tuple[Optional[CbsaEntry], str]:
        candidates = [c for c in self.cbsa_by_state.get(state, []) if not math.isnan(c.lat) and not math.isnan(c.lon)]
        if candidates:
            lat_arr = np.array([c.lat for c in candidates])
            lon_arr = np.array([c.lon for c in candidates])
            dists = haversine_km(lat, lon, lat_arr, lon_arr)
            idx = int(np.argmin(dists))
            if dists[idx] <= NEAREST_CBSA_THRESHOLD_KM:
                return candidates[idx], "nearest_cbsa_state"

        # fall back to nationwide nearest to catch cross-state metros
        all_candidates: list[CbsaEntry] = [c for v in self.cbsa_by_state.values() for c in v if not math.isnan(c.lat) and not math.isnan(c.lon)]
        lat_arr = np.array([c.lat for c in all_candidates])
        lon_arr = np.array([c.lon for c in all_candidates])
        dists = haversine_km(lat, lon, lat_arr, lon_arr)
        idx = int(np.argmin(dists))
        if dists[idx] <= NEAREST_CBSA_THRESHOLD_KM:
            return all_candidates[idx], "nearest_cbsa_cross_state"
        return None, "no_cbsa_within_threshold"


def process_chunk(
    mapper: LocationMapper,
    df: pd.DataFrame,
) -> pd.DataFrame:
    parsed = df["location"].apply(parse_location)
    parsed_cols = ["city", "state_parsed", "country"]
    parsed_df = pd.DataFrame(parsed.tolist(), columns=parsed_cols, index=df.index)

    results = [
        mapper.resolve(raw, city, state, country)
        for raw, city, state, country in zip(df["location"], parsed_df["city"], parsed_df["state_parsed"], parsed_df["country"])
    ]
    cols = ["cbsa", "cbsa_title", "state_assigned", "latitude", "longitude", "match_quality"]
    mapped = pd.DataFrame(results, columns=cols, index=df.index)
    df_out = pd.concat([df, parsed_df, mapped], axis=1)
    remote_flags = {"remote_keyword", "state_only", "non_us", "missing"}
    df_out["is_remote"] = df_out["match_quality"].isin(remote_flags) | df_out["cbsa"].isna()
    df_out.rename(columns={"location": "location_raw"}, inplace=True)
    return df_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build user location lookup with CBSA codes.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to User_location.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Destination file (CSV or parquet)")
    parser.add_argument("--sample", type=int, help="Limit to first N rows for testing")
    parser.add_argument("--chunk-size", type=int, default=500_000, help="Rows per chunk when streaming")
    parser.add_argument("--stats-output", type=Path, help="Optional CSV to store summary stats by match quality")
    args = parser.parse_args()

    require_file(args.input, nonempty=True, purpose="external raw User_location export")
    require_file(GAZETTEER_CSV, nonempty=True, purpose="gazetteer city lookup")
    require_file(CBSA_LOOKUP_CSV, nonempty=True, purpose="CBSA city lookup")
    ensure_dir(args.output.parent)

    mapper = LocationMapper(GAZETTEER_CSV, CBSA_LOOKUP_CSV)
    chunks: list[pd.DataFrame] = []
    reader = pd.read_csv(
        args.input,
        nrows=args.sample,
        chunksize=args.chunk_size,
        usecols=["user_id", "location"],
    )

    total_rows = 0
    for chunk in reader:
        total_rows += len(chunk)
        mapped_chunk = process_chunk(mapper, chunk)
        chunks.append(mapped_chunk)
        print(f"Processed {total_rows:,} rows…")

    if not chunks:
        print("No data processed; exiting.")
        return

    full = pd.concat(chunks, ignore_index=True)

    if args.output.suffix.lower() == ".parquet":
        try:
            full.to_parquet(args.output, index=False)
        except ImportError:
            alt_path = args.output.with_suffix(".csv")
            full.to_csv(alt_path, index=False)
            print(
                f"pyarrow/fastparquet not available; wrote {len(full):,} rows to CSV fallback "
                f"{alt_path} (requested parquet at {args.output})."
            )
        else:
            print(f"Wrote {len(full):,} rows to {args.output}")
    else:
        full.to_csv(args.output, index=False)
        print(f"Wrote {len(full):,} rows to {args.output}")

    summary = full["match_quality"].value_counts(dropna=False).rename_axis("match_quality").reset_index(name="rows")
    summary["share"] = summary["rows"] / len(full)
    print("\nMatch quality summary:")
    print(summary.to_string(index=False))

    if args.stats_output:
        ensure_dir(args.stats_output.parent)
        summary.to_csv(args.stats_output, index=False)
        print(f"Saved summary stats to {args.stats_output}")


if __name__ == "__main__":
    main()
