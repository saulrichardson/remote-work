#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

import pandas as pd


from src.py.project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW


COLS_PER_TABLE = 12
INDENT = r"\hspace{1em}"
COMBINED_MODELS = ("IV",)
PANEL_TITLES = {
    "OLS": r"\textbf{\uline{Panel A: OLS}}",
    "IV": r"\textbf{\uline{Panel B: IV}}",
}
PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}
PARAM_ORDER = ["var3", "var5"]
DIMS = ["growth_endog", "equity", "hhi"]
ROW_LABELS = {
    "growth_endog": "Firm Growth",
    "equity": "Equity Compensation",
    "hhi": "Centrality Score",
}
DIM_KEYWORDS = {
    "hhi": ["hhi"],
    "seniority": ["seniority"],
    "growth_endog": ["growth_endog"],
    "equity": ["equity"],
}
PREFERRED_ORDER = [
    "baseline",
    "growth_endog",
    "equity",
    "hhi",
    "growth_endog_equity",
]
EXCLUDED_SPECS = {
    "growth_exog",
    "rent_hhi",
    "rent_seniority",
    "seniority",
    "hhi_seniority",
}
DEFAULT_VARIANT = "precovid"


def _tabular_star_spec(n_cols: int) -> str:
    return "@{}l" + "@{\\extracolsep{\\fill}}c" * n_cols + "@{}"


def starify(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def fmt_cell(coef: float, se: float, pval: float) -> str:
    return r"\makecell[c]{{{coef:.2f}{stars}\\({se:.2f})}}".format(
        coef=coef,
        stars=starify(pval),
        se=se,
    )


def load_df(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def spec_has_dim(spec: str, dim: str) -> bool:
    low = spec.lower()
    return any(token in low for token in DIM_KEYWORDS.get(dim, []))


def checks(specs: list[str]) -> dict[str, list[bool]]:
    flags: dict[str, list[bool]] = {dim: [] for dim in DIMS}
    for spec in specs:
        for dim in DIMS:
            flags[dim].append(spec_has_dim(spec, dim))
    return flags


def panel_block(df_model: pd.DataFrame, specs: list[str]) -> list[str]:
    lines: list[str] = []
    for param in PARAM_ORDER:
        row = [INDENT + PARAM_LABELS[param]]
        for spec in specs:
            entry = df_model[(df_model["spec"] == spec) & (df_model["param"] == param)].head(1)
            if entry.empty:
                row.append("")
            else:
                coef = float(entry.iloc[0]["coef"])
                se = float(entry.iloc[0]["se"])
                pval = float(entry.iloc[0]["pval"])
                row.append(fmt_cell(coef, se, pval))
        lines.append(" & ".join(row) + r" \\")
    return lines


def fixed_effects_block(num_cols: int, row_labels: list[str]) -> list[str]:
    blanks = " & ".join([""] * num_cols)
    checks_row = " & ".join([r"$\checkmark$"] * num_cols)
    lines = [r"\textbf{Fixed Effects} & " + blanks + r" \\"]
    for label in row_labels:
        lines.append(INDENT + label + " & " + checks_row + r" \\")
    return lines


def controls_block(specs: list[str]) -> list[str]:
    marks = checks(specs)
    blanks = " & ".join([""] * len(specs))
    lines = [r"\textbf{Controls} & " + blanks + r" \\"]
    for dim in DIMS:
        row_marks = ["\\checkmark" if flag else "" for flag in marks[dim]]
        lines.append(INDENT + ROW_LABELS[dim] + " & " + " & ".join(row_marks) + r" \\")
    return lines


def panel_stats_block(df_model: pd.DataFrame, specs: list[str], *, model: str) -> list[str]:
    lines: list[str] = []
    n_values: list[str] = []
    for spec in specs:
        sub = df_model[df_model["spec"] == spec]
        if sub.empty or pd.isna(sub.iloc[0]["nobs"]):
            n_values.append("")
        else:
            n_values.append(f"{int(sub.iloc[0]['nobs']):,}")
    lines.append("N & " + " & ".join(n_values) + r" \\")

    if model == "IV" and "rkf" in df_model.columns:
        rkf_values: list[str] = []
        for spec in specs:
            sub = df_model[df_model["spec"] == spec]
            if sub.empty:
                rkf_values.append("")
                continue
            val = sub.iloc[0].get("rkf", float("nan"))
            if pd.isna(val):
                rkf_values.append("")
            else:
                rkf_values.append(f"{float(val):.2f}")
        if any(val for val in rkf_values):
            lines.append(r"KP\,rk Wald F & " + " & ".join(rkf_values) + r" \\")

    return lines


def format_combined_table_chunk(
    df: pd.DataFrame,
    specs: list[str],
    idx: int,
    total_parts: int,
    fe_row_labels: list[str],
) -> list[str]:
    n_cols = len(specs)
    header_nums = " & ".join(f"({i})" for i in range(1, n_cols + 1))
    col_spec = _tabular_star_spec(n_cols)

    return [
        f"% Auto-generated block: Combined (part {idx} of {total_parts})",
        r"{\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
        rf" & \multicolumn{{{n_cols}}}{{c}}{{Contribution Rank}} \\",
        rf"\cmidrule(lr){{2-{n_cols + 1}}}",
        " & " + header_nums + r" \\",
        r"\midrule",
        *[
            line
            for model in COMBINED_MODELS
            for line in [
                rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{{PANEL_TITLES[model]}}} \\",
                r"\addlinespace[2pt]",
                *panel_block(df[df.model_type == model], specs),
                r"\midrule",
                *panel_stats_block(df[df.model_type == model], specs, model=model),
                r"\midrule",
            ]
        ],
        *fixed_effects_block(n_cols, fe_row_labels),
        r"\midrule",
        *controls_block(specs),
        r"\bottomrule",
        r"\end{tabular*}",
        r"}",
    ]


def write_mechanisms_tables(
    *,
    input_csv: Path,
    output_tex_base: Path,
    fe_row_labels: list[str] | None = None,
) -> None:
    if not input_csv.exists():
        raise SystemExit(f"Missing input CSV: {input_csv}")

    df = load_df(input_csv)
    all_specs = [s for s in df["spec"].drop_duplicates().tolist() if s not in EXCLUDED_SPECS]
    middle = [s for s in all_specs if s not in set(PREFERRED_ORDER)]
    spec_order = [s for s in PREFERRED_ORDER if s in all_specs] + middle

    tables_needed = math.ceil(len(spec_order) / COLS_PER_TABLE)
    if fe_row_labels is None:
        fe_row_labels = [r"Time", r"Firm $\times$ Individual"]
    lines_combined: list[str] = []
    for i in range(tables_needed):
        chunk = spec_order[i * COLS_PER_TABLE : (i + 1) * COLS_PER_TABLE]
        lines_combined.extend(
            format_combined_table_chunk(
                df,
                chunk,
                idx=i + 1,
                total_parts=tables_needed,
                fe_row_labels=fe_row_labels,
            )
        )
        lines_combined.append("")

    output_tex_base.parent.mkdir(parents=True, exist_ok=True)
    if lines_combined and lines_combined[-1] == "":
        lines_combined.pop()
    output_tex_base.write_text("\n".join(lines_combined), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create keep-remote mechanisms latex table")
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default=DEFAULT_VARIANT,
        help="Which user_panel sample variant to load (default: %(default)s)",
    )
    args = parser.parse_args()

    specname = f"05_user_mechanisms_keep_remote_{args.variant}"
    input_csv = RESULTS_RAW / specname / "consolidated_results.csv"
    output_tex_base = RESULTS_CLEANED_TEX / f"user_mechanisms_keep_remote_{args.variant}.tex"

    write_mechanisms_tables(
        input_csv=input_csv,
        output_tex_base=output_tex_base,
    )

    print(f"Wrote {output_tex_base}")


if __name__ == "__main__":
    main()
