# Automation Orchestrator

This folder hosts the scaffolding for an LLM-driven workflow that turns
natural-language transcripts into actionable Codex runs.

Pipeline overview:

1. Drop the high-level discussion or planning transcripts into
   `automation/transcripts/`. Each file should capture the desired work in
   free-form text.
2. Run `python automation/orchestrate_codex.py`. The script:
   - Invokes the planner prompt via `codex exec` (`gpt-5-codex` with the prompt nudging high effort)
     so Codex reads the transcripts and emits a structured contract that
     matches `automation/contract.schema.json`.
   - Sequentially dispatches worker Codex runs (one at a time) based on the
     contract. Each worker operates inside its own git worktree, reads the
     repo-level `AGENTS.md`, and carries the task to completion without
     further approvals.
   - Captures the full JSON event stream from every Codex run alongside the
     final message, stderr, and session identifiers for auditing or resuming.
3. Inspect `automation/contracts/` for historical contracts and
   `automation/state.json` for run metadata. Per-task logs live inside each
   worktree under `.codex/`.

Key files:

- `prompts/planner.md` – instructions for the planner Codex pass.
- `prompts/worker_template.md` – template used to render the worker prompt
  for each task.
- `contract.schema.json` – JSON Schema the planner output must satisfy.
- `orchestrate_codex.py` – entry point that coordinates planning and worker
  dispatch.

Default assumptions:

- All tasks are independent and run sequentially in the order provided by the
  planner contract.
- Every worker uses the same permissions: `codex exec --sandbox
  danger-full-access --full-auto --model gpt-5-codex`.
- Worktrees are created under `worktrees/<task_id>/` with new git branches
  named in the contract.

Adjust the prompts or script as your workflow evolves. The scaffolding is
designed to be explicit and auditable so you can extend it with scheduling,
dashboards, or CI hooks later.
