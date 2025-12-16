"""
Build a LaTeX table for the VC quadruple-diff regression.

Consumes the consolidated CSV produced by `spec/stata/quad_diff_seriesA.do`:
  - results/raw/quad_diff_seriesA/consolidated_results.csv

and emits a paper-ready table fragment:
  - results/cleaned/tex/quad_diff_seriesA.tex
"""

from __future__ import annotations

import pandas as pd

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir

SPECNAME = "quad_diff_seriesA"
CSV_PATH = RESULTS_RAW / SPECNAME / "consolidated_results.csv"
TABLE_PATH = RESULTS_CLEANED_TEX / f"{SPECNAME}.tex"

def starify(pval: float) -> str:
    if pval < 0.01:
        return "\\textsuperscript{***}"
    if pval < 0.05:
        return "\\textsuperscript{**}"
    if pval < 0.1:
        return "\\textsuperscript{*}"
    return ""


def fmt_cell(coef: float, se: float, pval: float) -> str:
    star = starify(pval)
    def f(x: float) -> str:
        if abs(x) >= 1e6 or (abs(x) > 0 and abs(x) < 1e-3):
            return f"{x:,.2e}"
        return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:,.3f}"

    return f"\\makecell[c]{{{f(coef)}{star}\\\\({f(se)})}}"


def build_table(ols: dict[str, tuple[float, float, float]], iv: dict[str, tuple[float, float, float]], n_ols: int, n_iv: int, rkf: float | None) -> str:
    rows = [
        ("var3", "$Remote \\times Post$"),
        ("var5", "$Remote \\times Post \\times Startup$"),
        ("var3_vc", "$Remote \\times Post \\times Series\\,A\\!+$"),
        ("var5_vc", "$Remote \\times Post \\times Startup \\times Series\\,A\\!+$"),
        ("var4", "$Post \\times Startup$"),
        ("var4_vc", "$Post \\times Startup \\times Series\\,A\\!+$"),
    ]
    lines = []
    lines.append("\\begin{table}[H]\\centering\\caption{Series A+ (pre-2020) Quadruple-Diff: Remote Adoption and Growth}")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\begin{tabular*}{\\linewidth}{@{\\extracolsep{\\fill}}lc}")
    lines.append("\\toprule")
    lines.append("\\multicolumn{2}{@{}l}{\\textbf{\\uline{Panel A: OLS}}} \\\\")
    lines.append("Parameter & Estimate \\\\")
    lines.append("\\midrule")
    for var, label in rows:
        lines.append(f"{label} & {fmt_cell(*ols[var])} \\\\")
    lines.append("\\midrule")
    lines.append(f"\\scriptsize N & \\scriptsize {n_ols:,}\\\\")
    lines.append("\\midrule")
    lines.append("\\multicolumn{2}{@{}l}{\\textbf{\\uline{Panel B: IV (teleworkable instruments)}}} \\\\")
    lines.append("Parameter & Estimate \\\\")
    lines.append("\\midrule")
    for var, label in rows:
        lines.append(f"{label} & {fmt_cell(*iv[var])} \\\\")
    lines.append("\\midrule")
    lines.append(f"\\scriptsize N & \\scriptsize {n_iv:,}\\\\")
    if rkf is not None:
        lines.append(f"\\scriptsize KP rk Wald F & \\scriptsize {rkf:.3f}\\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular*}")
    lines.append("\\end{table}")
    return "\n".join(lines)

def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Missing consolidated results CSV: {CSV_PATH}. "
            "Run `do spec/stata/quad_diff_seriesA.do` to generate it."
        )

    df = pd.read_csv(CSV_PATH)
    required = {"model_type", "param", "coef", "se", "pval", "nobs", "rkf"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Expected columns {sorted(required)} in {CSV_PATH}; missing {sorted(missing)}.")

    ols_df = df[df["model_type"] == "OLS"]
    iv_df = df[df["model_type"] == "IV"]
    if ols_df.empty or iv_df.empty:
        raise RuntimeError("Expected both OLS and IV rows in consolidated_results.csv.")

    ols = {row.param: (float(row.coef), float(row.se), float(row.pval)) for row in ols_df.itertuples()}
    iv = {row.param: (float(row.coef), float(row.se), float(row.pval)) for row in iv_df.itertuples()}
    n_ols = int(ols_df["nobs"].iloc[0])
    n_iv = int(iv_df["nobs"].iloc[0])
    rkf = float(iv_df["rkf"].iloc[0]) if pd.notna(iv_df["rkf"].iloc[0]) else None

    table_tex = build_table(ols, iv, n_ols, n_iv, rkf=rkf)
    ensure_dir(RESULTS_CLEANED_TEX)
    TABLE_PATH.write_text(table_tex, encoding="utf-8")
    print(f"Wrote {TABLE_PATH}")


if __name__ == "__main__":
    main()
