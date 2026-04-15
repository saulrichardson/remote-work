#!/usr/bin/env python3
"""
Extract Data Axle sales fields for the Scoop firm universe via a name-merge.

This script is intentionally conservative:
  - It starts with a *deterministic* name normalization + exact match on
    (normalized company name, state).
  - It writes a row-level match file (for audit / manual QA), plus a
    company×year aggregated file for analysis.

Why this shape:
  - The full Data Axle files are huge; we avoid loading them fully.
  - "Name-merge" is ambiguous; preserving row-level candidates is the safest
    first pass before adding fuzzy matching.

Inputs (external):
  - Data Axle zip files like US_bus_2018.zip, US_bus_2019.zip, ...

Inputs (repo):
  - data/raw/Scoop_clean_public.dta (companyname, hqcity, hqstate)

Outputs (repo):
  - data/clean/data_axle_matches.csv.gz
  - data/clean/data_axle_sales_company_year.csv
"""

from __future__ import annotations

import argparse
import csv
import gzip
import re
import subprocess
from shutil import which
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd

from src.py.project_paths import DATA_CLEAN, DATA_RAW, ensure_dir


DEFAULT_DATA_AXLE_DIR = Path(
    "/Users/saulrichardson/Dropbox/Remote Work Startups/New/Data/Data Axle"
)

SUFFIX_TOKENS = {
    "INC",
    "INCORPORATED",
    "LLC",
    "L L C",
    "LTD",
    "LIMITED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "LP",
    "L P",
    "LLP",
    "L L P",
    "PLC",
    "P L C",
    "PC",
    "P C",
}


@dataclass(frozen=True)
class FirmKey:
    companyname: str
    hqcity: str
    hqstate: str
    name_norm: str
    city_norm: str


@dataclass(frozen=True)
class DataAxleSource:
    year: int
    kind: str  # "zip" | "gz"
    path: Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("Extract Data Axle sales via name merge")
    p.add_argument(
        "--data-axle-dir",
        type=str,
        default=str(DEFAULT_DATA_AXLE_DIR),
        help="Directory containing Data Axle zip files (US_bus_*.zip).",
    )
    p.add_argument(
        "--firm-source",
        type=str,
        default=str(DATA_RAW / "Scoop_clean_public.dta"),
        help="Firm universe with companyname + HQ city/state (Stata DTA).",
    )
    p.add_argument(
        "--out-matches",
        type=str,
        default=str(DATA_CLEAN / "data_axle_matches.csv.gz"),
        help="Row-level match output (gzipped CSV).",
    )
    p.add_argument(
        "--out-agg",
        type=str,
        default=str(DATA_CLEAN / "data_axle_sales_company_year.csv"),
        help="Company×year aggregated output (CSV).",
    )
    p.add_argument(
        "--out-agg-dta",
        type=str,
        default=str(DATA_CLEAN / "data_axle_sales_company_year.dta"),
        help="Company×year aggregated output (Stata DTA).",
    )
    p.add_argument(
        "--years",
        type=str,
        default="",
        help="Comma-separated years to process (e.g., 2018,2019). Default: all found.",
    )
    p.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Stop after this many Data Axle rows per inner file (debug).",
    )
    return p.parse_args()


def _norm_whitespace(text: str) -> str:
    return re.sub(r"\\s+", " ", text).strip()


def normalize_company_name(raw: str) -> str:
    if raw is None:
        return ""
    s = raw.upper()
    s = s.replace("&", " AND ")
    # Keep alphanumerics, turn everything else into spaces
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    s = _norm_whitespace(s)
    if not s:
        return ""

    tokens = s.split(" ")
    # Drop leading "THE"
    if tokens and tokens[0] == "THE":
        tokens = tokens[1:]

    # Drop trailing corporate suffix tokens (repeat until stable)
    # Also handle two-token suffixes like "L L C" by checking joined tail.
    changed = True
    while changed and tokens:
        changed = False
        if tokens and tokens[-1] in SUFFIX_TOKENS:
            tokens = tokens[:-1]
            changed = True
            continue
        if len(tokens) >= 3 and " ".join(tokens[-3:]) in SUFFIX_TOKENS:
            tokens = tokens[:-3]
            changed = True
            continue
        if len(tokens) >= 2 and " ".join(tokens[-2:]) in SUFFIX_TOKENS:
            tokens = tokens[:-2]
            changed = True
            continue

    return " ".join(tokens).strip()


def normalize_city(raw: str) -> str:
    if raw is None:
        return ""
    s = raw.upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return _norm_whitespace(s)


def _list_zip_members(zip_path: Path) -> list[str]:
    # Data Axle zip files are inconsistent across years:
    # - Some years (e.g., 2017) use LZMA, which `unzip` may not be able to stream.
    # - Some years (e.g., 2021) use deflate64, which `bsdtar` can't extract.
    #
    # Listing tends to work with both; we try bsdtar first, then unzip.
    if which("bsdtar") is not None:
        proc = subprocess.run(
            ["bsdtar", "-tf", str(zip_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    if which("unzip") is None:
        raise RuntimeError(
            "Missing required system dependency: `unzip`.\n"
            "On macOS this should ship with the OS; otherwise install InfoZip.\n"
            f"Needed to list members of: {zip_path}"
        )

    proc = subprocess.run(
        ["unzip", "-Z1", str(zip_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Unable to list zip members for: {zip_path}\n"
            f"unzip stderr:\n{proc.stderr}"
        )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _iter_zip_csv_rows(zip_path: Path, member: str) -> Iterator[list[str]]:
    def _popen(cmd: list[str]) -> subprocess.Popen[str]:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        return proc

    backends: list[tuple[str, list[str]]] = []
    if which("bsdtar") is not None:
        backends.append(("bsdtar", ["bsdtar", "-xOf", str(zip_path), member]))
    if which("unzip") is not None:
        backends.append(("unzip", ["unzip", "-p", str(zip_path), member]))

    if not backends:
        raise RuntimeError(
            "Missing required system dependencies to read Data Axle zip files.\n"
            "Need at least one of: `bsdtar` or `unzip`."
        )

    errors: list[str] = []
    for backend, cmd in backends:
        proc = _popen(cmd)
        reader = csv.reader(proc.stdout)
        try:
            first = next(reader)
        except StopIteration:
            stderr = proc.stderr.read() if proc.stderr is not None else ""
            rc = proc.wait()
            if rc == 0:
                return
            errors.append(f"{backend} rc={rc} stderr={stderr.strip()}")
            continue

        # Backend produced data; commit to it (don't silently fall back mid-stream).
        yield first
        for row in reader:
            yield row

        stderr = proc.stderr.read() if proc.stderr is not None else ""
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(
                f"{backend} failed extracting {member} from {zip_path} (rc={rc}).\nSTDERR:\n{stderr}"
            )
        return

    raise RuntimeError(
        f"Unable to extract {member} from {zip_path} using available backends.\n"
        + "\n".join(errors)
    )


def _coerce_float(x: str) -> float | None:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _get_col(header_map: dict[str, int], *names: str) -> int | None:
    for name in names:
        key = name.upper()
        if key in header_map:
            return header_map[key]
    return None


def _extract_fields(header: list[str]) -> dict[str, int | None]:
    cols = [h.strip().upper() for h in header]
    header_map = {c: i for i, c in enumerate(cols)}

    return {
        "company": _get_col(header_map, "COMPANY"),
        "city": _get_col(header_map, "CITY"),
        "state": _get_col(header_map, "STATE"),
        "zip": _get_col(header_map, "ZIPCODE", "ZIPCODE ", "ZIPCODE  "),
        "sales_loc": _get_col(header_map, "SALES VOLUME (9) - LOCATION"),
        "sales_corp": _get_col(header_map, "SALES VOLUME (9) - CORPORATE"),
        "parent_actual_sales": _get_col(header_map, "PARENT ACTUAL SALES VOLUME"),
        "location_sales_code": _get_col(header_map, "LOCATION SALES VOLUME CODE"),
        "parent_sales_code": _get_col(header_map, "PARENT SALES VOLUME CODE"),
        "naics_primary": _get_col(header_map, "PRIMARY NAICS CODE"),
        "sic_primary": _get_col(header_map, "PRIMARY SIC CODE"),
        "abi": _get_col(header_map, "ABI"),
        "parent_number": _get_col(header_map, "PARENT NUMBER"),
        "subsidiary_number": _get_col(header_map, "SUBSIDIARY NUMBER"),
        "address1": _get_col(header_map, "ADDRESS LINE 1"),
    }


def _safe_get(row: list[str], idx: int | None) -> str:
    if idx is None:
        return ""
    if idx < 0 or idx >= len(row):
        return ""
    return row[idx].strip()


def _load_firm_keys(path: Path) -> list[FirmKey]:
    df = pd.read_stata(path, convert_categoricals=False)
    required = {"companyname", "hqcity", "hqstate"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Firm source missing columns {sorted(missing)}: {path}")

    keys: list[FirmKey] = []
    for _, r in df.iterrows():
        company = str(r["companyname"]).strip()
        hqcity = str(r["hqcity"]).strip()
        hqstate = str(r["hqstate"]).strip()
        if not company or not hqstate:
            continue
        name_norm = normalize_company_name(company)
        if not name_norm:
            continue
        keys.append(
            FirmKey(
                companyname=company,
                hqcity=hqcity,
                hqstate=hqstate,
                name_norm=name_norm,
                city_norm=normalize_city(hqcity),
            )
        )
    return keys

def _discover_data_axle_sources(data_axle_dir: Path) -> dict[int, list[DataAxleSource]]:
    out: dict[int, list[DataAxleSource]] = defaultdict(list)

    # Most years ship as US_bus_YYYY.zip.
    for p in sorted(data_axle_dir.glob("US_bus_*.zip")):
        m = re.search(r"US_bus_(\d{4})\.zip$", p.name)
        if not m:
            continue
        year = int(m.group(1))
        out[year].append(DataAxleSource(year=year, kind="zip", path=p))

    # Some years are provided as a single gzipped text file (e.g., 2020).
    for p in sorted(data_axle_dir.glob("*.txt.gz")):
        m = re.search(r"(\d{4})_Business_.*\.(csv|txt)\.gz$", p.name, flags=re.IGNORECASE)
        if not m:
            continue
        year = int(m.group(1))
        out[year].append(DataAxleSource(year=year, kind="gz", path=p))

    return dict(out)


def _iter_gz_csv_rows(gz_path: Path) -> Iterator[list[str]]:
    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            yield row


def main() -> None:  # noqa: C901
    ns = _parse_args()

    data_axle_dir = Path(ns.data_axle_dir).expanduser().resolve()
    if not data_axle_dir.exists():
        raise SystemExit(f"Data Axle dir not found: {data_axle_dir}")

    firm_source = Path(ns.firm_source).expanduser().resolve()
    if not firm_source.exists():
        raise SystemExit(f"Firm source not found: {firm_source}")

    out_matches = Path(ns.out_matches).expanduser().resolve()
    out_agg = Path(ns.out_agg).expanduser().resolve()
    out_agg_dta = Path(ns.out_agg_dta).expanduser().resolve()
    ensure_dir(out_matches.parent)
    ensure_dir(out_agg.parent)
    ensure_dir(out_agg_dta.parent)

    years_filter: set[int] | None = None
    if ns.years.strip():
        years_filter = {int(y.strip()) for y in ns.years.split(",") if y.strip()}

    firms = _load_firm_keys(firm_source)
    if not firms:
        raise SystemExit(f"No firms loaded from {firm_source}")

    # Lookup: (name_norm, state) -> list[FirmKey]
    firm_lookup: dict[tuple[str, str], list[FirmKey]] = defaultdict(list)
    for f in firms:
        firm_lookup[(f.name_norm, f.hqstate.upper())].append(f)

    sources = _discover_data_axle_sources(data_axle_dir)
    if years_filter is not None:
        sources = {y: srcs for y, srcs in sources.items() if y in years_filter}

    if not sources:
        raise SystemExit(
            "No Data Axle files found.\n"
            f"Expected at least one of:\n"
            f"  - {data_axle_dir}/US_bus_*.zip\n"
            f"  - {data_axle_dir}/<year>_Business_*.txt.gz"
        )

    # Aggregation stats per company×year
    agg = defaultdict(
        lambda: {
            "n_rows": 0,
            "n_city_match": 0,
            "sales_loc_sum": 0.0,
            "sales_loc_max": None,
            "sales_corp_max": None,
            "parent_sales_max": None,
        }
    )

    match_header = [
        "companyname",
        "hqcity",
        "hqstate",
        "year",
        "match_key",
        "city_match",
        "data_axle_company",
        "data_axle_city",
        "data_axle_state",
        "data_axle_zip",
        "sales_loc",
        "sales_corp",
        "parent_actual_sales",
        "location_sales_code",
        "parent_sales_code",
        "naics_primary",
        "sic_primary",
        "abi",
        "parent_number",
        "subsidiary_number",
        "address1",
        "zip_member",
    ]

    with gzip.open(out_matches, "wt", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=match_header)
        writer.writeheader()

        for year, year_sources in sorted(sources.items()):
            for src in year_sources:
                if src.kind == "zip":
                    members = _list_zip_members(src.path)
                    if not members:
                        raise RuntimeError(f"No members found in zip: {src.path}")
                    source_members = [(m, _iter_zip_csv_rows(src.path, m)) for m in members]
                elif src.kind == "gz":
                    source_members = [(src.path.name, _iter_gz_csv_rows(src.path))]
                else:
                    raise RuntimeError(f"Unknown Data Axle source kind={src.kind!r} path={src.path}")

                for member, rows in source_members:
                    try:
                        header = next(rows)
                    except StopIteration:
                        continue

                    fields = _extract_fields(header)
                    if fields["company"] is None or fields["state"] is None:
                        raise RuntimeError(
                            f"Required columns missing in {src.path}::{member}. "
                            f"Have header: {header[:20]}..."
                        )

                    processed_rows = 0
                    for row in rows:
                        processed_rows += 1
                        if ns.max_rows and processed_rows > ns.max_rows:
                            break

                        company = _safe_get(row, fields["company"])
                        state = _safe_get(row, fields["state"]).upper()
                        if not company or not state:
                            continue

                        name_norm = normalize_company_name(company)
                        if not name_norm:
                            continue

                        key = (name_norm, state)
                        candidates = firm_lookup.get(key)
                        if not candidates:
                            continue

                        city = _safe_get(row, fields["city"])
                        zip_code = _safe_get(row, fields["zip"])
                        city_norm = normalize_city(city)

                        sales_loc = _coerce_float(_safe_get(row, fields["sales_loc"]))
                        sales_corp = _coerce_float(_safe_get(row, fields["sales_corp"]))
                        parent_sales = _coerce_float(
                            _safe_get(row, fields["parent_actual_sales"])
                        )

                        for firm in candidates:
                            city_match = int(
                                bool(firm.city_norm and city_norm and firm.city_norm == city_norm)
                            )

                            writer.writerow(
                                {
                                    "companyname": firm.companyname,
                                    "hqcity": firm.hqcity,
                                    "hqstate": firm.hqstate,
                                    "year": year,
                                    "match_key": "name_norm+state",
                                    "city_match": city_match,
                                    "data_axle_company": company,
                                    "data_axle_city": city,
                                    "data_axle_state": state,
                                    "data_axle_zip": zip_code,
                                    "sales_loc": sales_loc if sales_loc is not None else "",
                                    "sales_corp": sales_corp if sales_corp is not None else "",
                                    "parent_actual_sales": parent_sales if parent_sales is not None else "",
                                    "location_sales_code": _safe_get(
                                        row, fields["location_sales_code"]
                                    ),
                                    "parent_sales_code": _safe_get(row, fields["parent_sales_code"]),
                                    "naics_primary": _safe_get(row, fields["naics_primary"]),
                                    "sic_primary": _safe_get(row, fields["sic_primary"]),
                                    "abi": _safe_get(row, fields["abi"]),
                                    "parent_number": _safe_get(row, fields["parent_number"]),
                                    "subsidiary_number": _safe_get(row, fields["subsidiary_number"]),
                                    "address1": _safe_get(row, fields["address1"]),
                                    "zip_member": member,
                                }
                            )

                            a = agg[(firm.companyname, year)]
                            a["n_rows"] += 1
                            a["n_city_match"] += city_match

                            if sales_loc is not None:
                                a["sales_loc_sum"] += sales_loc
                                a["sales_loc_max"] = (
                                    sales_loc
                                    if a["sales_loc_max"] is None
                                    else max(a["sales_loc_max"], sales_loc)
                                )
                            if sales_corp is not None:
                                a["sales_corp_max"] = (
                                    sales_corp
                                    if a["sales_corp_max"] is None
                                    else max(a["sales_corp_max"], sales_corp)
                                )
                            if parent_sales is not None:
                                a["parent_sales_max"] = (
                                    parent_sales
                                    if a["parent_sales_max"] is None
                                    else max(a["parent_sales_max"], parent_sales)
                                )

    # Write aggregation --------------------------------------------------
    agg_rows: list[dict[str, object]] = []
    for (companyname, year), a in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        agg_rows.append(
            {
                "companyname": companyname,
                "year": year,
                "n_rows": a["n_rows"],
                "n_city_match": a["n_city_match"],
                "sales_loc_sum": a["sales_loc_sum"] if a["n_rows"] else None,
                "sales_loc_max": a["sales_loc_max"],
                "sales_corp_max": a["sales_corp_max"],
                "parent_sales_max": a["parent_sales_max"],
            }
        )

    agg_cols = [
        "companyname",
        "year",
        "n_rows",
        "n_city_match",
        "sales_loc_sum",
        "sales_loc_max",
        "sales_corp_max",
        "parent_sales_max",
    ]
    agg_df = pd.DataFrame(agg_rows, columns=agg_cols)

    # Ensure numeric columns are Stata-exportable even if they are all missing
    # for a given set of years/files (e.g., some years omit corporate sales).
    for col in ["sales_loc_sum", "sales_loc_max", "sales_corp_max", "parent_sales_max"]:
        agg_df[col] = pd.to_numeric(agg_df[col], errors="coerce")

    agg_df.to_csv(out_agg, index=False)
    agg_df.to_stata(out_agg_dta, write_index=False)

    matched_firms = {company for (company, _) in agg.keys()}
    matched_firms_by_year: dict[int, set[str]] = defaultdict(set)
    for company, year in agg.keys():
        matched_firms_by_year[year].add(company)

    print(f"Wrote row matches: {out_matches}")
    print(f"Wrote aggregates : {out_agg}")
    print(f"Wrote aggregates : {out_agg_dta}")
    print(f"Matched firms    : {len(matched_firms)} / {len(firms)} (any year)")
    print(f"Matched firm-years: {len(agg_rows)}")
    if matched_firms_by_year:
        print("Matched firms by year:")
        for year in sorted(matched_firms_by_year):
            print(f"  - {year}: {len(matched_firms_by_year[year])}")


if __name__ == "__main__":
    main()
