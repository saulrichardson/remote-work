#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_CLEANED_TEX = PROJECT_ROOT / "results" / "cleaned" / "tex"
STATIC_TABLES = PROJECT_ROOT / "writeup" / "static_tables"
DROPBOX_RESULTS_TABLES = (
    Path("/Users/saulrichardson/Dropbox/Apps/Overleaf/WFH Startups/Current/Results/Tables")
)


def run_python(script_rel: str, *args: str) -> None:
    script = PROJECT_ROOT / script_rel
    if not script.exists():
        raise FileNotFoundError(f"Missing script: {script}")
    cmd = [sys.executable, str(script), *args]
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True)


def require_table(filename: str) -> Path:
    path = RESULTS_CLEANED_TEX / filename
    if not path.exists():
        raise FileNotFoundError(f"Expected table was not created: {path}")
    return path


def copy_dropbox_table(filename: str, *, source_name: str | None = None) -> Path:
    source = DROPBOX_RESULTS_TABLES / (source_name or filename)
    if not source.exists():
        raise FileNotFoundError(f"Missing Dropbox table source: {source}")
    destination = RESULTS_CLEANED_TEX / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(f"Copied {source} -> {destination}")
    return destination


def copy_repo_static_table(filename: str, *, source_name: str | None = None) -> Path:
    source = STATIC_TABLES / (source_name or filename)
    if not source.exists():
        raise FileNotFoundError(f"Missing repo-local static table source: {source}")
    destination = RESULTS_CLEANED_TEX / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(f"Copied {source} -> {destination}")
    return destination
