#!/usr/bin/env python3
"""
Build LaTeX tables (base + robustness) for firm_scaling_vacancy_outcomes
from results/raw/<spec>/consolidated_results.csv without reusing repo helpers.

Outputs (written under results/cleaned/):
 - Base (k=5) per-model tables with 3 outcome columns and Pre-mean row
 - Robustness: fill rate min{1..5} per-model tables
 - Robustness: HTV min{1..5} per-model tables for 1/99 and 5/95 winsor sets
 - A wrapper TeX that inputs all fragments; optional PDF compilation
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Dict, Tuple

import pandas as pd


REQUIRED_COLUMNS = [
    "model_type", "outcome", "param", "coef", "se", "pval", "nobs", "rkf", "pre_mean",
]

PARAMS = ["var3", "var5", "var4"]


def stars(p: float) -> str:
    if pd.isna(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def make_cell(coef: float, se: float, p: float, decimals: int = 3) -> str:
    if pd.isna(coef) or pd.isna(se):
        return ""
    # Single-line cell: coefficient with stars and SE in parentheses
    return f"{coef:.{decimals}f}{stars(p)} ({se:.{decimals}f})"


def pretty_param(p: str) -> str:
    # Simpler labels to avoid math-mode complications in tabular
    mapping = {
        "var3": "Remote x Post",
        "var5": "Remote x Post x Startup",
        "var4": "Post x Startup",
    }
    return mapping.get(p, p)


def require(df: pd.DataFrame, cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"Error: {msg}")


def validate_schema(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    require(df, not missing, f"CSV missing required columns: {missing}")
    models = set(df["model_type"].unique())
    require(df, any(m in models for m in ("OLS", "IV")), "No recognised model types (OLS/IV) present")


def check_required_outcomes(df: pd.DataFrame, model: str, outcomes: Iterable[str]) -> None:
    for out in outcomes:
        sub = df[(df.model_type == model) & (df.outcome == out)]
        require(df, not sub.empty, f"Missing rows for model={model}, outcome={out}")
        for p in PARAMS:
            ok = ((sub.param == p).any())
            require(df, ok, f"Missing param {p} for model={model}, outcome={out}")


def first_value(sub: pd.DataFrame, col: str):
    s = sub[col].dropna()
    return None if s.empty else s.iloc[0]


def build_table(df: pd.DataFrame, *, model: str, outcomes: List[str], headers: List[str], caption: str, label: str, decimals: int = 3, include_kp: bool = False) -> str:
    # Validate presence
    check_required_outcomes(df, model, outcomes)

    # Header
    cols = ["Parameter", *headers]
    header_row = " & ".join(cols) + r" \\"

    # Body rows (var3, var5, var4)
    body_lines: List[str] = []
    for p in PARAMS:
        row_cells = [pretty_param(p)]
        for out in outcomes:
            sub = df[(df.model_type == model) & (df.outcome == out) & (df.param == p)]
            if sub.empty:
                row_cells.append("")
                continue
            coef = first_value(sub, "coef")
            se = first_value(sub, "se")
            pval = first_value(sub, "pval")
            row_cells.append(make_cell(coef, se, pval, decimals=decimals))
        body_lines.append(" & ".join(row_cells) + r" \\")

    # Summary rows: N, Pre-mean, KP rk F (IV only)
    # Pull per-outcome stats from any param row subset (they share nobs and pre_mean)
    ns: List[str] = []
    premeans: List[str] = []
    rkfs: List[str] = []
    for out in outcomes:
        sub_any = df[(df.model_type == model) & (df.outcome == out)]
        n = first_value(sub_any, "nobs")
        pm = first_value(sub_any, "pre_mean")
        rk = first_value(sub_any, "rkf") if include_kp else None
        ns.append("" if n is None or pd.isna(n) else f"{int(n):,}")
        premeans.append("" if pm is None or pd.isna(pm) else f"{pm:.3f}")
        rkfs.append("" if rk is None or pd.isna(rk) else f"{rk:.3f}")

    body_lines.append(r"\midrule")
    body_lines.append(" & ".join(["N", *ns]) + r" \\")
    body_lines.append(" & ".join(["Pre-mean", *premeans]) + r" \\")
    if include_kp:
        body_lines.append(" & ".join(["KP rk Wald F", *rkfs]) + r" \\")

    body = "\n".join(body_lines)

    colspec = "l" + "c" * len(outcomes)
    tex_lines = [
        "% Auto-generated table",
        "\\begin{table}[H]",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        "\\centering",
        f"\\begin{{tabular}}{{{colspec}}}",
        "\\toprule",
        header_row,
        "\\midrule",
        body,
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
    ]
    return "\n".join(tex_lines) + "\n"


def write_wrapper(out_dir: Path, include_paths: List[Path]) -> Path:
    wrapper = out_dir / "firm_scaling_vacancy_outcomes_report.tex"
    base_name = "firm_scaling_vacancy_outcomes_base.tex"
    vac_scaled = "firm_scaling_vacancy_outcomes_scaled.tex"
    fr_combined = "firm_scaling_vacancy_outcomes_fillrate_cutoffs.tex"
    htv1_combined = "firm_scaling_vacancy_outcomes_htv_min_1_99.tex"
    htv5_combined = "firm_scaling_vacancy_outcomes_htv_min_5_95.tex"

    parts = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{booktabs}",
        r"\usepackage{adjustbox}",
        
        r"\usepackage{amsmath}",
        r"\usepackage{float}",
        r"\begin{document}",
        r"\section*{Vacancy Outcomes: Base and Robustness}",
        r"\subsection*{Base (k=5)}",
        f"\\input{{{base_name}}}",
        r"\noindent\textit{Notes:} All models include firm and year-half fixed effects with standard errors clustered at the firm level. \textit{Fill rate} is filled within 3 months divided by vacancies, constructed with a minimum vacancy cutoff (base $k=5$; sensitivity tables vary $k$), and is \textbf{not winsorized}. \textit{Hires per vacancy} is join divided by vacancies; cutoffs require $\ge k$ vacancies and winsorization at either 1/99 or 5/95, as indicated. \textit{Pre-mean} is the mean of the outcome in pre-COVID periods.",
        r"\bigskip",
        r"\subsection*{Vacancy Normalizations}",
        f"\\input{{{vac_scaled}}}",
        r"\bigskip",
        r"\subsection*{Fill-Rate Cutoffs (k = 1..5)}",
        f"\\input{{{fr_combined}}}",
        r"\bigskip",
        r"\subsection*{Hires per Vacancy Cutoffs (winsor 1/99)}",
        f"\\input{{{htv1_combined}}}",
        r"\bigskip",
        r"\subsection*{Hires per Vacancy Cutoffs (winsor 5/95)}",
        f"\\input{{{htv5_combined}}}",
        r"\end{document}",
    ]
    wrapper.write_text("\n".join(parts) + "\n")
    return wrapper


def compile_pdf(tex_path: Path) -> None:
    # Use latexmk if available
    if shutil.which("latexmk") is None:
        print("latexmk not found; skipping compile. You can compile manually.")
        return
    cwd = tex_path.parent
    cmd = ["latexmk", "-pdf", "-quiet", tex_path.name]
    print("→ compiling:", " ".join(cmd), "in", cwd)
    subprocess.run(cmd, check=True, cwd=str(cwd))
    print("✓ PDF:", cwd / tex_path.with_suffix(".pdf").name)


def main() -> None:
    ap = argparse.ArgumentParser(description="Format vacancy outcomes tables and optional PDF")
    ap.add_argument("--spec-dir", required=True, help="Directory containing consolidated_results.csv")
    ap.add_argument("--compile", action="store_true", help="Compile wrapper to PDF via latexmk")
    ap.add_argument("--decimals", type=int, default=3, help="Decimal places for coef/SE")
    args = ap.parse_args()

    spec_dir = Path(args.spec_dir).expanduser().resolve()
    csv_path = spec_dir / "consolidated_results.csv"
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    out_dir = spec_dir.parents[1] / "cleaned"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    validate_schema(df)

    dec = args.decimals

    # Base outcomes (k=5)
    base_outcomes = [
        "vacancies",
        "fill_rate",  # alias to min5
        "hires_to_vacancies_winsor",  # alias to min5@1/99
    ]
    base_headers = [
        "Vacancies",
        "Fill Rate ($\\ge 5$ vacancies)",
        "Hires per vacancy (winsor 1/99, $\\ge 5$)",
    ]

    # Fill-rate min-k
    fr_outcomes = [f"fill_rate_min{k}" for k in range(1, 6)]
    fr_headers = [f"$\\ge {k}$" for k in range(1, 6)]

    # HTV min-k (1/99)
    htv_outcomes = [f"hires_to_vacancies_winsor_min{k}" for k in range(1, 6)]
    htv_headers = [f"$\\ge {k}$" for k in range(1, 6)]

    # HTV min-k (5/95)
    htv95_outcomes = [f"hires_to_vacancies_winsor95_min{k}" for k in range(1, 6)]
    htv95_headers = [f"$\\ge {k}$" for k in range(1, 6)]

    written: List[Path] = []
    # Generic builder: Panel A (OLS) and Panel B (IV) combined
    def build_panel_combined(df: pd.DataFrame, *, outcomes: List[str], headers: List[str], caption: str, label: str) -> str:
        # Validate both models first
        check_required_outcomes(df, "OLS", outcomes)
        check_required_outcomes(df, "IV", outcomes)

        header_row = " & ".join(["Parameter", *headers]) + r" \\\\"

        def panel_block(model: str) -> List[str]:
            lines: List[str] = []
            # Panel label
            panel_name = "Panel A: OLS" if model == "OLS" else "Panel B: IV"
            span = 1 + len(outcomes)
            # Avoid f-string backslash issues: build with format()
            lines.append("\\multicolumn{{{}}}{{l}}{{\\textit{{{}}}}} \\\\".format(span, panel_name))
            # Rows
            for p in PARAMS:
                row_cells = [pretty_param(p)]
                for out in outcomes:
                    sub = df[(df.model_type == model) & (df.outcome == out) & (df.param == p)]
                    coef = first_value(sub, "coef")
                    se = first_value(sub, "se")
                    pval = first_value(sub, "pval")
                    row_cells.append(make_cell(coef, se, pval, decimals=dec))
                lines.append(" & ".join(row_cells) + r" \\")
            # Summary rows
            ns: List[str] = []
            premeans: List[str] = []
            rkfs: List[str] = []
            for out in outcomes:
                sub_any = df[(df.model_type == model) & (df.outcome == out)]
                n = first_value(sub_any, "nobs")
                pm = first_value(sub_any, "pre_mean")
                rk = first_value(sub_any, "rkf") if model == "IV" else None
                ns.append("" if n is None or pd.isna(n) else f"{int(n):,}")
                premeans.append("" if pm is None or pd.isna(pm) else f"{pm:.3f}")
                rkfs.append("" if rk is None or pd.isna(rk) else f"{rk:.3f}")
            lines.append(r"\midrule")
            lines.append(" & ".join(["N", *ns]) + r" \\")
            lines.append(" & ".join(["Pre-mean", *premeans]) + r" \\")
            if model == "IV":
                lines.append(" & ".join(["KP rk Wald F", *rkfs]) + r" \\")
            return lines

        body_lines: List[str] = []
        body_lines.extend(panel_block("OLS"))
        body_lines.append(r"\midrule")
        body_lines.extend(panel_block("IV"))

        colspec = "l" + "c" * len(outcomes)
        table_lines = [
            "% Auto-generated table",
            "\\begin{table}[H]",
            f"\\caption{{{caption}}}",
            f"\\label{{{label}}}",
            "\\centering",
            f"\\begin{{adjustbox}}{{max width=\\textwidth}}",
            f"\\begin{{tabular}}{{{colspec}}}",
            "\\toprule",
            header_row,
            "\\midrule",
            *body_lines,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{adjustbox}",
            "\\end{table}",
        ]
        return "\n".join(table_lines) + "\n"

    # Base combined
    base_combined_tex = build_panel_combined(
        df,
        outcomes=base_outcomes,
        headers=base_headers,
        caption="Vacancy Outcomes – Base (k=5), Panel A: OLS; Panel B: IV",
        label="tab:vac_base_combined",
    )
    base_combined_path = out_dir / "firm_scaling_vacancy_outcomes_base.tex"
    base_combined_path.write_text(base_combined_tex)
    written.append(base_combined_path)
    print("✓ Wrote", base_combined_path)

    # Vacancy normalizations: per-thousand and per pre-COVID employees (exclude raw)
    vac_scaled_tex = build_panel_combined(
        df,
        outcomes=["vacancies_thousands", "vpe_pc_winsor"],
        headers=["Vacancies / 1000", "Vacancies per pre-COVID employees"],
        caption="Vacancy Normalizations, Panel A: OLS; Panel B: IV",
        label="tab:vac_scaled",
    )
    vac_scaled_path = out_dir / "firm_scaling_vacancy_outcomes_scaled.tex"
    vac_scaled_path.write_text(vac_scaled_tex)
    written.append(vac_scaled_path)
    print("✓ Wrote", vac_scaled_path)

    # Fill-rate cutoff tables (combined)
    fr_combined_tex = build_panel_combined(
        df,
        outcomes=fr_outcomes,
        headers=fr_headers,
        caption="Fill Rate by Min Vacancies (k = 1..5), Panel A: OLS; Panel B: IV",
        label="tab:vac_fr_cutoffs",
    )
    fr_combined_path = out_dir / "firm_scaling_vacancy_outcomes_fillrate_cutoffs.tex"
    fr_combined_path.write_text(fr_combined_tex)
    written.append(fr_combined_path)
    print("✓ Wrote", fr_combined_path)

    # HTV 1/99 (combined)
    htv1_combined_tex = build_panel_combined(
        df,
        outcomes=htv_outcomes,
        headers=htv_headers,
        caption="Hires per Vacancy (winsor 1/99) by Min Vacancies (k = 1..5), Panel A: OLS; Panel B: IV",
        label="tab:vac_htv_min_1_99",
    )
    htv1_combined_path = out_dir / "firm_scaling_vacancy_outcomes_htv_min_1_99.tex"
    htv1_combined_path.write_text(htv1_combined_tex)
    written.append(htv1_combined_path)
    print("✓ Wrote", htv1_combined_path)

    # HTV 5/95 (combined)
    htv5_combined_tex = build_panel_combined(
        df,
        outcomes=htv95_outcomes,
        headers=htv95_headers,
        caption="Hires per Vacancy (winsor 5/95) by Min Vacancies (k = 1..5), Panel A: OLS; Panel B: IV",
        label="tab:vac_htv_min_5_95",
    )
    htv5_combined_path = out_dir / "firm_scaling_vacancy_outcomes_htv_min_5_95.tex"
    htv5_combined_path.write_text(htv5_combined_tex)
    written.append(htv5_combined_path)
    print("✓ Wrote", htv5_combined_path)

    # Wrapper (include base combined first, then robustness tables)
    wrapper = write_wrapper(out_dir, written)
    print("✓ Wrote", wrapper)
    if args.compile:
        compile_pdf(wrapper)


if __name__ == "__main__":
    main()
