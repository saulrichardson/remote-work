#!/usr/bin/env python3
"""
Create a single PDF with baseline, both quadruple tests, and short explanations.

Usage:
  python py/format_user_mechanisms_quads_explained.py \
    --quad results/raw/user_mechanisms_quad_precovid/consolidated_results.csv \
    --mech results/raw/user_mechanisms_quad_precovid/consolidated_results_mechstyle.csv \
    --out results/cleaned
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


BASE_LABELS = {
    "var3": "Remote × Post",
    "var5": "Remote × Post × Startup",
}

REMOTE_LABELS = {
    "var3_M": "Remote × Post × M",
    "var5_M": "Remote × Post × Startup × M",
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
        "vacancy": "Vacancy (high, binary split)",
    }.get(mech, mech)
    if mech != "baseline" and variant and variant not in {"tile", "binary", "none"}:
        label = f"{label} – {variant}"
    return label


def build_panel(df: pd.DataFrame, mech: str, variant: str, rows: list[tuple[str, str]]) -> str:
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
    for key, label in rows:
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

    dfq = pd.read_csv(args.quad)
    dfm = pd.read_csv(args.mech)
    args.out.mkdir(parents=True, exist_ok=True)

    # Baseline
    baseline = build_panel(dfq, "baseline", "none", [("var3", BASE_LABELS["var3"]), ("var5", BASE_LABELS["var5"])])

    # Remote-anchored rows
    rem_rows = [("var3", BASE_LABELS["var3"]), ("var5", BASE_LABELS["var5"]), ("var3_M", REMOTE_LABELS["var3_M"]), ("var5_M", REMOTE_LABELS["var5_M"])]
    rem_sections = []
    for mech, var in [("rent", "tile"), ("hhi", "tile"), ("seniority4", "binary"), ("vacancy", "tile")]:
        sec = build_panel(dfq, mech, var, rem_rows)
        if sec:
            rem_sections.append(sec)

    # Post-anchored rows (canonical param names per mechanism)
    preferred = {
        "rent": ("var8", "var9", "Post × Rent", "Post × Startup × Rent"),
        "hhi": ("var11", "var12", "Post × HHI", "Post × Startup × HHI"),
        "seniority4": ("var14", "var15", "Post × Seniority4", "Post × Startup × Seniority4"),
        # Fall back to generic post_M/postSM but with clearer labels
        "vacancy": ("post_M", "postSM", "Post × Vacancy", "Post × Startup × Vacancy"),
    }
    mech_sections = []
    for mech, var in [("rent", "tile"), ("hhi", "tile"), ("seniority4", "binary"), ("vacancy", "tile")]:
        # Choose canonical names if available; fall back to post_M/postSM
        sub = dfm[(dfm["mechanism"] == mech) & (dfm["variant"] == var)]
        params = set(sub["param"].unique())
        p1p, p2p, l1p, l2p = preferred[mech]
        if p1p in params and p2p in params:
            p1, p2, l1, l2 = p1p, p2p, l1p, l2p
        else:
            p1, p2, l1, l2 = "post_M", "postSM", "Post × M", "Post × Startup × M"
        rows = [("var3", BASE_LABELS["var3"]), ("var5", BASE_LABELS["var5"]), (p1, l1), (p2, l2)]
        sec = build_panel(dfm, mech, var, rows)
        if sec:
            mech_sections.append(sec)

    doc = []
    doc.append("\\documentclass[11pt]{article}")
    doc.append("\\usepackage{booktabs}")
    doc.append("\\usepackage{amsmath}")
    doc.append("\\usepackage{float}")
    doc.append("\\usepackage[margin=1in]{geometry}")
    doc.append("\\title{Quadruple Tests with Explanations}")
    doc.append("\\date{\\today}")
    doc.append("\\begin{document}")
    doc.append("\\maketitle")

    # Overview
    doc.append("\\section*{Overview}")
    doc.append("This document shows two complementary tests of heterogeneity by a binary mechanism M (high vs low):")
    doc.append("(i) Remote-anchored: adds Remote × Post × M and Remote × Post × Startup × M to see how the remote channel's effect changes with M; these interaction terms are instrumented by teleworkability and its interaction with M.")
    doc.append("(ii) Post-anchored: adds Post × M and Post × Startup × M to capture non-remote post-COVID shifts correlated with M, while still instrumenting the remote terms as in baseline.")

    # (Removed the "How to Read the Tables" section per request)

    # Baseline
    doc.append("\\section*{Baseline}")
    if baseline:
        doc.append(baseline)

    # Remote-anchored
    doc.append("\\section*{Remote-Anchored Quadruple}")
    doc.append("Coefficients on Remote × Post × M and Remote × Post × Startup × M show how the average remote-in-post effect and the startup remote premium change with M.")
    for s in rem_sections:
        doc.append(s)

    # Post-anchored
    doc.append("\\section*{Post-Anchored Quadruple (Mechanism Style)}")
    doc.append("Coefficients on Post × M and Post × Startup × M show how post-COVID outcomes shift with M, while the remote terms remain instrumented as in baseline.")
    for s in mech_sections:
        doc.append(s)

    doc.append("\\end{document}")
    out_tex = args.out / "quads_explained.tex"
    out_tex.write_text("\n".join(doc))
    print("✓ Wrote explained LaTeX:", out_tex)


if __name__ == "__main__":
    main()
