#!/usr/bin/env python3
"""Build a compact LaTeX table that *scans* for statistically significant
equity-related coefficients (p < 0.10) in the backfill equity package.

This is intentionally descriptive:
  - It does NOT interpret magnitudes.
  - It only reports where equity-related terms are statistically significant.
  - It filters to the core outcomes used in the equity tech note:
      • firm scaling: growth_rate_we
      • user productivity: total_contributions_q100
"""

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

OUT_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_significance_scan.tex"

STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
INDENT: Final[str] = r"\hspace{1em}"

PVAL_CUTOFF: Final[float] = 0.10


def stars(p: float) -> str:
    for cutoff, symbol in STAR_RULES:
        if p < cutoff:
            return symbol
    return ""


def fmt_num(x: float) -> str:
    ax = abs(x)
    if ax >= 1e4 or (0 < ax < 1e-2):
        return f"{x:.2e}"
    return f"{x:.2f}"


def coef_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{fmt_num(coef)}{stars(pval)}\\({fmt_num(se)})}}"


def latex_escape(text: str) -> str:
    # Minimal escaping for table cells.
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
        .replace("#", r"\#")
    )


PARAM_LABEL: Final[dict[str, str]] = {
    # Firm-level equity (binary)
    "eq_any_firm_covid": r"$ \text{EquityFirm} \times \mathds{1}(\text{Post}) $",
    "var3_eq_firm": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{EquityFirm} $",
    "var5_eq_firm": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{EquityFirm} $",
    # Firm-level equity (binary) but named via `any`
    "var3_eq_any": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{EquityFirm} $",
    "var5_eq_any": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{Equity} $",
    # Cell-level / intensity variants
    "eq_any_zero": r"$ \text{Equity} $",
    "eq_share_zero": r"$ \text{EquityShare} $",
    "eq_share_firm_covid": r"$ \text{EquityShareFirm} \times \mathds{1}(\text{Post}) $",
    "eq_count_mean_firm_covid": r"$ \text{EquityCountMeanFirm} \times \mathds{1}(\text{Post}) $",
    "var3_eq_share": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{EquityShareFirm} $",
}


def pretty_param(param: str) -> str:
    return PARAM_LABEL.get(param, latex_escape(param))


def load_significant_rows() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []

    # --- Core heterogeneity (pooled interaction) ---
    firm_het = pd.read_csv(
        require_file(
            RESULTS_RAW / "firm_scaling_llm_equity_heterogeneity" / "consolidated_results.csv",
            nonempty=True,
            purpose="firm equity heterogeneity consolidated results",
        )
    )
    firm_het = firm_het[
        (firm_het["outcome"] == "growth_rate_we")
        & (firm_het["spec_variant"] == "pooled_interaction")
        & (firm_het["split_group"] == "all")
        & (firm_het["param"].astype(str).str.contains("eq"))
        & (firm_het["pval"].notna())
        & (firm_het["pval"] < PVAL_CUTOFF)
    ].copy()
    if not firm_het.empty:
        firm_het["panel"] = "firm"
        firm_het["spec"] = "Heterogeneity (pooled)"
        rows.append(firm_het[["panel", "spec", "model_type", "param", "coef", "se", "pval"]])

    user_het = pd.read_csv(
        require_file(
            RESULTS_RAW / "user_productivity_llm_equity_heterogeneity_precovid" / "consolidated_results.csv",
            nonempty=True,
            purpose="user equity heterogeneity consolidated results",
        )
    )
    user_het = user_het[
        (user_het["outcome"] == "total_contributions_q100")
        & (user_het["spec_variant"] == "pooled_interaction")
        & (user_het["split_group"] == "all")
        & (user_het["param"].astype(str).str.contains("eq"))
        & (user_het["pval"].notna())
        & (user_het["pval"] < PVAL_CUTOFF)
    ].copy()
    if not user_het.empty:
        user_het["panel"] = "user"
        user_het["spec"] = "Heterogeneity (pooled)"
        rows.append(user_het[["panel", "spec", "model_type", "param", "coef", "se", "pval"]])

    # --- No-CB modes: additional equity blocks (backfill only) ---
    firm_no_cb = pd.read_csv(
        require_file(
            RESULTS_RAW / "firm_scaling_llm_equity_no_cb_modes" / "consolidated_results.csv",
            nonempty=True,
            purpose="firm no-CB equity consolidated results",
        )
    )
    firm_no_cb = firm_no_cb[
        (firm_no_cb["sample_mode"] == "backfill")
        & (firm_no_cb["outcome"] == "growth_rate_we")
        & (firm_no_cb["param"].astype(str).str.contains("eq"))
        & (firm_no_cb["pval"].notna())
        & (firm_no_cb["pval"] < PVAL_CUTOFF)
        # avoid duplicating the core heterogeneity spec in this scan table
        & (firm_no_cb["analysis_block"] != "core_pooled")
    ].copy()
    if not firm_no_cb.empty:
        firm_no_cb["panel"] = "firm"
        firm_no_cb["spec"] = (
            "No-CB: "
            + firm_no_cb["analysis_block"].astype(str)
            + " ("
            + firm_no_cb["equity_measure"].astype(str)
            + ")"
        )
        rows.append(firm_no_cb[["panel", "spec", "model_type", "param", "coef", "se", "pval"]])

    user_no_cb = pd.read_csv(
        require_file(
            RESULTS_RAW / "user_productivity_llm_equity_no_cb_modes_precovid" / "consolidated_results.csv",
            nonempty=True,
            purpose="user no-CB equity consolidated results",
        )
    )
    user_no_cb = user_no_cb[
        (user_no_cb["sample_mode"] == "backfill")
        & (user_no_cb["outcome"] == "total_contributions_q100")
        & (user_no_cb["param"].astype(str).str.contains("eq"))
        & (user_no_cb["pval"].notna())
        & (user_no_cb["pval"] < PVAL_CUTOFF)
        & (user_no_cb["analysis_block"] != "core_pooled")
    ].copy()
    if not user_no_cb.empty:
        user_no_cb["panel"] = "user"
        user_no_cb["spec"] = (
            "No-CB: "
            + user_no_cb["analysis_block"].astype(str)
            + " ("
            + user_no_cb["equity_measure"].astype(str)
            + ")"
        )
        rows.append(user_no_cb[["panel", "spec", "model_type", "param", "coef", "se", "pval"]])

    # --- Variants ---
    firm_var = pd.read_csv(
        require_file(
            RESULTS_RAW / "firm_scaling_llm_equity_variants" / "consolidated_results.csv",
            nonempty=True,
            purpose="firm equity variants consolidated results",
        )
    )
    firm_var = firm_var[
        (firm_var["outcome"] == "growth_rate_we")
        & (firm_var["param"].astype(str).str.contains("eq"))
        & (firm_var["pval"].notna())
        & (firm_var["pval"] < PVAL_CUTOFF)
    ].copy()
    if not firm_var.empty:
        firm_var["panel"] = "firm"
        firm_var["spec"] = "Variants: " + firm_var["spec_variant"].astype(str)
        rows.append(firm_var[["panel", "spec", "model_type", "param", "coef", "se", "pval"]])

    user_var = pd.read_csv(
        require_file(
            RESULTS_RAW / "user_productivity_llm_equity_variants_precovid" / "consolidated_results.csv",
            nonempty=True,
            purpose="user equity variants consolidated results",
        )
    )
    user_var = user_var[
        (user_var["outcome"] == "total_contributions_q100")
        & (user_var["param"].astype(str).str.contains("eq"))
        & (user_var["pval"].notna())
        & (user_var["pval"] < PVAL_CUTOFF)
    ].copy()
    if not user_var.empty:
        user_var["panel"] = "user"
        user_var["spec"] = "Variants: " + user_var["spec_variant"].astype(str)
        rows.append(user_var[["panel", "spec", "model_type", "param", "coef", "se", "pval"]])

    if not rows:
        return pd.DataFrame(columns=["panel", "spec", "model_type", "param", "coef", "se", "pval"])

    out = pd.concat(rows, ignore_index=True)
    out["spec"] = out["spec"].astype(str)
    out["param"] = out["param"].astype(str)
    out["model_type"] = out["model_type"].astype(str)
    return out


def build_table(df: pd.DataFrame) -> str:
    cols = [
        "Specification & Model & Parameter & Coef. (SE) & $p$-value" + LB,
        MID,
    ]

    def add_panel(title: str, panel_df: pd.DataFrame) -> None:
        cols.append(rf"\multicolumn{{5}}{{@{{}}l}}{{\textbf{{\uline{{{title}}}}}}} {LB}")
        cols.append(r"\addlinespace[2pt]")
        if panel_df.empty:
            cols.append(INDENT + r"(no equity terms with $p<0.10$ in scan scope)" + r" &  &  &  &  " + LB)
            cols.append(MID)
            return

        work = panel_df.sort_values(["spec", "model_type", "param"]).copy()
        for _, r in work.iterrows():
            spec = latex_escape(str(r["spec"]))
            model = latex_escape(str(r["model_type"]))
            param = pretty_param(str(r["param"]))
            coef = float(r["coef"])
            se = float(r["se"])
            pval = float(r["pval"])
            cols.append(
                " & ".join(
                    [
                        spec,
                        model,
                        INDENT + param,
                        coef_cell(coef, se, pval),
                        f"{pval:.3f}",
                    ]
                )
                + LB
            )
        cols.append(MID)

    add_panel(
        "Panel A: Firm scaling (growth rate)",
        df[df["panel"] == "firm"],
    )
    add_panel(
        "Panel B: User productivity (contribution rank)",
        df[df["panel"] == "user"],
    )

    lines = [
        r"\centering",
        r"\begin{tabular*}{\linewidth}{@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}}",
        TOP,
        *cols,
        BOTTOM,
        r"\end{tabular*}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)
    df = load_significant_rows()
    OUT_TEX.write_text(build_table(df), encoding="utf-8")
    print(f"Wrote {OUT_TEX}")


if __name__ == "__main__":
    main()

