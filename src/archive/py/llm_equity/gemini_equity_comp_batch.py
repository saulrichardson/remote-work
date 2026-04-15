#!/usr/bin/env python3
"""
Prepare and submit Gemini Batch jobs for equity-compensation extraction on job postings.

This mirrors the OpenAI Batch workflow in `src/py/llm_equity_comp_batch.py`, but targets
Google's Gemini Batch API via the official `google-genai` client.

Inputs (recommended)
--------------------
Use a pre-filtered candidate parquet produced by:
  - src/py/extract_equity_postings_candidates.py

or any parquet with at least:
  - job_id, company_cleaned, post_date, title, description

Outputs
-------
prepare-candidates writes a directory containing:
  - gemini_requests_shardNNN.jsonl
  - mapping_shardNNN.jsonl
  - prepare_manifest.json

submit-dir uploads each shard request file and creates one Gemini Batch job per shard, writing:
  - submitted_gemini_batches.jsonl   (append-only; resumable)

Notes
-----
- We do NOT print or persist the Gemini API key.
- Gemini Batch request JSONL format expected by the GenAI Batch API is:
    {"key": "...", "request": {"contents": [...], ...}}
- Unlike synchronous `client.models.generate_content(..., config=...)`, Batch requests do not
  accept a top-level `config` field. Instead, we pass generation controls via `generation_config`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

import duckdb
import pandas as pd

# Reuse the extraction schema + prompts from the OpenAI example script to avoid drift.
import llm_equity_comp_examples as equity_examples


DEFAULT_MODEL = "models/gemini-2.5-flash"

# Conservative shard sizing. The Gemini batch file size limits vary by project; keep comfortably below ~200MB.
DEFAULT_MAX_REQUESTS_PER_SHARD = 8_000
DEFAULT_MAX_MB_PER_SHARD = 150


@dataclass(frozen=True)
class PostingRow:
    job_id: str
    company_cleaned: str
    post_date: str
    title: str
    description: str


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


def _normalize_job_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    # Strip Stata-style numeric formatting artifacts (e.g. "123.0").
    s = re.sub(r"\.0+$", "", s)
    return s or None


def iter_postings_from_parquet(
    *,
    con: duckdb.DuckDBPyConnection,
    parquet_path: Path,
    max_rows: int,
) -> Iterator[PostingRow]:
    parquet_path = parquet_path.expanduser().resolve()
    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing parquet: {parquet_path}")

    limit = "" if not max_rows else f"LIMIT {int(max_rows)}"
    query = f"""
    SELECT
      cast(job_id as varchar) as job_id,
      cast(coalesce(company_cleaned, '') as varchar) as company_cleaned,
      cast(coalesce(post_date, '') as varchar) as post_date,
      cast(coalesce(title, '') as varchar) as title,
      cast(coalesce(description, '') as varchar) as description
    FROM parquet_scan({_sql_quote_literal(parquet_path.as_posix())})
    {limit}
    """
    cur = con.execute(query)
    chunk = 10_000
    while True:
        rows = cur.fetchmany(chunk)
        if not rows:
            break
        for job_id, company_cleaned, post_date, title, description in rows:
            jid = _normalize_job_id(job_id)
            if not jid:
                continue
            desc = str(description or "")
            if not desc.strip():
                # We skip empty descriptions: there's no text to extract from.
                continue
            yield PostingRow(
                job_id=jid,
                company_cleaned=str(company_cleaned or ""),
                post_date=str(post_date or ""),
                title=str(title or ""),
                description=desc,
            )


def _build_prompt(row: PostingRow) -> str:
    # For batch requests we embed the "system prompt" into the user message. We still
    # also use JSON-lock output controls via generation_config (response_mime_type + schema).
    return equity_examples.system_prompt() + "\n\n" + equity_examples.user_prompt_template().format(
        job_id=row.job_id,
        company_cleaned=row.company_cleaned,
        post_date=row.post_date,
        title=row.title,
        keyword_snippets="",
        description=row.description,
    )


def _request_line(
    *,
    key: str,
    prompt: str,
    schema: Dict[str, Any],
    max_output_tokens: int,
) -> Dict[str, Any]:
    return {
        "key": key,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generation_config": {
                # Determinism + JSON lock.
                "temperature": 0,
                "response_mime_type": "application/json",
                "response_json_schema": schema,
                # Avoid spending output budget on hidden thoughts that can truncate JSON.
                "thinking_config": {"thinking_budget": 0},
                "max_output_tokens": int(max_output_tokens),
            },
        },
    }


def _write_jsonl_line(handle, obj: Dict[str, Any]) -> int:
    s = json.dumps(obj, ensure_ascii=False) + "\n"
    handle.write(s)
    return len(s.encode("utf-8"))


def prepare_candidates(
    *,
    candidates_parquet: Path,
    out_dir: Path,
    max_rows: int,
    max_requests_per_shard: int,
    max_mb_per_shard: int,
    max_output_tokens: int,
) -> Dict[str, Any]:
    if max_requests_per_shard <= 0:
        raise ValueError("--max-requests-per-shard must be > 0")
    if max_mb_per_shard <= 0:
        raise ValueError("--max-mb-per-shard must be > 0")

    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    schema = equity_examples.json_schema()["schema"]
    con = _connect_duckdb()
    try:
        rows = iter_postings_from_parquet(con=con, parquet_path=candidates_parquet, max_rows=max_rows)

        shard_idx = 0
        n_in = 0
        n_written = 0
        bytes_written = 0

        req_f = None
        map_f = None
        req_path = None
        map_path = None
        req_bytes = 0
        req_lines = 0

        def open_shard(i: int) -> Tuple[Any, Any, Path, Path]:
            rp = out_dir / f"gemini_requests_shard{i:03d}.jsonl"
            mp = out_dir / f"mapping_shard{i:03d}.jsonl"
            return rp.open("w", encoding="utf-8"), mp.open("w", encoding="utf-8"), rp, mp

        def close_shard() -> None:
            nonlocal req_f, map_f
            if req_f is not None:
                req_f.close()
            if map_f is not None:
                map_f.close()

        req_f, map_f, req_path, map_path = open_shard(shard_idx)

        max_bytes = int(max_mb_per_shard) * 1024 * 1024
        t0 = time.time()

        for row_idx, row in enumerate(rows, start=1):
            n_in += 1
            key = f"equity_missing__row_{row_idx:09d}__job_{row.job_id}"
            prompt = _build_prompt(row)
            req_obj = _request_line(
                key=key, prompt=prompt, schema=schema, max_output_tokens=int(max_output_tokens)
            )
            map_obj = {
                "key": key,
                "job_id": row.job_id,
                "company_cleaned": row.company_cleaned,
                "post_date": row.post_date,
            }

            # Pre-compute bytes to enforce shard size (requests file only).
            line_s = json.dumps(req_obj, ensure_ascii=False) + "\n"
            line_bytes = len(line_s.encode("utf-8"))

            should_roll = False
            if req_lines >= int(max_requests_per_shard):
                should_roll = True
            if req_bytes > 0 and (req_bytes + line_bytes > max_bytes):
                should_roll = True

            if should_roll:
                close_shard()
                shard_idx += 1
                req_lines = 0
                req_bytes = 0
                req_f, map_f, req_path, map_path = open_shard(shard_idx)

            assert req_f is not None and map_f is not None
            req_f.write(line_s)
            map_bytes = _write_jsonl_line(map_f, map_obj)

            req_lines += 1
            req_bytes += line_bytes
            n_written += 1
            bytes_written += line_bytes + map_bytes

            if n_written % 10_000 == 0:
                dt = time.time() - t0
                print(f"[prepare] written={n_written:,} shards={shard_idx+1} elapsed_s={dt:,.1f}")

        close_shard()

        meta = {
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {
                "candidates_parquet": str(Path(candidates_parquet).expanduser().resolve()),
                "max_rows": int(max_rows),
            },
            "model": DEFAULT_MODEL,
            "generation_config": {
                "temperature": 0,
                "response_mime_type": "application/json",
                "max_output_tokens": int(max_output_tokens),
                "thinking_config": {"thinking_budget": 0},
            },
            "limits": {
                "max_requests_per_shard": int(max_requests_per_shard),
                "max_mb_per_shard": int(max_mb_per_shard),
            },
            "totals": {
                "input_rows_seen": int(n_in),
                "requests_written": int(n_written),
                "approx_bytes_written": int(bytes_written),
                "n_shards": int(shard_idx + 1),
            },
        }
        (out_dir / "prepare_manifest.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"[prepare] wrote shards → {out_dir} (requests={n_written:,} shards={shard_idx+1})")
        return meta
    finally:
        con.close()


def _parse_env_file(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def require_gemini_key(*, env_file: Optional[Path]) -> str:
    # Env wins.
    for name in ("GEMINI_KEY", "GEMINI_API_KEY"):
        val = os.environ.get(name)
        if val and val.strip():
            return val.strip()
    if env_file is not None:
        env = _parse_env_file(env_file)
        for name in ("GEMINI_KEY", "GEMINI_API_KEY"):
            val = env.get(name)
            if val and val.strip():
                return val.strip()
    raise RuntimeError("Missing Gemini API key. Set GEMINI_KEY in env or pass --env-file containing GEMINI_KEY=...")


def submit_dir(
    *,
    input_dir: Path,
    model: str,
    display_name_prefix: str,
    env_file: Optional[Path],
    dry_run: bool,
) -> List[Dict[str, Any]]:
    input_dir = input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"--input-dir is not a directory: {input_dir}")

    request_paths: Dict[int, Path] = {}
    mapping_paths: Dict[int, Path] = {}
    for p in input_dir.glob("gemini_requests_shard*.jsonl"):
        token = p.name.removeprefix("gemini_requests_shard").removesuffix(".jsonl")
        if token.isdigit():
            request_paths[int(token)] = p
    for p in input_dir.glob("mapping_shard*.jsonl"):
        token = p.name.removeprefix("mapping_shard").removesuffix(".jsonl")
        if token.isdigit():
            mapping_paths[int(token)] = p

    shards = sorted(set(request_paths) & set(mapping_paths))
    if not shards:
        raise RuntimeError(f"No shard pairs found in {input_dir} (expected gemini_requests_shard*.jsonl + mapping_shard*.jsonl)")

    record_path = input_dir / "submitted_gemini_batches.jsonl"
    existing: set[int] = set()
    if record_path.exists():
        for raw in record_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("provider") == "gemini" and isinstance(obj.get("shard"), int):
                existing.add(int(obj["shard"]))

    if dry_run:
        print(f"[submit-dir] dry-run: would submit {len(shards) - len(existing)} shards (skip_existing={len(existing)})")
        return []

    key = require_gemini_key(env_file=env_file)
    from google import genai  # imported late so the script is importable without deps
    from google.genai.types import UploadFileConfig  # type: ignore

    client = genai.Client(api_key=key)
    submitted: List[Dict[str, Any]] = []

    def append_record(obj: Dict[str, Any]) -> None:
        with record_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    for shard in shards:
        if shard in existing:
            print(f"[submit-dir] skip shard={shard:03d} (already in {record_path.name})")
            continue

        req_path = request_paths[shard]
        display = f"{str(display_name_prefix).strip()}-shard{shard:03d}"
        print(f"[submit-dir] submit_start shard={shard:03d} file={req_path.name} model={model} display_name={display}")

        t0 = time.time()
        req_file = client.files.upload(file=req_path, config=UploadFileConfig(mime_type="application/jsonl"))
        batch = client.batches.create(model=str(model), src={"file_name": req_file.name}, config={"display_name": display})
        elapsed = round(time.time() - t0, 2)

        rec = {
            "provider": "gemini",
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "shard": int(shard),
            "display_name": display,
            "input_dir": str(input_dir),
            "requests_path": str(req_path),
            "mapping_path": str(mapping_paths[shard]),
            "model": str(model),
            "elapsed_seconds": float(elapsed),
            "uploaded_file_name": getattr(req_file, "name", ""),
            "batch_name": getattr(batch, "name", ""),
            "batch_state": str(getattr(batch, "state", "")),
        }
        append_record(rec)
        submitted.append(rec)
        print(f"[submit-dir] submit_ok shard={shard:03d} batch_name={rec['batch_name']} state={rec['batch_state']}")

    return submitted


def status_dir(
    *,
    input_dir: Path,
    env_file: Optional[Path],
    sleep_seconds: float,
) -> Dict[str, Any]:
    input_dir = input_dir.expanduser().resolve()
    record_path = input_dir / "submitted_gemini_batches.jsonl"
    if not record_path.exists():
        raise FileNotFoundError(f"Missing submission record: {record_path}")

    batches: Dict[int, Dict[str, Any]] = {}
    for raw in record_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("provider") != "gemini":
            continue
        shard = obj.get("shard")
        name = obj.get("batch_name")
        if isinstance(shard, int) and isinstance(name, str) and name:
            batches[shard] = obj

    if not batches:
        raise RuntimeError(f"Found 0 Gemini batch records in {record_path}")

    key = require_gemini_key(env_file=env_file)
    from google import genai  # imported late

    client = genai.Client(api_key=key)
    out_batches: List[Dict[str, Any]] = []
    status_counts: Dict[str, int] = {}

    for shard in sorted(batches):
        name = str(batches[shard]["batch_name"])
        try:
            job = client.batches.get(name=name)
            state = str(getattr(job, "state", ""))
            dest = getattr(job, "dest", None)
            dest_file_name = getattr(dest, "file_name", None) if dest else None
            err = None
        except Exception as exc:  # noqa: BLE001
            state = "error"
            dest_file_name = None
            err = str(exc)

        out_batches.append(
            {
                "shard": int(shard),
                "batch_name": name,
                "state": state,
                "dest_file_name": dest_file_name,
                "error": err,
            }
        )
        status_counts[state] = int(status_counts.get(state, 0)) + 1
        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

    out = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_dir": str(input_dir),
        "status_counts": status_counts,
        "batches": out_batches,
    }
    out_path = input_dir / "status_dir_summary.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("[status-dir] wrote:", out_path)
    return out


def download_dir(
    *,
    input_dir: Path,
    out_dir: Path,
    env_file: Optional[Path],
    skip_existing: bool,
    sleep_seconds: float,
) -> Dict[str, Any]:
    input_dir = input_dir.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    record_path = input_dir / "submitted_gemini_batches.jsonl"
    if not record_path.exists():
        raise FileNotFoundError(f"Missing submission record: {record_path}")

    batches: Dict[int, Dict[str, Any]] = {}
    for raw in record_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("provider") != "gemini":
            continue
        shard = obj.get("shard")
        name = obj.get("batch_name")
        if isinstance(shard, int) and isinstance(name, str) and name:
            batches[shard] = obj

    if not batches:
        raise RuntimeError(f"Found 0 Gemini batch records in {record_path}")

    key = require_gemini_key(env_file=env_file)
    from google import genai  # imported late

    client = genai.Client(api_key=key)

    downloaded = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []
    for shard in sorted(batches):
        out_path = out_dir / f"gemini_results_shard{shard:03d}.jsonl"
        if skip_existing and out_path.exists():
            skipped += 1
            continue

        name = str(batches[shard]["batch_name"])
        job = client.batches.get(name=name)
        state = str(getattr(job, "state", ""))
        if not state.endswith("SUCCEEDED"):
            continue

        dest = getattr(job, "dest", None)
        file_name = getattr(dest, "file_name", None) if dest else None
        if not file_name:
            errors.append({"shard": int(shard), "batch_name": name, "error": "missing dest.file_name"})
            continue

        try:
            blob = client.files.download(file=file_name)
        except Exception as exc:  # noqa: BLE001
            errors.append({"shard": int(shard), "batch_name": name, "error": str(exc)})
            continue

        out_path.write_bytes(blob)
        downloaded += 1
        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

    summary = {"downloaded": downloaded, "skipped": skipped, "errors": errors}
    (out_dir / "download_dir_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("[download-dir] wrote:", out_dir / "download_dir_summary.json")
    return summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("prepare-candidates", help="Prepare Gemini batch request shards from a candidates parquet.")
    pc.add_argument("--candidates-parquet", type=Path, required=True)
    pc.add_argument("--out-dir", type=Path, required=True)
    pc.add_argument("--max-rows", type=int, default=0, help="Optional cap for testing (0=all).")
    pc.add_argument(
        "--max-requests-per-shard",
        type=int,
        default=DEFAULT_MAX_REQUESTS_PER_SHARD,
        help="Max requests per shard file.",
    )
    pc.add_argument(
        "--max-mb-per-shard",
        type=int,
        default=DEFAULT_MAX_MB_PER_SHARD,
        help="Max MB per shard request file.",
    )
    pc.add_argument(
        "--max-output-tokens",
        type=int,
        default=2048,
        help="Gemini max_output_tokens per request (default: %(default)s).",
    )

    ps = sub.add_parser("submit-dir", help="Submit every gemini_requests_shard*.jsonl in a directory.")
    ps.add_argument("--input-dir", type=Path, required=True)
    ps.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Gemini model (default: %(default)s).")
    ps.add_argument("--display-name-prefix", type=str, default="equity-comp", help="Gemini display_name prefix.")
    ps.add_argument(
        "--env-file",
        type=Path,
        default=Path("/Users/saulrichardson/Projects/newspapers/newspaper-analysis/.env"),
        help="Optional .env file containing GEMINI_KEY (default: %(default)s).",
    )
    ps.add_argument("--dry-run", action="store_true")

    pst = sub.add_parser("status-dir", help="Fetch Gemini batch status for a prepared run directory.")
    pst.add_argument("--input-dir", type=Path, required=True)
    pst.add_argument(
        "--env-file",
        type=Path,
        default=Path("/Users/saulrichardson/Projects/newspapers/newspaper-analysis/.env"),
        help="Optional .env file containing GEMINI_KEY (default: %(default)s).",
    )
    pst.add_argument("--sleep-seconds", type=float, default=0.25)

    pdn = sub.add_parser("download-dir", help="Download succeeded Gemini batch outputs for a run directory.")
    pdn.add_argument("--input-dir", type=Path, required=True)
    pdn.add_argument("--out-dir", type=Path, required=True)
    pdn.add_argument(
        "--env-file",
        type=Path,
        default=Path("/Users/saulrichardson/Projects/newspapers/newspaper-analysis/.env"),
        help="Optional .env file containing GEMINI_KEY (default: %(default)s).",
    )
    pdn.add_argument("--skip-existing", action="store_true")
    pdn.add_argument("--sleep-seconds", type=float, default=0.25)

    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.cmd == "prepare-candidates":
        prepare_candidates(
            candidates_parquet=args.candidates_parquet,
            out_dir=args.out_dir,
            max_rows=int(args.max_rows),
            max_requests_per_shard=int(args.max_requests_per_shard),
            max_mb_per_shard=int(args.max_mb_per_shard),
            max_output_tokens=int(args.max_output_tokens),
        )
        return

    if args.cmd == "submit-dir":
        env_file = args.env_file.expanduser().resolve() if args.env_file else None
        submit_dir(
            input_dir=args.input_dir,
            model=str(args.model),
            display_name_prefix=str(args.display_name_prefix),
            env_file=env_file,
            dry_run=bool(args.dry_run),
        )
        return

    if args.cmd == "status-dir":
        env_file = args.env_file.expanduser().resolve() if args.env_file else None
        status_dir(input_dir=args.input_dir, env_file=env_file, sleep_seconds=float(args.sleep_seconds))
        return

    if args.cmd == "download-dir":
        env_file = args.env_file.expanduser().resolve() if args.env_file else None
        download_dir(
            input_dir=args.input_dir,
            out_dir=args.out_dir,
            env_file=env_file,
            skip_existing=bool(args.skip_existing),
            sleep_seconds=float(args.sleep_seconds),
        )
        return

    raise RuntimeError(f"Unhandled cmd: {args.cmd}")


if __name__ == "__main__":
    main()
