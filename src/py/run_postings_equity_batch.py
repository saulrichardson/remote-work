#!/usr/bin/env python3
"""
Prepare OpenAI Batch inputs for the active postings-equity extraction pipeline.

Why this exists
---------------
The active paper lane uses a postings-description branch that:
  1) optionally narrows raw posting shards to a deterministic keyword-screened candidate set, and
  2) sends posting text to the OpenAI Batch API (endpoint: /v1/responses) for structured extraction.

This script owns the Batch-API side of that workflow:
  - prepare request JSONL files
  - submit them
  - check status
  - download outputs

We still *optionally* skip rows with empty descriptions because there is no text to
extract from. If you want literal "send everything", use --include-empty.

Data layout assumption (matches current repo)
--------------------------------------------
The active shard source lives inside this repo:
  data/raw/postings_description/*.csv

Workflow (one shard at a time)
------------------------------
1) Prepare batch input JSONL (max 200MB / 50k requests per file):
   python src/py/run_postings_equity_batch.py prepare \
     --input-csv data/raw/postings_description/0000_part_00.csv \
     --out-dir results/raw/postings_description_equity/llm_batch_inputs/0000_part_00

Candidate-set workflow (recommended for cost)
---------------------------------------------
If you already built the deterministic keyword-screened candidate set using:
  - src/py/build_postings_equity_candidates.py

then you can prepare batch inputs directly from the parquet:
  python src/py/run_postings_equity_batch.py prepare-candidates \
    --candidates-parquet results/raw/postings_description_equity/equity_candidates.parquet

2) Submit ONE JSONL to OpenAI Batch:
   export OPENAI_API_KEY=...
   python src/py/run_postings_equity_batch.py submit \
     --input-jsonl results/raw/postings_description_equity/llm_batch_inputs/0000_part_00/batch_0000_part_00_0001.jsonl

3) Poll status:
   python src/py/run_postings_equity_batch.py status --batch-id batch_...

4) Download results:
   python src/py/run_postings_equity_batch.py download --batch-id batch_... \
     --out-dir results/raw/postings_description_equity/llm_batch_outputs/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

import duckdb
from openai import OpenAI
import yaml

from src.py import postings_equity_prompt_schema as equity_prompt
from src.py.project_paths import DATA_RAW, RESULTS_RAW


DEFAULT_MODEL = getattr(equity_prompt, "DEFAULT_MODEL", "gpt-5-nano")
DEFAULT_ENDPOINT = "/v1/responses"

# Batch API limits (reflected in OpenAI SDK docstrings).
MAX_REQUESTS_PER_BATCH_FILE = 50_000
MAX_BYTES_PER_BATCH_FILE = 200 * 1024 * 1024  # 200 MB


@dataclass(frozen=True)
class PostingRow:
    job_id: str
    company_cleaned: Optional[str]
    post_date: Optional[str]
    title: Optional[str]
    description: str


def default_postings_description_dir() -> Path:
    return DATA_RAW / "postings_description"


def default_out_dir_for_input(*, input_csv: Path) -> Path:
    stem = input_csv.stem
    return RESULTS_RAW / "postings_description_equity" / "llm_batch_inputs" / stem


def _connect_duckdb() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    threads = os.getenv("DUCKDB_THREADS")
    if threads:
        con.execute(f"PRAGMA threads={int(threads)}")
    else:
        con.execute(f"PRAGMA threads={max(4, (os.cpu_count() or 4))}")
    return con


def _sql_quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def iter_postings(
    *,
    con: duckdb.DuckDBPyConnection,
    input_csv: Path,
    include_empty: bool,
    max_rows: int,
) -> Iterator[PostingRow]:
    """
    Stream rows from a single postings-description shard.

    Note: We do not order; we preserve file order so chunking is stable and fast.
    """
    input_csv = input_csv.expanduser().resolve()
    if not input_csv.exists():
        raise FileNotFoundError(f"Missing input CSV: {input_csv}")

    where = "" if include_empty else "WHERE length(coalesce(description, '')) > 0"
    limit = "" if not max_rows else f"LIMIT {int(max_rows)}"

    query = f"""
    SELECT
      cast(job_id as varchar) as job_id,
      company_cleaned,
      cast(post_date as varchar) as post_date,
      title,
      cast(coalesce(description, '') as varchar) as description
    FROM read_csv_auto({_sql_quote_literal(input_csv.as_posix())}, SAMPLE_SIZE=20000)
    {where}
    {limit}
    """

    cur = con.execute(query)
    chunk = 10_000
    while True:
        rows = cur.fetchmany(chunk)
        if not rows:
            break
        for job_id, company_cleaned, post_date, title, description in rows:
            yield PostingRow(
                job_id=str(job_id),
                company_cleaned=company_cleaned if company_cleaned is None else str(company_cleaned),
                post_date=post_date if post_date is None else str(post_date),
                title=title if title is None else str(title),
                description=str(description or ""),
            )

def iter_postings_from_candidates_parquet(
    *,
    con: duckdb.DuckDBPyConnection,
    candidates_parquet: Path,
    max_rows: int,
) -> Iterator[PostingRow]:
    """
    Stream rows from the equity-candidates parquet produced by
    src/py/build_postings_equity_candidates.py.

    This parquet is already filtered to non-empty descriptions, but we still
    defensively coalesce null descriptions to '' so downstream code is total.
    """
    candidates_parquet = candidates_parquet.expanduser().resolve()
    if not candidates_parquet.exists():
        raise FileNotFoundError(f"Missing candidates parquet: {candidates_parquet}")

    limit = "" if not max_rows else f"LIMIT {int(max_rows)}"
    query = f"""
    SELECT
      cast(job_id as varchar) as job_id,
      company_cleaned,
      cast(post_date as varchar) as post_date,
      title,
      cast(coalesce(description, '') as varchar) as description
    FROM parquet_scan({json.dumps(candidates_parquet.as_posix())})
    {limit}
    """

    cur = con.execute(query)
    chunk = 10_000
    while True:
        rows = cur.fetchmany(chunk)
        if not rows:
            break
        for job_id, company_cleaned, post_date, title, description in rows:
            yield PostingRow(
                job_id=str(job_id),
                company_cleaned=company_cleaned if company_cleaned is None else str(company_cleaned),
                post_date=post_date if post_date is None else str(post_date),
                title=title if title is None else str(title),
                description=str(description or ""),
            )


def build_user_prompt(*, row: PostingRow, use_keyword_snippets: bool) -> str:
    """
    Build the user prompt for the active postings-equity extraction path.

    We keep the prompt contract stable while allowing the keyword-snippet section
    to be disabled. If use_keyword_snippets is True, reuse the active prompt helper.
    """
    tpl = equity_prompt.user_prompt_template()
    if use_keyword_snippets:
        snippets = equity_prompt.extract_keyword_snippets(title=row.title or "", description=row.description)
        keyword_snippets = "\n".join(f"- {s}" for s in snippets) if snippets else "- (none)"
    else:
        keyword_snippets = "- (none)"
    return tpl.format(
        job_id=row.job_id,
        company_cleaned=row.company_cleaned or "",
        post_date=row.post_date or "",
        title=row.title or "",
        keyword_snippets=keyword_snippets,
        description=row.description,
    )


def build_batch_request_line(
    *,
    custom_id: str,
    model: str,
    sys_prompt: str,
    user_prompt: str,
    schema: Dict[str, Any],
    endpoint_url: str,
) -> Dict[str, Any]:
    fmt = schema
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": endpoint_url,
        "body": {
            "model": model,
            "truncation": "disabled",
            "input": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": fmt["name"],
                    "strict": bool(fmt["strict"]),
                    "schema": fmt["schema"],
                }
            },
        },
    }


@dataclass(frozen=True)
class PreparedFile:
    path: Path
    n_requests: int
    n_bytes: int


def _prepare_batch_inputs_common(
    *,
    rows: Iterable[PostingRow],
    source_label: str,
    source_path: str,
    out_dir: Path,
    model: str,
    max_requests_per_file: int,
    max_mb_per_file: int,
    use_keyword_snippets: bool,
) -> List[PreparedFile]:
    if max_requests_per_file <= 0:
        raise ValueError("--max-requests-per-file must be positive.")
    if max_requests_per_file > MAX_REQUESTS_PER_BATCH_FILE:
        raise ValueError(
            f"--max-requests-per-file exceeds Batch API limit ({MAX_REQUESTS_PER_BATCH_FILE:,})."
        )

    max_bytes_per_file = int(max_mb_per_file) * 1024 * 1024
    if max_bytes_per_file <= 0:
        raise ValueError("--max-mb-per-file must be positive.")
    if max_bytes_per_file > MAX_BYTES_PER_BATCH_FILE:
        raise ValueError("--max-mb-per-file exceeds Batch API limit (200 MB).")

    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    sys_prompt = equity_prompt.system_prompt()
    schema = equity_prompt.json_schema()

    # Provenance: snapshot the prompts + schema into the output folder.
    (out_dir / "prompt_system.txt").write_text(sys_prompt + "\n", encoding="utf-8")
    (out_dir / "prompt_user_template.txt").write_text(equity_prompt.user_prompt_template() + "\n", encoding="utf-8")
    (out_dir / "schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    prepared: List[PreparedFile] = []
    file_idx = 0

    cur_path: Optional[Path] = None
    cur_fh = None
    cur_n = 0
    cur_bytes = 0
    total_rows = 0

    def open_next_file() -> Tuple[Path, Any]:
        nonlocal file_idx, cur_n, cur_bytes
        file_idx += 1
        cur_n = 0
        cur_bytes = 0
        path = out_dir / f"batch_{source_label}_{file_idx:04d}.jsonl"
        fh = path.open("w", encoding="utf-8")
        return path, fh

    cur_path, cur_fh = open_next_file()

    t0 = time.time()
    for row in rows:
        total_rows += 1
        user_prompt = build_user_prompt(row=row, use_keyword_snippets=use_keyword_snippets)

        # Ensure custom_id uniqueness even if job_id repeats.
        custom_id = f"{source_label}__row_{total_rows:09d}__job_{row.job_id}"

        obj = build_batch_request_line(
            custom_id=custom_id,
            model=model,
            sys_prompt=sys_prompt,
            user_prompt=user_prompt,
            schema=schema,
            endpoint_url=DEFAULT_ENDPOINT,
        )
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        line_bytes = len(line.encode("utf-8"))

        # If adding this line would breach limits, rotate *before* writing.
        rotate = False
        if cur_n >= max_requests_per_file:
            rotate = True
        if cur_bytes + line_bytes > max_bytes_per_file:
            rotate = True

        if rotate:
            assert cur_path is not None and cur_fh is not None
            cur_fh.close()
            prepared.append(PreparedFile(path=cur_path, n_requests=cur_n, n_bytes=cur_bytes))
            cur_path, cur_fh = open_next_file()

        assert cur_fh is not None
        cur_fh.write(line)
        cur_n += 1
        cur_bytes += line_bytes

        # Light progress heartbeat (every ~100k rows).
        if total_rows % 100_000 == 0:
            dt = time.time() - t0
            print(f"[prepare] rows={total_rows:,} files={file_idx} elapsed_s={dt:,.1f}")

    # Close final file.
    if cur_fh is not None:
        cur_fh.close()
    if cur_path is not None and cur_n > 0:
        prepared.append(PreparedFile(path=cur_path, n_requests=cur_n, n_bytes=cur_bytes))

    meta = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": {
            "label": source_label,
            "path": source_path,
        },
        "use_keyword_snippets": bool(use_keyword_snippets),
        "model": str(model),
        "endpoint": DEFAULT_ENDPOINT,
        "batch_limits": {
            "max_requests_per_file": int(max_requests_per_file),
            "max_mb_per_file": int(max_mb_per_file),
            "hard_max_requests_per_file": MAX_REQUESTS_PER_BATCH_FILE,
            "hard_max_mb_per_file": int(MAX_BYTES_PER_BATCH_FILE / (1024 * 1024)),
        },
        "files": [{"path": str(p.path), "n_requests": int(p.n_requests), "n_bytes": int(p.n_bytes)} for p in prepared],
        "totals": {
            "n_files": len(prepared),
            "n_requests": int(sum(p.n_requests for p in prepared)),
            "n_bytes": int(sum(p.n_bytes for p in prepared)),
        },
    }
    (out_dir / "prepare_manifest.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[prepare] wrote {len(prepared)} files → {out_dir}")
    return prepared


def prepare_batch_inputs(
    *,
    input_csv: Path,
    out_dir: Path,
    model: str,
    include_empty: bool,
    max_rows: int,
    max_requests_per_file: int,
    max_mb_per_file: int,
    use_keyword_snippets: bool,
) -> List[PreparedFile]:
    con = _connect_duckdb()
    try:
        rows = iter_postings(con=con, input_csv=input_csv, include_empty=include_empty, max_rows=max_rows)
        return _prepare_batch_inputs_common(
            rows=rows,
            source_label=Path(input_csv).stem,
            source_path=str(Path(input_csv).expanduser().resolve()),
            out_dir=out_dir,
            model=model,
            max_requests_per_file=max_requests_per_file,
            max_mb_per_file=max_mb_per_file,
            use_keyword_snippets=use_keyword_snippets,
        )
    finally:
        con.close()


def prepare_batch_inputs_from_candidates_parquet(
    *,
    candidates_parquet: Path,
    out_dir: Path,
    model: str,
    max_rows: int,
    max_requests_per_file: int,
    max_mb_per_file: int,
    use_keyword_snippets: bool,
) -> List[PreparedFile]:
    con = _connect_duckdb()
    try:
        rows = iter_postings_from_candidates_parquet(
            con=con, candidates_parquet=candidates_parquet, max_rows=max_rows
        )
        return _prepare_batch_inputs_common(
            rows=rows,
            source_label="equity_candidates",
            source_path=str(Path(candidates_parquet).expanduser().resolve()),
            out_dir=out_dir,
            model=model,
            max_requests_per_file=max_requests_per_file,
            max_mb_per_file=max_mb_per_file,
            use_keyword_snippets=use_keyword_snippets,
        )
    finally:
        con.close()


def _load_openai_api_key_from_yaml(*, config_yaml: Path) -> Optional[str]:
    config_yaml = config_yaml.expanduser().resolve()
    if not config_yaml.exists():
        return None
    obj = yaml.safe_load(config_yaml.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(obj, dict):
        return None
    key = obj.get("openai_key")
    if not isinstance(key, str):
        return None
    key = key.strip()
    if not key:
        return None
    # Best-effort guard: OpenAI keys are typically "sk-...". Don't accept obviously wrong values.
    if not key.startswith("sk-"):
        return None
    return key


def require_openai_api_key(*, config_yaml: Optional[Path]) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        if config_yaml is not None:
            yaml_key = _load_openai_api_key_from_yaml(config_yaml=config_yaml)
            if yaml_key:
                return yaml_key
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Provide it via:\n"
            "  - export OPENAI_API_KEY=...  (recommended), or\n"
            "  - pass --config-yaml pointing at a YAML that contains an 'openai_key' value."
        )
    return api_key.strip()


def _api_key_fingerprint(api_key: str) -> str:
    """
    Return a stable, non-reversible identifier for a key.

    This is useful for debugging situations where batches exist but are not visible
    due to key rotation / project mismatch, without ever writing the key itself to disk.
    """
    api_key = api_key.strip().encode("utf-8")
    return hashlib.sha256(api_key).hexdigest()[:16]


def submit_batch(*, input_jsonl: Path, metadata: Dict[str, str], config_yaml: Optional[Path]) -> str:
    api_key = require_openai_api_key(config_yaml=config_yaml)
    client = OpenAI(api_key=api_key)

    input_jsonl = input_jsonl.expanduser().resolve()
    if not input_jsonl.exists():
        raise FileNotFoundError(f"Missing input JSONL: {input_jsonl}")

    with input_jsonl.open("rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")

    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint=DEFAULT_ENDPOINT,
        completion_window="24h",
        metadata=metadata,
    )

    out = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_jsonl": str(input_jsonl),
        "file_id": file_obj.id,
        "batch_id": batch.id,
        "status": batch.status,
        "endpoint": batch.endpoint,
        "completion_window": batch.completion_window,
        "api_key_fingerprint": _api_key_fingerprint(api_key),
    }

    submission_path = input_jsonl.parent / f"submission_{batch.id}.json"
    submission_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("[submit] file_id:", file_obj.id)
    print("[submit] batch_id:", batch.id)
    print("[submit] wrote:", submission_path)
    return batch.id


def batch_status(*, batch_id: str, config_yaml: Optional[Path]) -> Dict[str, Any]:
    api_key = require_openai_api_key(config_yaml=config_yaml)
    client = OpenAI(api_key=api_key)
    b = client.batches.retrieve(batch_id)
    # Convert to plain dict for easy viewing/logging.
    return b.model_dump()


def download_batch_outputs(*, batch_id: str, out_dir: Path, config_yaml: Optional[Path]) -> List[Path]:
    api_key = require_openai_api_key(config_yaml=config_yaml)
    client = OpenAI(api_key=api_key)

    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    b = client.batches.retrieve(batch_id)
    dumped = b.model_dump()
    (out_dir / f"batch_{batch_id}_status.json").write_text(json.dumps(dumped, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    paths: List[Path] = []

    if b.output_file_id:
        content = client.files.content(b.output_file_id)
        p = out_dir / f"batch_{batch_id}_output.jsonl"
        p.write_bytes(content.read())
        paths.append(p)
        print("[download] output:", p)
    else:
        print("[download] no output_file_id (status:", b.status, ")")

    if b.error_file_id:
        content = client.files.content(b.error_file_id)
        p = out_dir / f"batch_{batch_id}_error.jsonl"
        p.write_bytes(content.read())
        paths.append(p)
        print("[download] error:", p)
    else:
        print("[download] no error_file_id")

    return paths


def status_dir(
    *,
    input_dir: Path,
    config_yaml: Optional[Path],
    sleep_seconds: float,
) -> Dict[str, Any]:
    """
    Fetch status for every batch referenced in input_dir.

    Discovery order:
      1) input_dir/submit_dir_manifest.json (preferred)
      2) input_dir/submission_*.json files
    """
    api_key = require_openai_api_key(config_yaml=config_yaml)
    client = OpenAI(api_key=api_key)

    input_dir = input_dir.expanduser().resolve()
    if not input_dir.exists():
        raise FileNotFoundError(f"input_dir not found: {input_dir}")

    batch_ids: List[str] = []
    manifest_path = input_dir / "submit_dir_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cand = manifest.get("batch_ids")
            if isinstance(cand, list) and all(isinstance(x, str) and x for x in cand):
                batch_ids = list(cand)
        except Exception:
            batch_ids = []

    if not batch_ids:
        for p in sorted(input_dir.glob("submission_*.json")):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            bid = obj.get("batch_id")
            if isinstance(bid, str) and bid:
                batch_ids.append(bid)

    if not batch_ids:
        raise RuntimeError(f"No batch IDs found in {input_dir} (expected submit_dir_manifest.json or submission_*.json).")

    statuses: List[Dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    req_totals = Counter()

    for i, bid in enumerate(batch_ids, 1):
        try:
            b = client.batches.retrieve(bid)
            dumped = b.model_dump()
            statuses.append(
                {
                    "batch_id": dumped.get("id"),
                    "status": dumped.get("status"),
                    "request_counts": dumped.get("request_counts"),
                    "output_file_id": dumped.get("output_file_id"),
                    "error_file_id": dumped.get("error_file_id"),
                    "created_at": dumped.get("created_at"),
                    "expires_at": dumped.get("expires_at"),
                    "metadata": dumped.get("metadata"),
                    "error": None,
                }
            )

            st = b.status
            status_counts[st] += 1
            rc = dumped.get("request_counts") or {}
            if isinstance(rc, dict):
                for k in ("completed", "failed", "total"):
                    v = rc.get(k)
                    if isinstance(v, int):
                        req_totals[k] += v
        except Exception as e:
            # Key mismatch / project mismatch often manifests as 404s; we still want a summary.
            statuses.append(
                {
                    "batch_id": bid,
                    "status": "error",
                    "request_counts": None,
                    "output_file_id": None,
                    "error_file_id": None,
                    "created_at": None,
                    "expires_at": None,
                    "metadata": None,
                    "error": {"type": type(e).__name__, "message": str(e)[:300]},
                }
            )
            status_counts["error"] += 1

        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

        # Lightweight heartbeat so long runs don't look stuck.
        if i % 10 == 0:
            print(f"[status-dir] fetched {i}/{len(batch_ids)}")

    out = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_dir": str(input_dir),
        "api_key_fingerprint": _api_key_fingerprint(api_key),
        "status_counts": dict(status_counts),
        "request_totals": dict(req_totals),
        "batches": statuses,
    }

    out_path = input_dir / "status_dir_summary.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("[status-dir] wrote:", out_path)
    return out


def _copy_text_if_exists(*, src: Path, dst: Path) -> Optional[Path]:
    if not src.exists():
        return None
    dst.write_text(src.read_text(encoding="utf-8", errors="replace") + "\n", encoding="utf-8")
    return dst


def prepare_retry_inputs(
    *,
    previous_input_dir: Path,
    previous_output_dir: Path,
    out_dir: Path,
    max_requests_per_file: int,
    max_mb_per_file: int,
) -> List[PreparedFile]:
    """
    Build new Batch input JSONL files that retry ONLY the requests that failed in a previous run.

    This keeps the exact original request payloads by filtering the original `batch_*.jsonl`
    files down to the set of `custom_id`s present in the prior run's `*_error.jsonl` outputs.
    """
    if max_requests_per_file <= 0:
        raise ValueError("--max-requests-per-file must be positive.")
    if max_requests_per_file > MAX_REQUESTS_PER_BATCH_FILE:
        raise ValueError(
            f"--max-requests-per-file exceeds Batch API limit ({MAX_REQUESTS_PER_BATCH_FILE:,})."
        )

    max_bytes_per_file = int(max_mb_per_file) * 1024 * 1024
    if max_bytes_per_file <= 0:
        raise ValueError("--max-mb-per-file must be positive.")
    if max_bytes_per_file > MAX_BYTES_PER_BATCH_FILE:
        raise ValueError("--max-mb-per-file exceeds Batch API limit (200 MB).")

    previous_input_dir = previous_input_dir.expanduser().resolve()
    previous_output_dir = previous_output_dir.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()

    if not previous_input_dir.exists():
        raise FileNotFoundError(f"previous_input_dir not found: {previous_input_dir}")
    if not previous_output_dir.exists():
        raise FileNotFoundError(f"previous_output_dir not found: {previous_output_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy provenance (best-effort).
    _copy_text_if_exists(src=previous_input_dir / "prompt_system.txt", dst=out_dir / "prompt_system.txt")
    _copy_text_if_exists(
        src=previous_input_dir / "prompt_user_template.txt", dst=out_dir / "prompt_user_template.txt"
    )
    _copy_text_if_exists(src=previous_input_dir / "schema.json", dst=out_dir / "schema.json")

    error_files = sorted(previous_output_dir.glob("*_error.jsonl"))
    if not error_files:
        raise RuntimeError(f"No *_error.jsonl files found under previous_output_dir: {previous_output_dir}")

    failed_custom_ids: set[str] = set()
    for p in error_files:
        with p.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"{p}:{line_no}: invalid JSON: {e}") from e
                cid = obj.get("custom_id")
                if isinstance(cid, str) and cid:
                    failed_custom_ids.add(cid)

    if not failed_custom_ids:
        raise RuntimeError("Found 0 failed custom_ids in prior error JSONL files; nothing to retry.")

    batch_files = sorted(previous_input_dir.glob("batch_*.jsonl"))
    if not batch_files:
        raise RuntimeError(f"No batch_*.jsonl files found under previous_input_dir: {previous_input_dir}")

    prepared: List[PreparedFile] = []
    file_idx = 0
    cur_path: Optional[Path] = None
    cur_fh = None
    cur_n = 0
    cur_bytes = 0
    matched = 0

    def open_next_file() -> Tuple[Path, Any]:
        nonlocal file_idx, cur_n, cur_bytes
        file_idx += 1
        cur_n = 0
        cur_bytes = 0
        path = out_dir / f"batch_retry_{file_idx:04d}.jsonl"
        fh = path.open("w", encoding="utf-8")
        return path, fh

    cur_path, cur_fh = open_next_file()

    t0 = time.time()
    for src_file in batch_files:
        with src_file.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"{src_file}:{line_no}: invalid JSON: {e}") from e
                cid = obj.get("custom_id")
                if not isinstance(cid, str) or not cid:
                    continue
                if cid not in failed_custom_ids:
                    continue

                line_bytes = len(line.encode("utf-8"))
                rotate = False
                if cur_n >= max_requests_per_file:
                    rotate = True
                if cur_bytes + line_bytes > max_bytes_per_file:
                    rotate = True

                if rotate:
                    assert cur_path is not None and cur_fh is not None
                    cur_fh.close()
                    prepared.append(PreparedFile(path=cur_path, n_requests=cur_n, n_bytes=cur_bytes))
                    cur_path, cur_fh = open_next_file()

                assert cur_fh is not None
                cur_fh.write(line)
                cur_n += 1
                cur_bytes += line_bytes
                matched += 1
                failed_custom_ids.remove(cid)

                if matched % 50_000 == 0:
                    dt = time.time() - t0
                    print(
                        f"[prepare-retry] matched={matched:,} files={file_idx} remaining={len(failed_custom_ids):,} elapsed_s={dt:,.1f}"
                    )

    if cur_fh is not None:
        cur_fh.close()
    if cur_path is not None and cur_n > 0:
        prepared.append(PreparedFile(path=cur_path, n_requests=cur_n, n_bytes=cur_bytes))

    meta = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "previous_input_dir": str(previous_input_dir),
        "previous_output_dir": str(previous_output_dir),
        "n_failed_custom_ids_total": matched + len(failed_custom_ids),
        "n_matched_requests": matched,
        "n_unmatched_custom_ids": len(failed_custom_ids),
        "unmatched_custom_ids_sample": sorted(list(failed_custom_ids))[:10],
        "batch_limits": {
            "max_requests_per_file": int(max_requests_per_file),
            "max_mb_per_file": int(max_mb_per_file),
            "hard_max_requests_per_file": MAX_REQUESTS_PER_BATCH_FILE,
            "hard_max_mb_per_file": int(MAX_BYTES_PER_BATCH_FILE / (1024 * 1024)),
        },
        "files": [{"path": str(p.path), "n_requests": int(p.n_requests), "n_bytes": int(p.n_bytes)} for p in prepared],
        "totals": {
            "n_files": len(prepared),
            "n_requests": int(sum(p.n_requests for p in prepared)),
            "n_bytes": int(sum(p.n_bytes for p in prepared)),
        },
    }
    (out_dir / "prepare_retry_manifest.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[prepare-retry] wrote {len(prepared)} files → {out_dir}")
    if failed_custom_ids:
        print(f"[prepare-retry] WARNING: {len(failed_custom_ids):,} failed custom_ids were not found in input JSONL.")
    return prepared


def rechunk_dir(
    *,
    input_dir: Path,
    out_dir: Path,
    max_requests_per_file: int,
    max_mb_per_file: int,
) -> List[PreparedFile]:
    """
    Re-chunk existing Batch request JSONL files into smaller files.

    This is useful when you prepared large batch files under the SDK limits
    (<=50k requests, <=200MB), but the *org/project* enqueued-token limit for a model
    is lower (e.g., 2,000,000 tokens), causing large batches to fail during validation.

    The function preserves the exact JSONL request lines (no re-generation).
    """
    if max_requests_per_file <= 0:
        raise ValueError("--max-requests-per-file must be positive.")
    if max_requests_per_file > MAX_REQUESTS_PER_BATCH_FILE:
        raise ValueError(
            f"--max-requests-per-file exceeds Batch API limit ({MAX_REQUESTS_PER_BATCH_FILE:,})."
        )

    max_bytes_per_file = int(max_mb_per_file) * 1024 * 1024
    if max_bytes_per_file <= 0:
        raise ValueError("--max-mb-per-file must be positive.")
    if max_bytes_per_file > MAX_BYTES_PER_BATCH_FILE:
        raise ValueError("--max-mb-per-file exceeds Batch API limit (200 MB).")

    input_dir = input_dir.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    if not input_dir.exists():
        raise FileNotFoundError(f"input_dir not found: {input_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy provenance (best-effort).
    _copy_text_if_exists(src=input_dir / "prompt_system.txt", dst=out_dir / "prompt_system.txt")
    _copy_text_if_exists(src=input_dir / "prompt_user_template.txt", dst=out_dir / "prompt_user_template.txt")
    _copy_text_if_exists(src=input_dir / "schema.json", dst=out_dir / "schema.json")

    batch_files = sorted(input_dir.glob("batch_*.jsonl"))
    if not batch_files:
        raise RuntimeError(f"No batch_*.jsonl files found under input_dir: {input_dir}")

    prepared: List[PreparedFile] = []
    file_idx = 0
    cur_path: Optional[Path] = None
    cur_fh = None
    cur_n = 0
    cur_bytes = 0
    total = 0

    def open_next_file() -> Tuple[Path, Any]:
        nonlocal file_idx, cur_n, cur_bytes
        file_idx += 1
        cur_n = 0
        cur_bytes = 0
        path = out_dir / f"batch_rechunk_{file_idx:04d}.jsonl"
        fh = path.open("w", encoding="utf-8")
        return path, fh

    cur_path, cur_fh = open_next_file()

    t0 = time.time()
    for src_file in batch_files:
        with src_file.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                if not line.endswith("\n"):
                    line = line + "\n"
                line_bytes = len(line.encode("utf-8"))

                rotate = False
                if cur_n >= max_requests_per_file:
                    rotate = True
                if cur_bytes + line_bytes > max_bytes_per_file:
                    rotate = True

                if rotate:
                    assert cur_path is not None and cur_fh is not None
                    cur_fh.close()
                    prepared.append(PreparedFile(path=cur_path, n_requests=cur_n, n_bytes=cur_bytes))
                    cur_path, cur_fh = open_next_file()

                assert cur_fh is not None
                cur_fh.write(line)
                cur_n += 1
                cur_bytes += line_bytes
                total += 1

                if total % 50_000 == 0:
                    dt = time.time() - t0
                    print(f"[rechunk-dir] rows={total:,} files={file_idx} elapsed_s={dt:,.1f}")

    if cur_fh is not None:
        cur_fh.close()
    if cur_path is not None and cur_n > 0:
        prepared.append(PreparedFile(path=cur_path, n_requests=cur_n, n_bytes=cur_bytes))

    meta = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_dir": str(input_dir),
        "out_dir": str(out_dir),
        "batch_limits": {
            "max_requests_per_file": int(max_requests_per_file),
            "max_mb_per_file": int(max_mb_per_file),
            "hard_max_requests_per_file": MAX_REQUESTS_PER_BATCH_FILE,
            "hard_max_mb_per_file": int(MAX_BYTES_PER_BATCH_FILE / (1024 * 1024)),
        },
        "files": [{"path": str(p.path), "n_requests": int(p.n_requests), "n_bytes": int(p.n_bytes)} for p in prepared],
        "totals": {
            "n_files": len(prepared),
            "n_requests": int(sum(p.n_requests for p in prepared)),
            "n_bytes": int(sum(p.n_bytes for p in prepared)),
        },
    }
    (out_dir / "rechunk_manifest.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[rechunk-dir] wrote {len(prepared)} files → {out_dir}")
    return prepared


def download_dir(
    *,
    input_dir: Path,
    out_dir: Path,
    config_yaml: Optional[Path],
    sleep_seconds: float,
    skip_existing: bool,
) -> Dict[str, Any]:
    """
    Download output/error JSONL for every batch referenced in input_dir.

    Discovery order:
      1) input_dir/submit_dir_manifest.json (preferred)
      2) input_dir/submission_*.json files

    Resume behavior:
    - If skip_existing is set and we already have a status JSON plus at least one of
      output/error JSONL in out_dir, we skip re-downloading that batch.
    """
    api_key = require_openai_api_key(config_yaml=config_yaml)

    input_dir = input_dir.expanduser().resolve()
    if not input_dir.exists():
        raise FileNotFoundError(f"input_dir not found: {input_dir}")

    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    batch_ids: List[str] = []
    manifest_path = input_dir / "submit_dir_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cand = manifest.get("batch_ids")
            if isinstance(cand, list) and all(isinstance(x, str) and x for x in cand):
                batch_ids = list(cand)
        except Exception:
            batch_ids = []

    if not batch_ids:
        for p in sorted(input_dir.glob("submission_*.json")):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            bid = obj.get("batch_id")
            if isinstance(bid, str) and bid:
                batch_ids.append(bid)

    if not batch_ids:
        raise RuntimeError(f"No batch IDs found in {input_dir} (expected submit_dir_manifest.json or submission_*.json).")

    downloaded: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for i, bid in enumerate(batch_ids, 1):
        status_path = out_dir / f"batch_{bid}_status.json"
        output_path = out_dir / f"batch_{bid}_output.jsonl"
        error_path = out_dir / f"batch_{bid}_error.jsonl"

        if skip_existing and status_path.exists() and (output_path.exists() or error_path.exists()):
            print("[download-dir] skip existing:", bid)
            downloaded.append({"batch_id": bid, "skipped": True})
        else:
            try:
                paths = download_batch_outputs(batch_id=bid, out_dir=out_dir, config_yaml=config_yaml)
                downloaded.append({"batch_id": bid, "skipped": False, "paths": [str(p) for p in paths]})
            except Exception as e:
                err = {"batch_id": bid, "type": type(e).__name__, "message": str(e)[:300]}
                print("[download-dir] error:", err)
                errors.append(err)

        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

        if i % 5 == 0:
            print(f"[download-dir] progress {i}/{len(batch_ids)}")

    out = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_dir": str(input_dir),
        "out_dir": str(out_dir),
        "api_key_fingerprint": _api_key_fingerprint(api_key),
        "n_batches": len(batch_ids),
        "n_errors": len(errors),
        "errors": errors,
        "downloaded": downloaded,
    }

    out_path = out_dir / "download_dir_manifest.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("[download-dir] wrote:", out_path)
    return out


def submit_dir(
    *,
    input_dir: Path,
    tag: str,
    config_yaml: Optional[Path],
    sleep_seconds: float,
    max_active_batches: int,
    poll_seconds: float,
    stop_after: int,
) -> List[str]:
    """
    Submit every batch_*.jsonl file under input_dir.

    Resume behavior:
    - If input_dir already contains submission_*.json files, we treat those input_jsonl
      paths as already-submitted and skip them.

    Throttling behavior (optional):
    - If max_active_batches is positive, we only keep up to that many batches in an
      "active" state (validating/in_progress/finalizing/cancelling) at a time.
    - This exists because some orgs/projects enforce a relatively low "enqueued token"
      limit per model; submitting too much at once can cause immediate batch failures
      with `token_limit_exceeded`.
    """
    input_dir = input_dir.expanduser().resolve()
    if not input_dir.exists():
        raise FileNotFoundError(f"input_dir not found: {input_dir}")
    if max_active_batches < 0:
        raise ValueError("--max-active-batches must be >= 0 (0 means no throttling).")
    if poll_seconds <= 0:
        raise ValueError("--poll-seconds must be positive.")
    if stop_after < 0:
        raise ValueError("--stop-after must be >= 0 (0 means no limit).")

    # Discover already submitted files.
    submitted_inputs: set[str] = set()
    existing_batch_ids: List[str] = []
    for p in sorted(input_dir.glob("submission_*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        ip = obj.get("input_jsonl")
        if isinstance(ip, str) and ip:
            submitted_inputs.add(str(Path(ip).expanduser().resolve()))
        bid = obj.get("batch_id")
        if isinstance(bid, str) and bid:
            existing_batch_ids.append(bid)

    batch_files = sorted(input_dir.glob("batch_*.jsonl"))
    if not batch_files:
        raise RuntimeError(f"No batch_*.jsonl files found in {input_dir}")

    api_key = require_openai_api_key(config_yaml=config_yaml)
    client = OpenAI(api_key=api_key) if max_active_batches > 0 else None
    active_statuses = {"validating", "in_progress", "finalizing", "cancelling"}

    active_batch_ids: set[str] = set()
    if client is not None and existing_batch_ids:
        # Best-effort: seed the "active" set for resume runs.
        for bid in existing_batch_ids:
            try:
                b = client.batches.retrieve(bid)
            except Exception:
                continue
            if getattr(b, "status", None) in active_statuses:
                active_batch_ids.add(bid)

    def write_manifest(*, newly_submitted_batch_ids: List[str], all_batch_ids: List[str]) -> None:
        manifest = {
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "input_dir": str(input_dir),
            "tag": tag or None,
            "api_key_fingerprint": _api_key_fingerprint(api_key),
            "limits": {
                "max_active_batches": int(max_active_batches),
                "poll_seconds": float(poll_seconds),
                "stop_after": int(stop_after),
            },
            "counts": {
                "n_batch_files": len(batch_files),
                "n_already_submitted": len(submitted_inputs),
                "n_newly_submitted": len(newly_submitted_batch_ids),
                "n_batches_total": len(all_batch_ids),
            },
            "batch_ids": all_batch_ids,
            "batch_ids_new": newly_submitted_batch_ids,
        }
        out_path = input_dir / "submit_dir_manifest.json"
        out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    submitted_batch_ids: List[str] = []
    for f in batch_files:
        if stop_after and len(submitted_batch_ids) >= stop_after:
            break

        f_res = f.expanduser().resolve()
        if str(f_res) in submitted_inputs:
            print("[submit-dir] skip already submitted:", f_res)
            continue

        # Optional throttling: wait until the active set falls below the limit.
        if client is not None and max_active_batches > 0:
            while len(active_batch_ids) >= max_active_batches:
                # Poll active batches and drop any terminal ones.
                still_active: set[str] = set()
                for bid in sorted(active_batch_ids):
                    try:
                        b = client.batches.retrieve(bid)
                        st = getattr(b, "status", None)
                    except Exception:
                        # If we can't retrieve, keep it active and try later.
                        st = None
                    if st in active_statuses or st is None:
                        still_active.add(bid)
                active_batch_ids = still_active
                if len(active_batch_ids) >= max_active_batches:
                    print(
                        f"[submit-dir] throttle: active={len(active_batch_ids)} max_active={max_active_batches} → sleep {poll_seconds}s"
                    )
                    time.sleep(float(poll_seconds))

        bid = submit_batch(input_jsonl=f_res, metadata={k: v for k, v in {"tag": tag}.items() if v}, config_yaml=config_yaml)
        submitted_batch_ids.append(bid)
        if client is not None and max_active_batches > 0:
            active_batch_ids.add(bid)

        # Keep the manifest updated so long-running submissions are resumable.
        all_batch_ids = list(dict.fromkeys(existing_batch_ids + submitted_batch_ids))
        write_manifest(newly_submitted_batch_ids=submitted_batch_ids, all_batch_ids=all_batch_ids)

        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

    all_batch_ids = list(dict.fromkeys(existing_batch_ids + submitted_batch_ids))
    write_manifest(newly_submitted_batch_ids=submitted_batch_ids, all_batch_ids=all_batch_ids)
    print("[submit-dir] wrote:", input_dir / "submit_dir_manifest.json")
    return submitted_batch_ids


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config-yaml",
        type=Path,
        default=None,
        help=(
            "Optional YAML config containing an 'openai_key' value. If OPENAI_API_KEY is not set, "
            "we will try this file as a fallback."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("prepare", help="Generate Batch-API request JSONL files from one shard CSV.")
    pp.add_argument("--input-csv", type=Path, required=True, help="Shard CSV under data/raw/postings_description/")
    pp.add_argument("--out-dir", type=Path, default=None, help="Output directory (default: auto).")
    pp.add_argument("--model", type=str, default=DEFAULT_MODEL, help="OpenAI model (default: %(default)s).")
    pp.add_argument(
        "--include-empty",
        action="store_true",
        help="Include rows with empty descriptions (default: skip empties).",
    )
    pp.add_argument("--max-rows", type=int, default=0, help="Optional cap for testing (0=all).")
    pp.add_argument(
        "--max-requests-per-file",
        type=int,
        default=30_000,
        help="Max requests per JSONL file (hard max 50k).",
    )
    pp.add_argument(
        "--max-mb-per-file",
        type=int,
        default=190,
        help="Max MB per JSONL file (hard max 200).",
    )
    pp.add_argument(
        "--use-keyword-snippets",
        action="store_true",
        help="Include EQUITY_KEYWORD_SNIPPETS in the prompt (slower, larger requests). Default: off.",
    )

    pc = sub.add_parser(
        "prepare-candidates",
        help="Generate Batch-API request JSONL files from equity_candidates.parquet.",
    )
    pc.add_argument(
        "--candidates-parquet",
        type=Path,
        default=equity_prompt.default_candidates_parquet(),
        help="Parquet produced by build_postings_equity_candidates.py (default: auto-detected).",
    )
    pc.add_argument("--out-dir", type=Path, default=None, help="Output directory (default: auto timestamped).")
    pc.add_argument("--model", type=str, default=DEFAULT_MODEL, help="OpenAI model (default: %(default)s).")
    pc.add_argument("--max-rows", type=int, default=0, help="Optional cap for testing (0=all).")
    pc.add_argument(
        "--max-requests-per-file",
        type=int,
        default=30_000,
        help="Max requests per JSONL file (hard max 50k).",
    )
    pc.add_argument(
        "--max-mb-per-file",
        type=int,
        default=190,
        help="Max MB per JSONL file (hard max 200).",
    )
    pc.add_argument(
        "--use-keyword-snippets",
        action="store_true",
        help="Include EQUITY_KEYWORD_SNIPPETS in the prompt (slower, larger requests). Default: off.",
    )

    pr = sub.add_parser("prepare-retry", help="Prepare Batch inputs to retry failed requests from a prior run.")
    pr.add_argument(
        "--previous-input-dir",
        type=Path,
        required=True,
        help="Prior run folder containing batch_*.jsonl (e.g. .../llm_batch_inputs/.../run_...).",
    )
    pr.add_argument(
        "--previous-output-dir",
        type=Path,
        required=True,
        help="Folder containing downloaded *_error.jsonl files for the prior run.",
    )
    pr.add_argument("--out-dir", type=Path, default=None, help="Output directory (default: auto timestamped).")
    pr.add_argument(
        "--max-requests-per-file",
        type=int,
        default=30_000,
        help="Max requests per JSONL file (hard max 50k).",
    )
    pr.add_argument(
        "--max-mb-per-file",
        type=int,
        default=190,
        help="Max MB per JSONL file (hard max 200).",
    )

    rd = sub.add_parser("rechunk-dir", help="Split existing batch_*.jsonl files into smaller batch_*.jsonl files.")
    rd.add_argument("--input-dir", type=Path, required=True, help="Directory containing batch_*.jsonl to split.")
    rd.add_argument("--out-dir", type=Path, default=None, help="Output directory (default: auto timestamped).")
    rd.add_argument(
        "--max-requests-per-file",
        type=int,
        default=30_000,
        help="Max requests per JSONL file (hard max 50k).",
    )
    rd.add_argument(
        "--max-mb-per-file",
        type=int,
        default=190,
        help="Max MB per JSONL file (hard max 200).",
    )

    ps = sub.add_parser("submit", help="Upload one JSONL file and create a Batch.")
    ps.add_argument("--input-jsonl", type=Path, required=True, help="One JSONL produced by 'prepare'.")
    ps.add_argument("--tag", type=str, default="", help="Optional metadata tag (stored on the batch).")

    psd = sub.add_parser("submit-dir", help="Submit every batch_*.jsonl in a directory (resume-safe).")
    psd.add_argument("--input-dir", type=Path, required=True, help="Directory containing batch_*.jsonl.")
    psd.add_argument("--tag", type=str, default="", help="Optional metadata tag (stored on the batch).")
    psd.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.25,
        help="Optional delay between submissions to reduce rate-limit risk (default: %(default)s).",
    )
    psd.add_argument(
        "--max-active-batches",
        type=int,
        default=0,
        help=(
            "If >0, throttle submissions so that at most this many batches are active "
            "(validating/in_progress/finalizing/cancelling) at once. This helps avoid "
            "token_limit_exceeded failures on orgs with low enqueued-token limits. "
            "Default: 0 (no throttling)."
        ),
    )
    psd.add_argument(
        "--poll-seconds",
        type=float,
        default=30.0,
        help="When throttling is enabled, sleep this many seconds between status polls (default: %(default)s).",
    )
    psd.add_argument(
        "--stop-after",
        type=int,
        default=0,
        help="Optional limit on how many new batches to submit in this run (0=all). Useful for testing.",
    )

    pt = sub.add_parser("status", help="Fetch batch status as JSON.")
    pt.add_argument("--batch-id", type=str, required=True)

    ptd = sub.add_parser("status-dir", help="Fetch status for every batch in a run folder.")
    ptd.add_argument("--input-dir", type=Path, required=True, help="Directory containing submit_dir_manifest.json.")
    ptd.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.25,
        help="Optional delay between API calls (default: %(default)s).",
    )

    pd = sub.add_parser("download", help="Download output/error JSONL for a batch.")
    pd.add_argument("--batch-id", type=str, required=True)
    pd.add_argument("--out-dir", type=Path, required=True, help="Directory to write downloaded files.")

    pdd = sub.add_parser("download-dir", help="Download output/error JSONL for every batch in a run folder.")
    pdd.add_argument("--input-dir", type=Path, required=True, help="Run folder containing submit_dir_manifest.json.")
    pdd.add_argument("--out-dir", type=Path, required=True, help="Directory to write downloaded files.")
    pdd.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.25,
        help="Optional delay between downloads (default: %(default)s).",
    )
    pdd.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip batches whose output/error already exists in out-dir.",
    )

    return p.parse_args()


def main() -> None:
    args = parse_args()
    config_yaml: Optional[Path] = args.config_yaml

    if args.cmd == "prepare":
        input_csv: Path = args.input_csv
        out_dir: Optional[Path] = args.out_dir
        if out_dir is None:
            out_dir = default_out_dir_for_input(input_csv=input_csv)
        prepare_batch_inputs(
            input_csv=input_csv,
            out_dir=out_dir,
            model=str(args.model),
            include_empty=bool(args.include_empty),
            max_rows=int(args.max_rows),
            max_requests_per_file=int(args.max_requests_per_file),
            max_mb_per_file=int(args.max_mb_per_file),
            use_keyword_snippets=bool(args.use_keyword_snippets),
        )
        return

    if args.cmd == "prepare-candidates":
        candidates_parquet: Path = args.candidates_parquet
        out_dir: Optional[Path] = args.out_dir
        if out_dir is None:
            ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
            out_dir = (
                RESULTS_RAW
                / "postings_description_equity"
                / "llm_batch_inputs"
                / "equity_candidates"
                / f"run_{ts}"
            )
        prepare_batch_inputs_from_candidates_parquet(
            candidates_parquet=candidates_parquet,
            out_dir=out_dir,
            model=str(args.model),
            max_rows=int(args.max_rows),
            max_requests_per_file=int(args.max_requests_per_file),
            max_mb_per_file=int(args.max_mb_per_file),
            use_keyword_snippets=bool(args.use_keyword_snippets),
        )
        return

    if args.cmd == "prepare-retry":
        prev_in: Path = args.previous_input_dir
        prev_out: Path = args.previous_output_dir
        out_dir: Optional[Path] = args.out_dir
        if out_dir is None:
            ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
            out_dir = (
                RESULTS_RAW
                / "postings_description_equity"
                / "llm_batch_inputs"
                / "equity_candidates"
                / f"retry_{Path(prev_in).name}_{ts}"
            )
        prepare_retry_inputs(
            previous_input_dir=prev_in,
            previous_output_dir=prev_out,
            out_dir=out_dir,
            max_requests_per_file=int(args.max_requests_per_file),
            max_mb_per_file=int(args.max_mb_per_file),
        )
        return

    if args.cmd == "rechunk-dir":
        input_dir: Path = args.input_dir
        out_dir: Optional[Path] = args.out_dir
        if out_dir is None:
            ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
            out_dir = (
                RESULTS_RAW
                / "postings_description_equity"
                / "llm_batch_inputs"
                / "equity_candidates"
                / f"rechunk_{Path(input_dir).name}_{ts}"
            )
        rechunk_dir(
            input_dir=input_dir,
            out_dir=out_dir,
            max_requests_per_file=int(args.max_requests_per_file),
            max_mb_per_file=int(args.max_mb_per_file),
        )
        return

    if args.cmd == "submit":
        batch_id = submit_batch(
            input_jsonl=args.input_jsonl,
            metadata={k: v for k, v in {"tag": args.tag}.items() if v},
            config_yaml=config_yaml,
        )
        print(batch_id)
        return

    if args.cmd == "submit-dir":
        batch_ids = submit_dir(
            input_dir=args.input_dir,
            tag=str(args.tag),
            config_yaml=config_yaml,
            sleep_seconds=float(args.sleep_seconds),
            max_active_batches=int(args.max_active_batches),
            poll_seconds=float(args.poll_seconds),
            stop_after=int(args.stop_after),
        )
        print(json.dumps(batch_ids))
        return

    if args.cmd == "status":
        dumped = batch_status(batch_id=str(args.batch_id), config_yaml=config_yaml)
        print(json.dumps(dumped, indent=2, ensure_ascii=False))
        return

    if args.cmd == "status-dir":
        dumped = status_dir(
            input_dir=args.input_dir,
            config_yaml=config_yaml,
            sleep_seconds=float(args.sleep_seconds),
        )
        print(json.dumps(dumped, indent=2, ensure_ascii=False))
        return

    if args.cmd == "download":
        download_batch_outputs(batch_id=str(args.batch_id), out_dir=args.out_dir, config_yaml=config_yaml)
        return

    if args.cmd == "download-dir":
        dumped = download_dir(
            input_dir=args.input_dir,
            out_dir=args.out_dir,
            config_yaml=config_yaml,
            sleep_seconds=float(args.sleep_seconds),
            skip_existing=bool(args.skip_existing),
        )
        print(json.dumps(dumped, indent=2, ensure_ascii=False))
        return

    raise RuntimeError(f"Unhandled cmd: {args.cmd}")


if __name__ == "__main__":
    main()
