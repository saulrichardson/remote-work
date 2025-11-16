#!/usr/bin/env python3
"""
Codex orchestration script.

Workflow:
1. Run the planner Codex prompt so transcripts -> contract JSON.
2. Sequentially dispatch worker Codex runs per task in the contract.
3. Capture JSON event logs, stderr, and final messages for auditing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_DIR = REPO_ROOT / "automation"
PROMPTS_DIR = AUTOMATION_DIR / "prompts"
TRANSCRIPTS_DIR = AUTOMATION_DIR / "transcripts"
CONTRACTS_DIR = AUTOMATION_DIR / "contracts"
LOGS_PLANNER_DIR = AUTOMATION_DIR / "logs" / "planner"
SCHEMA_PATH = AUTOMATION_DIR / "contract.schema.json"
STATE_PATH = AUTOMATION_DIR / "state.json"
WORKTREES_ROOT = REPO_ROOT / "worktrees"


def timestamp_slug() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"runs": []}


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def ensure_base_dirs() -> None:
    for path in [
        PROMPTS_DIR,
        TRANSCRIPTS_DIR,
        CONTRACTS_DIR,
        LOGS_PLANNER_DIR,
        WORKTREES_ROOT,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def transcripts_available() -> bool:
    for path in TRANSCRIPTS_DIR.iterdir():
        if path.is_file() and not path.name.startswith("."):
            return True
    return False


def run_codex_exec(
    *,
    prompt_text: str,
    cwd: Path,
    events_path: Path,
    stderr_path: Path,
    final_message_path: Path,
    extra_args: Optional[List[str]] = None,
) -> subprocess.CompletedProcess:
    cmd = [
        "codex",
        "exec",
        "--json",
        "--model",
        "gpt-5-codex",
        "--sandbox",
        "danger-full-access",
        "--full-auto",
        "--output-last-message",
        str(final_message_path),
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append("-")

    with open(events_path, "w") as events_file, open(stderr_path, "w") as stderr_file:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=events_file,
            stderr=stderr_file,
            check=True,
            text=True,
            input=prompt_text,
        )


def run_planner(run_id: str) -> Path:
    if not transcripts_available():
        raise RuntimeError(
            f"No transcripts found in {TRANSCRIPTS_DIR}. "
            "Add at least one file describing the requested work."
        )

    planner_prompt = PROMPTS_DIR / "planner.md"
    if not planner_prompt.exists():
        raise FileNotFoundError(f"Planner prompt missing: {planner_prompt}")

    contract_path = CONTRACTS_DIR / f"contract-{run_id}.json"
    events_path = LOGS_PLANNER_DIR / f"planner-{run_id}-events.jsonl"
    stderr_path = LOGS_PLANNER_DIR / f"planner-{run_id}-stderr.log"

    prompt_text = planner_prompt.read_text()
    run_codex_exec(
        prompt_text=prompt_text,
        cwd=REPO_ROOT,
        events_path=events_path,
        stderr_path=stderr_path,
        final_message_path=contract_path,
        extra_args=["--output-schema", str(SCHEMA_PATH)],
    )

    json.loads(contract_path.read_text())
    return contract_path


def parse_contract(contract_path: Path) -> Dict[str, Any]:
    try:
        return json.loads(contract_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Contract file is not valid JSON: {contract_path}") from exc


def ensure_worktree(task: Dict[str, Any]) -> Path:
    worktree_path = (REPO_ROOT / task["worktree_path"]).resolve()
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if worktree_path.exists():
        return worktree_path

    branch_name = task["branch_name"]
    branch_base = task["branch_base"]

    cmd = [
        "git",
        "worktree",
        "add",
        "-b",
        branch_name,
        str(worktree_path),
        branch_base,
    ]
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)
    return worktree_path


def render_worker_prompt(task: Dict[str, Any], prompt_path: Path) -> None:
    template_path = PROMPTS_DIR / "worker_template.md"
    template = Template(template_path.read_text())
    reference_list = "\n".join(f"- {doc}" for doc in task["reference_docs"])
    prompt_body = template.safe_substitute(
        repo_path=task["repo_path"],
        task_id=task["task_id"],
        title=task["title"],
        brief=task["brief"],
        reference_docs=reference_list,
        worktree_path=task["worktree_path"],
        branch_name=task["branch_name"],
    )
    prompt_path.write_text(prompt_body)


def extract_session_id(events_path: Path) -> Optional[str]:
    with open(events_path) as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started":
                return event.get("thread_id")
    return None


def run_worker(task: Dict[str, Any]) -> Dict[str, Any]:
    worktree_path = ensure_worktree(task)
    codex_dir = worktree_path / ".codex"
    codex_dir.mkdir(exist_ok=True)

    contract_copy = codex_dir / "contract.json"
    contract_copy.write_text(json.dumps(task, indent=2))

    prompt_path = codex_dir / "worker_prompt.md"
    render_worker_prompt(task, prompt_path)

    events_path = codex_dir / "events.jsonl"
    stderr_path = codex_dir / "stderr.log"
    final_path = codex_dir / "final.md"

    prompt_text = prompt_path.read_text()
    run_codex_exec(
        prompt_text=prompt_text,
        cwd=worktree_path,
        events_path=events_path,
        stderr_path=stderr_path,
        final_message_path=final_path,
    )

    session_id = extract_session_id(events_path)
    return {
        "worktree": str(worktree_path),
        "events": str(events_path.relative_to(REPO_ROOT)),
        "stderr": str(stderr_path.relative_to(REPO_ROOT)),
        "final_message": str(final_path.relative_to(REPO_ROOT)),
        "session_id": session_id,
    }


def orchestrate(args: argparse.Namespace) -> None:
    ensure_base_dirs()
    run_id = args.run_id or timestamp_slug()

    if args.contract:
        contract_path = Path(args.contract)
    else:
        contract_path = run_planner(run_id)

    contract = parse_contract(contract_path)
    tasks: List[Dict[str, Any]] = contract.get("tasks", [])
    if not tasks:
        raise ValueError("Contract contains no tasks.")

    state = load_state()
    run_record = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "contract": str(contract_path.relative_to(REPO_ROOT)),
        "tasks": [],
    }
    state["runs"].append(run_record)
    save_state(state)

    if args.plan_only:
        print(f"Contract created at {contract_path}. Skipping execution.")
        return

    for task in tasks:
        print(f"=== Running task {task['task_id']}: {task['title']} ===")
        task_record = {
            "task_id": task["task_id"],
            "title": task["title"],
            "worktree_path": task["worktree_path"],
            "branch_name": task["branch_name"],
            "status": "pending",
        }
        run_record["tasks"].append(task_record)
        save_state(state)

        try:
            result = run_worker(task)
            task_record.update(
                {
                    "status": "completed",
                    "logs": result,
                }
            )
            save_state(state)
        except subprocess.CalledProcessError as exc:
            task_record["status"] = "failed"
            task_record["error"] = str(exc)
            save_state(state)
            print(f"Task {task['task_id']} failed. Check logs. Stopping.")
            break


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan Codex tasks from transcripts and dispatch workers sequentially."
    )
    parser.add_argument(
        "--contract",
        type=str,
        help="Path to an existing contract JSON. If omitted, the planner will run.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Run the planner but skip worker execution.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        help="Optional identifier for this run (defaults to UTC timestamp).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    orchestration_env_warning()
    orchestrate(args)


def orchestration_env_warning() -> None:
    """Remind operators to log in before first use."""
    if not (REPO_ROOT / ".git").exists():
        raise RuntimeError("This script must be run from inside the git repository.")


if __name__ == "__main__":
    main()
