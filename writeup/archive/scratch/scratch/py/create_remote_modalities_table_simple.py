#!/usr/bin/env python3
"""Create a robust LaTeX table comparing fully-remote vs hybrid/in-person.

This formatter mirrors the stable layout used in user_productivity_precovid.tex
to avoid alignment issues when included in larger documents.  It avoids nested
tabulars and fragile left-column constructs.
"""

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
        (
            "remote",
            {
                "title": "Fully Remote",
                "suffix": "remote",
            },
        ),
        (
            "nonremote",
            {
                "title": "Hybrid / In-Person",
                "suffix": "nonremote",
            },
        ),
    ]
)

PARAM_LABELS_LATEX = {
    "var3": r"$ \mathds{1}(\text{Remote}) \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \mathds{1}(\text{Remote}) \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float | None) -> str:
    if p is None or math.isnan(p):
        return ""
    for cut, symbol in STAR_RULES:
        if p < cut:
            return symbol
    return ""


def fmt_cell(coef: float, se: float, p: float) -> str:
    return f"\\makecell[c]{{{coef:.2f}{stars(p)}\\\\({se:.2f})}}"


def load_treatment(variant: str, treat: str) -> dict:
    meta = TREAT_META[treat]
    suffix = meta["suffix"]
    candidates = [
        RAW_DIR / f"user_productivity_binary_{variant}_{treat}",
        RAW_DIR / f"user_productivity_{variant}_{treat}",
    ]
    base_dir = next((d for d in candidates if d.exists()), None)
    if base_dir is None:
        raise FileNotFoundError(f"Missing raw directory for {variant}/{treat}")
    csv_path = base_dir / "consolidated_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Expected {csv_path}")

    df = pd.read_csv(csv_path)

    out: dict[str, dict[str, pd.Series] | float | int | None] = {"OLS": {}, "IV": {}}
    for model in ("OLS", "IV"):
        sub = df[df["model_type"] == model]
        for param in ("var3", "var5"):
            param_name = f"{param}_{suffix}"
            row = sub[sub["param"] == param_name]
            if row.empty:
                raise ValueError(f"Missing {param_name} for {treat} ({model})")
            out[model][param] = row.iloc[0]

    any_ols = out["OLS"]["var3"]  # type: ignore[index]
    any_iv = out["IV"]["var3"]    # type: ignore[index]
    out["pre_mean"] = float(any_ols.pre_mean)
    out["nobs"] = int(any_ols.nobs)
    out["rkf"] = float(any_iv.rkf) if not math.isnan(any_iv.rkf) else None
    return out


def build_table(variant: str, treats: Iterable[str]) -> str:
    treats = list(treats)
    data = {treat: load_treatment(variant, treat) for treat in treats}

    headers = [TREAT_META[t]["title"].replace("&", "\\&") for t in treats]

    lines: list[str] = []
    lines.append("% Auto-generated: user productivity remote modalities (robust)")
    lines.append("\\begin{table}[H]")
    lines.append("\\centering")
    lines.append("\\caption{User Productivity -- Remote Modalities}")
    lines.append(f"\\label{{tab:user_prod_{variant}_modalities}}")
    # Match the layout style of the main user productivity table
    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * len(treats) + "@{}"
    lines.append(f"\\begin{{tabular*}}{{\\linewidth}}{{{colspec}}}")
    E = "\\\\"  # row terminator "\\\\"
    lines.append("\\toprule")
    lines.append("& " + " & ".join(headers) + " " + E)
    lines.append("\\midrule")

    # Panel A: OLS
    lines.append(f"\\multicolumn{{{len(treats)+1}}}{{@{{}}l}}{{\\textbf{{\\uline{{Panel A: OLS}}}}}} " + E)
    lines.append("\\addlinespace[2pt]")
    indent = r"\hspace{1em}"
    for param in ("var3", "var5"):
        label = PARAM_LABELS_LATEX[param]
        row = [f"{indent}{label}"]
        for t in treats:
            s = data[t]["OLS"][param]  # type: ignore[index]
            row.append(fmt_cell(float(s.coef), float(s.se), float(s.pval)))
        lines.append(" & ".join(row) + " " + E)
    lines.append("\\midrule")
    lines.append("Pre-Covid Mean & " + " & ".join(f"{data[t]['pre_mean']:.2f}" for t in treats) + " " + E)
    lines.append("N & " + " & ".join(f"{data[t]['nobs']:,}" for t in treats) + " " + E)
    lines.append("\\midrule")

    # Panel B: IV
    lines.append(f"\\multicolumn{{{len(treats)+1}}}{{@{{}}l}}{{\\textbf{{\\uline{{Panel B: IV}}}}}} " + E)
    lines.append("\\addlinespace[2pt]")
    for param in ("var3", "var5"):
        label = PARAM_LABELS_LATEX[param]
        row = [f"{indent}{label}"]
        for t in treats:
            s = data[t]["IV"][param]  # type: ignore[index]
            row.append(fmt_cell(float(s.coef), float(s.se), float(s.pval)))
        lines.append(" & ".join(row) + " " + E)
    lines.append("\\midrule")
    rkfs = [data[t]["rkf"] for t in treats]
    lines.append(
        "KP rk Wald F & "
        + " & ".join(f"{v:.2f}" if v is not None else "--" for v in rkfs)
        + " " + E)
    lines.append("N & " + " & ".join(f"{data[t]['nobs']:,}" for t in treats) + " " + E)
    lines.append("\\midrule")

    # Fixed effects block (mirror main table style: explicit header row)
    blanks = " & ".join(["" for _ in treats])
    lines.append("\\textbf{Fixed Effects} & " + blanks + " " + E)
    lines.append(f"{indent}Time FE & " + " & ".join(["$\\checkmark$"] * len(treats)) + " " + E)
    lines.append(f"{indent}Firm $\\times$ User FE & " + " & ".join(["$\\checkmark$"] * len(treats)) + " " + E)

    lines.append("\\bottomrule")
    lines.append("\\end{tabular*}")
    lines.append("\\end{table}")

    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Robust remote modalities summary table")
    p.add_argument("--variant", default="precovid")
    p.add_argument("--treats", default="remote,nonremote")
    p.add_argument("--out", default=None)
    a = p.parse_args()

    treats = [t.strip() for t in a.treats.split(",") if t.strip()]
    for t in treats:
        if t not in TREAT_META:
            raise ValueError(f"Unknown treatment '{t}'. Valid: {', '.join(TREAT_META)}")

    tex = build_table(a.variant, treats)
    out_path = Path(a.out) if a.out else CLEAN_DIR / f"user_productivity_{a.variant}_remote_modalities.tex"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
