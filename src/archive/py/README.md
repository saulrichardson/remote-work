# `src/archive/py/`

This tree holds archived Python source that remains useful as reference code or
for non-paper rebuilds, but is outside the active paper-owned lane.

The runtime contract is explicit:

- use [`../../../bin/archive-python`](../../../bin/archive-python) to execute
  these scripts
- import shared path helpers through `src.py.project_paths`
- do not rely on ambient `PYTHONPATH` or ad hoc shell setup

Examples:

```bash
./bin/archive-python src/archive/py/analysis_helpers/user_ids.py --help
./bin/archive-python src/archive/py/rendering_and_sweeps/run_vacancy_threshold_sweep.py --help
```

This directory is intentionally narrower than the full historical archive. It
is the portion of the archive we still treat as living reference code near the
active upstream pipeline.
