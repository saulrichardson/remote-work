#!/usr/bin/env python3
"""
Extract postings with equity-related language from the large postings-description shards.

Context
-------
This repo contains two job-posting exports:
  1) `main/data/raw/vacancy/Postings_scoop.csv` (NO freeform descriptions)
  2) `main/data/raw/postings_description/*.csv` (HAS a `description` free-text field)

For equity compensation work, we want a deterministic, keyword-based candidate subset
that we can then ship to an LLM for deeper extraction (instrument type, vesting, etc.).
This script:
  - streams the shards with DuckDB (no full-file pandas load),
  - applies token-aware regex triggers over title + description,
  - keeps only rows with non-empty descriptions (so there is text to send),
  - exports a de-duplicated candidate set and an LLM-ready JSONL payload.

Commands
--------
  report : counts + diagnostics (no output files)
  export : write `equity_candidates.parquet` and optional `llm_inputs.jsonl`
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import duckdb

from src.py.project_paths import DATA_RAW, RESULTS_RAW


def default_input_glob() -> str:
    return str(DATA_RAW / "postings_description" / "*.csv")


def sql_quote_literal(value: str) -> str:
    """Return *value* as a single-quoted SQL literal for DuckDB."""
    # DuckDB string literals do not require escaping backslashes, and escaping them
    # changes the resulting pattern/path. This matters a lot for regex patterns:
    #   '\bequity\b'   -> word-boundary regex (desired)
    #   '\\bequity\\b' -> literal backslashes (will NOT match)
    return "'" + value.replace("'", "''") + "'"


def equity_patterns() -> Dict[str, str]:
    """Named token-aware regex patterns for candidate screening (lowercased text)."""
    # Avoid very noisy tokens like bare "stock" or "vest/vesting" (stocking shelves,
    # safety vest, etc.). Use higher-precision equity language.
    return {
        # Broad: "equity" (high recall; context disambiguated later)
        "equity_word": r"\bequity\b",
        # Instruments / plans
        "stock_options": r"\b(stock options?|stock-option(s)?)\b",
        "rsu": r"\b(rsus?|restricted stock units?)\b",
        "restricted_stock": r"\brestricted stock( units)?\b",
        "espp": r"\b(espp|employee stock purchase plan|employee stock purchase)\b",
        "esop": r"\b(esop|employee stock ownership plan)\b",
        "phantom_equity": r"\b(phantom stock|phantom equity)\b",
        "profit_interest": r"\bprofit interest(s)?\b",
        "carried_interest": r"\bcarried interest\b",
        # Compensation phrasing
        "equity_comp_phrase": r"\bequity (compensation|grant|grants|award|awards|incentive|incentives|package)\b",
        "option_grant": r"\boption grant(s)?\b",
        "stock_or_share_based_comp": r"\b(stock[- ]based compensation|share[- ]based compensation)\b",
        # Plan mechanics (often present in option-heavy postings)
        "409a": r"\b409a\b",
        "cap_table": r"\b(cap table|capitalization table|cap-table)\b",
        "exercise_or_strike_price": r"\b(exercise price|strike price)\b",
        "stock_appreciation_rights": r"\bstock appreciation rights?\b",
        # Ownership language (kept narrow to reduce “stakeholder” noise)
        "ownership_stake": r"\b(ownership stake|ownership interest|equity stake|stake in the company|company ownership)\b",
    }


def build_candidate_sql(*, input_glob: str) -> Tuple[str, List[str]]:
    """Return (candidate_sql, flag_names) where candidate_sql yields deduped candidates."""
    patterns = equity_patterns()
    flag_names: List[str] = []
    flag_exprs: List[str] = []

    for name, regex in patterns.items():
        regex_q = sql_quote_literal(regex)
        flag_name = f"hit_{name}"
        flag_names.append(flag_name)
        flag_exprs.append(f"(regexp_matches(desc_l, {regex_q}) OR regexp_matches(title_l, {regex_q})) AS {flag_name}")

    any_hit = " OR ".join(flag_names)
    input_q = sql_quote_literal(Path(input_glob).as_posix())

    sql = f"""
WITH source AS (
  SELECT
    job_id,
    company,
    company_cleaned,
    post_date,
    remove_date,
    title,
    title_cleaned,
    role_k150,
    role_k50,
    role_k7,
    status,
    salary,
    location,
    city,
    state,
    state_long,
    zip,
    county,
    latitude,
    longitude,
    region_state,
    industry,
    industry_cleaned,
    gvkey,
    factset_entity_id,
    description,
    replace(replace(lower(coalesce(description, '')), '\\r', ' '), '\\n', ' ') AS desc_l,
    replace(replace(lower(coalesce(title, '')), '\\r', ' '), '\\n', ' ') AS title_l
  FROM read_csv_auto({input_q}, SAMPLE_SIZE=-1)
),
flagged AS (
  SELECT
    *,
    (length(desc_l) > 0) AS has_description,
    {', '.join(flag_exprs)}
  FROM source
),
candidates AS (
  SELECT
    *,
    ({any_hit}) AS hit_any_equity,
    row_number() OVER (PARTITION BY job_id) AS rn
  FROM flagged
  WHERE (length(desc_l) > 0) AND ({any_hit})
)
SELECT
  job_id,
  company,
  company_cleaned,
  post_date,
  remove_date,
  title,
  title_cleaned,
  role_k150,
  role_k50,
  role_k7,
  status,
  salary,
  location,
  city,
  state,
  state_long,
  zip,
  county,
  latitude,
  longitude,
  region_state,
  industry,
  industry_cleaned,
  gvkey,
  factset_entity_id,
  description,
  {', '.join(flag_names)},
  hit_any_equity
FROM candidates
WHERE rn = 1
"""

    return sql, flag_names


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input-glob",
        default=default_input_glob(),
        help="Glob for postings_description shards (default: auto-detected).",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("report", help="Print counts and diagnostics (no output files).")
    pr.add_argument("--examples", type=int, default=10, help="Print N example rows (default: %(default)s).")

    pe = sub.add_parser("export", help="Export candidate set and optional JSONL payload.")
    pe.add_argument(
        "--out-dir",
        type=Path,
        default=RESULTS_RAW / "postings_description_equity",
        help="Directory for outputs (default: %(default)s).",
    )
    pe.add_argument("--max-rows", type=int, default=0, help="Optional row cap for testing (0=all).")
    pe.add_argument("--jsonl", action="store_true", help="Also write llm_inputs.jsonl (model-agnostic).")

    return p.parse_args()


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()

    tmpdir = os.getenv("DUCKDB_TMPDIR")
    if tmpdir:
        con.execute(f"SET temp_directory={sql_quote_literal(tmpdir)}")

    threads = os.getenv("DUCKDB_THREADS")
    if threads:
        con.execute(f"PRAGMA threads={int(threads)}")
    else:
        con.execute("PRAGMA threads=4")

    return con


def report(*, con: duckdb.DuckDBPyConnection, input_glob: str, examples: int) -> None:
    sql, flag_names = build_candidate_sql(input_glob=input_glob)

    # Materialize once so the expensive CSV scan + regex evaluation happens once.
    con.execute("DROP TABLE IF EXISTS candidates")
    print("Building candidate table (one-time scan)...")
    con.execute(f"CREATE TEMP TABLE candidates AS {sql}")

    (n_candidates,) = con.execute("SELECT count(*) FROM candidates").fetchone()
    n_candidates = int(n_candidates)

    # Validation: should never have empty descriptions nor hit_any_equity = 0.
    (n_empty_desc,) = con.execute(
        "SELECT count(*) FROM candidates WHERE length(coalesce(description,'')) = 0"
    ).fetchone()
    (n_hit_false,) = con.execute("SELECT count(*) FROM candidates WHERE NOT hit_any_equity").fetchone()

    print("Input glob:", input_glob)
    print(f"Equity candidates (dedup job_id; non-empty desc): {n_candidates:,}")
    print(f"Validation empty descriptions: {int(n_empty_desc):,} (expected 0)")
    print(f"Validation hit_any_equity=0 : {int(n_hit_false):,} (expected 0)")

    if n_candidates == 0:
        print("\nNo candidates matched. If this is unexpected, check:")
        print("  - input_glob points at the postings_description shards you expect")
        print("  - patterns in equity_patterns() (esp. regex escaping / word boundaries)")
        return

    # Flag counts within candidates
    per_flag_exprs = [f"sum(CASE WHEN {fn} THEN 1 ELSE 0 END) AS {fn}" for fn in flag_names]
    per_flag = con.execute(f"SELECT {', '.join(per_flag_exprs)} FROM candidates").fetchone()
    print("\nCandidate trigger counts (not mutually exclusive):")
    for name, val in zip(flag_names, per_flag):
        print(f"  {name:30s} {int(val or 0):,}")

    if examples > 0:
        rows = con.execute(
            f"""
SELECT
  job_id,
  company_cleaned,
  post_date,
  title,
  substr(replace(replace(description, '\\r',' '), '\\n',' '), 1, 220) AS desc_preview
FROM candidates
LIMIT {int(examples)}
"""
        ).fetchall()

        print("\nExamples:")
        for job_id, company_cleaned, post_date, title, desc_preview in rows:
            print(f"\n- job_id={job_id} company={company_cleaned} post_date={post_date}")
            print(f"  title: {title}")
            prev = (desc_preview or "").replace("\n", " ").strip()
            print(f"  desc:  {prev[:220]}")


def export(
    *,
    con: duckdb.DuckDBPyConnection,
    input_glob: str,
    out_dir: Path,
    max_rows: int,
    write_jsonl: bool,
) -> None:
    sql, flag_names = build_candidate_sql(input_glob=input_glob)
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = out_dir / "equity_candidates.parquet"
    meta_path = out_dir / "metadata.json"

    sql_to_write = sql
    if max_rows and max_rows > 0:
        sql_to_write = f"SELECT * FROM ({sql}) LIMIT {int(max_rows)}"

    print("Writing parquet:", parquet_path)
    con.execute(f"COPY ({sql_to_write}) TO {sql_quote_literal(parquet_path.as_posix())} (FORMAT 'parquet');")

    # Validation on written parquet (fast-ish)
    parquet_q = sql_quote_literal(parquet_path.as_posix())
    (n_written,) = con.execute(f"SELECT count(*) FROM parquet_scan({parquet_q})").fetchone()
    n_written = int(n_written)
    if n_written <= 0:
        raise RuntimeError("Export produced an empty parquet file; check input_glob and patterns.")

    (n_empty_desc,) = con.execute(
        f"SELECT count(*) FROM parquet_scan({parquet_q}) WHERE length(coalesce(description,'')) = 0"
    ).fetchone()
    (n_hit_false,) = con.execute(
        f"SELECT count(*) FROM parquet_scan({parquet_q}) WHERE NOT hit_any_equity"
    ).fetchone()

    print(f"Parquet rows           : {n_written:,}")
    print(f"Parquet empty desc rows: {int(n_empty_desc):,} (expected 0)")
    print(f"Parquet hit_any_equity=0 rows: {int(n_hit_false):,} (expected 0)")

    if write_jsonl:
        jsonl_path = out_dir / "llm_inputs.jsonl"
        print("Writing JSONL:", jsonl_path)

        cursor = con.execute(
            f"""
SELECT
  job_id,
  company_cleaned,
  post_date,
  title,
  description
FROM parquet_scan({parquet_q})
"""
        )

        with jsonl_path.open("w", encoding="utf-8") as f:
            chunk_size = 10_000
            while True:
                rows = cursor.fetchmany(chunk_size)
                if not rows:
                    break
                for job_id, company_cleaned, post_date, title, description in rows:
                    payload = {
                        "job_id": str(job_id),
                        "company_cleaned": company_cleaned,
                        "post_date": str(post_date) if post_date is not None else None,
                        "title": title,
                        "text": f"TITLE: {title}\n\nDESCRIPTION:\n{description}",
                    }
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")

        # Quick line count (streaming read)
        n_lines = 0
        with jsonl_path.open("r", encoding="utf-8") as f:
            for _ in f:
                n_lines += 1
        print(f"JSONL lines: {n_lines:,}")

    meta = {
        "input_glob": input_glob,
        "patterns": equity_patterns(),
        "flags": flag_names,
        "row_cap": int(max_rows),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote metadata:", meta_path)


def main() -> None:
    args = parse_args()
    con = _connect()
    try:
        if args.cmd == "report":
            report(con=con, input_glob=args.input_glob, examples=int(args.examples))
            return
        if args.cmd == "export":
            export(
                con=con,
                input_glob=args.input_glob,
                out_dir=args.out_dir,
                max_rows=int(args.max_rows),
                write_jsonl=bool(args.jsonl),
            )
            return
        raise RuntimeError(f"Unhandled cmd: {args.cmd}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
