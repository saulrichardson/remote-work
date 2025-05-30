#!/usr/bin/env python3
r"""Generate LaTeX tables for the user mechanism tests.

Reads results from `results/raw/user_mechanisms/` and breaks the
specification columns into blocks of 8 per table.  The resulting tables are
concatenated into a single `.tex` file so the paper can include them via
`\\input{}` once.
r"""

from pathlib import Path
import math
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPECNAME = "user_mechanisms"
INPUT_CSV = PROJECT_ROOT / "results" / "raw" / SPECNAME / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "user_mechanisms.tex"

COLS_PER_TABLE = 8

PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

DIMS = ["Rent", "HHI", "Seniority", "Wage"]


def starify(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def load_df():
    df = pd.read_csv(INPUT_CSV)
    df["coef_str"] = df.apply(
        lambda r: f"{r.coef:.2f}{starify(r.pval)}" if r.param in ("var3", "var5") else f"{r.coef:.0f}",
        axis=1,
    )
    df["se_str"] = df.se.map(lambda s: f"({s:.2f})")
    return df


def checks(specs):
    out = {d: [] for d in DIMS}
    for s in specs:
        low = s.lower()
        out["Rent"].append("rent" in low)
        out["HHI"].append("hhi" in low)
        out["Seniority"].append("seniority" in low)
        out["Wage"].append(any(k in low for k in ("sd_wage", "sdw", "wage", "gap")))
    return out


def panel(sub):
    return {
        "coef": sub.pivot(index="param", columns="spec", values="coef_str"),
        "se": sub.pivot(index="param", columns="spec", values="se_str"),
    }


def one_table(df_iv, df_ols, specs, idx):
    check = checks(specs)

    p_iv = panel(df_iv[df_iv.spec.isin(specs)])
    p_ols = panel(df_ols[df_ols.spec.isin(specs)])

    nobs_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["nobs"].first()
    nobs_ols = df_ols[df_ols.spec.isin(specs)].groupby("spec")["nobs"].first()
    rkf_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["rkf"].first()

    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(rf"\caption{{User Mechanisms (Part {idx})}}")
    lines.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
    lines.append(r"\toprule")

    lines.append(r" & \multicolumn{%d}{c}{Total Contrib. (pct. rk)} \\" % len(specs))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(specs) + 1))

    lines.append("Specification & " + " & ".join(f"({i})" for i in range(1, len(specs) + 1)) + r" \\")
    lines.append(r"\midrule")

    for dim in DIMS:
        marks = ["\\checkmark" if v else "" for v in check[dim]]
        lines.append(dim.replace("_", " ").title() + " & " + " & ".join(marks) + r" \\")
    lines.append(r"\midrule")

    for p_idx, (panel_id, model, pdata) in enumerate([("A", "OLS", p_ols), ("B", "IV", p_iv)]):
        lines.append(r"\multicolumn{%d}{l}{\textbf{\uline{Panel %s: %s}}} \\" % (len(specs)+1, panel_id, model))
        lines.append(r"\addlinespace")

        for param in ("var3", "var5"):
            coefs = pdata["coef"].loc[param, specs]
            ses = pdata["se"].loc[param, specs]
            lines.append(PARAM_LABELS[param] + " & " + " & ".join(coefs) + r" \\")
            lines.append(" & " + " & ".join(ses) + r" \\")

        lines.append(r"\midrule")
        nvals = [f"{int(nobs_ols[s]):,}" if model == "OLS" else f"{int(nobs_iv[s]):,}" for s in specs]
        lines.append(r"N & " + " & ".join(nvals) + r" \\")
        if model == "IV":
            kvals = [f"{rkf_iv[s]:.2f}" for s in specs]
            lines.append(r"KP\,rk Wald F & " + " & ".join(kvals) + r" \\")

        if p_idx == 0:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(rf"\label{{tab:user_mechanisms_{idx}}}")
    lines.append(r"\end{table}")
    return lines


def main():
    df = load_df()
    df_iv = df[df.model_type == "IV"].copy()
    df_ols = df[df.model_type == "OLS"].copy()

    spec_order = df["spec"].drop_duplicates().tolist()
    tables_needed = math.ceil(len(spec_order) / COLS_PER_TABLE)

    lines: list[str] = []
    for i in range(tables_needed):
        chunk = spec_order[i * COLS_PER_TABLE : (i + 1) * COLS_PER_TABLE]
        lines.extend(one_table(df_iv, df_ols, chunk, idx=i + 1))
        lines.append("")

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_TEX}")


if __name__ == "__main__":
    main()
