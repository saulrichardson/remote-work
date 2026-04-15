#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python(
        "writeup/py/user_productivity/build_fr_focus_table.py",
        "--variant",
        "precovid",
    )
    require_table("user_productivity_fr_focus_precovid.tex")


if __name__ == "__main__":
    main()
