#!/usr/bin/env python3
"""Generate a compact heterogeneity table with one column per trait.

The original formatter mirrored the four-column productivity layout to remain
drop-in compatible with legacy LaTeX.  This script instead produces a
self-contained document that only reports the three traits we estimate:

    • Female
    • Graduate+
    • Age 25–45

For each trait we display the interaction coefficients for
Remote × Post × Trait and Remote × Post × Trait × Startup,
under both OLS and IV.  The script writes a standalone LaTeX document and
compiles it to PDF if a LaTeX engine (latexmk or pdflatex) is available on the
PATH.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_PATH = PROJECT_ROOT / "results" / "raw" / "user_productivity_traits_precovid" / "consolidated_results.csv"
OUTPUT_DIR = PROJECT_ROOT / "results" / "cleaned"
OUTPUT_TEX = OUTPUT_DIR / "user_productivity_traits_precovid_heterogeneity_compact.tex"

TRAITS = {
    "female_flag": {
        "label": "Female",
        "params": ("var3_female_flag", "var5_female_flag"),
    },
    "graddeg_flag": {
        "label": "Graduate+",
        "params": ("var3_graddeg_flag", "var5_graddeg_flag"),
    },
    "age_25_45_flag": {
        "label": "Age 25--45",
        "params": ("var3_age_25_45_flag", "var5_age_25_45_flag"),
    },
}

STAR_LEVELS = ((0.01, "***"), (0.05, "**"), (0.10, "*"))


def starify(p: float) -> str:
    for cut, sym in STAR_LEVELS:
        if p < cut:
            return sym
    return ""


def make_cell(coef: float | None, se: float | None, pval: float | None) -> str:
    if coef is None or se is None or pval is None:
        return ""
    return rf"\makecell[c]{{{coef:.2f}{starify(pval)}\\({se:.2f})}}"


def extract_metric(df: pd.DataFrame, model: str, trait_key: str, param: str, field: str) -> float | None:
    match = df[
        (df["model_type"] == model)
        & (df["trait"] == trait_key)
        & (df["param"] == param)
    ]
    if match.empty:
        return None
    value = match.iloc[0][field]
    return None if pd.isna(value) else float(value)


def trait_stat(
    df: pd.DataFrame,
    model: str,
    trait_key: str,
    field: str,
) -> float | None:
    """Return the first non-missing summary field for a given trait."""
    for param in TRAITS[trait_key]["params"]:
        value = extract_metric(df, model, trait_key, param, field)
        if value is not None:
            return value
    return None


def build_table(df: pd.DataFrame) -> str:
    header_labels = " & ".join([""] + [cfg["label"] for cfg in TRAITS.values()]) + r" \\"
    col_spec = r"@{}l" + r"@{\extracolsep{\fill}}c" * len(TRAITS) + r"@{}"

    lines: list[str] = [
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
        header_labels,
        r"\midrule",
        r"\multicolumn{" + str(len(TRAITS) + 1) + r"}{@{}l}{\textbf{\uline{Panel A: OLS}}} \\",
        r"\addlinespace[2pt]",
    ]

    for label_idx, param_desc in enumerate(
        (
            (0, r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Trait} $"),
            (1, r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Trait} \times \text{Startup} $"),
        )
    ):
        param_pos, row_label = param_desc
        row_cells = [row_label]
        for trait_key, cfg in TRAITS.items():
            param = cfg["params"][param_pos]
            coef = extract_metric(df, "OLS", trait_key, param, "coef")
            se = extract_metric(df, "OLS", trait_key, param, "se")
            pval = extract_metric(df, "OLS", trait_key, param, "pval")
            row_cells.append(make_cell(coef, se, pval))
        lines.append(" & ".join(row_cells) + r" \\")

    # OLS summary rows
    pre_row = ["Pre-Covid Mean"]
    n_row = ["N"]
    for trait_key in TRAITS:
        pre_val = trait_stat(df, "OLS", trait_key, "pre_mean")
        n_val = trait_stat(df, "OLS", trait_key, "nobs")
        pre_row.append("" if pre_val is None else f"{pre_val:.2f}")
        n_row.append("" if n_val is None else f"{int(n_val):,}")
    lines.append(r"\midrule")
    lines.append(" & ".join(pre_row) + r" \\")
    lines.append(" & ".join(n_row) + r" \\")
    lines.append(r"\midrule")

    lines.extend(
        [
            r"\multicolumn{" + str(len(TRAITS) + 1) + r"}{@{}l}{\textbf{\uline{Panel B: IV}}} \\",
            r"\addlinespace[2pt]",
        ]
    )

    for label_idx, param_desc in enumerate(
        (
            (0, r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Trait} $"),
            (1, r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Trait} \times \text{Startup} $"),
        )
    ):
        param_pos, row_label = param_desc
        row_cells = [row_label]
        for trait_key, cfg in TRAITS.items():
            param = cfg["params"][param_pos]
            coef = extract_metric(df, "IV", trait_key, param, "coef")
            se = extract_metric(df, "IV", trait_key, param, "se")
            pval = extract_metric(df, "IV", trait_key, param, "pval")
            row_cells.append(make_cell(coef, se, pval))
        lines.append(" & ".join(row_cells) + r" \\")

    # IV summary rows
    lines.append(r"\midrule")
    rkf_row = [r"KP\,rk Wald F"]
    n_iv_row = ["N"]
    for trait_key in TRAITS:
        rkf_val = trait_stat(df, "IV", trait_key, "rkf")
        n_val = trait_stat(df, "IV", trait_key, "nobs")
        rkf_row.append("" if rkf_val is None else f"{rkf_val:.2f}")
        n_iv_row.append("" if n_val is None else f"{int(n_val):,}")
    lines.append(" & ".join(rkf_row) + r" \\")
    lines.append(" & ".join(n_iv_row) + r" \\")

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular*}",
        ]
    )

    table_env = "\n".join(
        [
            r"\begin{table}[h!]",
            r"  \centering",
            *("  " + line for line in lines),
            r"\end{table}",
        ]
    )
    return table_env + "\n"


def compile_pdf(tex_path: Path) -> None:
    pdf_path = tex_path.with_suffix(".pdf")
    if pdf_path.exists():
        pdf_path.unlink()

    commands = []
    if shutil.which("latexmk"):
        commands.append(["latexmk", "-pdf", "-quiet", tex_path.name])
    if shutil.which("pdflatex"):
        commands.append(["pdflatex", "-interaction=nonstopmode", tex_path.name])

    if not commands:
        raise SystemExit("Neither latexmk nor pdflatex found on PATH; cannot compile PDF.")

    for cmd in commands:
        try:
            subprocess.run(cmd, cwd=tex_path.parent, check=True)
            break
        except subprocess.CalledProcessError as exc:
            if cmd is commands[-1]:
                raise SystemExit(f"LaTeX compilation failed: {exc}") from exc
        else:
            continue

    # Clean auxiliary files if latexmk is available.
    if shutil.which("latexmk"):
        subprocess.run(["latexmk", "-c", tex_path.name], cwd=tex_path.parent, check=False)


def main() -> None:
    if not RAW_PATH.exists():
        raise SystemExit(f"Missing traits results CSV: {RAW_PATH}")

    df = pd.read_csv(RAW_PATH)
    df = df[df["trait"].isin(TRAITS.keys())].copy()
    if df.empty:
        raise SystemExit("No matching trait rows found in consolidated results.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    table_env = build_table(df)
    document = "\n".join(
        [
            r"\documentclass{article}",
            r"\usepackage{booktabs}",
            r"\usepackage{makecell}",
            r"\usepackage{amsmath}",
            r"\usepackage{geometry}",
            r"\usepackage{dsfont}",
            r"\usepackage{ulem}",
            r"\geometry{margin=1in}",
            r"\begin{document}",
            r"\section*{User Productivity Heterogeneity (Compact)}",
            table_env,
            r"\end{document}",
            "",
        ]
    )

    OUTPUT_TEX.write_text(document, encoding="utf-8")
    compile_pdf(OUTPUT_TEX)
    print(f"Wrote {OUTPUT_TEX}")
    print(f"Wrote {OUTPUT_TEX.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
