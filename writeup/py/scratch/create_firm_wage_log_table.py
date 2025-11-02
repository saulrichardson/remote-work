#!/usr/bin/env python3
"""Build LaTeX table for firm-level log wage regressions."""

from __future__ import annotations

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FILE = PROJECT_ROOT / "results" / "raw" / "firm_scaling_wages" / "consolidated_results.csv"
OUTPUT_FILE = PROJECT_ROOT / "results" / "cleaned" / "firm_wage_log_precovid.tex"

OUTCOME_COLUMNS = [
    ("log_salary_mean", "Log Salary Mean"),
    ("log_salary_total", "Log Salary Total"),
]

PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}


def stars(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def make_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}"


def main() -> None:
    if not RAW_FILE.exists():
        raise SystemExit(f"Missing firm wage results: {RAW_FILE}")

    df = pd.read_csv(RAW_FILE)
    df = df[df["outcome"].isin([col for col, _ in OUTCOME_COLUMNS])]
    if df.empty:
        raise SystemExit("No log wage outcomes found in firm_scaling_wages results.")

    header_cols = " & ".join(f"({i})" for i in range(1, len(OUTCOME_COLUMNS) + 1))
    group_header = " & ".join(name for _, name in OUTCOME_COLUMNS)
    col_spec = r"@{}l" + r"@{\extracolsep{\fill}}c" * len(OUTCOME_COLUMNS) + r"@{}"

    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
        rf" & \multicolumn{{{len(OUTCOME_COLUMNS)}}}{{c}}{{Log wage outcomes}} \\",
        rf"\cmidrule(lr){{2-{len(OUTCOME_COLUMNS)+1}}}",
        " & " + header_cols + r" \\",
        r"\midrule",
        r"\multicolumn{" + str(len(OUTCOME_COLUMNS) + 1) + r"}{@{}l}{\textbf{\uline{Panel A: OLS}}} \\",
        r"\addlinespace[2pt]",
    ]

    for param in ("var3", "var5"):
        row = [PARAM_LABELS[param]]
        for outcome, _ in OUTCOME_COLUMNS:
            sub = df[
                (df["model_type"] == "OLS")
                & (df["outcome"] == outcome)
                & (df["param"] == param)
            ]
            if sub.empty:
                row.append("")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                row.append(make_cell(float(coef), float(se), float(pval)))
        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\midrule")
    pre_mean_row = ["Pre-Covid Mean"]
    n_row = ["N"]
    for outcome, _ in OUTCOME_COLUMNS:
        sub = df[(df["model_type"] == "OLS") & (df["outcome"] == outcome)]
        if sub.empty:
            pre_mean_row.append("")
            n_row.append("")
        else:
            pre_mean_row.append(f"{float(sub.iloc[0]['pre_mean']):.2f}")
            n_row.append(f"{int(sub.iloc[0]['nobs']):,}")
    lines.append(" & ".join(pre_mean_row) + r" \\")
    lines.append(" & ".join(n_row) + r" \\")

    lines.extend(
        [
            r"\midrule",
            r"\multicolumn{" + str(len(OUTCOME_COLUMNS) + 1) + r"}{@{}l}{\textbf{\uline{Panel B: IV}}} \\",
            r"\addlinespace[2pt]",
        ]
    )

    for param in ("var3", "var5"):
        row = [PARAM_LABELS[param]]
        for outcome, _ in OUTCOME_COLUMNS:
            sub = df[
                (df["model_type"] == "IV")
                & (df["outcome"] == outcome)
                & (df["param"] == param)
            ]
            if sub.empty:
                row.append("")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                row.append(make_cell(float(coef), float(se), float(pval)))
        lines.append(" & ".join(row) + r" \\")

    kp_row = [r"KP\,rk Wald F"]
    n_iv_row = ["N"]
    for outcome, _ in OUTCOME_COLUMNS:
        sub = df[(df["model_type"] == "IV") & (df["outcome"] == outcome)]
        if sub.empty:
            kp_row.append("")
            n_iv_row.append("")
        else:
            kp_row.append(f"{float(sub.iloc[0]['rkf']):.2f}")
            n_iv_row.append(f"{int(sub.iloc[0]['nobs']):,}")
    lines.append(r"\midrule")
    lines.append(" & ".join(kp_row) + r" \\")
    lines.append(" & ".join(n_iv_row) + r" \\")

    lines.extend(
        [
            r"\midrule",
            r"\textbf{Fixed Effects} & " + " & ".join([""] * len(OUTCOME_COLUMNS)) + r" \\",
            r"\hspace{1em}Time & " + " & ".join([r"$\checkmark$"] * len(OUTCOME_COLUMNS)) + r" \\",
            r"\hspace{1em}Firm & " + " & ".join([r"$\checkmark$"] * len(OUTCOME_COLUMNS)) + r" \\",
        ]
    )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
