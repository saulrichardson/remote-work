#!/usr/bin/env python3
"""Centralised helpers for resolving project-relative paths."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

_MARKERS: tuple[str, ...] = (".git", "README.md", "pyproject.toml")


def _find_root_from(start: Path) -> Path:
    """Walk parents of *start* until a repository marker is located."""
    current = start.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if _has_marker(candidate):
            return candidate
    raise RuntimeError(
        "Unable to determine project root. "
        "Set the PROJECT_ROOT environment variable to override detection."
    )


def _has_marker(path: Path) -> bool:
    return any((path / marker).exists() for marker in _MARKERS)


def resolve_project_root(start: Path | None = None) -> Path:
    """Return the absolute project root.

    Priority:
      1. PROJECT_ROOT environment variable
      2. Heuristic search starting from *start* (defaults to this file)
    """
    env_root = os.getenv("PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    if start is None:
        start = Path(__file__).resolve()
    return _find_root_from(start)


def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if missing, then return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


PROJECT_ROOT: Path = resolve_project_root()
DATA_DIR: Path = PROJECT_ROOT / "data"
DATA_RAW: Path = DATA_DIR / "raw"
DATA_PROCESSED: Path = DATA_DIR / "processed"
DATA_SAMPLES: Path = DATA_DIR / "samples"

RESULTS_DIR: Path = PROJECT_ROOT / "results"
RESULTS_RAW: Path = RESULTS_DIR / "raw"
RESULTS_FINAL: Path = RESULTS_DIR / "final"
RESULTS_FINAL_TEX: Path = RESULTS_FINAL / "tex"
RESULTS_FINAL_FIGURES: Path = RESULTS_FINAL / "figures"

PY_DIR: Path = PROJECT_ROOT / "py"
SPEC_DIR: Path = PROJECT_ROOT / "spec"
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
    "DATA_PROCESSED",
    "DATA_SAMPLES",
    "RESULTS_DIR",
    "RESULTS_RAW",
    "RESULTS_FINAL",
    "RESULTS_FINAL_TEX",
    "RESULTS_FINAL_FIGURES",
    "PY_DIR",
    "SPEC_DIR",
    "WRITEUP_DIR",
    "ensure_dir",
    "resolve_project_root",
    "relative_to_project",
]

