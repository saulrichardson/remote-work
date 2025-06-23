#!/usr/bin/env python3
"""Quick helper to regenerate minimal LaTeX tables from a list of result
directories.

Each *result* directory must contain the Stata-/Julia-produced
``consolidated_results.csv`` file with the standard columns

    model_type, outcome, param, coef, se, pval [, …]

The script iterates over the directories passed on the command line and for
every folder writes

    results/cleaned/<dirname>.tex

mirroring the behaviour of :pyfile:`simple_table_from_consolidated.py`.  It is
meant as a thin convenience wrapper so you can simply run

    python py/create_tables_from_dirs.py results/raw/*

without having to invoke the single-file helper once per specification.

The heavy lifting (formatting, star annotation, …) is delegated to
:pyfile:`simple_table_from_consolidated.py`.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# We re-use the existing standalone helper by importing it as a module through
# runpy.  This way we avoid any circular import shenanigans and keep a single
# implementation of the LaTeX rendering logic.


def call_single_helper(spec_dir: Path, caption: str | None, label: str | None, *, split: bool) -> None:
    """Invoke *simple_table_from_consolidated.py* programmatically.

    The helper is executed in a temporary module namespace via ``runpy`` which
    gives us the same behaviour as when calling it on the shell.  This lets us
    pass parameters *in-process* without spawning a new Python interpreter for
    every directory (significantly faster for dozens of specs).
    """

    module_filename = "split_tables_from_consolidated.py" if split else "simple_table_from_consolidated.py"
    module_path = HERE / module_filename

    # Build a fake ``sys.argv`` for the inner script.
    argv = [str(module_path), str(spec_dir)]
    if caption is not None:
        argv += ["--caption", caption]
    if label is not None:
        argv += ["--label", label]

    # Temporarily replace sys.argv and execute the helper.
    old_argv = sys.argv
    try:
        sys.argv = argv
        runpy.run_path(str(module_path), run_name="__main__")
    finally:
        sys.argv = old_argv


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Batch generation of minimal LaTeX regression tables")
    p.add_argument("dirs", nargs="+", type=Path, help="Result folders (must contain consolidated_results.csv)")
    p.add_argument("--caption", help="Override caption for ALL tables")
    p.add_argument("--label", help="Override label for ALL tables – must be unique if you compile multiple tables")
    p.add_argument("--split", action="store_true", help="Generate separate OLS/IV tables instead of a combined one")
    args = p.parse_args(argv)

    for d in args.dirs:
        d = d.expanduser().resolve()
        if not d.is_dir():
            print(f"⚠  {d} is not a directory – skipping")
            continue

        if not (d / "consolidated_results.csv").exists():
            print(f"⚠  consolidated_results.csv missing in {d} – skipping")
            continue

        try:
            call_single_helper(d, caption=args.caption, label=args.label, split=args.split)
        except Exception as err:
            print(f"✗  Failed for {d.name}: {err}")


if __name__ == "__main__":
    main()
