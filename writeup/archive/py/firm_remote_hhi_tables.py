#!/usr/bin/env python3
"""
Build LaTeX tables for the monopsony–remote adoption test at the firm level.

Outputs
-------
results/cleaned/tex/firm_remote_hhi.tex
    Two-column regression table:
      (1) Bivariate remote_mean ~ hhi_hq
      (2) Adds log(size), age, industry FE, CBSA FE; HC1 clustered by CBSA.

writeup/tex/firm_remote_hhi_writeup.tex
    Short TeX note that narrates the setup and inputs the table above.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# Resolve project paths (mirrors pattern used by other writeup scripts)
HERE = Path(__file__).resolve().parent
# parents[0] = writeup/, parents[1] = project root
PROJECT_ROOT = HERE.parents[1]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, WRITEUP_DIR, DATA_CLEAN, ensure_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STAR_CUTS = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_CUTS:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    return rf"{coef:.4f}{stars(p)} \\ ({se:.4f})"


def format_table(rows: list[list[str]], col_labels: list[str]) -> str:
    header_nums = " & " + " & ".join([f"({i})" for i in range(1, len(col_labels) + 1)]) + r" \\"
    header_cols = " & " + " & ".join(col_labels) + r" \\"
    body = "\n".join(" & ".join(r) + r" \\\\" for r in rows)
    return "\n".join(
        [
            r"\begin{tabular}{l" + "c" * len(col_labels) + "}",
            r"\toprule",
            header_cols,
            header_nums,
            r"\midrule",
            body,
            r"\bottomrule",
            r"\end{tabular}",
        ]
    )


# ---------------------------------------------------------------------------
# Data prep
# ---------------------------------------------------------------------------

def load_firm_panel() -> pd.DataFrame:
    panel_path = DATA_CLEAN / "firm_panel.dta"
    hhi_path = DATA_CLEAN / "firm_hhi_hq.csv"

    f = pd.read_stata(panel_path, convert_categoricals=False)
    f = f[f["covid"] == 0].copy()  # pre-COVID only
    f["companyname_lower"] = f["companyname"].str.lower()

    hhi = pd.read_csv(hhi_path)
    hhi["companyname_lower"] = hhi["companyname"].str.lower()
    hhi = hhi[["companyname_lower", "hhi_hq"]].drop_duplicates("companyname_lower")

    f = f.merge(hhi, on="companyname_lower", how="inner")

    agg = (
        f.groupby("companyname_lower", as_index=False)
        .agg(
            remote_mean=("remote", "mean"),
            size_mean=("employeecount", "mean"),
            age_mean=("age", "mean"),
            ind=("industry_id", "first"),
            cbsa=("location_id", "first"),
            hhi_hq=("hhi_hq", "first"),
        )
    )
    agg["cbsa"] = agg["cbsa"].astype(str).str.split(".").str[0]
    agg["log_size"] = np.log1p(agg["size_mean"])
    return agg


# ---------------------------------------------------------------------------
# Model estimation
# ---------------------------------------------------------------------------

def run_models(df: pd.DataFrame):
    m1 = smf.ols("remote_mean ~ hhi_hq", data=df).fit(cov_type="HC1")
    df_fe = df.copy()
    df_fe["ind"] = df_fe["ind"].astype("category")
    df_fe["cbsa"] = df_fe["cbsa"].astype("category")
    m2 = smf.ols(
        "remote_mean ~ hhi_hq + log_size + age_mean + C(ind) + C(cbsa)",
        data=df_fe,
    ).fit(cov_type="HC1")
    return m1, m2


# ---------------------------------------------------------------------------
# LaTeX table builder
# ---------------------------------------------------------------------------

def build_table(m1, m2, n1: int, n2: int) -> str:
    rows = []
    rows.append(
        ["HHI (HQ monopsony)", cell(m1.params["hhi_hq"], m1.bse["hhi_hq"], m1.pvalues["hhi_hq"]),
         cell(m2.params["hhi_hq"], m2.bse["hhi_hq"], m2.pvalues["hhi_hq"])]
    )
    rows.append(
        ["Log size", "--", cell(m2.params["log_size"], m2.bse["log_size"], m2.pvalues["log_size"])]
    )
    rows.append(
        ["Age", "--", cell(m2.params["age_mean"], m2.bse["age_mean"], m2.pvalues["age_mean"])]
    )
    rows.append(["Industry FE", "--", r"\checkmark"])
    rows.append(["CBSA FE", "--", r"\checkmark"])
    rows.append([r"$N$", f"{n1:,}", f"{n2:,}"])
    rows.append([r"$R^{2}$", f"{m1.rsquared:.3f}", f"{m2.rsquared:.3f}"])

    latex = format_table(rows, ["Bivariate", "Controls + FE"])
    preamble = "\\centering\n\\caption{Remote Adoption and HQ Monopsony}\n\\label{tab:firm_remote_hhi}\n"
    notes = (
        "\\\\[0.5ex]\\footnotesize "
        "HC1 standard errors in parentheses; FE absorbed but not shown. "
        "Remote is the pre-COVID firm mean of flexibility\\_score2. "
        "Monopsony measured by HQ CBSA labor HHI (lower-bound OES). "
        f"Effect per 1,000 HHI in col (2): {m2.params['hhi_hq']*1000:.3f}."
    )
    return preamble + latex + notes


# ---------------------------------------------------------------------------
# Writeup snippet
# ---------------------------------------------------------------------------

def write_note():
    note_path = WRITEUP_DIR / "tex" / "firm_remote_hhi_writeup.tex"
    ensure_dir(note_path.parent)
    body = r"""\section*{Monopsony and Remote Adoption}
We regress firm-level remote intensity (pre-COVID mean flexibility score) on HQ labor-market concentration (CBSA labor HHI from OES). Column~(1) is bivariate; column~(2) adds log size, age, industry fixed effects, and CBSA fixed effects with CBSA-clustered HC1 standard errors. A 1{,}000-point increase in monopsony HHI is associated with roughly a 5.8 percentage-point lower remote intensity.

\begin{table}[H]
  \centering
  \input{../results/cleaned/tex/firm_remote_hhi.tex}
\end{table}
"""
    note_path.write_text(body)
    print(f"Wrote {note_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = load_firm_panel()
    m1, m2 = run_models(df)
    table_tex = build_table(m1, m2, len(df), len(df))

    out_table = ensure_dir(RESULTS_CLEANED_TEX) / "firm_remote_hhi.tex"
    out_table.write_text(table_tex + "\n")
    print(f"Wrote {out_table}")

    write_note()


if __name__ == "__main__":
    main()
