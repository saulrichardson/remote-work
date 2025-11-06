#!/usr/bin/env python3
"""Build an OLS-only heterogeneity table for the duo-trait spec."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_PATH = (
    PROJECT_ROOT
    / "results"
    / "raw"
    / "user_productivity_traits_dual_precovid"
    / "consolidated_results.csv"
)
CLEANED_DIR = PROJECT_ROOT / "results" / "cleaned"
FINAL_DIR = PROJECT_ROOT / "results" / "final" / "tex"
OUTPUT_TEX = CLEANED_DIR / "user_productivity_traits_dual_precovid_ols.tex"
FINAL_TEX = FINAL_DIR / "user_productivity_traits_dual_precovid_ols.tex"

STAR_RULES = ((0.01, "***"), (0.05, "**"), (0.10, "*"))

COLUMN_CONFIG: List[Dict[str, str]] = [
    {
        "label": "(1)",
        "header": r"\makecell[c]{Rank \\ Individual + Firm FE}",
        "fe_tag": "fyhu",
    },
    {
        "label": "(2)",
        "header": r"\makecell[c]{Rank \\ Firm $\times$ Individual FE}",
        "fe_tag": "firmbyuseryh",
    },
]

TRAITS = {
    "female_flag": {
        "label": "Female",
        "rows": [
            ("baseline", "var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
            (
                "female_flag",
                "var3_female_flag",
                r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Female} $",
            ),
            (
                "baseline",
                "var5",
                r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
            ),
            (
                "female_flag",
                "var5_female_flag",
                r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Female} \times \text{Startup} $",
            ),
        ],
    },
    "age_25_45_flag": {
        "label": "Age 25--45",
        "rows": [
            ("baseline", "var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
            (
                "age_25_45_flag",
                "var3_age_25_45_flag",
                r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \mathds{1}(25 \le \text{Age} \le 45) $",
            ),
            (
                "baseline",
                "var5",
                r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
            ),
            (
                "age_25_45_flag",
                "var5_age_25_45_flag",
                r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \mathds{1}(25 \le \text{Age} \le 45) \times \text{Startup} $",
            ),
        ],
    },
}

FE_ROWS = [
    ("Time", {"firmbyuseryh": True, "fyhu": True}),
    ("Firm", {"firmbyuseryh": False, "fyhu": True}),
    ("Individual", {"firmbyuseryh": False, "fyhu": True}),
    (
        r"Firm $\times$ Individual",
        {"firmbyuseryh": True, "fyhu": False},
    ),
]

CHECK_MARK = r"$\checkmark$"


def starify(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def format_cell(coef: float | None, se: float | None, pval: float | None) -> str:
    if coef is None or se is None or pval is None:
        return ""
    return rf"\makecell[c]{{{coef:.2f}{starify(pval)}\\({se:.2f})}}"


def extract_cell(
    df: pd.DataFrame,
    trait_label: str,
    param: str,
    fe_tag: str,
) -> str:
    match = df[
        (df["model_type"] == "OLS")
        & (df["trait"] == trait_label)
        & (df["param"] == param)
        & (df["fe_tag"] == fe_tag)
        & (df["outcome"] == "total_contributions_q100")
    ]
    if match.empty:
        return ""
    coef, se, pval = match.iloc[0][["coef", "se", "pval"]]
    if pd.isna(coef) or pd.isna(se) or pd.isna(pval):
        return ""
    return format_cell(float(coef), float(se), float(pval))


def build_table(df: pd.DataFrame) -> str:
    header_nums = " & ".join([""] + [cfg["label"] for cfg in COLUMN_CONFIG]) + r" \\"
    col_spec = r"@{}l" + r"@{\extracolsep{\fill}}c" * len(COLUMN_CONFIG) + r"@{}"

    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
        r" & \multicolumn{2}{c}{Contribution Rank} \\",
        r"\cmidrule(lr){2-3}",
        header_nums,
        r"\midrule",
    ]

    for idx, (trait_key, cfg) in enumerate(TRAITS.items()):
        lines.append(
            rf"\multicolumn{{{len(COLUMN_CONFIG)+1}}}{{@{{}}l}}{{\textbf{{\uline{{Trait: {cfg['label']}}}}}}} \\"
        )
        lines.append(r"\addlinespace[2pt]")
        for trait_label, param, label in cfg["rows"]:
            lookup_trait = "baseline" if trait_label == "baseline" else trait_key
            row = [label]
            for column in COLUMN_CONFIG:
                row.append(
                    extract_cell(
                        df,
                        lookup_trait,
                        param,
                        column["fe_tag"],
                    )
                )
            lines.append(" & ".join(row) + r" \\")
        if idx < len(TRAITS) - 1:
            lines.append(r"\midrule")

    lines.append(r"\midrule")
    lines.append(r"\textbf{Fixed Effects} & " + " & ".join([""] * len(COLUMN_CONFIG)) + r" \\")
    for row_label, mapping in FE_ROWS:
        row = [r"\hspace{1em}" + row_label]
        for column in COLUMN_CONFIG:
            row.append(CHECK_MARK if mapping.get(column["fe_tag"], False) else "")
        lines.append(" & ".join(row) + r" \\")

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular*}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    if not RAW_PATH.exists():
        raise SystemExit(f"Missing input CSV: {RAW_PATH}")

    df = pd.read_csv(RAW_PATH)
    df = df[df["model_type"] == "OLS"].copy()
    if df.empty:
        raise SystemExit("No OLS rows found in consolidated results.")

    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    table_tex = build_table(df)
    OUTPUT_TEX.write_text(table_tex)
    FINAL_TEX.write_text(table_tex)
    print(f"Wrote {OUTPUT_TEX}")
    print(f"Wrote {FINAL_TEX}")


if __name__ == "__main__":
    main()
