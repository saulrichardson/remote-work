#!/usr/bin/env python3
"""Build horse-race table in the exact mini-writeup style for PI follow-ups."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import pandas as pd

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

IN_RAW: Final[Path] = RESULTS_RAW / "user_mechanisms_with_growth_precovid" / "consolidated_results.csv"
OUT_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_horse_race.tex"

SPEC_ORDER: Final[list[str]] = [
    "baseline",
    "growth_endog",
    "equity",
    "hhi",
    "seniority",
    "growth_endog_equity",
    "hhi_seniority",
]

PARAM_LABELS: Final[dict[str, str]] = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

CONTROL_DIMS: Final[list[tuple[str, str, str]]] = [
    ("hhi", "HHI", "hhi"),
    ("seniority", "Seniority", "seniority"),
    ("growth_endog", "Firm Growth", "growth_endog"),
    ("equity", "Equity Offers", "equity"),
]


def stars(p: float) -> str:
    for cutoff, mark in STAR_RULES:
        if p < cutoff:
            return mark
    return ""


def fmt_coef(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1e4 or (0 < abs_v < 1e-2):
        return f"{value:.2e}"
    return f"{value:.2f}"


def coef_cell(row: pd.Series | None) -> str:
    if row is None:
        return "--"
    coef = row.get("coef")
    se = row.get("se")
    pval = row.get("pval")
    if coef is None or se is None or pd.isna(coef) or pd.isna(se):
        return "--"
    if float(se) == 0.0:
        return "--"
    p = float(pval) if pval is not None and not pd.isna(pval) else 1.0
    return rf"\makecell[c]{{{fmt_coef(float(coef))}{stars(p)}\\({fmt_coef(float(se))})}}"


def stat_cell(row: pd.Series | None, field: str, fmt: str = "{:,.0f}") -> str:
    if row is None:
        return "--"
    value = row.get(field)
    if value is None or pd.isna(value):
        return "--"
    return fmt.format(value)


def tabular_star(colspec: str, body_lines: list[str]) -> str:
    lines = [r"{\centering", rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}", "}"])
    return "\n".join(lines) + "\n"


def find_row(df: pd.DataFrame, *, spec: str, model_type: str, param: str = "var5") -> pd.Series | None:
    hit = df[(df["spec"] == spec) & (df["model_type"] == model_type) & (df["param"] == param)].head(1)
    if hit.empty:
        return None
    return hit.iloc[0]


def spec_has_token(spec: str, token: str) -> bool:
    return token.lower() in spec.lower()


def build_horse_race_table(df: pd.DataFrame) -> str:
    spec_keys = [s for s in SPEC_ORDER if s in set(df["spec"].dropna().tolist())]
    n_cols = len(spec_keys)
    if n_cols == 0:
        raise RuntimeError("No expected horse-race specs found in mechanisms-with-growth results.")

    if n_cols != len(SPEC_ORDER):
        missing = [s for s in SPEC_ORDER if s not in spec_keys]
        raise RuntimeError(f"Missing expected specs for mini-style horse-race table: {missing}")

    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * n_cols + "@{}"
    lines: list[str] = [
        rf" & \multicolumn{{{n_cols}}}{{c}}{{Contribution Rank}}" + LB,
        rf"\cmidrule(lr){{2-{n_cols + 1}}}",
        " & " + " & ".join(f"({i})" for i in range(1, n_cols + 1)) + LB,
        MID,
        rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}}" + LB,
        r"\addlinespace[2pt]",
    ]

    for param in ["var3", "var5"]:
        cells = [coef_cell(find_row(df, spec=s, model_type="OLS", param=param)) for s in spec_keys]
        lines.append(INDENT + PARAM_LABELS[param] + " & " + " & ".join(cells) + LB)

    lines.extend([MID])
    n_ols = [stat_cell(find_row(df, spec=s, model_type="OLS", param="var5"), "nobs") for s in spec_keys]
    lines.append("N & " + " & ".join(n_ols) + LB)

    lines.extend(
        [
            MID,
            rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}}" + LB,
            r"\addlinespace[2pt]",
        ]
    )
    for param in ["var3", "var5"]:
        cells = [coef_cell(find_row(df, spec=s, model_type="IV", param=param)) for s in spec_keys]
        lines.append(INDENT + PARAM_LABELS[param] + " & " + " & ".join(cells) + LB)

    lines.extend([MID])
    n_iv = [stat_cell(find_row(df, spec=s, model_type="IV", param="var5"), "nobs") for s in spec_keys]
    kp = [stat_cell(find_row(df, spec=s, model_type="IV", param="var5"), "rkf", "{:.2f}") for s in spec_keys]
    lines.append("N & " + " & ".join(n_iv) + LB)
    lines.append(r"KP\,rk Wald F & " + " & ".join(kp) + LB)

    checks = " & ".join([r"$\checkmark$"] * n_cols)
    lines.extend(
        [
            MID,
            r"\textbf{Fixed Effects} & " + " & ".join([""] * n_cols) + LB,
            INDENT + "Time & " + checks + LB,
            INDENT + r"Firm $\times$ Individual & " + checks + LB,
            MID,
            r"\textbf{Controls} & " + " & ".join([""] * n_cols) + LB,
        ]
    )

    for _, row_label, token in CONTROL_DIMS:
        marks = [r"\checkmark" if spec_has_token(spec, token) else "" for spec in spec_keys]
        lines.append(INDENT + row_label + " & " + " & ".join(marks) + LB)

    return tabular_star(colspec, lines)


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)
    df = pd.read_csv(require_file(IN_RAW, nonempty=True, purpose="mini-style mechanisms horse-race results"))
    OUT_TEX.write_text(build_horse_race_table(df), encoding="utf-8")
    print(f"Wrote {OUT_TEX}")


if __name__ == "__main__":
    main()
