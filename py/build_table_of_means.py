#!/usr/bin/env python3
"""Generate LaTeX tables of descriptive statistics.

The script outputs firm-level (Panel A) and user-level (Panel B) summary
statistics in a single table. Means and standard deviations are stacked using
``\makecell`` and the entire table is written as stand-alone LaTeX.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import textwrap

# ----------------------------------------------------------------------
# Default file locations
# ----------------------------------------------------------------------
DEF_FIRM   = Path("../data/samples/firm_panel.csv")
DEF_WORKER = Path("../data/samples/worker_panel.csv")
DEF_OUT    = Path("../results/cleaned/table_of_means.tex")

# ----------------------------------------------------------------------
# Panel A: firm level settings
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

SD_DECIMALS_A = {
    **DECIMALS_A,
    "seniority_levels": 2,  # always show two decimals for SD
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

PERCENT_VARS_A: set[str] = set()

# ----------------------------------------------------------------------
# Panel B: user level settings
# ----------------------------------------------------------------------
VAR_MAP_B = {
    "total_contrib_q100":      "total_contributions",
    "restricted_contrib_q100": "restricted_contributions",
}

DECIMALS_B = {
    "total_contrib_q100":      2,
    "restricted_contrib_q100": 2,
}

NICE_B = {
    "total_contrib_q100":      r"Total Contributions",
    "restricted_contrib_q100": r"Restricted Contributions",
}

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _fmt(code: str, value: float | int | pd.Series, decimals: dict[str, int],
         pct_vars: set[str] | None = None) -> str:
    """Format a numeric value with optional percent scaling."""
    if pd.isna(value):
        return ""
    if pct_vars and code in pct_vars:
        value *= 100
    dec = decimals.get(code, 2)
    return f"{value:.{dec}f}"


def _mean_sd_cell(code: str, mean_val, sd_val,
                  mean_dec: dict[str, int], sd_dec: dict[str, int],
                  pct_vars: set[str] | None = None) -> str:
    """Return a ``\makecell`` string with mean and SD."""
    if pd.isna(mean_val) or pd.isna(sd_val):
        return ""
    if pct_vars and code in pct_vars:
        mean_val *= 100
        sd_val *= 100
    m_dec = mean_dec.get(code, 2)
    s_dec = sd_dec.get(code, 2)
    return rf"\makecell{{{mean_val:.{m_dec}f} \\ ({sd_val:.{s_dec}f})}}"


def build_panel(
    df: pd.DataFrame,
    var_map: dict[str, str],
    nice: dict[str, str],
    mean_dec: dict[str, int],
    sd_dec: dict[str, int],
    pct_vars: set[str] | None = None,
    *,
    startup_flag: str = "startup",
) -> pd.DataFrame:
    """Return formatted panel rows."""
    required = list(var_map.values()) + [startup_flag]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in input data")

    cols = list(var_map.values())
    stats_by_flag = df.groupby(startup_flag)[cols].agg(["mean", "std"])
    overall_stats = df[cols].agg(["mean", "std"]).T

    rows: list[dict[str, object]] = []
    for code, col in var_map.items():
        m_start = stats_by_flag.loc[1, (col, "mean")] if 1 in stats_by_flag.index else float("nan")
        sd_start = stats_by_flag.loc[1, (col, "std")] if 1 in stats_by_flag.index else float("nan")
        m_non = stats_by_flag.loc[0, (col, "mean")] if 0 in stats_by_flag.index else float("nan")
        sd_non = stats_by_flag.loc[0, (col, "std")] if 0 in stats_by_flag.index else float("nan")
        m_all, sd_all = overall_stats.loc[col]
        rows.append({
            "variable": nice[code],
            "Startup":    _mean_sd_cell(code, m_start, sd_start, mean_dec, sd_dec, pct_vars),
            "Incumbent":  _mean_sd_cell(code, m_non, sd_non, mean_dec, sd_dec, pct_vars),
            "All Firms":  _mean_sd_cell(code, m_all, sd_all, mean_dec, sd_dec, pct_vars),
        })

    rows.append({
        "variable": "N",
        "Startup":    int((df[startup_flag] == 1).sum()),
        "Incumbent":  int((df[startup_flag] == 0).sum()),
        "All Firms":  int(df.shape[0]),
    })
    return pd.DataFrame(rows)


def _strip_tabular(latex: str) -> str:
    """Remove the outer ``tabular`` environment produced by ``DataFrame.to_latex``."""
    skip = ("\\begin{tabular", "\\end{tabular", "\\toprule", "\\midrule", "\\bottomrule")
    return "\n".join(
        line for line in latex.splitlines()
        if not any(line.lstrip().startswith(p) for p in skip)
    )


def _with_gutter(colspec: str) -> str:
    """Insert a small horizontal gutter before the last column."""
    return colspec[:-1] + "@{\\hspace{6pt}}" + colspec[-1]


def _insert_midrule_before_N(tex: str) -> str:
    """Insert ``\addlinespace`` and ``\midrule`` before the N row."""
    return tex.replace("\nN &", "\n\\addlinespace\n\\midrule\nN &", 1)


def _notes_block(
    *,
    rate_scale: str = "fraction",
    firm_span: str = "2016 H2–2022 H1",
    user_span: str = "2017 H1–2022 H1",
) -> str:
    """Return a ``tablenotes`` environment."""
    if rate_scale not in {"fraction", "pp"}:
        raise ValueError("rate_scale must be 'fraction' or 'pp'")
    scale_sentence = (
        r"\textit{Growth}, \textit{Leave}, and \textit{Join} rates are "
        + ("fractions between 0 and 1" if rate_scale == "fraction" else "expressed in percentage points (0--100)")
        + "."
    )
    return textwrap.dedent(
        rf"""
        \begin{{tablenotes}}[flushleft]
        \footnotesize
        \item \emph{{Notes}}: Each cell shows the mean on the first line and the standard deviation (SD) beneath it in parentheses. Decimal precision reflects each variable’s scale. {scale_sentence} \textit{{Teleworkable}} and \textit{{Remote}} scores are index values between 0 and 1. The sample period spans {firm_span} at the firm level and {user_span} at the user level; $N$ denotes the number of observations in each subgroup.
        \end{{tablenotes}}
        """
    ).strip()


# ----------------------------------------------------------------------
# Main routine
# ----------------------------------------------------------------------
def main(*, firm_path: Path = DEF_FIRM, worker_path: Path = DEF_WORKER, out_path: Path = DEF_OUT) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    panel_a = build_panel(
        pd.read_csv(firm_path),
        VAR_MAP_A,
        NICE_A,
        mean_dec=DECIMALS_A,
        sd_dec=SD_DECIMALS_A,
        pct_vars=PERCENT_VARS_A,
    )

    panel_b = build_panel(
        pd.read_csv(worker_path),
        VAR_MAP_B,
        NICE_B,
        mean_dec=DECIMALS_B,
        sd_dec=DECIMALS_B,
        pct_vars=None,
    )

    with out_path.open("w") as fh:
        fh.write("\\begin{table}[H]\n")
        fh.write("\\centering\n")
        fh.write("\\begin{threeparttable}\n")
        fh.write("\\caption{Table of Means}\n")
        fh.write("\\label{tab:means}\n")
        fh.write(f"\\begin{{tabular}}{{{_with_gutter('lccc')}}}\n")
        fh.write("\\toprule\n")
        fh.write(" & Startup & Incumbent & All Firms \\\\\n")
        fh.write("\\midrule\n")
        fh.write("\\addlinespace\n")

        fh.write("\\multicolumn{4}{l}{\\textbf{\\uline{Panel A: Firm-level}}}\\\\[0.3em]\n")
        a_tex = panel_a.to_latex(index=False, header=False, escape=False, column_format=_with_gutter("lccc"))
        fh.write(_insert_midrule_before_N(_strip_tabular(a_tex)))
        fh.write("\n\\midrule\n\\addlinespace\n")

        fh.write("\\multicolumn{4}{l}{\\textbf{\\uline{Panel B: User-level}}}\\\\[0.3em]\n")
        b_tex = panel_b.to_latex(index=False, header=False, escape=False, column_format=_with_gutter("lccc"))
        fh.write(_insert_midrule_before_N(_strip_tabular(b_tex)))
        fh.write("\n\\bottomrule\n")
        fh.write("\\end{tabular}\n")
        fh.write(_notes_block())
        fh.write("\\end{threeparttable}\n")
        fh.write("\\end{table}\n")

    print(f"LaTeX table written to {out_path.resolve()}")


if __name__ == "__main__":
    main()
