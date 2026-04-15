#!/usr/bin/env python3
"""
Materialize JSONL LLM outputs into a "run folder" layout:
  - prompt files copied in
  - one JSON file per output line
  - a manifest.json for easy indexing

This is meant to make inspection / sharing easy without scrolling JSONL.

Example
-------
python main/src/py/materialize_llm_run_folder.py \
  --examples-dir main/results/raw/postings_description_equity/llm_examples \
  --model gpt-5-nano
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OutputLine:
    job_id: str
    tags: List[str]
    extraction: Dict[str, Any]


def _outer_repo_root_from_layout() -> Path:
    here = Path(__file__).resolve()
    outer = here.parents[3]
    if not (outer / "main").exists():
        raise RuntimeError(f"Expected outer repo root to contain main/: {outer}")
    return outer


def default_examples_dir() -> Path:
    outer = _outer_repo_root_from_layout()
    return outer / "main" / "results" / "raw" / "postings_description_equity" / "llm_examples"


def default_runs_dir() -> Path:
    outer = _outer_repo_root_from_layout()
    return outer / "main" / "results" / "raw" / "postings_description_equity" / "llm_runs"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--examples-dir",
        type=Path,
        default=default_examples_dir(),
        help="Directory containing prompt_*.txt and sample_outputs.jsonl (default: %(default)s).",
    )
    p.add_argument(
        "--runs-dir",
        type=Path,
        default=default_runs_dir(),
        help="Base directory where the run folder is created (default: %(default)s).",
    )
    p.add_argument(
        "--run-name",
        type=str,
        default="",
        help="Optional run folder name. If omitted, a timestamped name is generated.",
    )
    p.add_argument(
        "--model",
        type=str,
        default="",
        help="Optional model name to record in manifest.json (e.g. gpt-5-nano).",
    )
    return p.parse_args()


def _read_outputs_jsonl(path: Path) -> List[OutputLine]:
    out: List[OutputLine] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            job_id = str(obj.get("job_id", "")).strip()
            if not job_id:
                raise ValueError(f"{path}:{line_no}: missing job_id")
            tags_raw = obj.get("tags") or []
            tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else [str(tags_raw)]
            extraction = obj.get("extraction")
            if not isinstance(extraction, dict):
                raise ValueError(f"{path}:{line_no}: missing/invalid extraction object")
            out.append(OutputLine(job_id=job_id, tags=tags, extraction=extraction))
    if not out:
        raise RuntimeError(f"No outputs found in {path}")
    return out


def _copy_if_exists(src: Path, dst: Path) -> Optional[Path]:
    if not src.exists():
        return None
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def main() -> None:
    args = parse_args()
    examples_dir: Path = args.examples_dir.expanduser().resolve()
    runs_dir: Path = args.runs_dir.expanduser().resolve()

    if not examples_dir.exists():
        raise FileNotFoundError(f"examples_dir not found: {examples_dir}")

    prompt_system = examples_dir / "prompt_system.txt"
    prompt_user_template = examples_dir / "prompt_user_template.txt"
    sample_inputs = examples_dir / "sample_inputs.jsonl"
    sample_outputs = examples_dir / "sample_outputs.jsonl"

    if not sample_outputs.exists():
        raise FileNotFoundError(f"Missing: {sample_outputs}")

    outputs = _read_outputs_jsonl(sample_outputs)
    n = len(outputs)

    created_at = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_name = args.run_name.strip()
    if not run_name:
        model_part = args.model.strip().replace("/", "-") if args.model else "unknown-model"
        run_name = f"run_{created_at}_{model_part}_n{n}"

    run_dir = runs_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=False)

    # Copy prompt + the raw JSONL files for provenance.
    _copy_if_exists(prompt_system, run_dir / "prompt_system.txt")
    _copy_if_exists(prompt_user_template, run_dir / "prompt_user_template.txt")
    _copy_if_exists(sample_inputs, run_dir / "sample_inputs.jsonl")
    _copy_if_exists(sample_outputs, run_dir / "sample_outputs.jsonl")

    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=False)

    manifest_outputs: List[Dict[str, Any]] = []
    for idx, item in enumerate(outputs, start=1):
        fname = f"output_{idx:03d}_job_{item.job_id}.json"
        out_path = outputs_dir / fname
        payload = {
            "job_id": item.job_id,
            "tags": item.tags,
            "extraction": item.extraction,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest_outputs.append(
            {
                "job_id": item.job_id,
                "tags": item.tags,
                "file": f"outputs/{fname}",
            }
        )

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model or None,
        "source_examples_dir": str(examples_dir),
        "n_outputs": n,
        "files": {
            "prompt_system": "prompt_system.txt" if prompt_system.exists() else None,
            "prompt_user_template": "prompt_user_template.txt" if prompt_user_template.exists() else None,
            "sample_inputs_jsonl": "sample_inputs.jsonl" if sample_inputs.exists() else None,
            "sample_outputs_jsonl": "sample_outputs.jsonl",
        },
        "outputs": manifest_outputs,
    }

    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Created run folder:", run_dir)
    print("Outputs:", outputs_dir)


if __name__ == "__main__":
    main()

