#!/usr/bin/env python3
"""Create a combined firm-scaling table comparing remote modalities."""

from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

import math
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_DIR = PROJECT_ROOT / "results" / "raw"
CLEAN_DIR = PROJECT_ROOT / "results" / "cleaned"

TREAT_META = OrderedDict(
    [
        ("fullremote", {"title": "Full-Remote", "suffix": "fullrem"}),
        ("hybrid", {"title": "Hybrid", "suffix": "hybrid"}),
        ("inperson", {"title": "In-Person", "suffix": "inperson"}),
        ("anyremote", {"title": "Any Remote", "suffix": "anyremote"}),
    ]
)

OUTCOME_LABEL = {
    "growth_rate_we": r"Growth (wins.)",
}

PARAM_LABEL = {
    "var3": r"$ \mathds{1}(\text{Remote}) \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \mathds{1}(\text{Remote}) \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float | None) -> str:
    if p is None or math.isnan(p):
        return ""
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def format_single(row: pd.Series) -> str:
    coef = f"{row.coef:.2f}{stars(row.pval)}"
    se = f"({row.se:.2f})"
    return r"\makecell[c]{" + rf"{coef}\\{se}" + "}"


def load_treatment(treat: str) -> dict:
    meta = TREAT_META[treat]
    suffix = meta["suffix"]
    csv_path = RAW_DIR / f"firm_scaling_{treat}" / "consolidated_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    df = pd.read_csv(csv_path)

    data: dict[str, dict[str, dict[str, pd.Series]]] = {"OLS": {}, "IV": {}}
    for model in ("OLS", "IV"):
        sub = df[df["model_type"] == model]
        model_store: dict[str, dict[str, pd.Series]] = {}
        for outcome in OUTCOME_LABEL:
            outcome_sub = sub[sub["outcome"] == outcome]
            entry: dict[str, pd.Series] = {}
            for param in ("var3", "var5"):
                param_name = f"{param}_{suffix}"
                row = outcome_sub[outcome_sub["param"] == param_name]
                if row.empty:
                    raise ValueError(f"Missing {param_name} for {treat} ({model}, {outcome})")
                entry[param] = row.iloc[0]
            model_store[outcome] = entry
        data[model] = model_store

    # store summary stats by outcome (pre_mean, nobs from OLS; rkf from IV)
    summary: dict[str, dict[str, float | int | None]] = {}
    for outcome in OUTCOME_LABEL:
        ols_row = data["OLS"][outcome]["var3"]
        iv_row = data["IV"][outcome]["var3"]
        summary[outcome] = {
            "pre_mean": ols_row.pre_mean,
            "nobs": int(ols_row.nobs),
            "rkf": None if math.isnan(iv_row.rkf) else float(iv_row.rkf),
        }
    data["summary"] = summary
    return data


def build_table(treats: Iterable[str]) -> str:
    treats = list(treats)
    data = {treat: load_treatment(treat) for treat in treats}

    headers = [TREAT_META[t]["title"] for t in treats]

    lines: list[str] = []
    lines.append(r"% Auto-generated: firm scaling remote modalities summary")
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(r"\caption{Firm Scaling -- Remote Modalities}")
    lines.append(r"\label{tab:firm_scaling_remote}")
    col_spec = "l" + "c" * len(treats)
    lines.append(rf"\begin{{tabular}}{{{col_spec}}}")
    lines.append(r"\toprule")
    lines.append("Specification & " + " & ".join(headers) + r" \\")
    lines.append(r"\midrule")

    # Panel A: OLS
    lines.append(rf"\multicolumn{{{len(treats)+1}}}{{l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\")
    lines.append(r"\addlinespace")
    for outcome, out_label in OUTCOME_LABEL.items():
        lines.append(rf"\multicolumn{{{len(treats)+1}}}{{l}}{{\textbf{{{out_label}}}}} \\")
        for param, param_label in PARAM_LABEL.items():
            stub = rf"\quad {param_label}"
            row = [stub]
            for treat in treats:
                row.append(format_single(data[treat]["OLS"][outcome][param]))
            lines.append(" & ".join(row) + r" \\")
        summary = ["\quad Pre-COVID mean"] + [f"{data[t]['summary'][outcome]['pre_mean']:.3f}" for t in treats]
        lines.append(" & ".join(summary) + r" \\")
        summary_n = ["\quad N"] + [f"{data[t]['summary'][outcome]['nobs']:,}" for t in treats]
        lines.append(" & ".join(summary_n) + r" \\")
        lines.append(r"\addlinespace")
    lines.append(r"\midrule")

    # Panel B: IV
    lines.append(rf"\multicolumn{{{len(treats)+1}}}{{l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\")
    lines.append(r"\addlinespace")
    for outcome, out_label in OUTCOME_LABEL.items():
        lines.append(rf"\multicolumn{{{len(treats)+1}}}{{l}}{{\textbf{{{out_label}}}}} \\")
        for param, param_label in PARAM_LABEL.items():
            stub = rf"\quad {param_label}"
            row = [stub]
            for treat in treats:
                row.append(format_single(data[treat]["IV"][outcome][param]))
            lines.append(" & ".join(row) + r" \\")
        kp = ["\quad KP rk Wald F"] + [
            f"{data[t]['summary'][outcome]['rkf']:.2f}" if data[t]['summary'][outcome]['rkf'] is not None else "--"
            for t in treats
        ]
        lines.append(" & ".join(kp) + r" \\")
        n_iv = ["\quad N"] + [f"{data[t]['summary'][outcome]['nobs']:,}" for t in treats]
        lines.append(" & ".join(n_iv) + r" \\")
        lines.append(r"\addlinespace")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create firm scaling remote modalities summary table")
    parser.add_argument(
        "--treats",
        default="fullremote,hybrid,inperson,anyremote",
        help="Comma-separated list of treatments to include",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output TeX path (defaults to results/cleaned/firm_scaling_remote_modalities.tex)",
    )
    args = parser.parse_args()

    treats = [t.strip() for t in args.treats.split(",") if t.strip()]
    for treat in treats:
        if treat not in TREAT_META:
            raise ValueError(f"Unknown treatment '{treat}'.")

    tex = build_table(treats)
    out_path = Path(args.out) if args.out else CLEAN_DIR / "firm_scaling_remote_modalities.tex"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
