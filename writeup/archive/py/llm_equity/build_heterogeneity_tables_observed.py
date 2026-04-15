#!/usr/bin/env python3
"""Build LaTeX tables for observed-only LLM-equity heterogeneity specs."""

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


STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
INDENT: Final[str] = r"\hspace{1em}"

COLS: Final[list[tuple[str, str, str, str]]] = [
    ("pooled_interaction", "all", "OLS", "Pooled"),
    ("pooled_interaction", "all", "IV", "Pooled"),
    ("split_baseline", "equity_firm_0", "OLS", "Non-equity"),
    ("split_baseline", "equity_firm_0", "IV", "Non-equity"),
    ("split_baseline", "equity_firm_1", "OLS", "Equity"),
    ("split_baseline", "equity_firm_1", "IV", "Equity"),
]

PARAM_LABEL: Final[dict[str, str]] = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var3_eq_firm": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{EquityFirm} $",
    "var5_eq_firm": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{EquityFirm} $",
    "eq_any_firm_covid": r"$ \text{EquityFirm} \times \mathds{1}(\text{Post}) $",
}
PARAM_ORDER: Final[list[str]] = ["var3", "var5", "var3_eq_firm", "var5_eq_firm", "eq_any_firm_covid"]

FIRM_RAW: Final[Path] = RESULTS_RAW / "firm_scaling_llm_equity_heterogeneity_observed" / "consolidated_results.csv"
USER_RAW: Final[Path] = RESULTS_RAW / "user_productivity_llm_equity_heterogeneity_observed_precovid" / "consolidated_results.csv"

FIRM_OUT: Final[Path] = RESULTS_CLEANED_TEX / "firm_scaling_llm_equity_heterogeneity_observed.tex"
USER_OUT: Final[Path] = RESULTS_CLEANED_TEX / "user_productivity_llm_equity_heterogeneity_observed_precovid.tex"


def stars(p: float) -> str:
    for cutoff, symbol in STAR_RULES:
        if p < cutoff:
            return symbol
    return ""


def column_format(n_numeric: int) -> str:
    return r"@{}l" + (r"@{\extracolsep{\fill}}c" * n_numeric) + r"@{}"


def coef_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}"


def select_entry(
    df: pd.DataFrame,
    *,
    outcome: str,
    param: str,
    spec_variant: str,
    split_group: str,
    model_type: str,
) -> pd.Series | None:
    sub = df[
        (df["outcome"] == outcome)
        & (df["param"] == param)
        & (df["spec_variant"] == spec_variant)
        & (df["split_group"] == split_group)
        & (df["model_type"] == model_type)
    ].head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


def stat_cell(
    df: pd.DataFrame,
    *,
    outcome: str,
    field: str,
    spec_variant: str,
    split_group: str,
    model_type: str,
    fmt: str,
    force_model: str | None = None,
) -> str:
    model = force_model or model_type
    sub = df[
        (df["outcome"] == outcome)
        & (df["spec_variant"] == spec_variant)
        & (df["split_group"] == split_group)
        & (df["model_type"] == model)
    ].head(1)
    if sub.empty:
        return "--"
    value = sub.iloc[0].get(field)
    if pd.isna(value):
        return "--"
    return fmt.format(value)


def build_headers(ncols: int) -> list[str]:
    groups = ["Pooled", "Non-equity", "Equity"]
    group_row = " & " + " & ".join([rf"\multicolumn{{2}}{{c}}{{{g}}}" for g in groups]) + LB
    cmids = r"\cmidrule(lr){2-3}" + "\n" + r"\cmidrule(lr){4-5}" + "\n" + r"\cmidrule(lr){6-7}"
    sub_row = " & " + " & ".join(["OLS", "IV"] * 3) + LB
    num_row = " & " + " & ".join([f"({i})" for i in range(1, ncols + 1)]) + LB
    return [group_row, cmids, sub_row, num_row]


def build_panel(df: pd.DataFrame, *, outcome: str, panel_label: str) -> list[str]:
    lines: list[str] = [
        rf"\multicolumn{{7}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}",
        r"\addlinespace[2pt]",
    ]

    for param in PARAM_ORDER:
        row = [INDENT + PARAM_LABEL[param]]
        for spec_variant, split_group, model_type, _ in COLS:
            rec = select_entry(
                df,
                outcome=outcome,
                param=param,
                spec_variant=spec_variant,
                split_group=split_group,
                model_type=model_type,
            )
            if rec is None:
                row.append("--")
            else:
                row.append(coef_cell(float(rec["coef"]), float(rec["se"]), float(rec["pval"])))
        lines.append(" & ".join(row) + LB)

    lines.append(MID)

    pre = ["Pre-Covid Mean"]
    for spec_variant, split_group, model_type, _ in COLS:
        pre.append(
            stat_cell(
                df,
                outcome=outcome,
                field="pre_mean",
                spec_variant=spec_variant,
                split_group=split_group,
                model_type=model_type,
                force_model="OLS",
                fmt="{:.2f}",
            )
        )
    lines.append(" & ".join(pre) + LB)

    rkf = ["KP rk Wald F"]
    for spec_variant, split_group, model_type, _ in COLS:
        if model_type == "IV":
            rkf.append(
                stat_cell(
                    df,
                    outcome=outcome,
                    field="rkf",
                    spec_variant=spec_variant,
                    split_group=split_group,
                    model_type=model_type,
                    fmt="{:.2f}",
                )
            )
        else:
            rkf.append("")
    lines.append(" & ".join(rkf) + LB)

    nobs = ["N"]
    for spec_variant, split_group, model_type, _ in COLS:
        nobs.append(
            stat_cell(
                df,
                outcome=outcome,
                field="nobs",
                spec_variant=spec_variant,
                split_group=split_group,
                model_type=model_type,
                fmt="{:,.0f}",
            )
        )
    lines.append(" & ".join(nobs) + LB)

    firms = ["Firms"]
    for spec_variant, split_group, model_type, _ in COLS:
        firms.append(
            stat_cell(
                df,
                outcome=outcome,
                field="n_firms",
                spec_variant=spec_variant,
                split_group=split_group,
                model_type=model_type,
                fmt="{:,.0f}",
            )
        )
    lines.append(" & ".join(firms) + LB)
    return lines


def build_firm_table(df: pd.DataFrame) -> str:
    outcomes = [("growth_rate_we", "Panel A: Growth Rate")]
    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(6)}}}",
        TOP,
        *build_headers(6),
        MID,
    ]
    for outcome, label in outcomes:
        lines.extend(build_panel(df, outcome=outcome, panel_label=label))
    lines.extend(
        [
            MID,
            r"\textbf{Fixed Effects} &  &  &  &  &  &  " + LB,
            r"\hspace{1em}Firm & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            r"\hspace{1em}Half-year & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            BOTTOM,
            r"\end{tabular*}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_user_table(df: pd.DataFrame) -> str:
    outcome = "total_contributions_q100"
    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(6)}}}",
        TOP,
        *build_headers(6),
        MID,
    ]
    lines.extend(build_panel(df, outcome=outcome, panel_label="Panel A: Contribution Rank"))
    lines.extend(
        [
            MID,
            r"\textbf{Fixed Effects} &  &  &  &  &  &  " + LB,
            r"\hspace{1em}Individual & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            r"\hspace{1em}Firm & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            r"\hspace{1em}Half-year & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            BOTTOM,
            r"\end{tabular*}",
        ]
    )
    return "\n".join(lines) + "\n"


def require_columns(df: pd.DataFrame, path: Path, required: set[str]) -> None:
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"{path} is missing required columns: {sorted(missing)}")


def main() -> None:
    require_file(FIRM_RAW, nonempty=True, purpose="firm heterogeneity consolidated results")
    require_file(USER_RAW, nonempty=True, purpose="user heterogeneity consolidated results")

    firm_df = pd.read_csv(FIRM_RAW)
    user_df = pd.read_csv(USER_RAW)

    required = {
        "model_type",
        "spec_variant",
        "split_group",
        "outcome",
        "param",
        "coef",
        "se",
        "pval",
        "pre_mean",
        "rkf",
        "nobs",
        "n_firms",
    }
    require_columns(firm_df, FIRM_RAW, required)
    require_columns(user_df, USER_RAW, required | {"n_users"})

    ensure_dir(FIRM_OUT.parent)
    FIRM_OUT.write_text(build_firm_table(firm_df), encoding="utf-8")
    USER_OUT.write_text(build_user_table(user_df), encoding="utf-8")

    print(f"Wrote {FIRM_OUT}")
    print(f"Wrote {USER_OUT}")


if __name__ == "__main__":
    main()
