#!/usr/bin/env python3
"""Build a standalone mini-writeup for the postings-coverage equity quadruple."""

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

from project_paths import DATA_CLEAN, RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file

LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
INDENT: Final[str] = r"\hspace{1em}"
PREAMBLE: Final[str] = r"\centering"
STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

QUAD_BASE_RAW: Final[Path] = (
    RESULTS_RAW / "user_productivity_equity_quadruple_postings_coverage_precovid" / "consolidated_results.csv"
)
QUAD_PAIR_RAW: Final[Path] = (
    RESULTS_RAW / "user_productivity_equity_quadruple_pair_fe_postings_coverage_precovid" / "consolidated_results.csv"
)
USER_PANEL: Final[Path] = DATA_CLEAN / "user_panel_precovid.dta"
ENRICHED_PANEL: Final[Path] = (
    RESULTS_RAW / "postings_description_equity" / "firm_merge" / "latest_firm_yh_llm_equity_enriched.csv"
)

OUT_BASE_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_quadruple_postings_coverage_baseline_fe.tex"
OUT_PAIR_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_quadruple_postings_coverage_pair_fe.tex"
OUT_NOTE_TEX: Final[Path] = PROJECT_ROOT / "writeup" / "tex" / "llm_equity_quadruple_postings_coverage_note.tex"


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


def load_coverage_summary() -> pd.DataFrame:
    udf = pd.read_stata(require_file(USER_PANEL, nonempty=True, purpose="user panel"), columns=["companyname", "yh", "firm_id"])
    if pd.api.types.is_datetime64_any_dtype(udf["yh"]):
        udf["__yh_key"] = udf["yh"].dt.strftime("%Y-%m-%d")
    else:
        udf["__yh_key"] = pd.to_datetime(udf["yh"], unit="D", origin="1960-01-01").dt.strftime("%Y-%m-%d")
    udf["__firm_name_key"] = (
        udf["companyname"].astype(str).str.strip().str.lower().replace({".": "", "nan": "", "none": ""})
    )

    cols = ["companyname", "yh", "n_postings_desc_total", "n_keyword_hit_candidates", "llm_n_parse_ok_raw"]
    edf = pd.read_csv(require_file(ENRICHED_PANEL, nonempty=True, purpose="enriched equity panel"), usecols=cols)
    edf["__yh_key"] = pd.to_datetime(edf["yh"]).dt.strftime("%Y-%m-%d")
    edf["__firm_name_key"] = (
        edf["companyname"].astype(str).str.strip().str.lower().replace({".": "", "nan": "", "none": ""})
    )

    merged = udf.merge(
        edf[["__firm_name_key", "__yh_key", "n_postings_desc_total", "n_keyword_hit_candidates", "llm_n_parse_ok_raw"]],
        how="left",
        on=["__firm_name_key", "__yh_key"],
    )
    for col in ["n_postings_desc_total", "n_keyword_hit_candidates", "llm_n_parse_ok_raw"]:
        merged[col] = merged[col].fillna(0)

    merged["has_postings"] = merged["n_postings_desc_total"] > 0
    merged["keyword_hit"] = merged["n_keyword_hit_candidates"] > 0
    merged["parse_ok"] = merged["llm_n_parse_ok_raw"] > 0

    merged["bucket"] = "no_postings_or_unmatched"
    merged.loc[merged["has_postings"], "bucket"] = "postings_no_keyword"
    merged.loc[merged["has_postings"] & merged["keyword_hit"] & ~merged["parse_ok"], "bucket"] = "keyword_hit_unparsed"
    merged.loc[merged["has_postings"] & merged["keyword_hit"] & merged["parse_ok"], "bucket"] = "keyword_hit_parse"

    row_counts = merged["bucket"].value_counts()

    firm = (
        merged.groupby("firm_id", observed=False)
        .agg(
            has_postings=("has_postings", "max"),
            keyword_hit=("keyword_hit", "max"),
            parse_ok=("parse_ok", "max"),
        )
        .reset_index()
    )
    firm["bucket"] = "no_postings_or_unmatched"
    firm.loc[firm["has_postings"], "bucket"] = "postings_no_keyword"
    firm.loc[firm["has_postings"] & firm["keyword_hit"] & ~firm["parse_ok"], "bucket"] = "keyword_hit_unparsed"
    firm.loc[firm["has_postings"] & firm["keyword_hit"] & firm["parse_ok"], "bucket"] = "keyword_hit_parse"
    firm_counts = firm["bucket"].value_counts()

    labels = {
        "keyword_hit_parse": "Keyword hit with parse-successful LLM output",
        "postings_no_keyword": "Postings but no keyword hit",
        "keyword_hit_unparsed": "Keyword hit but no parse-successful output",
        "no_postings_or_unmatched": "No postings or unmatched",
    }
    included = {
        "keyword_hit_parse": "Yes",
        "postings_no_keyword": "Yes",
        "keyword_hit_unparsed": "No",
        "no_postings_or_unmatched": "No",
    }
    order = [
        "keyword_hit_parse",
        "postings_no_keyword",
        "keyword_hit_unparsed",
        "no_postings_or_unmatched",
    ]

    rows: list[dict[str, object]] = []
    for key in order:
        rows.append(
            {
                "bucket": key,
                "label": labels[key],
                "firm_count": int(firm_counts.get(key, 0)),
                "row_count": int(row_counts.get(key, 0)),
                "included": included[key],
            }
        )
    return pd.DataFrame(rows)


def build_coverage_table(df: pd.DataFrame) -> str:
    colspec = "@{}l@{\\extracolsep{\\fill}}c@{\\extracolsep{\\fill}}c@{\\extracolsep{\\fill}}c@{}"
    lines = [
        r"Bucket & Firms & Worker-half-years & Included in quadruple sample" + LB,
        MID,
    ]
    for _, row in df.iterrows():
        lines.append(
            f"{row['label']} & {int(row['firm_count']):,} & {int(row['row_count']):,} & {row['included']}"
            + LB
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

\section*{{User Productivity Equity Quadruple}}

\noindent The quadruple specifications use the postings-based equity coverage rule. In the equity-augmented column, firms are included only if they have job-posting coverage. Among covered firms, periods with postings but no equity-related keyword hit are backfilled to zero, while keyword-hit firms without parse-successful LLM output are excluded.

\section*{{1. Equity quadruple: Separate worker and firm fixed effects}}

\subsection*{{Empirical setup}}
\noindent The equity quadruple appends the equity signal directly to the core empirical setup:
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
\noindent In IV, the remote-post term, the remote-post-startup term, the remote-post-equity term, and the remote-post-startup-equity term are instrumented with the matching teleworkability interactions. Column (1) keeps the original baseline sample. Column (2) applies the postings-based equity coverage rule described above.

\begin{{table}}[H]
  \centering
  \caption{{User productivity equity quadruple}}
  \TableInput{{\cleanedresultsdir/llm_equity_quadruple_postings_coverage_baseline_fe.tex}}
  \FloatNote{{The outcome is the worker contribution-rank measure used throughout the user-productivity analysis. Panel A reports OLS estimates and Panel B reports IV estimates. Column (1) is the baseline user-productivity specification with separate worker, firm, and half-year fixed effects. Column (2) appends the equity signal through $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times\text{{Offers equity}}$, $\mathds{{1}}(\text{{Post}})\times\text{{Startup}}\times\text{{Offers equity}}$, and $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times\text{{Startup}}\times\text{{Offers equity}}$. The remote interactions are instrumented by the matching teleworkability interactions. The equity-augmented column is estimated on firms with postings coverage; among covered firms, posting periods with no keyword hit are backfilled to zero and keyword-hit firms without parse-successful LLM output are excluded. Standard errors are clustered by worker.}}
\end{{table}}

\section*{{2. Equity quadruple: Firm-by-worker fixed effects}}

\noindent The pair fixed-effects version keeps the same quadruple interaction structure, but replaces separate worker and firm effects with firm-by-worker match fixed effects plus half-year fixed effects. Column (1) again keeps the original baseline sample, and Column (2) applies the postings-based equity coverage rule.
\begin{{table}}[H]
  \centering
  \caption{{User productivity equity quadruple}}
  \TableInput{{\cleanedresultsdir/llm_equity_quadruple_postings_coverage_pair_fe.tex}}
  \FloatNote{{The outcome is the worker contribution-rank measure used throughout the user-productivity analysis. Panel A reports OLS estimates and Panel B reports IV estimates. Column (1) is the pair fixed-effects baseline specification with firm-by-worker match and half-year fixed effects. Column (2) appends the same equity quadruple terms as in Section 2. The remote interactions are instrumented by the matching teleworkability interactions. The equity-augmented column is estimated on firms with postings coverage; among covered firms, posting periods with no keyword hit are backfilled to zero and keyword-hit firms without parse-successful LLM output are excluded. Standard errors are clustered by worker.}}
\end{{table}}

\end{{document}}
"""


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)

    quad_base_df = pd.read_csv(
        require_file(QUAD_BASE_RAW, nonempty=True, purpose="baseline FE postings-coverage quadruple results")
    )
    quad_pair_df = pd.read_csv(
        require_file(QUAD_PAIR_RAW, nonempty=True, purpose="pair FE postings-coverage quadruple results")
    )

    OUT_BASE_TEX.write_text(build_quadruple_table(quad_base_df, pair_fe=False), encoding="utf-8")
    OUT_PAIR_TEX.write_text(build_quadruple_table(quad_pair_df, pair_fe=True), encoding="utf-8")
    OUT_NOTE_TEX.write_text(build_note_tex(), encoding="utf-8")

    print(f"Wrote {OUT_BASE_TEX}")
    print(f"Wrote {OUT_PAIR_TEX}")
    print(f"Wrote {OUT_NOTE_TEX}")


if __name__ == "__main__":
    main()
