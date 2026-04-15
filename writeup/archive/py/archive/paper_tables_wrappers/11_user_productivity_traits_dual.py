#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python("writeup/py/user_productivity/build_traits_dual_table.py")
    require_table("user_productivity_traits_dual_precovid_ols.tex")


if __name__ == "__main__":
    main()
