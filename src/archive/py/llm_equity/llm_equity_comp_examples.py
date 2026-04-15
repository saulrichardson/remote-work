#!/usr/bin/env python3
"""
Generate a small, working end-to-end example of equity-compensation extraction using an LLM.

What this does
--------------
- Samples a handful of postings from:
    main/results/raw/postings_description_equity/equity_candidates.parquet
- Sends each posting (title + description) to OpenAI via the Responses API
- Forces a strict JSON output schema (Structured Outputs)
- Writes a compact bundle you can inspect/share:
    - prompt_system.txt
    - prompt_user_template.txt
    - sample_inputs.jsonl
    - sample_outputs.jsonl

Notes
-----
- This script intentionally does NOT optimize for token count; it aims for clarity and
  robust downstream regression features.
- For security, prefer setting OPENAI_API_KEY in your environment.
  If not set, this script can *optionally* load a key from a local config file path
  (explicitly enabled via --allow-local-key-fallback).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import duckdb
from openai import OpenAI


DEFAULT_MODEL = "gpt-5-nano"


@dataclass(frozen=True)
class SampleRow:
    job_id: str
    company_cleaned: Optional[str]
    post_date: Optional[str]
    title: Optional[str]
    description: str
    tags: List[str]


def _outer_repo_root_from_layout() -> Path:
    here = Path(__file__).resolve()
    outer = here.parents[3]
    if not (outer / "main").exists():
        raise RuntimeError(f"Expected outer repo root to contain main/: {outer}")
    return outer


def default_candidates_parquet() -> Path:
    outer = _outer_repo_root_from_layout()
    return outer / "main" / "results" / "raw" / "postings_description_equity" / "equity_candidates.parquet"


def default_out_dir() -> Path:
    outer = _outer_repo_root_from_layout()
    return outer / "main" / "results" / "raw" / "postings_description_equity" / "llm_examples"


def default_inclusionary_zoning_dir() -> Path:
    return Path("/Users/saulrichardson/Dropbox/Inclusionary Zoning")


def _load_openai_api_key_from_ai_zoning_config(*, inclusionary_zoning_dir: Path) -> Optional[str]:
    """
    Best-effort loader for an API key from a local ai-zoning config module.

    Important: This is intentionally NOT the default behavior. Only use when explicitly enabled,
    because it encourages storing secrets in files.
    """
    config_py = (
        inclusionary_zoning_dir
        / "Github"
        / "ai-zoning"
        / "code"
        / "Web-Scraping"
        / "Web Agents"
        / "shared"
        / "config.py"
    )
    if not config_py.exists():
        return None

    spec = importlib.util.spec_from_file_location("ai_zoning_shared_config", config_py)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    api_key = getattr(module, "OPENAI_API_KEY", None)
    if isinstance(api_key, str) and api_key.strip().startswith("sk-"):
        return api_key.strip()
    return None


def load_openai_api_key(*, allow_local_fallback: bool, inclusionary_zoning_dir: Path) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and api_key.strip():
        return api_key.strip()

    if allow_local_fallback:
        api_key = _load_openai_api_key_from_ai_zoning_config(inclusionary_zoning_dir=inclusionary_zoning_dir)
        if api_key:
            return api_key

    raise RuntimeError(
        "OPENAI_API_KEY is not set. Either:\n"
        "  - export OPENAI_API_KEY in your shell, or\n"
        "  - re-run with --allow-local-key-fallback (less secure)."
    )


def system_prompt() -> str:
    return (
        "You are an information extraction engine.\n"
        "Extract equity-compensation-related information from a job posting.\n"
        "\n"
        "Rules:\n"
        "- Output must be valid JSON matching the provided schema (no markdown).\n"
        "- Do not hallucinate. Only extract details explicitly supported by the text.\n"
        "- If a field is unknown or not stated, use null (or false for booleans).\n"
        "- Treat 'equity instruments' as offered compensation/benefits to the employee, not job duties.\n"
        "- Keep evidence quotes short and directly copied from the text.\n"
        "- Evidence quotes must justify the key decisions (context + offered/not offered + instruments).\n"
        "- You may use the EQUITY_KEYWORD_SNIPPETS section to find relevant lines quickly.\n"
    )


def user_prompt_template() -> str:
    return (
        "Job posting:\n"
        "job_id: {job_id}\n"
        "company_cleaned: {company_cleaned}\n"
        "post_date: {post_date}\n"
        "title: {title}\n"
        "\n"
        "EQUITY_KEYWORD_SNIPPETS (auto-extracted, may be empty):\n"
        "{keyword_snippets}\n"
        "\n"
        "DESCRIPTION:\n"
        "{description}\n"
    )


def json_schema() -> Dict[str, Any]:
    """
    Strict schema optimized for downstream regressions:
    - Separates *employee equity compensation* from other uses of the word "equity"
      (DEI, home equity, private equity investing role, etc.)
    - Captures instrument presence + any hard numbers (rare but valuable)
    """
    instrument_obj = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "mentioned": {"type": "boolean"},
            "details_text": {"type": ["string", "null"]},
        },
        "required": ["mentioned", "details_text"],
    }

    return {
        "name": "equity_comp_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "job_id": {"type": "string"},
                "equity_context": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "employee_equity_compensation",
                            "private_equity_investing",
                            "dei_or_pay_equity",
                            "home_equity_lending",
                            "other",
                        ],
                    },
                },
                "employee_equity_comp_offered": {"type": "boolean"},
                "equity_instruments": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "stock_options": instrument_obj,
                        "rsu": instrument_obj,
                        "restricted_stock": instrument_obj,
                        "espp": instrument_obj,
                        "esop": instrument_obj,
                        "phantom_equity": instrument_obj,
                        "profit_interest": instrument_obj,
                        "carried_interest": instrument_obj,
                        "stock_appreciation_rights": instrument_obj,
                        "other_equity": instrument_obj,
                    },
                    "required": [
                        "stock_options",
                        "rsu",
                        "restricted_stock",
                        "espp",
                        "esop",
                        "phantom_equity",
                        "profit_interest",
                        "carried_interest",
                        "stock_appreciation_rights",
                        "other_equity",
                    ],
                },
                "vesting": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "mentioned": {"type": "boolean"},
                        "cliff_months": {"type": ["integer", "null"]},
                        "duration_months": {"type": ["integer", "null"]},
                        "schedule_text": {"type": ["string", "null"]},
                    },
                    "required": ["mentioned", "cliff_months", "duration_months", "schedule_text"],
                },
                "pricing_or_valuation": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "mentions_409a": {"type": "boolean"},
                        "mentions_strike_or_exercise_price": {"type": "boolean"},
                        "strike_or_exercise_price_amount": {"type": ["number", "null"]},
                        "strike_or_exercise_price_currency": {"type": ["string", "null"]},
                    },
                    "required": [
                        "mentions_409a",
                        "mentions_strike_or_exercise_price",
                        "strike_or_exercise_price_amount",
                        "strike_or_exercise_price_currency",
                    ],
                },
                "equity_amounts": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "mentions_shares": {"type": "boolean"},
                        "shares": {"type": ["number", "null"]},
                        "mentions_percent_ownership": {"type": "boolean"},
                        "percent_ownership": {"type": ["number", "null"]},
                        "mentions_dollar_value": {"type": "boolean"},
                        "dollar_value": {"type": ["number", "null"]},
                        "dollar_value_currency": {"type": ["string", "null"]},
                    },
                    "required": [
                        "mentions_shares",
                        "shares",
                        "mentions_percent_ownership",
                        "percent_ownership",
                        "mentions_dollar_value",
                        "dollar_value",
                        "dollar_value_currency",
                    ],
                },
                "evidence_quotes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                },
                "notes": {"type": ["string", "null"]},
            },
            "required": [
                "job_id",
                "equity_context",
                "employee_equity_comp_offered",
                "equity_instruments",
                "vesting",
                "pricing_or_valuation",
                "equity_amounts",
                "evidence_quotes",
                "notes",
            ],
        },
    }


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    threads = os.getenv("DUCKDB_THREADS")
    if threads:
        con.execute(f"PRAGMA threads={int(threads)}")
    else:
        con.execute("PRAGMA threads=4")
    return con


def sample_rows(*, con: duckdb.DuckDBPyConnection, parquet_path: Path) -> List[SampleRow]:
    """
    Pick a deterministic, diverse sample:
    - One RSU example
    - One stock options example
    - One ESPP example
    - One ESOP example
    - One 'equity_word_only' example (likely DEI/private-equity/home-equity noise)
    """
    pq = parquet_path.as_posix()

    # Discover hit columns so we can compute equity_word_only robustly.
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM parquet_scan({json.dumps(pq)})").fetchall()]
    hit_cols = [c for c in cols if c.startswith("hit_") and c not in {"hit_any_equity"}]
    other_hits = [c for c in hit_cols if c != "hit_equity_word"]
    other_or = " OR ".join(other_hits) if other_hits else "FALSE"

    def one(where_sql: str, tag: str) -> SampleRow:
        row = con.execute(
            f"""
SELECT
  cast(job_id as varchar) as job_id,
  company_cleaned,
  cast(post_date as varchar) as post_date,
  title,
  description
FROM parquet_scan({json.dumps(pq)})
WHERE {where_sql}
ORDER BY job_id
LIMIT 1
"""
        ).fetchone()
        if not row:
            raise RuntimeError(f"Could not find a sample row for: {tag} ({where_sql})")
        job_id, company_cleaned, post_date, title, description = row
        if not description or not str(description).strip():
            raise RuntimeError(f"Sample row {job_id} had an empty description; unexpected for candidates parquet.")
        return SampleRow(
            job_id=str(job_id),
            company_cleaned=company_cleaned,
            post_date=post_date,
            title=title,
            description=str(description),
            tags=[tag],
        )

    samples = [
        one("hit_rsu", "rsu"),
        # "stock options" can appear in non-comp contexts (e.g., tax/finance advice).
        # Bias toward postings that look like compensation/benefits language.
        one(
            "hit_stock_options AND (hit_equity_comp_phrase OR hit_option_grant OR hit_stock_or_share_based_comp OR hit_409a OR hit_cap_table OR hit_exercise_or_strike_price)",
            "stock_options",
        ),
        one("hit_espp", "espp"),
        one("hit_esop", "esop"),
        one(f"hit_equity_word AND NOT ({other_or})", "equity_word_only"),
    ]

    # If any duplicates (rare, but possible), make them unique by adding more rows.
    seen: set[str] = set()
    deduped: List[SampleRow] = []
    for s in samples:
        if s.job_id in seen:
            continue
        seen.add(s.job_id)
        deduped.append(s)

    if len(deduped) < 3:
        raise RuntimeError("Sample unexpectedly collapsed too much; investigate candidate parquet contents.")
    return deduped


def build_user_prompt(row: SampleRow) -> str:
    tpl = user_prompt_template()
    snippets = extract_keyword_snippets(title=row.title or "", description=row.description)
    return tpl.format(
        job_id=row.job_id,
        company_cleaned=row.company_cleaned or "",
        post_date=row.post_date or "",
        title=row.title or "",
        keyword_snippets="\n".join(f"- {s}" for s in snippets) if snippets else "- (none)",
        description=row.description,
    )


def extract_keyword_snippets(*, title: str, description: str) -> List[str]:
    """
    Pull short windows around equity-related tokens so the model sees the relevant
    language early, even when descriptions are long.
    """
    text = f"{title}\n{description}".strip()
    low = text.lower()

    tokens = [
        "restricted stock unit",
        "restricted stock",
        "rsu",
        "stock option",
        "option grant",
        "equity compensation",
        "equity grant",
        "equity",
        "espp",
        "employee stock purchase",
        "esop",
        "employee stock ownership",
        "phantom equity",
        "phantom stock",
        "profit interest",
        "carried interest",
        "stock appreciation right",
        "409a",
        "cap table",
        "capitalization table",
        "strike price",
        "exercise price",
    ]

    # Prefer longer tokens first so we don't swamp the snippet list with "equity".
    tokens.sort(key=len, reverse=True)

    snippets: List[str] = []
    seen: set[str] = set()

    for tok in tokens:
        idx = 0
        while True:
            hit = low.find(tok, idx)
            if hit < 0:
                break
            start = max(0, hit - 90)
            end = min(len(text), hit + len(tok) + 120)
            snippet = re.sub(r"\\s+", " ", text[start:end]).strip()
            key = snippet.lower()
            if key not in seen:
                seen.add(key)
                snippets.append(snippet)
            idx = hit + len(tok)
            if len(snippets) >= 8:
                return snippets

    return snippets


def call_llm(*, client: OpenAI, model: str, sys_prompt: str, user_prompt: str) -> Dict[str, Any]:
    fmt = json_schema()
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": fmt["name"],
                "strict": bool(fmt["strict"]),
                "schema": fmt["schema"],
            }
        },
    )
    raw = resp.output_text
    if not raw or not raw.strip():
        raise RuntimeError("Empty model output_text")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Model output was not valid JSON: {e}") from e


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model (default: %(default)s).")
    p.add_argument(
        "--candidates-parquet",
        type=Path,
        default=default_candidates_parquet(),
        help="Parquet file created by extract_equity_postings_candidates.py",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=default_out_dir(),
        help="Directory for sample outputs (default: %(default)s).",
    )
    p.add_argument(
        "--allow-local-key-fallback",
        action="store_true",
        help="If OPENAI_API_KEY is not set, attempt to load from a local config.py (less secure).",
    )
    p.add_argument(
        "--inclusionary-zoning-dir",
        type=Path,
        default=default_inclusionary_zoning_dir(),
        help="Root dir used for the local-key fallback (default: %(default)s).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    parquet_path: Path = args.candidates_parquet.expanduser().resolve()
    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing candidates parquet: {parquet_path}")

    out_dir: Path = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key = load_openai_api_key(
        allow_local_fallback=bool(args.allow_local_key_fallback),
        inclusionary_zoning_dir=args.inclusionary_zoning_dir.expanduser().resolve(),
    )

    client = OpenAI(api_key=api_key)
    con = _connect()
    try:
        rows = sample_rows(con=con, parquet_path=parquet_path)
    finally:
        con.close()

    sys_p = system_prompt()
    user_tpl = user_prompt_template()
    (out_dir / "prompt_system.txt").write_text(sys_p + "\n", encoding="utf-8")
    (out_dir / "prompt_user_template.txt").write_text(user_tpl + "\n", encoding="utf-8")

    inputs_path = out_dir / "sample_inputs.jsonl"
    outputs_path = out_dir / "sample_outputs.jsonl"

    with inputs_path.open("w", encoding="utf-8") as fin, outputs_path.open("w", encoding="utf-8") as fout:
        for row in rows:
            user_p = build_user_prompt(row)

            fin.write(
                json.dumps(
                    {
                        "job_id": row.job_id,
                        "company_cleaned": row.company_cleaned,
                        "post_date": row.post_date,
                        "title": row.title,
                        "tags": row.tags,
                        "user_prompt": user_p,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

            extracted = call_llm(client=client, model=str(args.model), sys_prompt=sys_p, user_prompt=user_p)
            fout.write(
                json.dumps(
                    {
                        "job_id": row.job_id,
                        "tags": row.tags,
                        "extraction": extracted,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    print("Wrote:", inputs_path)
    print("Wrote:", outputs_path)
    print("Wrote:", out_dir / "prompt_system.txt")
    print("Wrote:", out_dir / "prompt_user_template.txt")


if __name__ == "__main__":
    main()
