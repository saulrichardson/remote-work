#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python(
        "writeup/py/user_productivity/build_wage_fe_tables.py",
        "--variant",
        "precovid",
    )
    require_table("user_wage_fe_variants_precovid_log_salary.tex")


if __name__ == "__main__":
    main()
