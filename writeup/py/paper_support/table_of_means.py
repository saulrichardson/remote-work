#!/usr/bin/env python3
r"""Generate LaTeX tables of descriptive statistics.

The script outputs firm-level (Panel A) and individual-level (Panel B) summary
statistics in a single table. Means and standard deviations are stacked using
``\makecell`` and the entire table is written as stand-alone LaTeX.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import textwrap
import re
import warnings
import pandas as pd

from src.py.project_paths import DATA_CLEAN, RESULTS_CLEANED_TEX, RESULTS_RAW, require_file


def _read_dataset(path: Path) -> pd.DataFrame:
    """Load a supported project dataset from CSV or Stata."""
    require_file(path, nonempty=True, purpose="table-of-means input")
    if path.suffix.lower() == ".dta":
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UnicodeWarning)
            return pd.read_stata(path, convert_categoricals=False)
    if path.suffix.lower() == ".csv":
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1")
    raise ValueError(f"Unsupported dataset type for {path}")
# ----------------------------------------------------------------------
# Default file locations
# ----------------------------------------------------------------------
DEF_FIRM = DATA_CLEAN / "firm_panel.dta"
DEF_WORKER = DATA_CLEAN / "user_panel_precovid.dta"
DEF_EQUITY = (
    RESULTS_RAW
    / "postings_description_equity"
    / "firm_merge"
    / "latest_firm_yh_llm_equity_enriched.csv"
)
DEF_OUT = RESULTS_CLEANED_TEX / "table_of_means.tex"

# ----------------------------------------------------------------------
# Panel A: firm level settings
# ----------------------------------------------------------------------
VAR_MAP_A = {
    "growth": "growth_rate_we",
    "leave": "leave_rate_we",
    "join": "join_rate_we",
    "teleworkable": "teleworkable",
    "remote": "remote",
    "equity_comp_pct": "equity_comp_ever",
    "total_employees": "total_employees",
    "age": "age",
    "rent": "rent",
    "hhi_1000": "hhi_1000",
}

DECIMALS_A = {
    "growth": 2,
    "leave": 2,
    "join": 2,
    "teleworkable": 2,
    "remote": 2,
    "equity_comp_pct": 2,
    "total_employees": 0,
    "age": 0,
    "rent": 0,
    "hhi_1000": 0,
}

SD_DECIMALS_A = {
    **DECIMALS_A,
}

NICE_A = {
    "growth": r"Growth",
    "leave": r"Leave",
    "join": r"Join",
    "teleworkable": r"Teleworkable Score \,(0--1)",
    "remote": r"Remote Score \,(0--1)",
    "equity_comp_pct": r"Offers Equity Compensation (\%)",
    "total_employees": r"Employees (Count)",
    "age": r"Age",
    "rent": r"Rent (\textdollar/sq ft)",
    "hhi_1000": r"Centrality Score",
}

PERCENT_VARS_A: set[str] = {"equity_comp_pct"}

# ----------------------------------------------------------------------
# Panel B: individual level settings
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
    mean_fmt = f"{mean_val:.{m_dec}f}"
    sd_fmt = f"{sd_val:.{s_dec}f}"
    return "\\makecell[c]{{{mean}\\\\({sd})}}".format(mean=mean_fmt, sd=sd_fmt)


def _normalize_yh_key(value: object) -> str:
    """Convert half-year labels or datelike values to YYYY-MM-DD merge keys."""
    if pd.isna(value):
        raise ValueError("Encountered missing half-year value during equity merge")

    timestamp = pd.to_datetime(value, errors="coerce")
    if not pd.isna(timestamp):
        return timestamp.normalize().strftime("%Y-%m-%d")

    text = str(value).strip()
    match = re.fullmatch(r"(\d{4})h([12])", text)
    if match:
        year, half = match.groups()
        return f"{year}-01-01" if half == "1" else f"{year}-07-01"

    raise ValueError(f"Unexpected half-year label: {value!r}")


def attach_equity_compensation(df_firms: pd.DataFrame, equity_path: Path) -> pd.DataFrame:
    """Attach firm-level equity-compensation indicators to the sample panel."""
    equity = _read_dataset(equity_path)
    required = {"firm_id_key", "yh", "llm_equity_any_strict"}
    missing = required.difference(equity.columns)
    if missing:
        raise ValueError(f"Missing columns {sorted(missing)} in equity input")

    merged = df_firms.copy()
    if "yh" not in merged.columns:
        raise ValueError("Firm panel must include yh to merge equity.")
    if "firm_id" not in merged.columns and "companyname" not in merged.columns:
        raise ValueError("Firm panel must include firm_id or companyname to merge equity.")

    merged["__yh_key"] = merged["yh"].map(_normalize_yh_key)
    if "firm_id" in merged.columns:
        merged["__firm_key"] = merged["firm_id"].astype(str).str.strip().str.lower()
    else:
        merged["__firm_key"] = merged["companyname"].astype(str).str.strip().str.lower()

    equity = equity[["firm_id_key", "yh", "llm_equity_any_strict"]].copy()
    equity["__firm_key"] = equity["firm_id_key"].astype(str).str.strip().str.lower()
    equity["__yh_key"] = equity["yh"].map(_normalize_yh_key)
    if equity.duplicated(["__firm_key", "__yh_key"]).any():
        raise ValueError("Equity input has duplicate firm-half-year rows.")
    equity = equity.drop(columns=["firm_id_key", "yh"])

    merged = merged.merge(equity, on=["__firm_key", "__yh_key"], how="left", validate="1:1")
    merged["equity_comp_any"] = merged["llm_equity_any_strict"].fillna(0).clip(lower=0, upper=1)
    if "firm_id" not in merged.columns:
        raise ValueError("Firm sample must include firm_id to compute ever-offer equity flags.")
    merged["equity_comp_ever"] = (
        merged.groupby("firm_id")["equity_comp_any"].transform("max").clip(lower=0, upper=1)
    )
    return merged.drop(columns=["__firm_key", "__yh_key", "llm_equity_any_strict"])


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
    INDENT = r"\hspace{1em}"
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
                "variable": INDENT + nice[code],
                "Startup": _mean_sd_cell(
                    code, m_start, sd_start, mean_dec, sd_dec, pct_vars
                ),
                "Established": _mean_sd_cell(
                    code, m_non, sd_non, mean_dec, sd_dec, pct_vars
                ),
                "All Firms": _mean_sd_cell(
                    code, m_all, sd_all, mean_dec, sd_dec, pct_vars
                ),
            }
        )

    rows.append(
        {
            "variable": "\\addlinespace[2pt]\n\\midrule\nN",
            "Startup": int((df[startup_flag] == 1).sum()),
            "Established": int((df[startup_flag] == 0).sum()),
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


def _tabular_star_colspec(n_numeric: int) -> str:
    """Return a tabular* column spec with evenly spaced numeric columns."""
    return "@{}l" + "@{\\extracolsep{\\fill}}c" * n_numeric + "@{}"


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
        \item \emph{{Notes}}: Panel~A uses firm--half--year observations. Panel~B relies on worker--half--year observations. ``Number of firms'' counts distinct firm\,IDs that ever appear in each category over the full sample window, so Startup and Established counts need not sum to the ``All'' column. {scale_sentence} \textit{{Teleworkable}} and \textit{{Remote}} scores are index values between~0 and~1.  The sample period spans {firm_span} at the firm level and {user_span} at the user level.
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
    equity_path: Path = DEF_EQUITY,
    out_path: Path = DEF_OUT,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df_firms = _read_dataset(firm_path)
    df_firms = attach_equity_compensation(df_firms, equity_path)

    # ------------------------------------------------------------------
    # Sample-size block for Panel A
    # ------------------------------------------------------------------
    firm_counts = df_firms.groupby("startup")["firm_id"].nunique()
    obs_counts = df_firms.groupby("startup").size()

    extra_a = pd.DataFrame(
        [
            {
                "variable": "\\addlinespace[2pt]\n\\midrule\nNumber of firms",
                "Startup": int(firm_counts.get(1, 0)),
                "Established": int(firm_counts.get(0, 0)),
                "All Firms": int(df_firms["firm_id"].nunique()),
            },
            {
                "variable": "Observations",
                "Startup": int(obs_counts.get(1, 0)),
                "Established": int(obs_counts.get(0, 0)),
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
            "equity_comp_ever",
            "age",
            "rent",
            "hhi_1000",
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

    df_users = _read_dataset(worker_path)
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
                "variable": "\\addlinespace[2pt]\n\\midrule\nNumber of firms",
                "Startup": int(company_counts.get(1, 0)),
                "Established": int(company_counts.get(0, 0)),
                "All Firms": int(df_users["firm_id"].nunique()),
            },
            {
                # distinct from the subsequent ``N`` (individual–period observations)
                "variable": "Number of individuals",
                "Startup": int(user_counts.get(1, 0)),
                "Established": int(user_counts.get(0, 0)),
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
                        "Established": int(n_row_b.Established),
                        "All Firms": int(n_row_b["All Firms"]),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    raw_a = panel_a.to_latex(
        index=False, header=False, escape=False,
        column_format="lccc",
    )
    a_stripped = _strip_tabular(raw_a)
    a_tex = re.sub(r"^\\midrule[ \t]*\n", "", a_stripped, count=1)
    a_tex = a_tex.replace(
        r"\hspace{1em}Rent (\textdollar/sq ft)",
        r"%\hspace{1em}Rent (\textdollar/sq ft)",
        1,
    )

    raw_b = panel_b.to_latex(
        index=False, header=False, escape=False,
        column_format="lccc",
    )
    b_stripped = _strip_tabular(raw_b)
    b_tex = re.sub(r"^\\midrule[ \t]*\n", "", b_stripped, count=1)


    # Notes removed from the rendered table to keep the layout compact.
    # Original text (for reference):
    # {_notes_block()}

    colspec = _tabular_star_colspec(3)
    table_tex = textwrap.dedent(
        rf"""\centering
\begin{{tabular*}}{{\linewidth}}{{{colspec}}}
\toprule
 & Startup & Established & All Firms \\
\midrule
\multicolumn{{4}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: Firm-level}}}}}} \\
\addlinespace[2pt]
{a_tex}
\midrule
\multicolumn{{4}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: Individual-level}}}}}} \\
\addlinespace[2pt]
{b_tex}
\bottomrule
\end{{tabular*}}"""
    ).strip()

    out_path.write_text(table_tex + "\n")

    print(f"LaTeX table written to {out_path.resolve()}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build table of means")
    parser.add_argument(
        "--firm-file",
        type=Path,
        default=DEF_FIRM,
        help="Dataset with firm-level panel data",
    )
    parser.add_argument(
        "--worker-file",
        type=Path,
        default=DEF_WORKER,
        help="Dataset with worker-level panel data",
    )
    parser.add_argument(
        "--equity-file",
        type=Path,
        default=DEF_EQUITY,
        help="CSV file with firm-half-year equity panel",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(
        firm_path=args.firm_file,
        worker_path=args.worker_file,
        equity_path=args.equity_file,
    )
