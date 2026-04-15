#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python(
        "writeup/py/user_productivity/build_single_model_tables.py",
        "--variant",
        "precovid",
        "--outcome-set",
        "total",
    )
    require_table("user_productivity_precovid_total_iv_single.tex")


if __name__ == "__main__":
    main()
