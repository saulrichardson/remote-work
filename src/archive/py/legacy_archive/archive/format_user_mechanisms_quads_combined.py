#!/usr/bin/env python3
"""
Combine remote-anchored quadruple (var3_M, var5_M) and startup-anchored
quadruple (post_M, postSM) with the baseline into a single PDF-ready LaTeX.

Usage:
  python py/format_user_mechanisms_quads_combined.py \
    --quad results/raw/user_mechanisms_quad_precovid/consolidated_results.csv \
    --mech results/raw/user_mechanisms_quad_precovid/consolidated_results_mechstyle.csv \
    --out results/cleaned
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


PARAM_LABELS_QUAD = {
    "var3": r"Remote $\times$ Post",
    "var5": r"Remote $\times$ Post $\times$ Startup",
    "var3_M": r"Remote $\times$ Post $\times$ M",
    "var5_M": r"Remote $\times$ Post $\times$ Startup $\times$ M",
}

PARAM_LABELS_MECH = {
    "var3": r"Remote $\times$ Post",
    "var5": r"Remote $\times$ Post $\times$ Startup",
    "post_M": r"Post $\times$ M",
    "postSM": r"Post $\times$ Startup $\times$ M",
}


def stars(p):
    if p is None or pd.isna(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def fmt_coef(b, p):
    return f"{b:.3f}{stars(p)}"


def fmt_se(se):
    return f"({se:.3f})"


def mech_title(mech: str, variant: str) -> str:
    label = {
        "baseline": "Baseline",
        "rent": "Rent (high, binary split)",
        "hhi": "HHI (high, binary split)",
        "seniority4": "Seniority L4+ (binary)",
    }.get(mech, mech)
    if mech != "baseline" and variant and variant not in {"tile", "binary", "none"}:
        label = f"{label} – {variant}"
    return label


def build_panel(df: pd.DataFrame, mech: str, variant: str, labels: dict[str, str], order: list[str]) -> str:
    sub = df[(df["mechanism"] == mech) & (df["variant"] == variant)]
    if sub.empty:
        return ""
    def get(mt: str, param: str):
        r = sub[(sub["model_type"] == mt) & (sub["param"] == param)]
        if r.empty:
            return ("", "")
        r = r.iloc[0]
        return fmt_coef(r["coef"], r.get("pval")), fmt_se(r["se"])  # type: ignore[index]

    iv = sub[sub["model_type"] == "IV"].head(1)
    N = int(iv["nobs"].iloc[0]) if not iv.empty else None
    rkf = float(iv["rkf"].iloc[0]) if (not iv.empty and pd.notna(iv["rkf"].iloc[0])) else None

    lines: list[str] = []
    lines.append("\\begin{table}[H]")
    lines.append("\\centering")
    lines.append(f"\\caption{{{mech_title(mech, variant)} }}")
    lines.append("\\begin{tabular}{lcc}")
    lines.append("\\toprule")
    lines.append(" & OLS & IV \\\\")
    lines.append("\\midrule")
    for key in order:
        label = labels[key]
        oc, os = get("OLS", key)
        ic, is_ = get("IV", key)
        lines.append(f"{label} & {oc} & {ic} \\\\")
        lines.append(f" & {os} & {is_} \\\\")
    if N is not None:
        lines.append("\\midrule")
        if rkf is not None:
            lines.append(f"N & \\multicolumn{{2}}{{c}}{{{N:,}}} \\\\")
            lines.append(f"KP rk Wald F & \\multicolumn{{2}}{{c}}{{{rkf:.2f}}} \\\\")
        else:
            lines.append(f"N & \\multicolumn{{2}}{{c}}{{{N:,}}} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quad", type=Path, required=True)
    ap.add_argument("--mech", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results/cleaned"))
    args = ap.parse_args()

    df_quad = pd.read_csv(args.quad)
    df_mech = pd.read_csv(args.mech)
    args.out.mkdir(parents=True, exist_ok=True)

    # Sections: Baseline, then for each mechanism two tables: remote-anchored and startup-anchored
    preferred = [("baseline", "none"), ("rent", "tile"), ("hhi", "tile"), ("seniority4", "binary")]
    sections: list[str] = []

    # Baseline panel from df_quad
    sections.append(build_panel(df_quad, "baseline", "none", PARAM_LABELS_QUAD, ["var3", "var5"]))

    for mech, variant in preferred[1:]:
        # Remote-anchored quadruple (from df_quad)
        sec1 = build_panel(df_quad, mech, variant, PARAM_LABELS_QUAD, ["var3", "var5", "var3_M", "var5_M"]) 
        if sec1:
            sections.append(sec1)

        # Startup-anchored quadruple (from df_mech)
        sub = df_mech[(df_mech["mechanism"] == mech) & (df_mech["variant"] == variant)]
        params = set(sub["param"].unique())
        # Choose canonical mechanism-specific names if present; otherwise fall back
        if mech == "rent" and {"var8", "var9"}.issubset(params):
            order = ["var3", "var5", "var8", "var9"]
            labels = PARAM_LABELS_MECH | {"var8": r"Post $\times$ Rent", "var9": r"Post $\times$ Startup $\times$ Rent"}
        elif mech == "hhi" and {"var11", "var12"}.issubset(params):
            order = ["var3", "var5", "var11", "var12"]
            labels = PARAM_LABELS_MECH | {"var11": r"Post $\times$ HHI", "var12": r"Post $\times$ Startup $\times$ HHI"}
        elif mech == "seniority4" and {"var14", "var15"}.issubset(params):
            order = ["var3", "var5", "var14", "var15"]
            labels = PARAM_LABELS_MECH | {"var14": r"Post $\times$ Seniority4", "var15": r"Post $\times$ Startup $\times$ Seniority4"}
        else:
            order = ["var3", "var5", "post_M", "postSM"]
            labels = PARAM_LABELS_MECH
        sec2 = build_panel(df_mech, mech, variant, labels, order)
        if sec2:
            sections.append(sec2)

    doc = []
    doc.append("\\documentclass[11pt]{article}")
    doc.append("\\usepackage{booktabs}")
    doc.append("\\usepackage{float}")
    doc.append("\\usepackage[margin=1in]{geometry}")
    doc.append("\\title{Quadruple Mechanisms – Baseline and Combined}")
    doc.append("\\date{\\today}")
    doc.append("\\begin{document}")
    doc.append("\\maketitle")
    for s in sections:
        if s:
            doc.append(s)
    doc.append("\\end{document}")
    out_tex = args.out / "quads_combined.tex"
    out_tex.write_text("\n".join(doc))
    print("✓ Wrote combined LaTeX:", out_tex)


if __name__ == "__main__":
    main()
