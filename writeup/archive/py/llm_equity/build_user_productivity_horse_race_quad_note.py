#!/usr/bin/env python3
"""Build a focused mini-writeup note for startup-swapped horse races and equity quadruples."""

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

LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
INDENT: Final[str] = r"\hspace{1em}"
PREAMBLE: Final[str] = r"\centering"
STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

HORSE_BASE_RAW: Final[Path] = RESULTS_RAW / "user_horse_race_startup_swapped_precovid" / "consolidated_results.csv"
HORSE_PAIR_RAW: Final[Path] = RESULTS_RAW / "user_horse_race_startup_swapped_pair_fe_precovid" / "consolidated_results.csv"
QUAD_BASE_RAW: Final[Path] = RESULTS_RAW / "user_productivity_equity_quadruple_precovid" / "consolidated_results.csv"
QUAD_PAIR_RAW: Final[Path] = RESULTS_RAW / "user_productivity_equity_quadruple_pair_fe_precovid" / "consolidated_results.csv"

OUT_HORSE_BASE_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_startup_swapped_horse_race_baseline.tex"
OUT_HORSE_PAIR_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_startup_swapped_horse_race_pairfe.tex"
OUT_QUAD_BASE_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_quadruple_baseline_fe.tex"
OUT_QUAD_PAIR_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_quadruple_pair_fe.tex"
OUT_NOTE_TEX: Final[Path] = PROJECT_ROOT / "writeup" / "tex" / "llm_equity_startup_swapped_horse_race_note.tex"


def stars(p: float) -> str:
    for cutoff, symbol in STAR_RULES:
        if p < cutoff:
            return symbol
    return ""


def fmt_coef(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1e4 or (0 < abs_v < 1e-2):
        return f"{value:.2e}"
    return f"{value:.2f}"


def coef_cell(row: pd.Series | None) -> str:
    if row is None:
        return "--"
    coef = row.get("coef")
    se = row.get("se")
    pval = row.get("pval")
    if coef is None or se is None or pd.isna(coef) or pd.isna(se) or float(se) == 0.0:
        return "--"
    p = float(pval) if pval is not None and not pd.isna(pval) else 1.0
    return rf"\makecell[c]{{{fmt_coef(float(coef))}{stars(p)}\\({fmt_coef(float(se))})}}"


def stat_cell(row: pd.Series | None, field: str, fmt: str = "{:,.0f}") -> str:
    if row is None:
        return "--"
    value = row.get(field)
    if value is None or pd.isna(value):
        return "--"
    return fmt.format(value)


def tabular_star(colspec: str, body_lines: list[str]) -> str:
    lines = [PREAMBLE, rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def _row(df: pd.DataFrame, **filters: object) -> pd.Series | None:
    mask = pd.Series(True, index=df.index)
    for col, value in filters.items():
        mask &= df[col] == value
    hit = df.loc[mask].head(1)
    if hit.empty:
        return None
    return hit.iloc[0]


def build_horse_race_table(
    df: pd.DataFrame,
    *,
    spec_order: list[str],
    spec_titles: list[str],
    pair_fe: bool,
) -> str:
    core_labels = {
        "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
        "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    }
    control_labels = {
        "hr_scale_post": r"$ \text{Firm growth bin} \times \mathds{1}(\text{Post}) $",
        "hr_scale_remote": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Firm growth bin} $",
        "hr_eq_post": r"$ \text{Offers equity} \times \mathds{1}(\text{Post}) $",
        "hr_eq_remote": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Offers equity} $",
    }
    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * len(spec_order) + "@{}"
    lines = [
        rf" & \multicolumn{{{len(spec_order)}}}{{c}}{{Contribution Rank}}" + LB,
        rf"\cmidrule(lr){{2-{len(spec_order) + 1}}}",
        " & " + " & ".join(f"({i})" for i in range(1, len(spec_order) + 1)) + LB,
        " & " + " & ".join(spec_titles) + LB,
        MID,
        rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}}" + LB,
        r"\addlinespace[2pt]",
    ]
    for param in ["var3", "var5"]:
        cells = [coef_cell(_row(df, model_type="OLS", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + core_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            r"\addlinespace[2pt]",
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textit{{Added controls}}}}" + LB,
        ]
    )
    for param in ["hr_scale_post", "hr_scale_remote", "hr_eq_post", "hr_eq_remote"]:
        cells = [coef_cell(_row(df, model_type="OLS", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + control_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            MID,
            "N & " + " & ".join(stat_cell(_row(df, model_type="OLS", spec=spec, param="var5"), "nobs") for spec in spec_order) + LB,
            MID,
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}}" + LB,
            r"\addlinespace[2pt]",
        ]
    )
    for param in ["var3", "var5"]:
        cells = [coef_cell(_row(df, model_type="IV", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + core_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            r"\addlinespace[2pt]",
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textit{{Added controls}}}}" + LB,
        ]
    )
    for param in ["hr_scale_post", "hr_scale_remote", "hr_eq_post", "hr_eq_remote"]:
        cells = [coef_cell(_row(df, model_type="IV", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + control_labels[param] + " & " + " & ".join(cells) + LB)

    fe_line = r"Firm $\times$ individual" if pair_fe else r"Individual"
    lines.extend(
        [
            MID,
            "N & " + " & ".join(stat_cell(_row(df, model_type="IV", spec=spec, param="var5"), "nobs") for spec in spec_order) + LB,
            r"KP\,rk Wald F & " + " & ".join(stat_cell(_row(df, model_type="IV", spec=spec, param="var5"), "rkf", "{:.2f}") for spec in spec_order) + LB,
            MID,
            r"\textbf{Fixed Effects} &  &  &  & " + LB,
            INDENT + fe_line + r" & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
        ]
    )
    if not pair_fe:
        lines.append(INDENT + r"Firm & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB)
    lines.extend(
        [
            INDENT + r"Half-year & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            MID,
            r"\textbf{Controls} &  &  &  & " + LB,
            INDENT + r"Firm growth channel &  & \checkmark &  & \checkmark" + LB,
            INDENT + r"Equity channel &  &  & \checkmark & \checkmark" + LB,
        ]
    )
    return tabular_star(colspec, lines)


def build_quadruple_table(df: pd.DataFrame, *, pair_fe: bool) -> str:
    spec_order = ["baseline", "quadruple"]
    spec_titles = ["Baseline", "Equity quadruple"]
    core_labels = {
        "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
        "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
        "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
    }
    added_labels = {
        "var3_eq": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Offers equity} $",
        "var5_eq": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{Offers equity} $",
        "var4_eq": r"$ \mathds{1}(\text{Post}) \times \text{Startup} \times \text{Offers equity} $",
    }
    colspec = "@{}l@{\\extracolsep{\\fill}}c@{\\extracolsep{\\fill}}c@{}"
    lines = [
        r" & \multicolumn{2}{c}{Contribution Rank}" + LB,
        r"\cmidrule(lr){2-3}",
        r" & (1) & (2)" + LB,
        " & " + " & ".join(spec_titles) + LB,
        MID,
        r"\multicolumn{3}{@{}l}{\textbf{\uline{Panel A: OLS}}}" + LB,
        r"\addlinespace[2pt]",
    ]
    for param in ["var3", "var5", "var4"]:
        cells = [coef_cell(_row(df, model_type="OLS", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + core_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            r"\addlinespace[2pt]",
            r"\multicolumn{3}{@{}l}{\textit{Equity-appended terms}}" + LB,
        ]
    )
    for param in ["var3_eq", "var5_eq", "var4_eq"]:
        cells = [coef_cell(_row(df, model_type="OLS", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + added_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            MID,
            "N & " + " & ".join(stat_cell(_row(df, model_type="OLS", spec=spec, param="var5"), "nobs") for spec in spec_order) + LB,
            MID,
            r"\multicolumn{3}{@{}l}{\textbf{\uline{Panel B: IV}}}" + LB,
            r"\addlinespace[2pt]",
        ]
    )
    for param in ["var3", "var5", "var4"]:
        cells = [coef_cell(_row(df, model_type="IV", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + core_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            r"\addlinespace[2pt]",
            r"\multicolumn{3}{@{}l}{\textit{Equity-appended terms}}" + LB,
        ]
    )
    for param in ["var3_eq", "var5_eq", "var4_eq"]:
        cells = [coef_cell(_row(df, model_type="IV", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + added_labels[param] + " & " + " & ".join(cells) + LB)

    fe_line = r"Firm $\times$ individual" if pair_fe else r"Individual"
    lines.extend(
        [
            MID,
            "N & " + " & ".join(stat_cell(_row(df, model_type="IV", spec=spec, param="var5"), "nobs") for spec in spec_order) + LB,
            r"KP\,rk Wald F & " + " & ".join(stat_cell(_row(df, model_type="IV", spec=spec, param="var5"), "rkf", "{:.2f}") for spec in spec_order) + LB,
            MID,
            r"\textbf{Fixed Effects} &  &  " + LB,
            INDENT + fe_line + r" & $\checkmark$ & $\checkmark$" + LB,
        ]
    )
    if not pair_fe:
        lines.append(INDENT + r"Firm & $\checkmark$ & $\checkmark$" + LB)
    lines.append(INDENT + r"Half-year & $\checkmark$ & $\checkmark$" + LB)
    return tabular_star(colspec, lines)


def build_note_tex() -> str:
    return rf"""\documentclass{{article}}
\usepackage[margin=1.0in]{{geometry}}
\usepackage{{booktabs}}
\usepackage{{makecell}}
\usepackage{{float}}
\usepackage{{caption}}
\usepackage{{amsmath,amssymb,amsfonts}}
\usepackage{{dsfont}}
\usepackage[normalem]{{ulem}}
\usepackage{{setspace}}
\setstretch{{1.05}}

\newcommand{{\cleanedresultsdir}}{{../../results/cleaned/tex}}
\newcommand{{\TableInput}}[1]{{\input{{#1}}}}
\DeclareCaptionStyle{{noteflush}}{{%
  format=plain,
  justification=raggedright,
  singlelinecheck=false,
  font=footnotesize,
  width=\linewidth,
  skip=0pt
}}
\newcommand{{\FloatNote}}[1]{{%
  \begingroup
    \captionsetup{{style=noteflush}}%
    \caption*{{\textit{{Notes:}}~#1}}%
  \endgroup
}}

\begin{{document}}

\section*{{User Productivity: Startup-swapped horse races and equity specs}}

\noindent This note reports two user-productivity exercises built off the current core design. The first keeps the baseline startup triple-difference in place and re-runs the horse race with startup-swapped controls on the remote margin. The second estimates a separate equity quadruple that appends the equity signal directly to the core empirical setup.

\section*{{1. Startup-swapped horse race}}

\subsection*{{Empirical setup}}
\noindent For each added control $Z_f$ in the current horse-race stack, the modified specification keeps the baseline startup term and adds a startup-swapped remote channel:
\[
  \begin{{aligned}}
    y_{{ifh}} =\; & \beta_3 \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \right)
    + \beta_5 \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \times \text{{Startup}}_f \right) \\
    & + \sum_{{Z \in \mathcal{{Z}}}} \left[
        \gamma_Z \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \times Z_f \right)
        + \theta_Z \left( \mathds{{1}}(\text{{Post}})_h \times Z_f \right)
      \right]
    + \text{{FE}} + \varepsilon_{{ifh}} .
  \end{{aligned}}
\]
\noindent Here $\mathcal{{Z}}$ contains the two competing channels in the note: a firm-level bin for average post-COVID employment growth and the firm-level equity-offer signal. In IV, each remote interaction $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times Z_f$ is instrumented by the matching $\text{{Teleworkable}}\times\mathds{{1}}(\text{{Post}})\times Z_f$ interaction. Within each fixed-effects family, every column is estimated on the same merged sample.

\subsection*{{Baseline FE}}
\begin{{table}}[H]
  \centering
  \caption{{User productivity startup-swapped horse race, baseline FE}}
  \TableInput{{\cleanedresultsdir/llm_equity_startup_swapped_horse_race_baseline.tex}}
  \FloatNote{{Columns mirror the current baseline-FE horse-race structure: baseline, firm growth only, equity only, and both. The first two rows report the baseline remote coefficients on $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})$ and $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times\text{{Startup}}$. The growth channel uses a firm-level median split of average post-COVID employment growth. The added rows use startup-swapped controls: $\mathds{{1}}(\text{{Post}})\times Z$ and $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times Z$ for firm growth and equity, with the remote interactions instrumented by the matching teleworkability interactions. Standard errors are clustered by worker.}}
\end{{table}}

\subsection*{{Pair FE}}
\begin{{table}}[H]
  \centering
  \caption{{User productivity startup-swapped horse race, pair FE}}
  \TableInput{{\cleanedresultsdir/llm_equity_startup_swapped_horse_race_pairfe.tex}}
  \FloatNote{{Columns mirror the current pair-FE horse-race structure: baseline, firm growth only, equity only, and both. The growth channel uses the same firm-level median split of average post-COVID employment growth as in Table 1. The added rows use the same startup-swapped controls as in Table 1, estimated with firm$\times$individual and half-year fixed effects. Standard errors are clustered by worker.}}
\end{{table}}

\section*{{2. Equity quadruple}}

\subsection*{{Empirical setup}}
\noindent The separate equity-quadruple exercise appends the equity signal directly to the core empirical setup:
\[
  \begin{{aligned}}
    y_{{ifh}} =\; & \beta_1 \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \right)
    + \beta_2 \left( \mathds{{1}}(\text{{Post}})_h \times \text{{Startup}}_f \right)
    + \beta_3 \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \times \text{{Startup}}_f \right) \\
    & + \delta_1 \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \times \text{{Offers equity}}_f \right) \\
    & + \delta_2 \left( \mathds{{1}}(\text{{Post}})_h \times \text{{Startup}}_f \times \text{{Offers equity}}_f \right) \\
    & + \delta_3 \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \times \text{{Startup}}_f \times \text{{Offers equity}}_f \right)
    + \text{{FE}} + \varepsilon_{{ifh}} .
  \end{{aligned}}
\]
\noindent In IV, the remote-post term, the remote-post-startup term, the remote-post-equity term, and the remote-post-startup-equity term are instrumented with the matching teleworkability interactions. The post-startup term and the post-startup-equity term enter as included exogenous controls.

\subsection*{{Baseline FE}}
\begin{{table}}[H]
  \centering
  \caption{{User productivity equity quadruple, baseline FE}}
  \TableInput{{\cleanedresultsdir/llm_equity_quadruple_baseline_fe.tex}}
  \FloatNote{{Column (1) is the baseline user-productivity specification. Column (2) appends the equity signal to the core empirical setup through $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times\text{{Offers equity}}$, $\mathds{{1}}(\text{{Post}})\times\text{{Startup}}\times\text{{Offers equity}}$, and $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times\text{{Startup}}\times\text{{Offers equity}}$. The remote interactions are instrumented by the matching teleworkability interactions. Standard errors are clustered by worker.}}
\end{{table}}

\subsection*{{Pair FE}}
\begin{{table}}[H]
  \centering
  \caption{{User productivity equity quadruple, pair FE}}
  \TableInput{{\cleanedresultsdir/llm_equity_quadruple_pair_fe.tex}}
  \FloatNote{{Column (1) is the pair-FE baseline specification. Column (2) appends the equity signal to the core empirical setup under firm$\times$individual and half-year fixed effects. The remote interactions are instrumented by the matching teleworkability interactions. Standard errors are clustered by worker.}}
\end{{table}}

\end{{document}}
"""


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)

    horse_base_df = pd.read_csv(require_file(HORSE_BASE_RAW, nonempty=True, purpose="baseline FE startup-swapped horse-race results"))
    horse_pair_df = pd.read_csv(require_file(HORSE_PAIR_RAW, nonempty=True, purpose="pair FE startup-swapped horse-race results"))
    quad_base_df = pd.read_csv(require_file(QUAD_BASE_RAW, nonempty=True, purpose="baseline FE equity quadruple results"))
    quad_pair_df = pd.read_csv(require_file(QUAD_PAIR_RAW, nonempty=True, purpose="pair FE equity quadruple results"))

    OUT_HORSE_BASE_TEX.write_text(
        build_horse_race_table(
            horse_base_df,
            spec_order=["baseline", "labor_scaling", "equity_comp", "labor_scaling_equity_comp"],
            spec_titles=["Baseline", "Firm growth", "Equity offer", "Both"],
            pair_fe=False,
        ),
        encoding="utf-8",
    )
    OUT_HORSE_PAIR_TEX.write_text(
        build_horse_race_table(
            horse_pair_df,
            spec_order=["baseline", "growth_endog", "equity", "growth_endog_equity"],
            spec_titles=["Baseline", "Firm growth", "Equity offer", "Both"],
            pair_fe=True,
        ),
        encoding="utf-8",
    )
    OUT_QUAD_BASE_TEX.write_text(build_quadruple_table(quad_base_df, pair_fe=False), encoding="utf-8")
    OUT_QUAD_PAIR_TEX.write_text(build_quadruple_table(quad_pair_df, pair_fe=True), encoding="utf-8")

    note_tex = build_note_tex()
    OUT_NOTE_TEX.write_text(note_tex, encoding="utf-8")

    print(f"Wrote {OUT_HORSE_BASE_TEX}")
    print(f"Wrote {OUT_HORSE_PAIR_TEX}")
    print(f"Wrote {OUT_QUAD_BASE_TEX}")
    print(f"Wrote {OUT_QUAD_PAIR_TEX}")
    print(f"Wrote {OUT_NOTE_TEX}")


if __name__ == "__main__":
    main()
