#!/usr/bin/env python3
"""
Generate LaTeX tables and a short PDF writeup for user productivity trait results.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO / "results" / "raw" / "user_productivity_traits_precovid"
WRITEUP_DIR = REPO / "writeup"
WRITEUP_DIR.mkdir(exist_ok=True)

TRAIT_LABELS: Dict[str, str] = {
    "baseline": "Baseline",
    "female_flag": "Female",
    "graddeg_flag": "Graduate degree",
    "doctorate_flag": "Doctorate",
    "top_school_flag": "Top school",
    "age_under30": "Age $< 30$",
    "age_40plus": "Age $\\ge 40$",
}

BASE_LABELS: Dict[str, str] = {
    "var3": "Remote $\\times$ COVID",
    "var5": "Remote $\\times$ COVID $\\times$ Startup",
    "var4": "COVID $\\times$ Startup",
}

MODEL_ORDER = {"OLS": 0, "IV": 1}


def trait_suffix_label(suffix: str) -> str:
    return TRAIT_LABELS.get(suffix, suffix.replace("_", " ").title())


def param_label(name: str) -> str:
    if "_" not in name:
        return BASE_LABELS.get(name, name)
    base, suffix = name.split("_", 1)
    base_label = BASE_LABELS.get(base, base)
    trait_label = trait_suffix_label(suffix)
    return f"{base_label} × {trait_label}"


def stars(pval: float) -> str:
    if pd.isna(pval):
        return ""
    if pval < 0.01:
        return "***"
    if pval < 0.05:
        return "**"
    if pval < 0.1:
        return "*"
    return ""


def fmt_coef(coef: float, pval: float, se: float) -> str:
    if pd.isna(coef):
        return ""
    star = stars(pval)
    return f"{coef: .3f}{star} ({se:.3f})"


def fmt_n(n: float) -> str:
    if pd.isna(n):
        return ""
    return f"{int(n):,}"


def fmt_rkf(rkf: float) -> str:
    if pd.isna(rkf):
        return ""
    return f"{rkf:.2f}"


def build_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Trait"] = df["trait"].map(TRAIT_LABELS).fillna(df["trait"])
    df["Parameter"] = df["param"].map(param_label)
    df["Estimate"] = df.apply(lambda row: fmt_coef(row["coef"], row["pval"], row["se"]), axis=1)
    df["Model"] = df["model_type"]
    df["N"] = df["nobs"].map(fmt_n)
    df["rkF"] = df["rkf"].map(fmt_rkf)
    trait_order = {TRAIT_LABELS.get(k, k): i for i, k in enumerate(TRAIT_LABELS.keys())}
    df["trait_order"] = df["Trait"].map(trait_order).fillna(math.inf)
    df["model_order"] = df["Model"].map(MODEL_ORDER).fillna(math.inf)
    df.sort_values(by=["trait_order", "model_order", "Parameter"], inplace=True)
    df = df[["Model", "Trait", "Parameter", "Estimate", "N", "rkF"]]
    return df


def write_tables() -> tuple[str, str]:
    interactions = build_table(RESULTS_DIR / "consolidated_results.csv")

    # For splits include group information in parameter column
    split_raw = pd.read_csv(RESULTS_DIR / "split_results.csv")
    group_map = {"1": "Trait = 1", "0": "Trait = 0"}
    group_map.update({1: "Trait = 1", 0: "Trait = 0"})
    split_raw["Trait"] = split_raw["trait"].map(TRAIT_LABELS).fillna(split_raw["trait"])
    split_raw["Group"] = split_raw["group"].map(group_map).fillna(split_raw["group"].astype(str))
    split_raw["Parameter"] = split_raw["param"].map(param_label)
    split_raw["Estimate"] = split_raw.apply(lambda row: fmt_coef(row["coef"], row["pval"], row["se"]), axis=1)
    split_raw["Model"] = split_raw["model_type"]
    split_raw["N"] = split_raw["nobs"].map(fmt_n)
    split_raw["rkF"] = split_raw["rkf"].map(fmt_rkf)
    split_trait_order = {TRAIT_LABELS.get(k, k): i for i, k in enumerate(TRAIT_LABELS.keys())}
    split_group_order = {"Trait = 1": 0, "Trait = 0": 1}
    split_raw["trait_order"] = split_raw["Trait"].map(split_trait_order).fillna(math.inf)
    split_raw["group_order"] = split_raw["Group"].map(split_group_order).fillna(math.inf)
    split_raw["model_order"] = split_raw["Model"].map(MODEL_ORDER).fillna(math.inf)
    split_raw.sort_values(
        by=["trait_order", "group_order", "model_order", "Parameter"], inplace=True
    )
    split_table = split_raw[["Model", "Trait", "Group", "Parameter", "Estimate", "N", "rkF"]]

    interactions_tex = interactions.to_latex(
        index=False,
        escape=False,
        longtable=True,
        column_format="llllrr",
        caption="Regression results with trait interactions (OLS and IV).",
        label="tab:traits-interactions",
    )
    interactions_tex = "{\\small\n" + interactions_tex + "\n}"

    split_tex = split_table.to_latex(
        index=False,
        escape=False,
        longtable=True,
        column_format="llllrrr",
        caption="Split-sample regressions by worker trait.",
        label="tab:traits-split",
    )
    split_tex = "{\\small\n" + split_tex + "\n}"

    return interactions_tex, split_tex


def write_latex_document(interactions_tex: str, split_tex: str) -> Path:
    doc_path = WRITEUP_DIR / "user_productivity_traits.tex"
    content = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{caption}
\usepackage{amsmath}
\captionsetup{labelfont=bf}
\begin{document}
\begin{center}
{\LARGE Worker-Trait Productivity Results}\\[1ex]
{\large Precovid panel}
\end{center}

\noindent\textbf{Trait flags.}  Female = 1 when the gender classifier assigns $p(\text{female}) \ge 0.6$ (else 0); Graduate degree = 1 if the highest credential is masters/MBA/professional/doctoral (else 0, covering bachelor and below or missing); Doctorate = 1 only when the top credential is doctoral (else 0); Top school = 1 when the top U.S. institution matches the elite lookup; Age flags rely on the approximate age derived from graduation year and are missing outside 18--80.\\[0.6em]
\noindent\textbf{Baseline IV.}  With worker$\times$firm fixed effects $\gamma_{if}$ and half-year effects $\lambda_t$,
\begin{align*}
 y_{ift} &= \beta_1 (\text{Remote}_{it} \times \text{COVID}_t) + \beta_2 (\text{Remote}_{it} \times \text{COVID}_t \times \text{Startup}_f) \\
         &\quad + \beta_3 (\text{COVID}_t \times \text{Startup}_f) + \gamma_{if} + \lambda_t + \varepsilon_{ift},
\end{align*}
with the remote terms instrumented by firm teleworkability interacted with the same timing and startup indicators.\\[0.6em]
\noindent\textbf{Trait interactions.}  For each worker attribute $T_i$ we append
\begin{align*}
 y_{ift} &= \cdots + \beta_{1T} (\text{Remote}_{it} \times \text{COVID}_t \times T_i) + \beta_{2T} (\text{Remote}_{it} \times \text{COVID}_t \times \text{Startup}_f \times T_i) \\
         &\quad + \beta_{3T} (\text{COVID}_t \times \text{Startup}_f \times T_i) + \varepsilon_{ift},
\end{align*}
and instrument each additional endogenous term with the corresponding teleworkability interaction.\\[0.6em]
\noindent\textbf{Split samples.}  As a robustness check, the baseline IV is re-estimated on the subsample with $T_i=1$ and separately on the subsample with $T_i=0$, reporting the same coefficient and first-stage diagnostics.\\[1em]
\section*{Trait Interaction Regressions}
%INTERACTIONS%

\section*{Split-Sample Regressions}
%SPLITS%

\end{document}
"""
    content = content.replace("%INTERACTIONS%", interactions_tex)
    content = content.replace("%SPLITS%", split_tex)
    doc_path.write_text(content)
    return doc_path


def main() -> None:
    interactions_tex, split_tex = write_tables()
    doc_path = write_latex_document(interactions_tex, split_tex)
    print(f"LaTeX document written to {doc_path}")


if __name__ == "__main__":
    main()
