#!/usr/bin/env python3
"""Deprecated wage table formatter.

The canonical wage table formatter now lives under:
  `writeup/py/user_productivity/build_wage_fe_tables.py`

and consumes results written by:
  `spec/stata/user_wage_fe_variants.do`

This file previously wrote a standalone TeX+PDF into `results/cleaned/`, which
does not match the repository's convention (cleaned artefacts live under
`results/cleaned/tex` and `results/cleaned/figures`).
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "src/py/format_user_wage_table.py is deprecated.\n"
        "Use:\n"
        "  python writeup/py/user_productivity/build_wage_fe_tables.py --variant precovid\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

