#!/usr/bin/env python3
"""Format quad specification outputs into LaTeX tables."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIRM_CSV = ROOT / "results/raw/firm_quad/consolidated_results.csv"
USER_CSV = ROOT / "results/raw/user_quad/consolidated_results.csv"
OUT_DIR = ROOT / "results/cleaned"

OUT_DIR.mkdir(parents=True, exist_ok=True)

COEF_DECIMALS = 2
SE_DECIMALS = 2

LABELS_BASE = {
    "var3": r"Remote $\times$ Post",
    "var5": r"Remote $\times$ Post $\times$ Startup",
    "var4": r"Post $\times$ Startup",
}

INTERACTION_LABELS = {
    "rent": {
        "var3_rent": r"Remote $\times$ Post $\times$ Rent",
        "var5_rent": r"Remote $\times$ Post $\times$ Startup $\times$ Rent",
        "var4_rent": r"Post $\times$ Startup $\times$ Rent",
    },
    "hhi": {
        "var3_hhi": r"Remote $\times$ Post $\times$ HHI",
        "var5_hhi": r"Remote $\times$ Post $\times$ Startup $\times$ HHI",
        "var4_hhi": r"Post $\times$ Startup $\times$ HHI",
    },
    "seniority": {
        "var3_sen": r"Remote $\times$ Post $\times$ Seniority (L4+)",
        "var5_sen": r"Remote $\times$ Post $\times$ Startup $\times$ Seniority (L4+)",
        "var4_sen": r"Post $\times$ Startup $\times$ Seniority (L4+)",
    },
}

FIRM_OUTCOME_LABELS = {
    "growth_rate_we": r"Growth (wins.)",
    "join_rate_we": r"Join (wins.)",
    "leave_rate_we": r"Leave (wins.)",
}

USER_OUTCOME_LABELS = {
    "total_contributions_q100": r"Total Contributions (pctl)",
}


def significance_stars(pval: float | int | None) -> str:
    if pval is None or np.isnan(pval):
        return ""
    if pval <= 0.01:
        return "***"
    if pval <= 0.05:
        return "**"
    if pval <= 0.10:
        return "*"
    return ""


def fmt_coef(value: float | int | None, pval: float | int | None) -> str:
    if value is None or np.isnan(value):
        return "-"
    adj = 0.0 if abs(value) < 10 ** (-(COEF_DECIMALS + 1)) else value
    stars = significance_stars(pval)
    return f"{adj:.{COEF_DECIMALS}f}{stars}"


def fmt_se(value: float | int | None) -> str:
    if value is None or np.isnan(value):
        return "-"
    adj = 0.0 if abs(value) < 10 ** (-(SE_DECIMALS + 1)) else value
    return f"({adj:.{SE_DECIMALS}f})"


def fmt_number(value: float | int | None, decimals: int = 2) -> str:
    if value is None or np.isnan(value):
        return "-"
    return f"{value:,.{decimals}f}"


def get_row(df: pd.DataFrame, *, model: str, outcome: str | None, param: str) -> pd.Series | None:
    mask = (df["model_type"] == model) & (df["param"] == param)
    if outcome is not None and "outcome" in df.columns:
        mask &= df["outcome"] == outcome
    subset = df.loc[mask]
    if subset.empty:
        return None
    return subset.iloc[0]


def build_panel_rows(
    df: pd.DataFrame,
    *,
    model: str,
    outcome_keys: Iterable[str],
    row_params: Iterable[Tuple[str, str]],
    include_outcome: bool,
) -> List[str]:
    lines: List[str] = []
    for idx, (param, label) in enumerate(row_params):
        coef_parts = [label]
        se_parts = [" "]
        for outcome in outcome_keys:
            row = get_row(df, model=model, outcome=outcome if include_outcome else None, param=param)
            coef = fmt_coef(row["coef"] if row is not None else np.nan, row["pval"] if row is not None else np.nan)
            se = fmt_se(row["se"] if row is not None else np.nan)
            coef_parts.append(coef)
            se_parts.append(se)
        lines.append(" & ".join(coef_parts) + r" \\")
        lines.append(" & ".join(se_parts) + r" \\")
        if idx != len(row_params) - 1:
            lines.append(r"\addlinespace[0.35em]")
    return lines


def build_footer(
    df: pd.DataFrame,
    *,
    outcome_keys: Iterable[str],
    include_outcome: bool,
    n_source_model: str,
    rkf_model: str | None = None,
) -> List[str]:
    outcome_keys = list(outcome_keys)
    footer_lines: List[str] = []
    # Pre-Covid mean
    pre_means = []
    ns = []
    rkfs = []
    for outcome in outcome_keys:
        row = get_row(df, model=n_source_model, outcome=outcome if include_outcome else None, param="var3")
        pre_means.append(fmt_number(row["pre_mean"] if row is not None else np.nan, decimals=2))
        ns.append(f"{int(row['nobs']):,}" if row is not None and not np.isnan(row["nobs"]) else "-")
        if rkf_model is not None:
            rk_row = get_row(df, model=rkf_model, outcome=outcome if include_outcome else None, param="var3")
            rkfs.append(fmt_number(rk_row["rkf"] if rk_row is not None else np.nan, decimals=1))
    footer_lines.append("Pre-COVID Mean" + " & " + " & ".join(pre_means) + r" \\")
    footer_lines.append("N" + " & " + " & ".join(ns) + r" \\")
    if rkf_model is not None:
        footer_lines.append("KP rk Wald F" + " & " + " & ".join(rkfs) + r" \\")
    return footer_lines


def format_table(
    *,
    df: pd.DataFrame,
    spec: str,
    caption: str,
    notes: str,
    outcome_labels: Dict[str, str],
    interaction_labels: Dict[str, str] | None,
    output_path: Path,
    include_outcome: bool,
) -> None:
    df_spec = df[df["spec"] == spec].copy() if "spec" in df.columns else df.copy()

    outcome_keys = list(outcome_labels.keys())
    header_cols = [f"({idx})" for idx in range(1, len(outcome_keys) + 1)]

    base_rows = list(LABELS_BASE.items())
    interaction_rows: List[Tuple[str, str]] = []
    if interaction_labels:
        # preserve parameter order based on LABELS dict keys order
        for param, label in interaction_labels.items():
            if param in df_spec["param"].values:
                interaction_rows.append((param, label))
    row_sequence = base_rows + interaction_rows

    table_lines: List[str] = []
    table_lines.append(r"\begin{table}[H]")
    table_lines.append(r"\centering")
    table_lines.append(caption)
    table_lines.append(r"\begin{threeparttable}")
    table_lines.append(r"\begin{adjustbox}{max width=\textwidth}")
    column_spec = "l" + "c" * len(outcome_keys)
    table_lines.append(fr"\begin{{tabular}}{{{column_spec}}}")
    table_lines.append(r"\toprule")
    table_lines.append(" & " + " & ".join(header_cols) + r" \\")
    table_lines.append(" & " + " & ".join(outcome_labels.values()) + r" \\")
    table_lines.append(r"\midrule")
    table_lines.append(r"\multicolumn{" + str(len(outcome_keys) + 1) + r"}{l}{\textbf{Panel A: OLS}} \\")
    table_lines.append(r"\addlinespace")
    table_lines.extend(
        build_panel_rows(
            df_spec,
            model="OLS",
            outcome_keys=outcome_keys,
            row_params=row_sequence,
            include_outcome=include_outcome,
        )
    )
    table_lines.append(r"\midrule")
    table_lines.append(r"\multicolumn{" + str(len(outcome_keys) + 1) + r"}{l}{\textbf{Panel B: IV}} \\")
    table_lines.append(r"\addlinespace")
    table_lines.extend(
        build_panel_rows(
            df_spec,
            model="IV",
            outcome_keys=outcome_keys,
            row_params=row_sequence,
            include_outcome=include_outcome,
        )
    )
    table_lines.append(r"\midrule")
    table_lines.extend(
        build_footer(
            df_spec,
            outcome_keys=outcome_keys,
            include_outcome=include_outcome,
            n_source_model="OLS",
            rkf_model="IV",
        )
    )
    table_lines.append(r"\bottomrule")
    table_lines.append(r"\end{tabular}")
    table_lines.append(r"\end{adjustbox}")
    table_lines.append(r"\begin{tablenotes}")
    table_lines.append(r"\footnotesize")
    table_lines.append(notes)
    table_lines.append(r"\end{tablenotes}")
    table_lines.append(r"\end{threeparttable}")
    table_lines.append(r"\end{table}")

    output_path.write_text("\n".join(table_lines) + "\n")


def main() -> None:
    firm_df = pd.read_csv(FIRM_CSV)
    user_df = pd.read_csv(USER_CSV)

    # Firm tables
    for spec in ["baseline", "rent", "hhi", "seniority"]:
        inter_labels = INTERACTION_LABELS.get(spec)
        caption = {
            "baseline": r"\caption{Firm Scaling — Baseline Quad Specification}",
            "rent": r"\caption{Firm Scaling — Rent Interaction (Quad)}",
            "hhi": r"\caption{Firm Scaling — HHI Interaction (Quad)}",
            "seniority": r"\caption{Firm Scaling — Seniority Interaction (Quad)}",
        }[spec]
        notes = r"\item \textit{Notes:} Firm-level regressions with firm and half-year fixed effects; standard errors clustered at the firm level. Remote indicates firm remote share, Startup indicates firms $\leq$10 years old. * $p<0.10$, ** $p<0.05$, *** $p<0.01$."
        out_path = OUT_DIR / f"firm_scaling_quad_{spec}.tex"
        format_table(
            df=firm_df,
            spec=spec,
            caption=caption,
            notes=notes,
            outcome_labels=FIRM_OUTCOME_LABELS,
            interaction_labels=inter_labels,
            output_path=out_path,
            include_outcome=True,
        )

    # User tables (single outcome)
    for spec in ["baseline", "rent", "hhi", "seniority"]:
        inter_labels = INTERACTION_LABELS.get(spec)
        caption = {
            "baseline": r"\caption{User Productivity — Baseline Quad Specification}",
            "rent": r"\caption{User Productivity — Rent Interaction (Quad)}",
            "hhi": r"\caption{User Productivity — HHI Interaction (Quad)}",
            "seniority": r"\caption{User Productivity — Seniority Interaction (Quad)}",
        }[spec]
        notes = r"\item \textit{Notes:} Worker-level regressions with user-by-firm and half-year fixed effects; standard errors clustered at the user level. Dependent variable is percentile rank of total contributions. * $p<0.10$, ** $p<0.05$, *** $p<0.01$."
        out_path = OUT_DIR / f"user_productivity_quad_{spec}.tex"
        format_table(
            df=user_df[user_df["spec"] == spec],
            spec=spec,
            caption=caption,
            notes=notes,
            outcome_labels=USER_OUTCOME_LABELS,
            interaction_labels=inter_labels,
            output_path=out_path,
            include_outcome=False,
        )


if __name__ == "__main__":
    main()
