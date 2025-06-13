#!/usr/bin/env python3
"""Generate LaTeX tables for the *Lean‐period* user mechanism tests.

This mirrors `create_user_mechanisms_table.py` but points to the results
produced by `spec/user_mechanisms_lean.do`.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]


# Directory & filenames ------------------------------------------------------
# ---------------------------------------------------------------------------
# Variant handling mirroring the baseline mechanisms builder.
# Allow panel-sample variants (unbalanced / balanced / precovid / balanced_pre).
# ---------------------------------------------------------------------------

import argparse

DEFAULT_VARIANT = "unbalanced"

parser = argparse.ArgumentParser(description="Create lean user mechanisms regression tables")
parser.add_argument(
    "--variant",
    choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
    default=DEFAULT_VARIANT,
    help="Which user_panel sample variant to load (default: %(default)s)",
)
# Optional comma-separated mechanism exclusion list
parser.add_argument(
    "--exclude",
    default="",
    help="Comma-separated list of mechanism dimensions to exclude (e.g. Wage)",
)

args = parser.parse_args()

variant = args.variant

# ------------------------------------------------------------------
# Apply exclusions
# ------------------------------------------------------------------

exclude_set = {x.strip() for x in args.exclude.split(",") if x.strip()}

# We will filter DIMS and ROW_LABELS below once they are defined.

# Stata exports follow the pattern `user_mechanisms_lean_<variant>`.  Keep
# compatibility with the legacy directory lacking a suffix when *unbalanced*
# is requested.

SPECNAME = f"user_mechanisms_lean_{variant}"

RAW_DIR = PROJECT_ROOT / "results" / "raw"
input_dir = RAW_DIR / SPECNAME

if not input_dir.exists():
    # 1) Legacy non-variant directory
    legacy_dir = RAW_DIR / "user_mechanisms_lean"
    if legacy_dir.exists():
        input_dir = legacy_dir
    else:
        # 2) Check archived location
        archive_dir = RAW_DIR / "archive" / "user_mechanisms_lean"
        if archive_dir.exists():
            input_dir = archive_dir

INPUT_CSV = input_dir / "consolidated_results.csv"

OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"user_mechanisms_lean_{variant}.tex"

# Keep parity with the baseline version --------------------------------------
COLS_PER_TABLE = 8

PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# Mechanism dimensions in desired display order. Explicit strings ensure
# acronyms retain intended capitalisation (e.g. "HHI").
DIMS = [
    "Rent",
    "HHI",
    "Seniority",
    "Wage",
]

# Mapping from dimension code to pretty label shown in the table.
ROW_LABELS = {
    "Rent": "Rent",
    "HHI": "HHI",
    "Seniority": "Seniority",
    "Wage": "Wage",
}

# Keywords per dimension for spec detection
DIM_KEYWORDS = {
    "Rent": ["rent"],
    "HHI": ["hhi"],
    "Seniority": ["seniority"],
    "Wage": ["sd_wage", "sdw", "wage", "gap"],
}

# Apply exclusions

if exclude_set:
    DIMS = [d for d in DIMS if d not in exclude_set]
    ROW_LABELS = {k: v for k, v in ROW_LABELS.items() if k in DIMS}

# ------------------------------------------------------------------
# Remove excluded dimensions if requested
# ------------------------------------------------------------------

if exclude_set:
    DIMS = [d for d in DIMS if d not in exclude_set]
    ROW_LABELS = {k: v for k, v in ROW_LABELS.items() if k in DIMS}


# ---------------------------------------------------------------------------
# Helper functions (verbatim from the baseline builder)
# ---------------------------------------------------------------------------


def starify(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def load_df() -> pd.DataFrame:
    df = pd.read_csv(INPUT_CSV)
    # Pretty coefficient / SE strings -------------------------------------------------
    df["coef_str"] = df.apply(
        lambda r: f"{r.coef:.2f}{starify(r.pval)}" if r.param in ("var3", "var5") else f"{r.coef:.0f}",
        axis=1,
    )
    df["se_str"] = df.se.map(lambda s: f"({s:.2f})")
    return df


def checks(specs: list[str]):
    out = {d: [] for d in DIMS}
    for s in specs:
        low = s.lower()
        out["Rent"].append("rent" in low)
        out["HHI"].append("hhi" in low)
        out["Seniority"].append("seniority" in low)
        if "Wage" in out:
            out["Wage"].append(any(k in low for k in ("sd_wage", "sdw", "wage", "gap")))
    return out


def panel(sub: pd.DataFrame):
    return {
        "coef": sub.pivot(index="param", columns="spec", values="coef_str"),
        "se": sub.pivot(index="param", columns="spec", values="se_str"),
    }


def one_table(df_iv: pd.DataFrame, df_ols: pd.DataFrame, specs: list[str], idx: int):
    check = checks(specs)

    p_iv = panel(df_iv[df_iv.spec.isin(specs)])
    p_ols = panel(df_ols[df_ols.spec.isin(specs)])

    nobs_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["nobs"].first()
    nobs_ols = df_ols[df_ols.spec.isin(specs)].groupby("spec")["nobs"].first()
    rkf_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["rkf"].first()

    lines: list[str] = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    variant_tex = variant.capitalize().replace("_", r"\_")
    lines.append(rf"\caption{{User Mechanisms – Lean ({variant_tex}) – Part {idx}}}")
    lines.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
    lines.append(r"\toprule")

    lines.append(r" & \multicolumn{%d}{c}{Total Contrib. (pct. rk)} \\" % len(specs))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(specs) + 1))

    lines.append("Specification & " + " & ".join(f"({i})" for i in range(1, len(specs) + 1)) + r" \\")
    lines.append(r"\midrule")

    # Dimension check-marks ---------------------------------------------------
    for dim in DIMS:
        marks = ["\\checkmark" if v else "" for v in check[dim]]
        pretty_dim = ROW_LABELS.get(dim, dim)
        lines.append(pretty_dim + " & " + " & ".join(marks) + r" \\")
    lines.append(r"\midrule")

    # Two-panel (OLS / IV) layout -------------------------------------------
    for p_idx, (panel_id, model, pdata) in enumerate([("A", "OLS", p_ols), ("B", "IV", p_iv)]):
        lines.append(r"\multicolumn{%d}{l}{\textbf{\uline{Panel %s: %s}}} \\" % (len(specs)+1, panel_id, model))
        lines.append(r"\addlinespace")

        for param in ("var3", "var5"):
            coefs = pdata["coef"].loc[param, specs]
            ses = pdata["se"].loc[param, specs]
            lines.append(PARAM_LABELS[param] + " & " + " & ".join(coefs) + r" \\")
            lines.append(" & " + " & ".join(ses) + r" \\")

        lines.append(r"\midrule")
        nvals = [f"{int(nobs_ols[s]):,}" if model == "OLS" else f"{int(nobs_iv[s]):,}" for s in specs]
        lines.append(r"N & " + " & ".join(nvals) + r" \\")
        if model == "IV":
            kvals = [f"{rkf_iv[s]:.2f}" for s in specs]
            lines.append(r"KP\,rk Wald F & " + " & ".join(kvals) + r" \\")

        if p_idx == 0:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(rf"\label{{tab:user_mechanisms_lean_{variant}_{idx}}}")
    lines.append(r"\end{table}")
    return lines


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Expected Stata output {INPUT_CSV} not found. Run spec/user_mechanisms_lean.do first."
        )

    df = load_df()

    # Split IV vs OLS before pivoting for convenience -----------------------
    df_iv = df[df.model_type == "IV"].copy()
    df_ols = df[df.model_type == "OLS"].copy()

    # Filter specifications to drop those containing excluded dimensions
    spec_all = df["spec"].drop_duplicates().tolist()

    def spec_has_dim(s: str, dim: str) -> bool:
        low = s.lower()
        return any(k in low for k in DIM_KEYWORDS.get(dim, []))

    if exclude_set:
        spec_order = [
            s for s in spec_all if not any(spec_has_dim(s, d) for d in exclude_set)
        ]
        df_iv = df_iv[df_iv.spec.isin(spec_order)]
        df_ols = df_ols[df_ols.spec.isin(spec_order)]
    else:
        spec_order = spec_all
    tables_needed = math.ceil(len(spec_order) / COLS_PER_TABLE)

    lines: list[str] = []

    for t_idx in range(tables_needed):
        start = t_idx * COLS_PER_TABLE
        end = min((t_idx + 1) * COLS_PER_TABLE, len(spec_order))
        specs = spec_order[start:end]
        lines.extend(one_table(df_iv, df_ols, specs, t_idx + 1))
        lines.append("")  # blank line between tables for readability

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    tex_content = "\n".join(lines)
    OUTPUT_TEX.write_text(tex_content)
    if variant == "unbalanced":
        legacy_tex = OUTPUT_TEX.with_name("user_mechanisms_lean.tex")
        legacy_tex.write_text(tex_content)


if __name__ == "__main__":
    main()
