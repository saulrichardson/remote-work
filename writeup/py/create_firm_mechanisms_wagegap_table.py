#!/usr/bin/env python3

"""Create LaTeX table for firm-level wage-dispersion mechanism specs."""

from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPECNAME = "firm_mechanisms_wagegap"
INPUT_CSV = PROJECT_ROOT / "results" / "raw" / SPECNAME / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "firm_mechanisms_wagegap.tex"


SPEC_LIST = ["sd_wage", "gap", "sd_wage_gap"]
DIMENSIONS = ["sd_wage", "p90_p10_gap"]


def starify(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def main() -> None:
    df = pd.read_csv(INPUT_CSV)

    df["coef_str"] = df.apply(
        lambda r: f"{r.coef:.2f}{starify(r.pval)}" if r.param in ("var3", "var5") else f"{r.coef:.0f}",
        axis=1,
    )
    df["se_str"] = df.se.map(lambda s: f"({s:.2f})")

    df_iv = df[df.model_type == "IV"]
    df_ols = df[df.model_type == "OLS"]

    def to_panel(sub: pd.DataFrame):
        return {
            "coef": sub.pivot(index="param", columns="spec", values="coef_str"),
            "se": sub.pivot(index="param", columns="spec", values="se_str"),
        }

    panel = {"A": to_panel(df_ols), "B": to_panel(df_iv)}

    nobs_iv = df_iv.groupby("spec")["nobs"].first()
    nobs_ols = df_ols.groupby("spec")["nobs"].first()
    rkf_iv = df_iv.groupby("spec")["rkf"].first()

    # header check-marks
    check = {d: [] for d in DIMENSIONS}
    for spec in SPEC_LIST:
        check["sd_wage"].append("sd_wage" in spec)
        check["p90_p10_gap"].append("gap" in spec)

    lines: list[str] = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(r"\caption{Firm Scaling – Wage Dispersion Mechanisms}")
    lines.append(r"\begin{tabular}{l" + "c" * len(SPEC_LIST) + "}")
    lines.append(r"\toprule")

    lines.append(r" & \multicolumn{%d}{c}{Growth Rate} \\" % len(SPEC_LIST))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(SPEC_LIST) + 1))

    lines.append("Specification & " + " & ".join(f"({i})" for i in range(1, len(SPEC_LIST) + 1)) + r" \\")
    lines.append(r"\midrule")

    for dim in DIMENSIONS:
        marks = ["\\checkmark" if v else "" for v in check[dim]]
        lines.append(dim.replace("_", " ").title() + " & " + " & ".join(marks) + r" \\")
    lines.append(r"\midrule")

    for idx, (panel_id, model) in enumerate([("A", "OLS"), ("B", "IV")]):
        lines.append(r"\multicolumn{" + f"{len(SPEC_LIST)+1}" + r"}{l}{\textbf{\uline{Panel " + panel_id + ": " + model + r"}}} \\")
        lines.append(r"\addlinespace")

        for p in ("var3", "var5"):
            coefs = panel[panel_id]["coef"].loc[p, SPEC_LIST]
            ses = panel[panel_id]["se"].loc[p, SPEC_LIST]
            label = "$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) $" if p == "var3" else "$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) \\times \\text{Startup} $"
            lines.append(label + " & " + " & ".join(coefs) + r" \\")
            lines.append(" & " + " & ".join(ses) + r" \\")

        lines.append(r"\midrule")
        nvals = [f"{int(nobs_ols[s]):,}" if model == "OLS" else f"{int(nobs_iv[s]):,}" for s in SPEC_LIST]
        lines.append(r"N & " + " & ".join(nvals) + r" \\")

        if model == "IV":
            kvals = [f"{rkf_iv[s]:.2f}" for s in SPEC_LIST]
            lines.append(r"KP\,rk Wald F & " + " & ".join(kvals) + r" \\")

        if idx == 0:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\label{tab:firm_mechanisms_wagegap}")
    lines.append(r"\end{table}")

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")


if __name__ == "__main__":
    main()
