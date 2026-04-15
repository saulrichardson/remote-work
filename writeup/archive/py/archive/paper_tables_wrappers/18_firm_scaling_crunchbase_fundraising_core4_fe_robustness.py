#!/usr/bin/env python3
from __future__ import annotations

from _common import require_table, run_python


def main() -> None:
    run_python(
        "writeup/py/firm_scaling/build_crunchbase_fundraising_core4_fe_robustness_tables.py"
    )
    require_table("firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.tex")


if __name__ == "__main__":
    main()
