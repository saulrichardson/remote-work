#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python("writeup/py/user_productivity/build_first_stage_table.py")
    require_table("first_stage_summary.tex")


if __name__ == "__main__":
    main()
