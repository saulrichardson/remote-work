#!/usr/bin/env python3
r"""
Generate both firm‑level (Panel A) and worker‑level (Panel B) summary tables
and write them sequentially into a single stand‑alone LaTeX file.

Key features (May 2025)
-----------------------
* **siunitx** column alignment (`table-format=4.2`, `S` columns).
* One unified `tabular` ⇒ perfectly aligned horizontal rules.
* **Mean ± SD stacked** via `\makecell{mean \\ (sd)}`.
* **Single‑pass** statistics (`groupby().agg(['mean','std'])`).
* Dollar sign pre‑escaped in the “Rent” label.

Prerequisites in your LaTeX preamble:

```latex
\usepackage{siunitx}
\usepackage{makecell}
```

Usage
-----
Simply run the script — it relies on **default paths** defined near the top.
If you need different files, either:
1. Edit the three `DEF_*` paths below **or**
2. Import the module in Python and call `main(firm_path=..., worker_path=..., out_path=...)`.
"""
from __future__ import annotations

from pathlib import Path
import logging as log
import pandas as pd
import textwrap

# ----------------------------------------------------------------------
# 1  DEFAULT PATHS  (edit here if needed)
# ----------------------------------------------------------------------
DEF_FIRM   = Path("../data/samples/firm_panel.csv")
DEF_WORKER = Path("../data/samples/worker_panel.csv")
DEF_OUT    = Path("../results/cleaned/table_of_means.tex")

# ----------------------------------------------------------------------
# 2  PANEL-A SETTINGS  (Firm-level stats)
# ----------------------------------------------------------------------
VAR_MAP_A = {
    "growth":           "growth_rate_we",
    "leave":            "leave_rate_we",
    "join":             "join_rate_we",
    "teleworkable":     "teleworkable",
    "remote":           "remote",
    "total_employees":  "total_employees",
    "age":              "age",
    "rent":             "rent",
    "hhi_1000":         "hhi_1000",
    "seniority_levels": "seniority_levels",
}

DECIMALS_A = {
    "growth": 2,
    "leave": 2,
    "join": 2,
    "teleworkable": 2,
    "remote": 2,
    "total_employees": 0,
    "age": 0,
    "rent": 0,
    "hhi_1000": 0,
    "seniority_levels": 2,
}

NICE_A = {
    "growth":           r"Growth",
    "leave":            r"Leave",
    "join":             r"Join",
    "teleworkable":     r"Teleworkable Score \,(0--1)",
    "remote":           r"Remote Score \,(0--1)",
    "total_employees":  r"Employees (Count)",
    "age":              r"Age",
    "rent":             r"Rent (\textdollar/sq ft)",
    "hhi_1000":         r"Centrality Score",
    "seniority_levels": r"Seniority Levels (Count)",
}

PERCENT_VARS_A: set[str] = {}
#PERCENT_VARS_A: set[str] = {"growth", "leave", "join"}
#{"growth", "leave", "join"}

# ----------------------------------------------------------------------
# 3  PANEL-B SETTINGS  (Worker-level contributions)
# ----------------------------------------------------------------------
VAR_MAP_B = {
    "total_contrib_q100":      "total_contributions",
    "restricted_contrib_q100": "restricted_contributions",
}

DECIMALS_B = {
    "total_contrib_q100":      2,
    "restricted_contrib_q100": 2,
}

# How many decimals for the SD of each variable
SD_DECIMALS_A = {
    # everything else uses the same as the mean:
    **DECIMALS_A,
    # but override seniority_levels to get two decimals
    "seniority_levels": 2,
}
    

NICE_B = {
    "total_contrib_q100":      r"Total Contributions",
    "restricted_contrib_q100": r"Restricted Contributions",
}

# ----------------------------------------------------------------------
# 4  HELPERS
# ----------------------------------------------------------------------
def _fmt(code: str, value: float | int | pd.Series, decimals: dict[str, int],
         pct_vars: set[str] | None = None) -> str:
    r"""Format numeric value with optional % scaling."""
    if pd.isna(value):
        return ""
    if pct_vars and code in pct_vars:
        value *= 100  # decimals refer to percentage‑points
    dec = decimals.get(code, 2)
    return f"{value:.{dec}f}"

#def _mean_sd_cell(code: str, mean_val, sd_val, decimals: dict[str, int],
#                  pct_vars: set[str] | None = None) -> str:
#    r"""Stack mean and (sd) into one LaTeX \makecell."""
#    mean_str = _fmt(code, mean_val, decimals, pct_vars)
#    sd_str   = _fmt(code, sd_val,  decimals, pct_vars)
#    return rf"\makecell{{{mean_str} \\ ({sd_str})}}"

def _mean_sd_cell(code: str,
                  mean_val,
                  sd_val,
                  mean_decimals: dict[str,int],
                  sd_decimals: dict[str,int],
                  pct_vars: set[str]|None = None) -> str:
    """Stack mean and (sd) into one LaTeX \makecell, with separate precision."""
    if pd.isna(mean_val) or pd.isna(sd_val):
        return ""
    # apply % scaling if needed
    if pct_vars and code in pct_vars:
        mean_val *= 100
        sd_val   *= 100
    # pick decimals
    mdec = mean_decimals.get(code, 2)
    sdec = sd_decimals .get(code, 2)
    mean_str = f"{mean_val:.{mdec}f}"
    sd_str   = f"{sd_val:.{sdec}f}"
    return rf"\makecell{{{mean_str} \\ ({sd_str})}}"

def build_panel(df: pd.DataFrame,
                var_map: dict[str, str],
                nice: dict[str, str],
                mean_decimals: dict[str, int],
                sd_decimals:   dict[str, int],
                pct_vars:      set[str] | None = None,
                startup_flag:  str = "startup"):
    r"""Return panel rows (mean \n sd) via a single aggregation pass."""
    print(df.columns.to_list())
    missing = [c for c in list(var_map.values()) + [startup_flag] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in input data")
    is_startup = df[startup_flag].astype(int)
    cols = list(var_map.values())
    stats_by_flag = df[cols].groupby(is_startup).agg(['mean', 'std'])
    overall_stats = df[cols].agg(['mean', 'std']).T
    rows: list[dict[str, object]] = []
    for code, col in var_map.items():
        m_start = stats_by_flag.loc[1, (col, 'mean')] if 1 in stats_by_flag.index else float('nan')
        sd_start = stats_by_flag.loc[1, (col, 'std')] if 1 in stats_by_flag.index else float('nan')
        m_non = stats_by_flag.loc[0, (col, 'mean')] if 0 in stats_by_flag.index else float('nan')
        sd_non = stats_by_flag.loc[0, (col, 'std')] if 0 in stats_by_flag.index else float('nan')
        m_all, sd_all = overall_stats.loc[col]
        rows.append({
            "variable": nice[code],
            "Startup":     _mean_sd_cell(
                                code,
                                m_start,
                                sd_start,
                                mean_decimals,
                                sd_decimals,
                                pct_vars
                            ),
            "Incumbent": _mean_sd_cell(
                                code,
                                m_non,
                                sd_non,
                                mean_decimals,
                                sd_decimals,
                                pct_vars
                            ),
            "All Firms":   _mean_sd_cell(
                                code,
                                m_all,
                                sd_all,
                                mean_decimals,
                                sd_decimals,
                                pct_vars
                            ),
        })
    rows.append({
        "variable": "N",
        "Startup":     int(is_startup.eq(1).sum()),
        "Incumbent": int(is_startup.eq(0).sum()),
        "All Firms":   int(df.shape[0]),
    })
    return pd.DataFrame(rows)

def _strip_tabular(latex: str) -> str:
    r"""Remove pandas' outer tabular + booktabs rules (so we stay in our master tabular)."""
    skip = (r"\begin{tabular", r"\end{tabular", r"\toprule", r"\midrule", r"\bottomrule")
    return "\n".join(
        line for line in latex.splitlines()
        if not any(line.lstrip().startswith(p) for p in skip)
    )

# ------------------------------------------------------------------
def _with_gutter(colspec: str) -> str:
    """
    Insert a thin space before the *last* column
    E.g. 'lccc' -> 'lcc@{\\hspace{6pt}}c'
    """
    return colspec[:-1] + "@{\\hspace{6pt}}" + colspec[-1]

def _insert_blank_before_N(tex: str) -> str:
    """
    Add \\addlinespace *once* before the first line that starts with 'N &'.
    """
    return tex.replace("\nN &", "\n\\addlinespace\nN &", 1)

def _strip_tabular(s: str) -> str:
    """
    Remove the outer \begin{tabular} ... \end{tabular} produced by DataFrame.to_latex().
    """
    lines = s.splitlines()
    # keep everything between the first and last line
    return "\n".join(lines[1:-1])


def _strip_tabular(latex: str) -> str:
    skip = (r"\begin{tabular", r"\end{tabular", r"\toprule", r"\midrule", r"\bottomrule")
    return "\n".join(
        line for line in latex.splitlines()
        if not any(line.lstrip().startswith(p) for p in skip)
    )

def _insert_midrule_before_N(tex: str) -> str:
    """
    Add a full-width \\midrule immediately before the first line that starts with 'N &'.
    """
    # Replace the first occurrence of "\nN &" with "\n\midrule\nN &"
    return tex.replace("\nN &", "\n\\midrule\nN &", 1)

def _insert_midrule_before_N(tex: str) -> str:
    """
    Add a bit of vertical whitespace and a \\midrule immediately before
    the first line that starts with 'N &'.
    """
    # Insert \addlinespace then \midrule before the N‐row
    return tex.replace(
        "\nN &",
        "\n\\addlinespace\n\\midrule\nN &",
        1
    )

# ------------------------------------------------------------------
# Foot-note helper (returns one multi-line raw string)
# ------------------------------------------------------------------
def _notes_block() -> str:
    r"""
    Return a fully-formatted \begin{tablenotes} … \end{tablenotes} block.

    • Each data cell shows the mean on the first line and the standard
      deviation (SD) beneath it in parentheses.
    • Decimal precision matches what is displayed in the table; the SD for
      **Seniority Levels** is always given with two decimals.
    • **Growth, Leave, and Join** rates are reported in percentage points
      (0–100) with two-decimal precision.
    • **Teleworkable** and **Remote** scores are index values between 0 and 1
      and are printed with two decimals.
    • Counts (e.g.\ $N$, employees, seniority levels) and ages are integers.
    • Sample period: 2010–2024. $N$ denotes the number of observations in
      each subgroup.
    """
    return r"""
\begin{tablenotes}[flushleft]
\footnotesize
\item \emph{Notes}: Each data cell shows the mean on the first line and the
standard deviation (SD) beneath it in parentheses. Decimal precision
reflects each variable’s scale. \textit{Growth}, \textit{Leave}, and
\textit{Join} rates are expressed in percentage points (0--100). \textit{Teleworkable} and \textit{Remote} scores are
index values between 0 and 1. The sample
period spans the 2nd half of 2016 to the 1st half of 2022 at the firm level and the first half of 2017 to the first half of 2022 at the user level; 
$N$ indicates the number of observations in each
subgroup.
\end{tablenotes}
"""

def _notes_block() -> str:
    return r"""
\begin{tablenotes}[flushleft]
\footnotesize
\item \emph{Notes}: Each data cell shows the mean on the first line and the
standard deviation (SD) beneath it in parentheses. Decimal precision
reflects each variable’s scale. \textit{Growth}, \textit{Leave}, and
\textit{Join} rates are reported as fractions between 0 and 1}. \textit{Teleworkable} and \textit{Remote} scores are
index values between 0 and 1. The sample
period spans the 2nd half of 2016 to the 1st half of 2022 at the firm level and the 1st half of 2017 to the 1st half of 2022 at the user level;
$N$ indicates the number of observations in each
subgroup.
\end{tablenotes}
"""

# ----------------------------------------------------------------------
# 4  NOTE-BLOCK FACTORY
# ----------------------------------------------------------------------
def _notes_block(*,
                     rate_scale: str = "fraction",
                     firm_span: str = "2016 H2–2022 H1",
                     user_span: str = "2017 H1–2022 H1") -> str:
    """
    Return a LaTeX tablenotes environment.

    Parameters
    ----------
    rate_scale : {"fraction", "pp"}
        • "fraction" → “… rates are reported as fractions between 0 and 1”
        • "pp"       → “… rates are expressed in percentage points (0–100)”
    firm_span, user_span : str
        Text that appears in the sample-period sentence.
    """
    if rate_scale not in {"fraction", "pp"}:
        raise ValueError("rate_scale must be 'fraction' or 'pp'")

    scale_sentence = (
        r"\textit{Growth}, \textit{Leave}, and \textit{Join} rates are "
        + (
            r"fractions between 0 and 1"
            if rate_scale == "fraction"
            else r"expressed in percentage points (0--100)"
        )
        + "."
    )

    return textwrap.dedent(rf"""
    \begin{{tablenotes}}[flushleft]
    \footnotesize
    \item \emph{{Notes}}: Each cell shows the mean on the first line and the
    standard deviation (SD) beneath it in parentheses. Decimal precision
    reflects each variable’s scale. {scale_sentence}
    \textit{{Teleworkable}} and \textit{{Remote}} scores are index values
    between 0 and 1. The sample period spans {firm_span} at the firm level and
    {user_span} at the user level; $N$ denotes the number of observations in
    each subgroup.
    \end{{tablenotes}}
    """).strip()


# ----------------------------------------------------------------------
# 5  MAIN
# ----------------------------------------------------------------------
def main(*, firm_path: Path = DEF_FIRM, worker_path: Path = DEF_WORKER, out_path: Path = DEF_OUT) -> None:
    """Create the LaTeX summary table using provided or default paths."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    #panel_a = build_panel(pd.read_csv(firm_path),  VAR_MAP_A, NICE_A, DECIMALS_A)
    panel_a = build_panel(
        pd.read_csv(firm_path),
        VAR_MAP_A,
        NICE_A,
        mean_decimals=DECIMALS_A,
        sd_decimals  =SD_DECIMALS_A,
        pct_vars     = PERCENT_VARS_A
    )

    panel_b = build_panel(
        pd.read_csv(worker_path),
        VAR_MAP_B,
        NICE_B,
        mean_decimals=DECIMALS_B,
        sd_decimals  =DECIMALS_B,
        pct_vars     = None
    )
    with out_path.open("w") as fh:
        fh.write("\\begin{table}[H]\n")
        fh.write("\\centering\n")
        fh.write("\\begin{threeparttable}\n")
        fh.write("\\caption{Table of Means}\n")
        fh.write("\\label{tab:means}\n")
        fh.write("\\begin{tabular}{" + _with_gutter("lccc") + "}\n")
        fh.write("\\toprule\n")
        fh.write(" & Startup & Non-Startup & All \\\\\n")
        fh.write("\\midrule\n")
        fh.write("\\addlinespace\n") 
    
        # ---------- Panel A --------------------------------------------------
        #fh.write(
        #    "\\multicolumn{4}{l}{\\textbf{\\underline{Panel A: "
        #    "Firm-level Descriptive Statistics}}}\\\\[0.3em]\n"
        #)
        #fh.write(
        #    "\\multicolumn{4}{l}{\\textbf{Panel A: Firm-level}}\\\\[0.1em]\n"
        #)
        #fh.write("\\cmidrule(lr){1-4}\n")
        fh.write(
            "\\multicolumn{4}{l}{\\textbf{\\uline{"
            "Panel A: Firm-level"
            "}}}\\\\[0.3em]\n"
        )
        #fh.write("\\addlinespace\n")
        a_tex = panel_a.to_latex(
            index=False,
            header=False,
            escape=False,
            column_format=_with_gutter("lccc")
        )
        #fh.write(_strip_tabular(_insert_midrule_before_N(a_tex)))
        fh.write(_insert_midrule_before_N(_strip_tabular(a_tex)))
        fh.write("\n\\midrule\n")
        fh.write("\\addlinespace\n") 
    
        # ---------- Panel B --------------------------------------------------
        #fh.write(
        #    "\\multicolumn{4}{l}{\\textbf{\\underline{Panel B: "
        #    "Worker-level Contribution Metrics}}}\\\\[0.3em]\n"
        #)
        
        #fh.write(
        #    "\\multicolumn{4}{l}{\\textbf{Panel B: User-level}}\\\\[0.1em]\n"
        #)
        #fh.write("\\cmidrule(lr){1-4}\n")
#        fh.write(
#            "\\multicolumn{4}{l}{\\textbf{\\underline{"
#            "Panel B: Worker-level Contribution Metrics"
#            "}}}\\\\[0.3em]\n"
#        )
        fh.write(
            "\\multicolumn{4}{l}{\\textbf{\\uline{"
            "Panel B: User-level"
            "}}}\\\\[0.3em]\n"
        )
        #fh.write("\\addlinespace\n")
        b_tex = panel_b.to_latex(
            index=False,
            header=False,
            escape=False,
            column_format=_with_gutter("lccc")
        )
        #fh.write(_strip_tabular(_insert_midrule_before_N(b_tex)))
        fh.write(_insert_midrule_before_N(_strip_tabular(b_tex)))
        fh.write("\n\\bottomrule\n")
        fh.write("\\end{tabular}\n")
    
        # ---------- foot-notes ----------------------------------------------
        fh.write(_notes_block())
    
        fh.write("\\end{threeparttable}\n")
        fh.write("\\end{table}\n")
    
    print(f"LaTeX table written to {out_path.resolve()}")

if __name__ == "__main__":
    main()



'''
def main(*, firm_path: Path = DEF_FIRM, worker_path: Path = DEF_WORKER, out_path: Path = DEF_OUT) -> None:
    """Create the LaTeX summary table using provided or default paths."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    panel_a = build_panel(pd.read_csv(firm_path),  VAR_MAP_A, NICE_A, DECIMALS_A)
    panel_b = build_panel(pd.read_csv(worker_path), VAR_MAP_B, NICE_B, DECIMALS_B, None)
    with out_path.open("w") as fh:
        fh.write("\\begin{table}[htbp]\n")
        fh.write("\\centering\n")
        fh.write("\\caption{Table of Means}\n")
        fh.write("\\label{tab:means}\n")
        #fh.write("\\sisetup{table-format=4.2,detect-all}\n\n")
        fh.write(
            "\\sisetup{\n"
            "  table-format = 4.2,\n"
            "  mode = match,\n"
            "  propagate-math-font = true,\n"
            "  reset-math-version = false,\n"
            "  reset-text-family = false,\n"
            "  reset-text-series = false,\n"
            "  reset-text-shape = false,\n"
            "  text-family-to-math = true,\n"
            "  text-series-to-math = true\n"
            "}\n\n"
        )
        fh.write("\\begin{tabular}{lccc}\n")
        fh.write("\\toprule\n")
        fh.write("Variable & {Startup} & {Non-Startup} & {All Firms} \\\\\n")
        fh.write("\\midrule\n")
        fh.write("\\multicolumn{4}{l}{\\textbf{\\underline{Panel A: Firm-level Descriptive Statistics}}}\\\\[0.3em]\n")
        fh.write(_strip_tabular(
            panel_a.to_latex(index=False, header=False, escape=False, column_format="l*{3}{S}")
        ) + "\n")
        fh.write("\\addlinespace\n")
        fh.write("\\midrule\n")
        fh.write("\\addlinespace\n")
        fh.write("\\multicolumn{4}{l}{\\textbf{\\underline{Panel B: Worker-level Contribution Metrics}}}\\\\[0.3em]\n")
        fh.write(_strip_tabular(
            panel_b.to_latex(index=False, header=False, escape=False, column_format="l*{3}{S}")
        ) + "\n")
        fh.write("\\bottomrule\n")
        fh.write("\\end{tabular}\n")
        fh.write("\\end{table}\n")
    log.basicConfig(level=log.INFO, format="%(levelname)s: %(message)s")
    log.info("LaTeX table written to %s", out_path.resolve())
    '''
