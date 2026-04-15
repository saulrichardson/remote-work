#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


ACTIVE_BATCH_STATUSES = {"validating", "in_progress", "finalizing", "cancelling"}
FAILED_BATCH_STATUSES = {"failed", "cancelled", "expired"}
SCRIPT_NAME = "llm_equity_comp_batch.py"


@dataclass
class RunSnapshot:
    run_input_dir: Path
    run_download_dir: Path
    total_batch_files: int
    submitted_batch_files: int
    status_counts: Dict[str, int]
    request_totals: Dict[str, int]
    failed_batch_ids: List[str]

    @property
    def active_batches(self) -> int:
        return sum(int(self.status_counts.get(status, 0)) for status in ACTIVE_BATCH_STATUSES)

    @property
    def failed_batches(self) -> int:
        failed = sum(int(self.status_counts.get(status, 0)) for status in FAILED_BATCH_STATUSES)
        failed += int(self.status_counts.get("error", 0))
        return failed

    @property
    def completed_batches(self) -> int:
        return int(self.status_counts.get("completed", 0))


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def timestamp_slug() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_log(log_path: Path, line: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(line.rstrip() + "\n")


def shell_join(cmd: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def run_logged(cmd: List[str], *, cwd: Path, log_path: Path) -> subprocess.CompletedProcess[str]:
    append_log(log_path, f"[{utc_now()}] RUN {shell_join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if proc.stdout:
        append_log(log_path, proc.stdout.rstrip("\n"))
    if proc.stderr:
        append_log(log_path, proc.stderr.rstrip("\n"))
    append_log(log_path, f"[{utc_now()}] EXIT {proc.returncode}")
    return proc


def spawn_logged(cmd: List[str], *, cwd: Path, log_path: Path) -> subprocess.Popen[Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{utc_now()}] SPAWN {shell_join(cmd)}\n")
    log_stream = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        text=True,
        close_fds=True,
    )
    return process


def pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def count_files(directory: Path, pattern: str) -> int:
    return sum(1 for _ in directory.glob(pattern))


def load_submitter_pid(pid_path: Path) -> Optional[int]:
    if not pid_path.exists():
        return None
    try:
        payload = read_json(pid_path)
    except Exception:
        return None
    pid = payload.get("pid")
    if isinstance(pid, int) and pid > 0 and pid_is_alive(pid):
        return pid
    return None


def save_submitter_pid(pid_path: Path, *, pid: int, log_path: Path, run_input_dir: Path) -> None:
    write_json(
        pid_path,
        {
            "created_at_utc": utc_now(),
            "pid": int(pid),
            "log_path": str(log_path),
            "run_input_dir": str(run_input_dir),
        },
    )


def refresh_status(*, repo_root: Path, config_yaml: Path, run_input_dir: Path, log_path: Path) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        f"src/py/{SCRIPT_NAME}",
        "--config-yaml",
        str(config_yaml),
        "status-dir",
        "--input-dir",
        str(run_input_dir),
        "--sleep-seconds",
        "0.0",
    ]
    proc = run_logged(cmd, cwd=repo_root, log_path=log_path)
    if proc.returncode != 0:
        raise RuntimeError(f"status-dir failed for {run_input_dir}")
    summary_path = run_input_dir / "status_dir_summary.json"
    if not summary_path.exists():
        raise RuntimeError(f"status_dir_summary.json missing under {run_input_dir}")
    return read_json(summary_path)


def refresh_downloads(
    *,
    repo_root: Path,
    config_yaml: Path,
    run_input_dir: Path,
    run_download_dir: Path,
    download_sleep_seconds: float,
    log_path: Path,
) -> None:
    run_download_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        f"src/py/{SCRIPT_NAME}",
        "--config-yaml",
        str(config_yaml),
        "download-dir",
        "--input-dir",
        str(run_input_dir),
        "--out-dir",
        str(run_download_dir),
        "--sleep-seconds",
        str(download_sleep_seconds),
        "--skip-existing",
    ]
    proc = run_logged(cmd, cwd=repo_root, log_path=log_path)
    if proc.returncode != 0:
        raise RuntimeError(f"download-dir failed for {run_input_dir}")


def ensure_submitter(
    *,
    repo_root: Path,
    config_yaml: Path,
    run_input_dir: Path,
    tag: str,
    max_active_batches: int,
    submit_poll_seconds: float,
    supervisor_log_path: Path,
) -> Optional[int]:
    total_files = count_files(run_input_dir, "batch_*.jsonl")
    submitted_files = count_files(run_input_dir, "submission_*.json")
    if total_files == 0:
        raise RuntimeError(f"No batch_*.jsonl files found under {run_input_dir}")
    if submitted_files >= total_files:
        return None

    pid_path = run_input_dir / ".submitter_pid.json"
    existing_pid = load_submitter_pid(pid_path)
    if existing_pid is not None:
        return existing_pid

    submit_log_path = run_input_dir / f"submit_dir_supervisor_{timestamp_slug()}.log"
    cmd = [
        sys.executable,
        f"src/py/{SCRIPT_NAME}",
        "--config-yaml",
        str(config_yaml),
        "submit-dir",
        "--input-dir",
        str(run_input_dir),
        "--tag",
        tag,
        "--max-active-batches",
        str(max_active_batches),
        "--poll-seconds",
        str(submit_poll_seconds),
    ]
    process = spawn_logged(cmd, cwd=repo_root, log_path=submit_log_path)
    save_submitter_pid(pid_path, pid=process.pid, log_path=submit_log_path, run_input_dir=run_input_dir)
    append_log(
        supervisor_log_path,
        f"[{utc_now()}] submitter-started pid={process.pid} input_dir={run_input_dir} log={submit_log_path}",
    )
    return process.pid


def collect_failed_batch_ids(status_summary: Dict[str, Any]) -> List[str]:
    failed_ids: List[str] = []
    for batch in status_summary.get("batches", []):
        if not isinstance(batch, dict):
            continue
        status = batch.get("status")
        batch_id = batch.get("batch_id")
        if isinstance(status, str) and isinstance(batch_id, str):
            if status in FAILED_BATCH_STATUSES:
                failed_ids.append(batch_id)
    return failed_ids


def build_snapshot(
    *,
    run_input_dir: Path,
    run_download_dir: Path,
    status_summary: Dict[str, Any],
) -> RunSnapshot:
    total_batch_files = count_files(run_input_dir, "batch_*.jsonl")
    submitted_batch_files = count_files(run_input_dir, "submission_*.json")
    status_counts = status_summary.get("status_counts") or {}
    request_totals = status_summary.get("request_totals") or {}
    failed_batch_ids = collect_failed_batch_ids(status_summary)
    return RunSnapshot(
        run_input_dir=run_input_dir,
        run_download_dir=run_download_dir,
        total_batch_files=int(total_batch_files),
        submitted_batch_files=int(submitted_batch_files),
        status_counts={str(k): int(v) for k, v in status_counts.items() if isinstance(v, int)},
        request_totals={str(k): int(v) for k, v in request_totals.items() if isinstance(v, int)},
        failed_batch_ids=failed_batch_ids,
    )


def copy_provenance_files(*, src_dir: Path, dst_dir: Path) -> None:
    for filename in ("prompt_system.txt", "prompt_user_template.txt", "schema.json"):
        src_path = src_dir / filename
        if src_path.exists():
            shutil.copy2(src_path, dst_dir / filename)


def create_rechunk_retry_from_failed_batches(
    *,
    run_input_dir: Path,
    failed_batch_ids: List[str],
    retries_root_dir: Path,
    rechunk_requests_per_file: int,
    retry_max_mb_per_file: int,
    repo_root: Path,
    supervisor_log_path: Path,
) -> Path:
    if not failed_batch_ids:
        raise RuntimeError("No failed batch IDs to requeue.")

    batch_to_input_jsonl: Dict[str, Path] = {}
    for submission_path in sorted(run_input_dir.glob("submission_*.json")):
        payload = read_json(submission_path)
        batch_id = payload.get("batch_id")
        input_jsonl = payload.get("input_jsonl")
        if isinstance(batch_id, str) and isinstance(input_jsonl, str):
            batch_to_input_jsonl[batch_id] = Path(input_jsonl).expanduser().resolve()

    missing_batch_ids = [batch_id for batch_id in failed_batch_ids if batch_id not in batch_to_input_jsonl]
    if missing_batch_ids:
        raise RuntimeError(f"Missing submission mapping for failed batch IDs: {missing_batch_ids[:5]}")

    ts = timestamp_slug()
    copy_dir = retries_root_dir / f"retry_failed_batches_{run_input_dir.name}_{ts}"
    copy_dir.mkdir(parents=True, exist_ok=True)
    copy_provenance_files(src_dir=run_input_dir, dst_dir=copy_dir)

    copied_paths: List[Path] = []
    for batch_id in failed_batch_ids:
        src_path = batch_to_input_jsonl[batch_id]
        if not src_path.exists():
            raise FileNotFoundError(f"Missing input JSONL for failed batch {batch_id}: {src_path}")
        dst_path = copy_dir / src_path.name
        shutil.copy2(src_path, dst_path)
        copied_paths.append(dst_path)

    write_json(
        copy_dir / "requeue_failed_batches_manifest.json",
        {
            "created_at_utc": utc_now(),
            "source_input_dir": str(run_input_dir),
            "n_failed_batches": len(failed_batch_ids),
            "failed_batch_ids": failed_batch_ids,
            "copied_batch_files": [str(path) for path in copied_paths],
            "rechunk_requests_per_file": int(rechunk_requests_per_file),
            "retry_max_mb_per_file": int(retry_max_mb_per_file),
        },
    )

    rechunk_dir = retries_root_dir / f"rechunk_{copy_dir.name}"
    cmd = [
        sys.executable,
        f"src/py/{SCRIPT_NAME}",
        "rechunk-dir",
        "--input-dir",
        str(copy_dir),
        "--out-dir",
        str(rechunk_dir),
        "--max-requests-per-file",
        str(rechunk_requests_per_file),
        "--max-mb-per-file",
        str(retry_max_mb_per_file),
    ]
    proc = run_logged(cmd, cwd=repo_root, log_path=supervisor_log_path)
    if proc.returncode != 0:
        raise RuntimeError(f"rechunk-dir failed for failed batch fallback: {copy_dir}")
    return rechunk_dir


def attempt_prepare_retry(
    *,
    run_input_dir: Path,
    run_download_dir: Path,
    retries_root_dir: Path,
    retry_max_requests_per_file: int,
    retry_max_mb_per_file: int,
    repo_root: Path,
    supervisor_log_path: Path,
    fallback_failed_batch_ids: List[str],
    rechunk_requests_on_validation_failure: int,
) -> Path:
    ts = timestamp_slug()
    retry_dir = retries_root_dir / f"retry_{run_input_dir.name}_{ts}"
    cmd = [
        sys.executable,
        f"src/py/{SCRIPT_NAME}",
        "prepare-retry",
        "--previous-input-dir",
        str(run_input_dir),
        "--previous-output-dir",
        str(run_download_dir),
        "--out-dir",
        str(retry_dir),
        "--max-requests-per-file",
        str(retry_max_requests_per_file),
        "--max-mb-per-file",
        str(retry_max_mb_per_file),
    ]
    proc = run_logged(cmd, cwd=repo_root, log_path=supervisor_log_path)
    if proc.returncode == 0:
        manifest_path = retry_dir / "prepare_retry_manifest.json"
        if not manifest_path.exists():
            raise RuntimeError(f"prepare-retry finished but manifest missing: {manifest_path}")
        manifest = read_json(manifest_path)
        totals = manifest.get("totals") or {}
        n_files = int(totals.get("n_files", 0))
        n_requests = int(totals.get("n_requests", 0))
        if n_files <= 0 or n_requests <= 0:
            raise RuntimeError(f"prepare-retry returned empty workload in {retry_dir}")
        return retry_dir

    append_log(
        supervisor_log_path,
        f"[{utc_now()}] prepare-retry failed; falling back to failed-batch rechunk workflow.",
    )
    return create_rechunk_retry_from_failed_batches(
        run_input_dir=run_input_dir,
        failed_batch_ids=fallback_failed_batch_ids,
        retries_root_dir=retries_root_dir,
        rechunk_requests_per_file=rechunk_requests_on_validation_failure,
        retry_max_mb_per_file=retry_max_mb_per_file,
        repo_root=repo_root,
        supervisor_log_path=supervisor_log_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Supervise an OpenAI Batch directory: monitor progress, download outputs, and auto-retry failures."
    )
    parser.add_argument("--config-yaml", type=Path, required=True, help="YAML with openai_key.")
    parser.add_argument("--input-dir", type=Path, required=True, help="Initial batch input directory.")
    parser.add_argument("--tag", type=str, required=True, help="Batch metadata tag for new submissions.")
    parser.add_argument(
        "--downloads-root",
        type=Path,
        default=Path("results/raw/postings_description_equity/llm_batch_outputs"),
        help="Root folder for downloaded batch outputs (per-run subdirectories are created).",
    )
    parser.add_argument(
        "--retries-root",
        type=Path,
        default=Path("results/raw/postings_description_equity/llm_batch_inputs/equity_candidates"),
        help="Root folder where retry input directories are created.",
    )
    parser.add_argument("--poll-seconds", type=float, default=180.0, help="Supervisor polling interval.")
    parser.add_argument("--submit-max-active-batches", type=int, default=1, help="submit-dir --max-active-batches.")
    parser.add_argument("--submit-poll-seconds", type=float, default=20.0, help="submit-dir --poll-seconds.")
    parser.add_argument("--download-sleep-seconds", type=float, default=0.05, help="download-dir --sleep-seconds.")
    parser.add_argument(
        "--retry-max-requests-per-file",
        type=int,
        default=250,
        help="prepare-retry --max-requests-per-file.",
    )
    parser.add_argument("--retry-max-mb-per-file", type=int, default=25, help="prepare-retry --max-mb-per-file.")
    parser.add_argument(
        "--rechunk-requests-on-validation-failure",
        type=int,
        default=125,
        help="Fallback rechunk request size for full-batch validation failures.",
    )
    parser.add_argument("--max-retry-rounds", type=int, default=8, help="Maximum number of auto retry rounds.")
    parser.add_argument(
        "--max-loops",
        type=int,
        default=0,
        help="Optional loop limit for testing (0 means unlimited until done).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.poll_seconds <= 0:
        raise ValueError("--poll-seconds must be > 0.")
    if args.submit_max_active_batches < 0:
        raise ValueError("--submit-max-active-batches must be >= 0.")
    if args.max_retry_rounds < 0:
        raise ValueError("--max-retry-rounds must be >= 0.")

    repo_root = Path(__file__).resolve().parents[2]
    config_yaml = args.config_yaml.expanduser().resolve()
    current_input_dir = args.input_dir.expanduser().resolve()
    downloads_root = (repo_root / args.downloads_root).resolve() if not args.downloads_root.is_absolute() else args.downloads_root.expanduser().resolve()
    retries_root = (repo_root / args.retries_root).resolve() if not args.retries_root.is_absolute() else args.retries_root.expanduser().resolve()
    downloads_root.mkdir(parents=True, exist_ok=True)
    retries_root.mkdir(parents=True, exist_ok=True)

    supervisor_state_path = current_input_dir / "supervisor_state.json"
    supervisor_log_path = current_input_dir / f"supervisor_{timestamp_slug()}.log"

    retry_round = 0
    loop_index = 0

    while True:
        loop_index += 1
        current_download_dir = downloads_root / current_input_dir.name
        current_download_dir.mkdir(parents=True, exist_ok=True)

        submitter_pid = ensure_submitter(
            repo_root=repo_root,
            config_yaml=config_yaml,
            run_input_dir=current_input_dir,
            tag=args.tag,
            max_active_batches=int(args.submit_max_active_batches),
            submit_poll_seconds=float(args.submit_poll_seconds),
            supervisor_log_path=supervisor_log_path,
        )

        status_summary = refresh_status(
            repo_root=repo_root,
            config_yaml=config_yaml,
            run_input_dir=current_input_dir,
            log_path=supervisor_log_path,
        )
        refresh_downloads(
            repo_root=repo_root,
            config_yaml=config_yaml,
            run_input_dir=current_input_dir,
            run_download_dir=current_download_dir,
            download_sleep_seconds=float(args.download_sleep_seconds),
            log_path=supervisor_log_path,
        )

        snapshot = build_snapshot(
            run_input_dir=current_input_dir,
            run_download_dir=current_download_dir,
            status_summary=status_summary,
        )

        state_payload = {
            "updated_at_utc": utc_now(),
            "loop_index": loop_index,
            "retry_round": retry_round,
            "run_input_dir": str(snapshot.run_input_dir),
            "run_download_dir": str(snapshot.run_download_dir),
            "submitter_pid": submitter_pid,
            "counts": {
                "total_batch_files": snapshot.total_batch_files,
                "submitted_batch_files": snapshot.submitted_batch_files,
                "completed_batches": snapshot.completed_batches,
                "failed_batches": snapshot.failed_batches,
                "active_batches": snapshot.active_batches,
            },
            "request_totals": snapshot.request_totals,
            "status_counts": snapshot.status_counts,
            "failed_batch_ids_sample": snapshot.failed_batch_ids[:10],
        }
        write_json(supervisor_state_path, state_payload)

        run_submission_complete = snapshot.submitted_batch_files >= snapshot.total_batch_files
        run_has_active = snapshot.active_batches > 0

        if run_submission_complete and not run_has_active:
            if snapshot.failed_batches <= 0:
                append_log(supervisor_log_path, f"[{utc_now()}] run complete with zero failed batches.")
                break

            if retry_round >= int(args.max_retry_rounds):
                raise RuntimeError(
                    f"Reached max retry rounds ({args.max_retry_rounds}) with failed batches still present."
                )

            retry_round += 1
            append_log(
                supervisor_log_path,
                (
                    f"[{utc_now()}] run has failures; starting retry round {retry_round}. "
                    f"failed_batches={snapshot.failed_batches}"
                ),
            )
            next_input_dir = attempt_prepare_retry(
                run_input_dir=current_input_dir,
                run_download_dir=current_download_dir,
                retries_root_dir=retries_root,
                retry_max_requests_per_file=int(args.retry_max_requests_per_file),
                retry_max_mb_per_file=int(args.retry_max_mb_per_file),
                repo_root=repo_root,
                supervisor_log_path=supervisor_log_path,
                fallback_failed_batch_ids=snapshot.failed_batch_ids,
                rechunk_requests_on_validation_failure=int(args.rechunk_requests_on_validation_failure),
            )

            current_input_dir = next_input_dir
            supervisor_state_path = current_input_dir / "supervisor_state.json"
            supervisor_log_path = current_input_dir / f"supervisor_{timestamp_slug()}.log"
            continue

        if args.max_loops and loop_index >= int(args.max_loops):
            append_log(supervisor_log_path, f"[{utc_now()}] max loop limit reached ({args.max_loops}).")
            break

        time.sleep(float(args.poll_seconds))


if __name__ == "__main__":
    main()
