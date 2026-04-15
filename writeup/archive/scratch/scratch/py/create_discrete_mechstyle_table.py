#!/usr/bin/env python3
"""Create a mechanisms-style two-panel table for discrete remote treatments.

Layout:
  - Columns: Full-Remote (Remote==1), Hybrid (0<Remote<1)
  - Panel A (top): OLS
  - Panel B (bottom): IV (adds KP rk Wald F row)

Supports firm scaling (3 outcomes summarized to common layout) and user
productivity (Total Contributions). Reads consolidated_results.csv from the
discrete result folders written by the Stata specs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW = PROJECT_ROOT / "results" / "raw"
CLEAN = PROJECT_ROOT / "results" / "cleaned"

PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

def star(p: float) -> str:
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""

def cell(coef: float, se: float, pval: float) -> str:
    return f"\\makecell[c]{{{coef:.2f}{star(pval)}\\\\({se:.2f})}}"

def load_discrete(spec: str, model: str, variant: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    if spec == "firm_scaling":
        full = pd.read_csv(RAW / "firm_scaling_fullremote" / "consolidated_results.csv")
        hyb  = pd.read_csv(RAW / "firm_scaling_hybrid" / "consolidated_results.csv")
        nr   = RAW / "firm_scaling_nonremote" / "consolidated_results.csv"
    else:
        base = f"user_productivity_{variant}"
        full = pd.read_csv(RAW / f"{base}_fullremote" / "consolidated_results.csv")
        hyb  = pd.read_csv(RAW / f"{base}_hybrid" / "consolidated_results.csv")
        nr   = RAW / f"{base}_nonremote" / "consolidated_results.csv"
    nr_df = pd.read_csv(nr) if isinstance(nr, Path) and nr.exists() else None
    return full, hyb, nr_df

def first_row(df: pd.DataFrame, model: str, param: str) -> pd.Series | None:
    sub = df[(df.model_type == model) & (df.param == param)]
    return sub.iloc[0] if not sub.empty else None

def build_table(spec: str, variant: str | None, out_tex: Path) -> None:
    full, hyb, nr = load_discrete(spec, model="", variant=variant)

    caption_core = ("Firm Scaling" if spec == "firm_scaling" else f"User Productivity ({variant})")
    label_core   = ("firm_scaling" if spec == "firm_scaling" else f"user_prod_{variant}")

    lines: list[str] = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(rf"\caption{{{caption_core} — Discrete Remote (Mechanisms style)}}")
    lines.append(rf"\label{{tab:{label_core}_discrete_mech}}")
    has_nr = nr is not None
    cols = "lccc" if has_nr else "lcc"
    head = " & Full-Remote & Hybrid & Non-Remote \\\\" if has_nr else " & Full-Remote & Hybrid \\\\" 
    lines.append(rf"\begin{{tabular}}{{{cols}}}")
    lines.append(r"\toprule")
    lines.append(head)
    lines.append(r"\midrule")

    def render_panel(model: str, panel_tag: str):
        span = 4 if has_nr else 3
        lines.append(rf"\multicolumn{{{span}}}{{l}}{{\textbf{{\uline{{Panel {panel_tag}: {model}}}}}}} \\")
        lines.append(r"\addlinespace")
        for p in ("var3", "var5"):
            rf = first_row(full, model, p.replace("var3", "var3_fullrem").replace("var5", "var5_fullrem"))
            rh = first_row(hyb,  model, p.replace("var3", "var3_hybrid").replace("var5", "var5_hybrid"))
            rn = first_row(nr,   model, p.replace("var3", "var3_nonrem").replace("var5", "var5_nonrem")) if has_nr else None
            if rf is None and rh is None:
                continue
            c_full = cell(rf.coef, rf.se, rf.pval) if rf is not None else ""
            c_hyb  = cell(rh.coef, rh.se, rh.pval) if rh is not None else ""
            row = PARAM_LABEL[p] + " & " + c_full + " & " + c_hyb
            if has_nr:
                c_nr = cell(rn.coef, rn.se, rn.pval) if rn is not None else ""
                row += " & " + c_nr
            lines.append(row + r" \\")
        lines.append(r"\midrule")
        # Summary rows (use first available row to pull N and KP)
        rf_any = first_row(full, model, "var3_fullrem")
        if rf_any is None:
            rf_any = first_row(full, model, "var5_fullrem")
        rh_any = first_row(hyb,  model, "var3_hybrid")
        if rh_any is None:
            rh_any = first_row(hyb,  model, "var5_hybrid")
        rn_any = None
        if has_nr:
            rn_any = first_row(nr, model, "var3_nonrem")
            if rn_any is None:
                rn_any = first_row(nr, model, "var5_nonrem")
        n_full = f"{int(rf_any.nobs):,}" if rf_any is not None else ""
        n_hyb  = f"{int(rh_any.nobs):,}" if rh_any is not None else ""
        rowN = "N & " + n_full + " & " + n_hyb
        if has_nr:
            rowN += " & " + (f"{int(rn_any.nobs):,}" if rn_any is not None else "")
        lines.append(rowN + r" \\")
        if model == "IV":
            k_full = f"{rf_any.rkf:.2f}" if rf_any is not None and pd.notna(rf_any.rkf) else ""
            k_hyb  = f"{rh_any.rkf:.2f}" if rh_any is not None and pd.notna(rh_any.rkf) else ""
            rowK = r"KP\,rk Wald F & " + k_full + " & " + k_hyb
            if has_nr:
                rowK += " & " + (f"{rn_any.rkf:.2f}" if rn_any is not None and pd.notna(rn_any.rkf) else "")
            lines.append(rowK + r" \\")

    # Panel A: OLS, Panel B: IV
    render_panel("OLS", "A")
    render_panel("IV",  "B")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    out_tex.parent.mkdir(parents=True, exist_ok=True)
    out_tex.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(description="Mechanisms-style table for discrete remote treatments")
    ap.add_argument("--spec", choices=["firm_scaling", "user_productivity"], required=True)
    ap.add_argument("--variant", default="precovid", help="User panel variant (when spec=user_productivity)")
    args = ap.parse_args()

    if args.spec == "firm_scaling":
        out_tex = CLEAN / "firm_scaling_discrete_mechstyle.tex"
        build_table("firm_scaling", None, out_tex)
        print(f"Wrote {out_tex}")
    else:
        out_tex = CLEAN / f"user_productivity_{args.variant}_discrete_mechstyle.tex"
        build_table("user_productivity", args.variant, out_tex)
        print(f"Wrote {out_tex}")

if __name__ == "__main__":
    main()
