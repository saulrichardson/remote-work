#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python("writeup/py/paper_support/build_table_of_means.py")
    require_table("table_of_means.tex")


if __name__ == "__main__":
    main()
