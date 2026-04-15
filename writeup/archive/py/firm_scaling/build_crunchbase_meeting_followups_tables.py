#!/usr/bin/env python3
"""Build small TeX tables for the Crunchbase meeting follow-up doc.

This script is intentionally narrow: it produces reproducible sample-accounting
and distribution diagnostics directly from the analysis panel CSV, so the
wrapper PDF can answer meeting questions without manual copy/paste.

Inputs:
  - data/clean/firm_panel_with_cb_funding.csv

Outputs:
  - results/cleaned/tex/firm_scaling_crunchbase_meeting_followups_sample.tex
  - results/cleaned/tex/firm_scaling_crunchbase_meeting_followups_distribution.tex
  - results/cleaned/tex/firm_scaling_crunchbase_meeting_followups_maturity.tex
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))
SCRIPTS_DIR = HERE.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_paths import DATA_CLEAN, RESULTS_CLEANED_TEX, ensure_dir  # type: ignore
from user_productivity.build_baseline_table import PREAMBLE_FLEX, TOP, MID, BOTTOM  # type: ignore

LB = r" \\"

PANEL_CSV = DATA_CLEAN / "firm_panel_with_cb_funding.csv"


def column_format_padded(n_numeric: int) -> str:
    return "l" + (r"@{\extracolsep{\fill}}c" * n_numeric)


def fmt_int(x: int | float | None) -> str:
    if x is None:
        return ""
    return f"{int(x):,}"


def fmt_share(x: float | None) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{float(x):.3f}"


def load_panel() -> pd.DataFrame:
    if not PANEL_CSV.exists():
        raise FileNotFoundError(
            f"Missing panel input: {PANEL_CSV}. "
            "Build via: python src/py/build_firm_scaling_crunchbase_outcomes.py"
        )
    df = pd.read_csv(PANEL_CSV, low_memory=False)

    # Ensure key columns are numeric for reliable comparisons.
    for col in ["cb_matched", "public", "startup", "cb_raised_usd"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def sample_accounting_table(panel: pd.DataFrame) -> str:
    # Define samples explicitly (mirrors fundraising scripts).
    full = panel.copy()
    matched = panel[panel["cb_matched"] == 1].copy()
    matched_public = matched[matched["public"] == 1].copy()
    matched_private = matched[matched["public"] != 1].copy()

    def _summarise(df: pd.DataFrame) -> dict[str, float]:
        out: dict[str, float] = {}
        out["n_obs"] = int(len(df))
        out["n_firms"] = int(df["firm_id"].nunique()) if "firm_id" in df.columns else float("nan")

        # Startup shares: compute at the firm level when startup is available.
        if "startup" in df.columns:
            # Firm-level: dedupe firm_id first.
            if "firm_id" in df.columns:
                firms = df[["firm_id", "startup"]].drop_duplicates("firm_id")
                out["startup_share_firms"] = float((firms["startup"] == 1).mean())

        # Funding zeros are meaningful only within the Crunchbase-matched sample.
        # Unmatched firms have cb_raised_usd missing by construction, so we avoid
        # reporting a conditional-on-match share for the full panel.
        if "cb_raised_usd" in df.columns and "cb_matched" in df.columns and (df["cb_matched"] == 1).all():
            s = df["cb_raised_usd"].dropna()
            if s.shape[0] > 0:
                out["share_usd_zero"] = float((s == 0).mean())
                out["share_usd_pos"] = float((s > 0).mean())
        return out

    rows = [
        ("Full panel", _summarise(full)),
        ("CB matched", _summarise(matched)),
        ("Matched, public", _summarise(matched_public)),
        ("Matched, private", _summarise(matched_private)),
    ]

    # Build TeX
    headers = [
        "Sample",
        "Obs",
        "Firms",
        "Non-startup (firms)",
        "Share USD=0",
    ]

    lines: list[str] = [
        PREAMBLE_FLEX + r"\small" + "\n",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(headers)-1)}}}",
        TOP,
        " & ".join(headers) + LB,
        MID,
    ]

    for label, stats in rows:
        startup_f = stats.get("startup_share_firms")
        nonstartup_f = None if startup_f is None else (1.0 - float(startup_f))

        cells = [
            label,
            fmt_int(stats.get("n_obs")),
            fmt_int(stats.get("n_firms")),
            fmt_share(nonstartup_f),
            fmt_share(stats.get("share_usd_zero")),
        ]
        lines.append(" & ".join(cells) + LB)

    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def distribution_table(panel: pd.DataFrame) -> str:
    # Baseline fundraising sample: matched + private.
    df = panel[(panel["cb_matched"] == 1) & (panel["public"] != 1)].copy()

    s = df["cb_raised_usd"]
    s = s[s.notna()].astype(float)
    n = int(s.shape[0])
    share0 = float((s == 0).mean()) if n else float("nan")

    percentiles = {p: float(s.quantile(p)) for p in [0.50, 0.75, 0.90, 0.95, 0.99]} if n else {}
    maxv = float(s.max()) if n else float("nan")

    headers = ["Variable", "N", "Share=0", "p50", "p75", "p90", "p95", "p99", "Max"]

    def _fmt_money(x: float | None) -> str:
        if x is None or pd.isna(x):
            return ""
        # Keep raw dollars as integers with commas (Crunchbase USD is integer-like).
        return f"{int(round(float(x))):,}"

    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(headers)-1)}}}",
        TOP,
        " & ".join(headers) + LB,
        MID,
    ]

    lines.append(
        " & ".join(
            [
                r"USD raised (half-year)",
                fmt_int(n),
                fmt_share(share0),
                _fmt_money(percentiles.get(0.50)),
                _fmt_money(percentiles.get(0.75)),
                _fmt_money(percentiles.get(0.90)),
                _fmt_money(percentiles.get(0.95)),
                _fmt_money(percentiles.get(0.99)),
                _fmt_money(maxv),
            ]
        )
        + LB
    )

    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def maturity_table(panel: pd.DataFrame) -> str:
    # Matched + private fundraising sample (mirrors fundraising scripts).
    df = panel[(panel["cb_matched"] == 1) & (panel["public"] != 1)].copy()

    # Firm-level age snapshot (age is time-invariant in this pipeline).
    required = {"firm_id", "age"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing required columns for maturity table: {sorted(missing)}")

    firms = df[["firm_id", "age"]].drop_duplicates("firm_id").copy()
    firms["age"] = pd.to_numeric(firms["age"], errors="coerce")
    firms = firms[firms["age"].notna()].copy()

    n_firms = int(firms.shape[0])

    def _count_share_gt(cut: float) -> tuple[int, float]:
        mask = firms["age"] > cut
        return int(mask.sum()), float(mask.mean()) if n_firms else float("nan")

    cuts = [10, 15, 20]
    stats = {c: _count_share_gt(float(c)) for c in cuts}

    headers = ["Sample", "Firms", "Age>10", "Age>15", "Age>20"]

    def _fmt_cs(x: tuple[int, float]) -> str:
        n, s = x
        return f"{n:,} ({s:.3f})"

    lines: list[str] = [
        PREAMBLE_FLEX + r"\small" + "\n",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(headers)-1)}}}",
        TOP,
        " & ".join(headers) + LB,
        MID,
        " & ".join(
            [
                "Matched, private",
                fmt_int(n_firms),
                _fmt_cs(stats[10]),
                _fmt_cs(stats[15]),
                _fmt_cs(stats[20]),
            ]
        )
        + LB,
        BOTTOM,
        r"\end{tabular*}",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output-sample",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_meeting_followups_sample.tex",
        help="Destination TeX file for sample accounting table.",
    )
    p.add_argument(
        "--output-distribution",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_meeting_followups_distribution.tex",
        help="Destination TeX file for distribution diagnostics table.",
    )
    p.add_argument(
        "--output-maturity",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_meeting_followups_maturity.tex",
        help="Destination TeX file for sample maturity (age cutoffs) table.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    panel = load_panel()

    ensure_dir(args.output_sample.parent)
    args.output_sample.write_text(sample_accounting_table(panel), encoding="utf-8")
    print(f"Wrote sample accounting table → {args.output_sample}")

    ensure_dir(args.output_distribution.parent)
    args.output_distribution.write_text(distribution_table(panel), encoding="utf-8")
    print(f"Wrote distribution diagnostics table → {args.output_distribution}")

    ensure_dir(args.output_maturity.parent)
    args.output_maturity.write_text(maturity_table(panel), encoding="utf-8")
    print(f"Wrote sample maturity table → {args.output_maturity}")


if __name__ == "__main__":
    main()
