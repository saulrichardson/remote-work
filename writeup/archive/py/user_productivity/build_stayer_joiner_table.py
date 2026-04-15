#!/usr/bin/env python3
"""Create a two-column table (stayers vs joiners) for the main user productivity spec."""

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

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
PARAM_ORDER = ("var3", "var5", "var4")
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def load_results(variant: str, sample_mode: str) -> pd.DataFrame:
    """
    Load the raw regression output. For the single-column stayer table we
    prefer the dedicated stayer spec (which skips the joiner block that can
    be collinear under match FE). For two-column output we fall back to the
    combined stayer-joiner file.
    """
    if sample_mode == "stayer":
        path = RESULTS_RAW / f"user_productivity_{variant}_stayer" / "consolidated_results.csv"
    else:
        path = RESULTS_RAW / f"user_productivity_{variant}_stayer_joiner" / "consolidated_results.csv"

    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path)
    # The stayer-only raw file does not tag sample; add it for uniform handling.
    if "sample" not in df.columns:
        df["sample"] = "stayer"
    return df


def table_lines(df: pd.DataFrame, samples: list[str]) -> list[str]:
    lines: list[str] = []
    lines.append("% Auto-generated – do not edit")
    lines.append(r"\centering")

    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * len(samples) + "@{}"
    width = len(samples) + 1
    lines.append(rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}")
    lines.append(r"\toprule")
    if len(samples) == 1:
        # Single-column layout: outcome header row, then sample label row with column number
        label = samples[0].capitalize()
        lines.append(r" & Contribution Rank \\")
        lines.append(r"\cmidrule(lr){2-2}")
        lines.append(rf"\textbf{{{label}}} & (1) \\")
    else:
        lines.append(rf" & \multicolumn{{{len(samples)}}}{{c}}{{Contribution Rank}} \\")
        lines.append(rf"\cmidrule(lr){{2-{len(samples)+1}}}")
        lines.append(" & " + " & ".join(s.capitalize() for s in samples) + r" \\")
        cmid_single = "".join(rf"\cmidrule(lr){{{i}-{i}}}" for i in range(2, len(samples)+2))
        lines.append(cmid_single)
        lines.append(" & " + " & ".join(f"({i})" for i in range(1, len(samples)+1)) + r" \\")
    lines.append(r"\midrule")

    for panel_label, model in (("Panel A: OLS", "OLS"), ("Panel B: IV", "IV")):
        lines.append(rf"\multicolumn{{{width}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} \\")
        lines.append(r"\addlinespace[2pt]")
        for param in PARAM_ORDER:
            row = [r"\hspace{1em}" + PARAM_LABEL.get(param, param)]
            for sample in samples:
                sub = df[
                    (df["sample"] == sample)
                    & (df["model_type"] == model)
                    & (df["param"] == param)
                    & (df["outcome"] == "total_contributions_q100")
                ].head(1)
                if sub.empty:
                    row.append("--")
                else:
                    rec = sub.iloc[0]
                    row.append(cell(rec.coef, rec.se, rec.pval))
            lines.append(" & ".join(row) + r" \\")
    lines.append(r"\midrule")

    # Summary rows
    def summary_row(label: str, field: str, fmt: str, model: str | None = None) -> str:
        vals = []
        for sample in samples:
            sub = df[(df["sample"] == sample)]
            if model:
                sub = sub[sub["model_type"] == model]
            sub = sub[sub["outcome"] == "total_contributions_q100"]
            val = sub[field].iloc[0] if not sub.empty else None
            vals.append(fmt.format(val) if val is not None and pd.notna(val) else "--")
        return " & ".join([label, *vals]) + r" \\"

    lines.append(summary_row("Pre-Covid Mean", "pre_mean", "{:.2f}", model="OLS"))
    lines.append(summary_row("KP rk Wald F", "rkf", "{:.2f}", model="IV"))
    lines.append(summary_row("N", "nobs", "{:,}", model="OLS"))

    lines.append(r"\midrule")
    lines.append(" & ".join([r"\textbf{Fixed effects}"] + [""] * len(samples)) + r" \\")
    for fe_label in ("Time", r"Firm $\times$ Individual"):
        checks = [r"$\checkmark$"] * len(samples)
        lines.append(" & ".join([r"\hspace{1em}" + fe_label] + checks) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default="precovid",
        help="User panel variant (default: %(default)s)",
    )
    parser.add_argument(
        "--samples",
        choices=["both", "stayer", "joiner"],
        default="both",
        help="Which sample(s) to include (default: %(default)s)",
    )
    args = parser.parse_args()

    df = load_results(args.variant, args.samples if args.samples != "both" else "both")

    if args.samples == "both":
        samples = ["stayer", "joiner"]
        out_suffix = "stayer_joiner"
    else:
        samples = [args.samples]
        out_suffix = f"{args.samples}_only"

    lines = table_lines(df, samples)

    out_path = RESULTS_CLEANED_TEX / f"user_productivity_{args.variant}_{out_suffix}.tex"
    ensure_dir(out_path.parent)
    out_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
