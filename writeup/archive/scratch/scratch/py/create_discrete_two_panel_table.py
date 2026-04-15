#!/usr/bin/env python3
"""Create a two‑panel LaTeX table comparing discrete remote treatments.

Panel A: Full‑remote (remote == 1)
Panel B: Hybrid (0 < remote < 1)

Supports:
  - Firm scaling (multiple outcomes)
  - User productivity (user panel variants)

Inputs are the consolidated Stata CSVs under results/raw/…
Outputs a single TeX table under results/cleaned/… using the repo's table style
  (booktabs + makecell + centering), including significance stars, FE indicators
  (when appropriate), pre‑COVID mean, KP rk Wald F (for IV), and N.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import textwrap
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_DIR = PROJECT_ROOT / "results" / "raw"
CLEAN_DIR = PROJECT_ROOT / "results" / "cleaned"


# ---------------------------------------------------------------------------
# Formatting helpers (consistent with other table scripts)
# ---------------------------------------------------------------------------
STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# Column labels for firm outcomes
FIRM_OUTCOME_LABEL = {
    "growth_rate_we": r"\makecell[c]{Growth\\(wins.)}",
    "join_rate_we": r"\makecell[c]{Join\\(wins.)}",
    "leave_rate_we": r"\makecell[c]{Leave\\(wins.)}",
}


def column_format(n_numeric: int) -> str:
    pad = r"@{\hspace{4pt}}"
    body = (pad + r">{\centering\arraybackslash}X" + pad) * n_numeric
    return "l" + body


PREAMBLE_FLEX = r"""{\scriptsize%
\setlength{\tabcolsep}{3pt}%
\renewcommand{\arraystretch}{0.95}%
%
"""
POSTAMBLE_FLEX = r"}"


def build_panel(
    df: pd.DataFrame,
    model: str,
    outcomes: list[str],
    outcome_labels: dict[str, str],
    include_kp: bool,
    param3: str = "var3",
    param5: str = "var5",
) -> str:
    # Column headers: (1..K) and short outcome names
    col_nums = [f"({i})" for i in range(1, len(outcomes) + 1)]
    header_nums = " & ".join(["", *col_nums]) + " \\"  # first empty is the stub column
    sub_hdr = ""

    # Coefficient rows (var3, var5)
    rows: list[str] = []
    for p_name, p_label_key in ((param3, "var3"), (param5, "var5")):
        cells = [PARAM_LABEL[p_label_key]]
        for outcome in outcomes:
            sub = df.query(
                "model_type == @model and outcome == @outcome and param == @p_name"
            ).head(1)
            if sub.empty:
                cells.append("")
            else:
                coef, se, p = sub.iloc[0][["coef", "se", "pval"]]
                cells.append(f"\\makecell[c]{{{coef:.2f}{stars(p)}\\\\({se:.2f})}}")
        rows.append(" & ".join(cells) + " \\")
    coef_block = "\n".join(rows)

    # Summary rows
    def stat_row(label: str, field: str, fmt: str | None = None) -> str:
        cells = [label]
        for outcome in outcomes:
            sub = df[(df["model_type"] == model) & (df["outcome"] == outcome)].head(1)
            if sub.empty or pd.isna(sub.iloc[0].get(field, None)):
                cells.append("")
            else:
                v = sub.iloc[0][field]
                cells.append(fmt.format(v) if fmt else str(v))
        return " & ".join(cells) + " \\"  # EOL

    pre_mean_row = stat_row("Pre-Covid Mean", "pre_mean", "{:.2f}")
    kp_row = stat_row("KP rk Wald F", "rkf", "{:.2f}") if include_kp else ""
    n_row = stat_row("N", "nobs", "{:,}")

    # Assemble the tabularx block
    col_fmt = "l" + ("c" * len(outcomes))
    tabular = textwrap.dedent(
        rf"""
        \begin{{tabular}}{{{col_fmt}}}
        \toprule
        {header_nums}
        \midrule
        \midrule
        {coef_block}
        \midrule
        {pre_mean_row}
        {kp_row}
        {n_row}
        \bottomrule
        \end{{tabular}}
        """
    )

    return PREAMBLE_FLEX + tabular + POSTAMBLE_FLEX


def main() -> None:
    p = argparse.ArgumentParser(description="Two‑panel discrete remote table (Full‑remote vs Hybrid)")
    p.add_argument("--spec", choices=["firm_scaling", "user_productivity"], required=True)
    p.add_argument("--model", choices=["ols", "iv"], default="iv")
    p.add_argument("--variant", default="precovid", help="User panel variant (user_productivity only)")
    args = p.parse_args()

    model = "IV" if args.model.lower() == "iv" else "OLS"
    include_kp = model == "IV"

    if args.spec == "firm_scaling":
        dir_full = RAW_DIR / "firm_scaling_fullremote" / "consolidated_results.csv"
        dir_hyb = RAW_DIR / "firm_scaling_hybrid" / "consolidated_results.csv"
        outcomes = ["growth_rate_we", "join_rate_we", "leave_rate_we"]
        outcome_labels = FIRM_OUTCOME_LABEL
        tex_out = CLEAN_DIR / f"firm_scaling_discrete_two_panel_{args.model}.tex"
        caption = f"Firm Scaling (Discrete Remote) — {model}"
        label = f"tab:firm_scaling_discrete_{args.model}"
    else:
        base = f"user_productivity_{args.variant}"
        dir_full = RAW_DIR / f"{base}_fullremote" / "consolidated_results.csv"
        dir_hyb = RAW_DIR / f"{base}_hybrid" / "consolidated_results.csv"
        outcomes = ["total_contributions_q100"]
        outcome_labels = {"total_contributions_q100": "Total Contrib. (pct. rk)"}
        tex_out = CLEAN_DIR / f"{base}_discrete_two_panel_{args.model}.tex"
        caption = f"User Productivity ({args.variant}, Discrete Remote) — {model}"
        label = f"tab:user_prod_{args.variant}_discrete_{args.model}"

    # Load CSVs
    if not dir_full.exists() or not dir_hyb.exists():
        raise FileNotFoundError(f"Missing inputs: {dir_full} or {dir_hyb}")

    df_full = pd.read_csv(dir_full)
    df_hyb = pd.read_csv(dir_hyb)

    # Build panels
    if args.spec == "firm_scaling":
        panel_full = build_panel(
            df_full, model, outcomes, outcome_labels, include_kp,
            param3="var3_fullrem", param5="var5_fullrem",
        ).rstrip()
        panel_hyb = build_panel(
            df_hyb, model, outcomes, outcome_labels, include_kp,
            param3="var3_hybrid", param5="var5_hybrid",
        ).rstrip()
    else:
        panel_full = build_panel(
            df_full, model, outcomes, outcome_labels, include_kp,
            param3="var3_fullrem", param5="var5_fullrem",
        ).rstrip()
        panel_hyb = build_panel(
            df_hyb, model, outcomes, outcome_labels, include_kp,
            param3="var3_hybrid", param5="var5_hybrid",
        ).rstrip()

    # Compose final two‑panel table
    lines = [
        "\\begin{table}[H]",
        "\\centering",
        "{\\scriptsize\\centering",
        f"  \\caption{{{caption}}}",
        f"  \\label{{{label}}}",
        "}",
        "\\centering",
        "\\textbf{Panel A: Full‑Remote (Remote = 1)}\\\\[2pt]",
        panel_full,
        "\\vspace{0.6em}",
        "\\textbf{Panel B: Hybrid (0 < Remote < 1)}\\\\[2pt]",
        panel_hyb,
        "\\end{table}",
    ]

    tex_out.parent.mkdir(parents=True, exist_ok=True)
    tex_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote LaTeX table to {tex_out.resolve()}")


if __name__ == "__main__":
    main()
