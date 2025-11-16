#!/usr/bin/env python3
"""Centralised helpers for resolving project-relative paths."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _root_from_repo_layout() -> Path:
    """Return the repo root assuming this file lives under PROJECT_ROOT/src/py/."""
    here = Path(__file__).resolve()
    root = here.parents[2]
    sentinel = root / "README.md"
    if not sentinel.exists():
        raise RuntimeError(
            "project_paths.py expected to reside in PROJECT_ROOT/src/py/. "
            "Set PROJECT_ROOT to override automatic detection."
        )
    return root


def resolve_project_root() -> Path:
    """Return the absolute project root.

    Priority:
      1. PROJECT_ROOT environment variable
      2. Known repo layout (assumes this module sits inside PROJECT_ROOT/src/py/)
    """
    env_root = os.getenv("PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return _root_from_repo_layout()


def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if missing, then return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


PROJECT_ROOT: Path = resolve_project_root()
DATA_DIR: Path = PROJECT_ROOT / "data"
DATA_RAW: Path = DATA_DIR / "raw"
DATA_CLEAN: Path = DATA_DIR / "clean"
DATA_PROCESSED: Path = DATA_CLEAN  # backward-compatible alias
DATA_SAMPLES: Path = DATA_DIR / "samples"

RESULTS_DIR: Path = PROJECT_ROOT / "results"
RESULTS_RAW: Path = RESULTS_DIR / "raw"
RESULTS_CLEANED: Path = RESULTS_DIR / "cleaned"
RESULTS_CLEANED_TEX: Path = RESULTS_CLEANED / "tex"
RESULTS_CLEANED_FIGURES: Path = RESULTS_CLEANED / "figures"

PY_DIR: Path = PROJECT_ROOT / "src" / "py"
SPEC_DIR: Path = PROJECT_ROOT / "spec" / "stata"
WRITEUP_DIR: Path = PROJECT_ROOT / "writeup"


def relative_to_project(path: Path | str) -> Path:
    """Return *path* resolved relative to the project root."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


__all__: Iterable[str] = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "DATA_RAW",
    "DATA_CLEAN",
    "DATA_PROCESSED",
    "DATA_SAMPLES",
    "RESULTS_DIR",
    "RESULTS_RAW",
    "RESULTS_CLEANED",
    "RESULTS_CLEANED_TEX",
    "RESULTS_CLEANED_FIGURES",
    "PY_DIR",
    "SPEC_DIR",
    "WRITEUP_DIR",
    "ensure_dir",
    "resolve_project_root",
    "relative_to_project",
]
