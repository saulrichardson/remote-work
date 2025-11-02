#!/usr/bin/env python3
"""Create heterogeneity tables (OLS + IV) for selected worker traits.

The consolidated results from ``user_productivity_traits.do`` contain
coefficients for the baseline remote effect (var3 / var5) and the trait
interactions (var3_trait / var5_trait).  We focus on three traits:

    • female_flag
    • graddeg_flag (masters+)
    • age_25_45_flag

For each trait we report the interaction rows
    Remote × Post × Trait             (var3_trait)
    Remote × Post × Trait × Startup   (var5_trait)

The output mirrors the look of Table 2 (four columns, Panel A/B) so that it
can be dropped into the write-up directly.  At present the traits spec only
exports a single fixed-effect configuration (firm × user pair + time).  The
formatter therefore repeats that coefficient across the four displayed
columns so the LaTeX layout stays compatible with the rest of the document.
Once additional FE variants are exported, the filling logic can be updated to
map each ``fe_tag`` to a distinct column.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_PATH = PROJECT_ROOT / "results" / "raw" / "user_productivity_traits_precovid" / "consolidated_results.csv"
OUTPUT_DIR = PROJECT_ROOT / "results" / "cleaned"

COLUMN_HEADERS = ["(1)", "(2)", "(3)", "(4)"]
TRAIT_CONFIG = {
    "female_flag": {
        "label": "Female",
        "param_var3": "var3_female_flag",
        "param_var5": "var5_female_flag",
    },
    "graddeg_flag": {
        "label": "Graduate+",
        "param_var3": "var3_graddeg_flag",
        "param_var5": "var5_graddeg_flag",
    },
    "age_25_45_flag": {
        "label": "Age 25-45",
        "param_var3": "var3_age_25_45_flag",
        "param_var5": "var5_age_25_45_flag",
    },
}

STAR_LEVELS = ((0.01, "***"), (0.05, "**"), (0.10, "*"))


def starify(p: float) -> str:
    for cut, sym in STAR_LEVELS:
        if p < cut:
            return sym
    return ""


def make_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{starify(pval)}\\({se:.2f})}}"


def build_panel(df: pd.DataFrame, model: str) -> str:
    lines: list[str] = []
    panel_letter = "A" if model == "OLS" else "B"
    lines.append(
        rf"\multicolumn{{5}}{{@{{}}l}}{{\textbf{{\uline{{Panel {panel_letter}: {model}}}}}}} \\"
    )
    lines.append(r"\addlinespace[2pt]")

    for trait_key, cfg in TRAIT_CONFIG.items():
        subset = df[(df["model_type"] == model) & (df["trait"] == trait_key)]
        if subset.empty:
            continue

        row_label_var3 = rf"$ \text{{Remote}} \times \mathds{{1}}(\text{{Post}}) \times \text{{{cfg['label']}}} $"
        row_label_var5 = (
            rf"$ \text{{Remote}} \times \mathds{{1}}(\text{{Post}}) \times \text{{{cfg['label']}}} \times \text{{Startup}} $"
        )

        row_var3 = [row_label_var3]
        row_var5 = [row_label_var5]

        for _ in COLUMN_HEADERS:
            sub3 = subset[subset["param"] == cfg["param_var3"]]
            sub5 = subset[subset["param"] == cfg["param_var5"]]
            if sub3.empty:
                row_var3.append("")
            else:
                c, s, p = sub3.iloc[0][["coef", "se", "pval"]]
                row_var3.append(make_cell(float(c), float(s), float(p)))

            if sub5.empty:
                row_var5.append("")
            else:
                c, s, p = sub5.iloc[0][["coef", "se", "pval"]]
                row_var5.append(make_cell(float(c), float(s), float(p)))

        lines.append(" & ".join(row_var3) + r" \\")
        lines.append(" & ".join(row_var5) + r" \\")
        lines.append(r"\addlinespace[2pt]")

    return "\n".join(lines)


def build_table(df: pd.DataFrame, model: str) -> str:
    header_cols = " & ".join([""] + COLUMN_HEADERS) + r" \\"
    col_spec = r"@{}l" + r"@{\extracolsep{\fill}}c" * len(COLUMN_HEADERS) + r"@{}"
    body = build_panel(df, model)

    lines = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
        header_cols,
        r"\midrule",
        body,
        r"\bottomrule",
        r"\end{tabular*}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    if not RAW_PATH.exists():
        raise SystemExit(f"Missing traits results CSV: {RAW_PATH}")

    df = pd.read_csv(RAW_PATH)
    df = df[df["trait"].isin(TRAIT_CONFIG.keys())].copy()
    if df.empty:
        raise SystemExit("No matching trait rows found in consolidated results.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    table_ols = build_table(df, "OLS")
    table_iv = build_table(df, "IV")

    out_ols = OUTPUT_DIR / "user_productivity_traits_precovid_heterogeneity_ols.tex"
    out_iv = OUTPUT_DIR / "user_productivity_traits_precovid_heterogeneity_iv.tex"

    out_ols.write_text(table_ols, encoding="utf-8")
    out_iv.write_text(table_iv, encoding="utf-8")

    print(f"Wrote {out_ols}")
    print(f"Wrote {out_iv}")


if __name__ == "__main__":
    main()
