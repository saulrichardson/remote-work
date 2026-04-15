#!/usr/bin/env python3
"""Create split versions of the user mechanisms + growth table.

Existing output (``create_user_mechanisms_with_growth_table.py``) produces
six columns per model.  The write-up now requires:

* Table 4 – columns 1–4 with Panel A (OLS) and Panel B (IV)
* Table 5 – columns 5–6 with the same panel layout

This script re-generates those subsets so the formatting stays aligned with
the original tables.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_DIR = PROJECT_ROOT / "results" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "results" / "cleaned"

# Dimension checklist rows (growth rows listed last to match column layout).
DIMS = [
    "rent",
    "hhi",
    "seniority",
    "growth_endog",
]

ROW_LABELS = {
    "rent": "Rent",
    "hhi": "HHI",
    "seniority": "Seniority",
    "growth_endog": "Post-COVID Growth",
}

DIM_KEYWORDS = {
    "rent": ["rent"],
    "hhi": ["hhi"],
    "seniority": ["seniority"],
    "growth_endog": ["growth_endog"],
}

PARAM_ORDER = ["var3", "var5"]
PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}
INDENT = r"\hspace{1em}"


def _tabular_star_spec(n_cols: int) -> str:
    return "@{}l" + "@{\\extracolsep{\\fill}}c" * n_cols + "@{}"


def stars(p: float) -> str:
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
        stars=stars(pval),
        se=se,
    )


def spec_has_dim(spec: str, dim: str) -> bool:
    low = spec.lower()
    return any(token in low for token in DIM_KEYWORDS.get(dim, []))


def build_checks(specs: Iterable[str]) -> dict[str, list[bool]]:
    specs = list(specs)
    out: dict[str, list[bool]] = {dim: [] for dim in DIMS}
    for spec in specs:
        for dim in DIMS:
            out[dim].append(spec_has_dim(spec, dim))
    return out


def load_results(variant: str) -> pd.DataFrame:
    csv_path = RAW_DIR / f"user_mechanisms_with_growth_{variant}" / "consolidated_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing consolidated results: {csv_path}")
    return pd.read_csv(csv_path)


def determine_spec_order(df: pd.DataFrame) -> list[str]:
    all_specs = df["spec"].drop_duplicates().tolist()
    baseline = [s for s in all_specs if s == "baseline"]
    growth = [s for s in ["growth_endog"] if s in all_specs]
    excluded = set(baseline + growth + ["growth_exog"])
    middle = [s for s in all_specs if s not in excluded]
    drop_pairs = {"rent_hhi", "rent_seniority", "hhi_seniority"}
    middle = [s for s in middle if s not in drop_pairs]
    spec_order = baseline + middle + [s for s in all_specs if s not in baseline and s in growth]
    return spec_order


def panel_block(
    df: pd.DataFrame,
    model: str,
    specs: list[str],
) -> list[str]:
    df_model = df[df["model_type"] == model]
    lines: list[str] = []
    for param in PARAM_ORDER:
        row = [INDENT + PARAM_LABELS[param]]
        for spec in specs:
            sub = df_model[(df_model["spec"] == spec) & (df_model["param"] == param)]
            if sub.empty:
                row.append("")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                row.append(fmt_cell(float(coef), float(se), float(pval)))
        lines.append(" & ".join(row) + r" \\")
    return lines



def fixed_effects_block(num_cols: int) -> list[str]:
    blanks = " & ".join([""] * num_cols)
    lines = [
        r"\textbf{Fixed Effects} & " + blanks + r" \\",
        INDENT + r"Time & " + " & ".join([r"$\checkmark$"] * num_cols) + r" \\",
        INDENT + r"Firm $\times$ Individual & " + " & ".join([r"$\checkmark$"] * num_cols) + r" \\",
    ]
    return lines


def controls_block(specs: list[str]) -> list[str]:
    checks = build_checks(specs)
    blanks = " & ".join([""] * len(specs))
    lines = [r"\textbf{Controls} & " + blanks + r" \\"]
    for dim in DIMS:
        marks = ["\\checkmark" if flag else "" for flag in checks[dim]]
        lines.append(INDENT + ROW_LABELS[dim] + " & " + " & ".join(marks) + r" \\")
    return lines


def panel_stats_block(df: pd.DataFrame, specs: list[str], *, model: str) -> list[str]:
    lines: list[str] = []
    model_df = df[df["model_type"] == model]

    n_values: list[str] = []
    for spec in specs:
        sub = model_df[model_df["spec"] == spec]
        if sub.empty or pd.isna(sub.iloc[0]["nobs"]):
            n_values.append("")
        else:
            n_values.append(f"{int(sub.iloc[0]['nobs']):,}")
    lines.append("N & " + " & ".join(n_values) + r" \\")

    if model == "IV" and "rkf" in model_df.columns:
        rkf_values: list[str] = []
        for spec in specs:
            sub = model_df[model_df["spec"] == spec]
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


def build_table(
    df: pd.DataFrame,
    specs: list[str],
    table_id: str,
) -> str:
    n_cols = len(specs)
    header_nums = " & ".join(f"({i})" for i in range(1, n_cols + 1))
    col_spec = _tabular_star_spec(n_cols)

    lines: list[str] = [
        f"% Auto-generated block: {table_id}",
        r"{\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
        rf" & \multicolumn{{{n_cols}}}{{c}}{{Contributions}} \\",
        rf"\cmidrule(lr){{2-{n_cols + 1}}}",
        " & " + header_nums + r" \\",
        r"\midrule",
        rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
        r"\addlinespace[2pt]",
        *panel_block(df, "OLS", specs),
        r"\midrule",
        *panel_stats_block(df, specs, model="OLS"),
        r"\midrule",
        rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\",
        r"\addlinespace[2pt]",
        *panel_block(df, "IV", specs),
        r"\midrule",
        *panel_stats_block(df, specs, model="IV"),
        r"\midrule",
        *fixed_effects_block(n_cols),
        r"\midrule",
        *controls_block(specs),
        r"\bottomrule",
        r"\end{tabular*}",
        r"}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create split tables for user mechanisms with growth spec"
    )
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default="precovid",
        help="User panel variant to load (default: %(default)s)",
    )
    args = parser.parse_args()

    df = load_results(args.variant)
    spec_order = determine_spec_order(df)
    if len(spec_order) < 6:
        raise RuntimeError(
            f"Expected at least 6 specifications for subset split, found {len(spec_order)}"
        )

    first_subset = spec_order[:4]
    second_subset = spec_order[4:6]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    table1 = build_table(df, first_subset, "Columns 1-4")
    out1 = OUTPUT_DIR / f"user_mechanisms_with_growth_{args.variant}_cols1_4.tex"
    out1.write_text(table1, encoding="utf-8")
    print(f"Wrote {out1}")

    table2 = build_table(df, second_subset, "Columns 5-6")
    out2 = OUTPUT_DIR / f"user_mechanisms_with_growth_{args.variant}_cols5_6.tex"
    out2.write_text(table2, encoding="utf-8")
    print(f"Wrote {out2}")


if __name__ == "__main__":
    main()
