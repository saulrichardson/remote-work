#!/usr/bin/env python3
"""
Read consolidated results from user_mechanisms_quad.do and emit LaTeX tables.

Usage:
  python py/format_user_mechanisms_quad.py \
    results/raw/user_mechanisms_quad_precovid/consolidated_results.csv \
    --out results/cleaned

Outputs one table per (mechanism, variant), with OLS and IV panels and rows:
  - Remote × Post (var3)
  - Remote × Post × Startup (var5)
  - Remote × Post × M (var3_M)
  - Remote × Post × Startup × M (var5_M)
Also writes a small combined summary for var5_M across mechanisms.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


PARAM_LABELS = {
    "var3": r"Remote $\times$ Post",
    "var5": r"Remote $\times$ Post $\times$ Startup",
    "var3_M": r"Remote $\times$ Post $\times$ M",
    "var5_M": r"Remote $\times$ Post $\times$ Startup $\times$ M",
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
    s = stars(p)
    return f"{b:.3f}{s}"


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
    rows = [
        ("var3", PARAM_LABELS["var3"]),
        ("var5", PARAM_LABELS["var5"]),
        ("var3_M", PARAM_LABELS["var3_M"]),
        ("var5_M", PARAM_LABELS["var5_M"]),
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
    lines.append(f"\\caption{{Quadruple Mechanism: {mechanism_title(mech, variant)} }}")
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


def build_summary(df: pd.DataFrame) -> str:
    pref = {
        "rent": "tile",
        "hhi": "tile",
        "seniority4": "binary",
        "vacancy_size": "hi_median",
    }
    entries = []
    for mech, variant in pref.items():
        sub = df[(df["mechanism"] == mech) & (df["variant"] == variant) & (df["model_type"] == "IV") & (df["param"] == "var5_M")]
        if sub.empty:
            continue
        r = sub.iloc[0]
        entries.append((mech, variant, r["coef"], r["se"], r["pval"]))
    if not entries:
        return ""
    lines: list[str] = []
    lines.append("\\begin{table}[H]")
    lines.append("\\centering")
    lines.append("\\caption{Quadruple Effect (IV): Startup-specific moderation by mechanism}")
    lines.append("\\begin{tabular}{lc}")
    lines.append("\\toprule")
    lines.append(r"Mechanism & $\beta_{\text{Remote}\times\text{Post}\times\text{Startup}\times M}$ \\\\")
    lines.append("\\midrule")
    for mech, variant, b, se, p in entries:
        label = mechanism_title(mech, variant)
        lines.append(f"{label} & {fmt_coef(b, p)} \\\\")
        lines.append(f" & {fmt_se(se)} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path, help="Path to consolidated_results.csv from Stata")
    ap.add_argument("--out", type=Path, default=Path("results/cleaned"))
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    args.out.mkdir(parents=True, exist_ok=True)

    mechanisms = sorted(df["mechanism"].dropna().unique())
    for mech in mechanisms:
        variants = sorted(df.loc[df["mechanism"] == mech, "variant"].dropna().unique())
        for variant in variants:
            tex = build_table(df, mech, variant)
            if tex:
                out_path = args.out / f"quad_{mech}_{variant}.tex"
                out_path.write_text(tex)

    summ = build_summary(df)
    if summ:
        (args.out / "quad_summary.tex").write_text(summ)

    # Build a single consolidated LaTeX document with preferred variants only
    preferred = [
        ("baseline", "none"),
        ("rent", "tile"),
        ("hhi", "tile"),
        ("seniority4", "binary"),
    ]
    sections = []
    for mech, variant in preferred:
        t = build_table(df, mech, variant)
        if t:
            sections.append(t)
    if sections:
        doc = []
        doc.append("\\documentclass[11pt]{article}")
        doc.append("\\usepackage{booktabs}")
        doc.append("\\usepackage{float}")
        doc.append("\\usepackage[margin=1in]{geometry}")
        doc.append("\\title{Quadruple Mechanisms (Preferred Variants)}")
        doc.append("\\date{\\today}")
        doc.append("\\begin{document}")
        doc.append("\\maketitle")
        doc.extend(sections)
        # (omit summary table from consolidated PDF)
        doc.append("\\end{document}")
        (args.out / "quad_all.tex").write_text("\n".join(doc))
        print("✓ Wrote consolidated LaTeX: ", args.out / "quad_all.tex")

    print(f"✓ Wrote LaTeX tables to {args.out}")


if __name__ == "__main__":
    main()
