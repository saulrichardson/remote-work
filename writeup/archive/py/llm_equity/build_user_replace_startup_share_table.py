#!/usr/bin/env python3
"""Build a LaTeX table for the share-based replace-startup specification (user).

Inputs:
  - results/raw/user_productivity_llm_equity_replace_startup_share_<panel>/consolidated_results.csv

Outputs:
  - results/cleaned/tex/llm_equity_replace_startup_share_user.tex
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Final

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file

LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
INDENT: Final[str] = r"\hspace{1em}"

STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cutoff, mark in STAR_RULES:
        if p < cutoff:
            return mark
    return ""


def fmt_coef(x: float) -> str:
    ax = abs(x)
    if ax >= 1e4 or (0 < ax < 1e-2):
        return f"{x:.2e}"
    return f"{x:.2f}"


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    v = str(value).strip()
    if v == "" or v.lower() in {"nan", "na", "none"}:
        return None
    return float(v)


def coef_cell(row: dict[str, str] | None) -> str:
    if row is None:
        return "--"
    coef = _to_float(row.get("coef"))
    se = _to_float(row.get("se"))
    pval = _to_float(row.get("pval"))
    if coef is None or se is None or float(se) == 0.0:
        return "--"
    p = float(pval) if pval is not None else 1.0
    return rf"\makecell[c]{{{fmt_coef(float(coef))}{stars(p)}\\({fmt_coef(float(se))})}}"


def stat_cell(row: dict[str, str] | None, field: str, fmt: str = "{:,.0f}") -> str:
    if row is None:
        return "--"
    parsed = _to_float(row.get(field))
    if parsed is None:
        return "--"
    return fmt.format(parsed)


IndexKey = tuple[str, str, str]


def read_results(path: Path) -> dict[IndexKey, dict[str, str]]:
    required = {"model_type", "param"}
    index: dict[IndexKey, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise RuntimeError(f"Empty/invalid CSV (missing header): {path}")
        missing = required.difference(set(reader.fieldnames))
        if missing:
            raise RuntimeError(f"CSV missing required columns {sorted(missing)}: {path}")
        for row in reader:
            model_type = (row.get("model_type") or "").strip()
            param = (row.get("param") or "").strip()
            if not model_type or not param:
                continue
            index[(model_type, "total_contributions_q100", param)] = row
    if not index:
        raise RuntimeError(f"No usable rows read from CSV: {path}")
    return index


def tabular_star(colspec: str, body_lines: list[str]) -> str:
    lines = [r"\centering", rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build share-based replace-startup user table.")
    parser.add_argument("--panel", default="precovid", help="Panel variant (e.g., precovid).")
    return parser.parse_args()


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)
    args = parse_args()

    in_path = require_file(
        RESULTS_RAW / f"user_productivity_llm_equity_replace_startup_share_{args.panel}" / "consolidated_results.csv",
        nonempty=True,
        purpose="replace-startup share consolidated_results.csv",
    )
    index = read_results(in_path)

    def row(model: str, param: str) -> dict[str, str] | None:
        return index.get((model, "total_contributions_q100", param))

    params: list[tuple[str, str]] = [
        ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
        ("var3_eq_shp_post", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Share of postings offering equity} $"),
        ("eq_shp_post_mean_f_covid", r"$ \text{Share of postings offering equity} \times \mathds{1}(\text{Post}) $"),
    ]

    lines: list[str] = [
        "Parameter & OLS & IV" + LB,
        " & (1) & (2)" + LB,
        MID,
    ]
    for param, label in params:
        lines.append(INDENT + label + " & " + coef_cell(row("OLS", param)) + " & " + coef_cell(row("IV", param)) + LB)

    ref_ols = row("OLS", "var3")
    ref_iv = row("IV", "var3")
    lines.extend(
        [
            MID,
            "Pre-shift mean & " + stat_cell(ref_ols, "pre_mean", "{:.2f}") + " & " + stat_cell(ref_iv, "pre_mean", "{:.2f}") + LB,
            "KP rk Wald F &  & " + stat_cell(ref_iv, "rkf", "{:.2f}") + LB,
            "N & " + stat_cell(ref_ols, "nobs") + " & " + stat_cell(ref_iv, "nobs") + LB,
            "Firms & " + stat_cell(ref_ols, "n_firms") + " & " + stat_cell(ref_iv, "n_firms") + LB,
            "Users & " + stat_cell(ref_ols, "n_users") + " & " + stat_cell(ref_iv, "n_users") + LB,
            MID,
            r"\textbf{Controls Included} &  & " + LB,
            INDENT + r"Firm & $\checkmark$ & $\checkmark$" + LB,
            INDENT + r"Half-year & $\checkmark$ & $\checkmark$" + LB,
            INDENT + r"Individual & $\checkmark$ & $\checkmark$" + LB,
        ]
    )

    tex = tabular_star(r"@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}", lines)

    out_path = RESULTS_CLEANED_TEX / "llm_equity_replace_startup_share_user.tex"
    out_path.write_text(tex, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
