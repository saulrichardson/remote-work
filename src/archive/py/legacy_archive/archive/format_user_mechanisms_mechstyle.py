#!/usr/bin/env python3
"""
Format mechanism-tests style results (Post×M, Post×Startup×M) from
spec/user_mechanisms_quad.do into LaTeX tables and a consolidated PDF-ready .tex.

Usage:
  python py/format_user_mechanisms_mechstyle.py \
    results/raw/user_mechanisms_quad_precovid/consolidated_results_mechstyle.csv \
    --out results/cleaned
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


PARAM_LABELS = {
    "var3": "Remote × Post",
    "var5": "Remote × Post × Startup",
    "post_M": "Post × M",
    "postSM": "Post × Startup × M",
}


def stars(p: float | None) -> str:
    if p is None or pd.isna(p):
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def fmt_coef(b: float, p: float | None) -> str:
    return f"{b:.3f}{stars(p)}"


def fmt_se(se: float) -> str:
    return f"({se:.3f})"


def mechanism_title(mech: str, variant: str) -> str:
    label = {
        "rent": "Rent (high, binary split)",
        "hhi": "HHI (high, binary split)",
        "seniority4": "Seniority L4+ (binary)",
        "vacancy_size": "Vacancy per Size",
    }.get(mech, mech)
    if variant and variant not in {"tile", "binary"}:
        label = f"{label} – {variant}"
    return label


def build_table(df: pd.DataFrame, mech: str, variant: str) -> str:
    sub = df[(df["mechanism"] == mech) & (df["variant"] == variant)]
    if sub.empty:
        return ""
    BASE_LABELS = {
        "var3": "Remote × Post",
        "var5": "Remote × Post × Startup",
    }
    # Prefer canonical var names; fall back to post_M/postSM if needed
    preferred = {
        "rent": ("var8", "var9", "Post × Rent", "Post × Startup × Rent"),
        "hhi": ("var11", "var12", "Post × HHI", "Post × Startup × HHI"),
        "seniority4": ("var14", "var15", "Post × Seniority4", "Post × Startup × Seniority4"),
    }
    p1p, p2p, l1p, l2p = preferred.get(mech, ("post_M", "postSM", "Post × M", "Post × Startup × M"))
    params_available = set(sub["param"].unique())
    if p1p in params_available and p2p in params_available:
        p1, p2, l1, l2 = p1p, p2p, l1p, l2p
    else:
        p1, p2, l1, l2 = "post_M", "postSM", "Post × M", "Post × Startup × M"
    rows = [
        ("var3", BASE_LABELS["var3"]),
        ("var5", BASE_LABELS["var5"]),
        (p1, l1),
        (p2, l2),
    ]

    def extract(mt: str, param: str):
        r = sub[(sub["model_type"] == mt) & (sub["param"] == param)]
        if r.empty:
            return None
        r = r.iloc[0]
        return fmt_coef(r["coef"], r.get("pval")), fmt_se(r["se"])  # type: ignore[index]

    iv = sub[sub["model_type"] == "IV"].head(1)
    N = int(iv["nobs"].iloc[0]) if not iv.empty else None
    rkf = float(iv["rkf"].iloc[0]) if (not iv.empty and pd.notna(iv["rkf"].iloc[0])) else None

    lines: list[str] = []
    lines.append("\\begin{table}[H]")
    lines.append("\\centering")
    lines.append(f"\\caption{{Mechanism Tests: {mechanism_title(mech, variant)} }}")
    lines.append("\\begin{tabular}{lcc}")
    lines.append("\\toprule")
    lines.append(" & OLS & IV \\\\")
    lines.append("\\midrule")
    for key, label in rows:
        ols_vals = extract("OLS", key)
        iv_vals = extract("IV", key)
        if ols_vals is None and iv_vals is None:
            continue
        ols_coef, ols_se = ols_vals if ols_vals else ("", "")
        iv_coef, iv_se = iv_vals if iv_vals else ("", "")
        lines.append(f"{label} & {ols_coef} & {iv_coef} \\\\")
        lines.append(f" & {ols_se} & {iv_se} \\\\")
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
    ap.add_argument("csv", type=Path)
    ap.add_argument("--out", type=Path, default=Path("results/cleaned"))
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    args.out.mkdir(parents=True, exist_ok=True)

    preferred = [
        ("rent", "tile"),
        ("hhi", "tile"),
        ("seniority4", "binary"),
        ("vacancy_size", "hi_median"),
    ]
    sections = []
    for mech, variant in preferred:
        t = build_table(df, mech, variant)
        if t:
            sections.append(t)
            (args.out / f"mech_{mech}_{variant}.tex").write_text(t)

    if sections:
        doc = []
        doc.append("\\documentclass[11pt]{article}")
        doc.append("\\usepackage{booktabs}")
        doc.append("\\usepackage{float}")
        doc.append("\\usepackage[margin=1in]{geometry}")
        doc.append("\\title{Mechanism Tests (Post×M, Post×Startup×M)}")
        doc.append("\\date{\\today}")
        doc.append("\\begin{document}")
        doc.append("\\maketitle")
        doc.extend(sections)
        doc.append("\\end{document}")
        (args.out / "mech_all.tex").write_text("\n".join(doc))
        print("✓ Wrote consolidated mechanism LaTeX:", args.out / "mech_all.tex")


if __name__ == "__main__":
    main()
