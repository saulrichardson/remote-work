#!/usr/bin/env python3
r"""Generate LaTeX tables of descriptive statistics.

The script outputs firm-level (Panel A) and user-level (Panel B) summary
statistics in a single table. Means and standard deviations are stacked using
``\makecell`` and the entire table is written as stand-alone LaTeX.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import textwrap
import re
# ----------------------------------------------------------------------
# Default file locations
# ----------------------------------------------------------------------
DEF_FIRM = Path("../data/samples/firm_panel.csv")
# worker-level sample (expected file name: ``user_panel.csv``)
DEF_WORKER = Path("../data/samples/user_panel.csv")
DEF_OUT = Path("../results/cleaned/table_of_means.tex")

# ----------------------------------------------------------------------
# Panel A: firm level settings
# ----------------------------------------------------------------------
VAR_MAP_A = {
    "growth": "growth_rate_we",
    "leave": "leave_rate_we",
    "join": "join_rate_we",
    "teleworkable": "teleworkable",
    "remote": "remote",
    "total_employees": "total_employees",
    "age": "age",
    "rent": "rent",
    "hhi_1000": "hhi_1000",
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
    "growth": r"Growth",
    "leave": r"Leave",
    "join": r"Join",
    "teleworkable": r"Teleworkable Score \,(0--1)",
    "remote": r"Remote Score \,(0--1)",
    "total_employees": r"Employees (Count)",
    "age": r"Age",
    "rent": r"Rent (\textdollar/sq ft)",
    "hhi_1000": r"Centrality Score",
    "seniority_levels": r"Seniority Levels (Count)",
}

PERCENT_VARS_A: set[str] = set()

# ----------------------------------------------------------------------
# Panel B: user level settings
# ----------------------------------------------------------------------
VAR_MAP_B = {
    "total_contrib_q100": "total_contributions",
    "restricted_contrib_q100": "restricted_contributions",
}

DECIMALS_B = {
    "total_contrib_q100": 2,
    "restricted_contrib_q100": 2,
}

NICE_B = {
    "total_contrib_q100": r"Total Contributions",
    "restricted_contrib_q100": r"Restricted Contributions",
}


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _fmt(
    code: str,
    value: float | int | pd.Series,
    decimals: dict[str, int],
    pct_vars: set[str] | None = None,
) -> str:
    """Format a numeric value with optional percent scaling."""
    if pd.isna(value):
        return ""
    if pct_vars and code in pct_vars:
        value *= 100
    dec = decimals.get(code, 2)
    return f"{value:.{dec}f}"


def _mean_sd_cell(
    code: str,
    mean_val,
    sd_val,
    mean_dec: dict[str, int],
    sd_dec: dict[str, int],
    pct_vars: set[str] | None = None,
) -> str:
    r"""Return a ``\makecell`` string with mean and SD."""
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
    id_col: str | None = None,
    dedup_vars: set[str] | None = None,
) -> pd.DataFrame:
    """Return formatted panel rows."""
    required = list(var_map.values()) + [startup_flag]
    if id_col:
        required.append(id_col)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in input data")

    cols = list(var_map.values())
    stats_by_flag = df.groupby(startup_flag)[cols].agg(["mean", "std"])
    overall_stats = df[cols].agg(["mean", "std"]).T

    # ------------------------------------------------------------------
    # Optional deduplication for static variables
    # ------------------------------------------------------------------
    if id_col and dedup_vars:
        dcols = list(dedup_vars)
        dedup = df.drop_duplicates(id_col)
        dedup_stats_by_flag = dedup.groupby(startup_flag)[dcols].agg(["mean", "std"])
        dedup_overall_stats = dedup[dcols].agg(["mean", "std"]).T
    else:
        dedup_stats_by_flag = None
        dedup_overall_stats = None

    rows: list[dict[str, object]] = []
    for code, col in var_map.items():
        use_dedup = dedup_stats_by_flag is not None and col in (dedup_vars or set())
        flag_stats = dedup_stats_by_flag if use_dedup else stats_by_flag
        overall = dedup_overall_stats if use_dedup else overall_stats

        m_start = (
            flag_stats.loc[1, (col, "mean")] if 1 in flag_stats.index else float("nan")
        )
        sd_start = (
            flag_stats.loc[1, (col, "std")] if 1 in flag_stats.index else float("nan")
        )
        m_non = (
            flag_stats.loc[0, (col, "mean")] if 0 in flag_stats.index else float("nan")
        )
        sd_non = (
            flag_stats.loc[0, (col, "std")] if 0 in flag_stats.index else float("nan")
        )
        m_all, sd_all = overall.loc[col]
        rows.append(
            {
                "variable": nice[code],
                "Startup": _mean_sd_cell(
                    code, m_start, sd_start, mean_dec, sd_dec, pct_vars
                ),
                "Incumbent": _mean_sd_cell(
                    code, m_non, sd_non, mean_dec, sd_dec, pct_vars
                ),
                "All Firms": _mean_sd_cell(
                    code, m_all, sd_all, mean_dec, sd_dec, pct_vars
                ),
            }
        )

    rows.append(
        {
            "variable": "\\addlinespace\n\\midrule\nN",
            "Startup": int((df[startup_flag] == 1).sum()),
            "Incumbent": int((df[startup_flag] == 0).sum()),
            "All Firms": int(df.shape[0]),
        }
    )
    return pd.DataFrame(rows)


def _strip_tabular(latex: str) -> str:
    """Remove the outer ``tabular`` environment produced by ``DataFrame.to_latex``."""
    skip = (
        "\\begin{tabular",
        "\\end{tabular",
        "\\toprule",
        "\\bottomrule",
    )
    return "\n".join(
        line
        for line in latex.splitlines()
        if not any(line.lstrip().startswith(p) for p in skip)
    )


def _with_gutter(colspec: str) -> str:
    """Insert a small horizontal gutter before the last column."""
    return colspec[:-1] + "@{\\hspace{6pt}}" + colspec[-1]


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
        + (
            "fractions between 0 and 1"
            if rate_scale == "fraction"
            else "expressed in percentage points (0--100)"
        )
        + "."
    )
    notes = rf"""
        \begin{{tablenotes}}[flushleft]
        \footnotesize
        \item \emph{{Notes}}: Panel A is on firm--period observations.  Its bottom rows (``Number of firms'' and ``Observations'') define the sample; above are mean (SD) across firm--periods.  Panel B is based on worker--period observations and ends with three rows: ``Number of firms'', ``Number of users'', and ``N'' (worker--period observations). {scale_sentence} \textit{{Teleworkable}} and \textit{{Remote}} scores are index values between 0 and 1. The sample period spans {firm_span} at the firm level and {user_span} at the user level.
        \end{{tablenotes}}
    """
    return textwrap.dedent(notes).strip()


# ----------------------------------------------------------------------
# Main routine
# ----------------------------------------------------------------------
def main(
    *,
    firm_path: Path = DEF_FIRM,
    worker_path: Path = DEF_WORKER,
    out_path: Path = DEF_OUT,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df_firms = pd.read_csv(firm_path)

    # ------------------------------------------------------------------
    # Sample-size block for Panel A
    # ------------------------------------------------------------------
    firm_counts = df_firms.groupby("startup")["firm_id"].nunique()
    obs_counts = df_firms.groupby("startup").size()

    extra_a = pd.DataFrame(
        [
            {
                "variable": "\\addlinespace\n\\midrule\nNumber of firms",
                "Startup": int(firm_counts.get(1, 0)),
                "Incumbent": int(firm_counts.get(0, 0)),
                "All Firms": int(df_firms["firm_id"].nunique()),
            },
            {
                "variable": "Observations",
                "Startup": int(obs_counts.get(1, 0)),
                "Incumbent": int(obs_counts.get(0, 0)),
                "All Firms": int(df_firms.shape[0]),
            },
        ]
    )

    panel_means = build_panel(
        df_firms.copy(),
        VAR_MAP_A,
        NICE_A,
        mean_dec=DECIMALS_A,
        sd_dec=SD_DECIMALS_A,
        pct_vars=PERCENT_VARS_A,
        id_col="firm_id",
        dedup_vars={
            "teleworkable",
            "remote",
            "age",
            "rent",
            "hhi_1000",
            "seniority_levels",
        },
    )

    # extract and drop the auto-generated ``N`` row so we can place it last
    n_mask_a = panel_means.variable.str.contains("\\nN$")
    n_row_a = panel_means.loc[n_mask_a].squeeze()
    panel_means = panel_means.loc[~n_mask_a]

    # The automatically generated ``N`` row duplicates the ``Observations``
    # counts for firm–period data, so we exclude it from Panel A to keep the
    # table concise (requested by the manuscript team).
    panel_a = pd.concat(
        [panel_means, extra_a],
        ignore_index=True,
    )

    df_users = pd.read_csv(worker_path)
    panel_b = build_panel(
        df_users.copy(),
        VAR_MAP_B,
        NICE_B,
        mean_dec=DECIMALS_B,
        sd_dec=DECIMALS_B,
        pct_vars=None,
    )

    # extract and drop the auto-generated ``N`` row
    n_mask_b = panel_b.variable.str.contains("\\nN$")
    n_row_b = panel_b.loc[n_mask_b].squeeze()
    panel_b = panel_b.loc[~n_mask_b]

    # compute counts for the user sample
    company_counts = df_users.groupby("startup")["firm_id"].nunique()
    user_counts = df_users.groupby("startup")["user_id"].nunique()

    extra_b = pd.DataFrame(
        [
            {
                "variable": "\\addlinespace\n\\midrule\nNumber of firms",
                "Startup": int(company_counts.get(1, 0)),
                "Incumbent": int(company_counts.get(0, 0)),
                "All Firms": int(df_users["firm_id"].nunique()),
            },
            {
                # distinct from the subsequent ``N`` (user–period observations)
                "variable": "Number of users",
                "Startup": int(user_counts.get(1, 0)),
                "Incumbent": int(user_counts.get(0, 0)),
                "All Firms": int(df_users["user_id"].nunique()),
            },
        ]
    )

    # append it to Panel B and place the ``N`` row last
    panel_b = pd.concat(
        [
            panel_b,
            extra_b,
            pd.DataFrame(
                [
                    {
                        "variable": "Observations",
                        "Startup": int(n_row_b.Startup),
                        "Incumbent": int(n_row_b.Incumbent),
                        "All Firms": int(n_row_b["All Firms"]),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    raw_a = panel_a.to_latex(
        index=False, header=False, escape=False,
        column_format=_with_gutter("lccc"),
    )
    a_stripped = _strip_tabular(raw_a)
    a_tex = re.sub(r"^\\midrule[ \t]*\n", "", a_stripped, count=1)

    raw_b = panel_b.to_latex(
        index=False, header=False, escape=False,
        column_format=_with_gutter("lccc"),
    )
    b_stripped = _strip_tabular(raw_b)
    b_tex = re.sub(r"^\\midrule[ \t]*\n", "", b_stripped, count=1)


    table_tex = textwrap.dedent(
        rf"""
        \begin{{table}}[H]
        \centering
        \begin{{threeparttable}}
        \caption{{Table of Means}}
        \label{{tab:means}}
        \begin{{tabular}}{{{_with_gutter('lccc')}}}
        \toprule
         & Startup & Incumbent & All Firms \\
        \midrule
        \addlinespace
        \multicolumn{{4}}{{l}}{{\textbf{{\uline{{Panel A: Firm-level}}}}}}\\[0.3em]
        {a_tex}
        \addlinespace
        \midrule
        \addlinespace
        \multicolumn{{4}}{{l}}{{\textbf{{\uline{{Panel B: User-level}}}}}}\\[0.3em]
        {b_tex}
        \bottomrule
        \end{{tabular}}
        {_notes_block()}
        \end{{threeparttable}}
        \end{{table}}
        """
    ).strip()

    out_path.write_text(table_tex + "\n")

    print(f"LaTeX table written to {out_path.resolve()}")


if __name__ == "__main__":
    main()
