#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python(
        "writeup/py/user_productivity/build_stayer_panel_table.py",
        "--variant",
        "precovid",
    )
    require_table("user_productivity_precovid_stayer_table3.tex")


if __name__ == "__main__":
    main()
