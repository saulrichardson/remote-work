#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python("writeup/py/firm_scaling/build_location_ratio_table.py")
    require_table("firm_scaling_location_ratios.tex")


if __name__ == "__main__":
    main()
