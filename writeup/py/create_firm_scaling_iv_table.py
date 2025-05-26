#!/usr/bin/env python3
"""Generate a two-panel IV table for the Firm-Scaling specification."""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPEC = "firm_scaling"
RAW_DIR = PROJECT_ROOT / "results" / "raw"
INPUT_BASE = RAW_DIR / SPEC / "consolidated_results.csv"
INPUT_ALT = RAW_DIR / f"{SPEC}_alternative_fe" / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"{SPEC}_iv.tex"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

OUTCOME_LABEL = {
    "growth_rate_we": "Growth",
    "join_rate_we": "Join",
    "leave_rate_we": "Leave",
}

TAG_ORDER = ["none", "firm", "time", "fyh"]
COL_LABELS = ["(1)", "(2)", "(3)", "(4)"]
N_COLS = max(len(TAG_ORDER), len(OUTCOME_LABEL))

FIRM_FE_INCLUDED = {"fyh": True, "time": False, "firm": True, "none": False}
TIME_FE_INCLUDED = {"fyh": True, "time": True, "firm": False, "none": False}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
TABLE_WIDTH = r"\textwidth"


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def row(cells: list[str]) -> str:
    padded = cells + ["" for _ in range((1 + N_COLS) - len(cells))]
    return " & ".join(padded) + r" \\"


def indicator_row(label: str, mapping: dict[str, bool]) -> str:
    checks = [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in TAG_ORDER]
    return row([label] + checks)


def build_obs_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    cells = ["N"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k))
        n = int(sub.iloc[0]["nobs"]) if not sub.empty else 0
        cells.append(f"{n:,}")
    return row(cells)


def build_kp_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    cells = ["KP rk Wald F"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k)).head(1)
        val = sub.iloc[0]["rkf"] if not sub.empty else float("nan")
        cells.append(f"{val:.2f}" if pd.notna(val) else "")
    return row(cells)


def build_panel_fe(df: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    lines.append(row([rf"\multicolumn{{{1 + len(TAG_ORDER)}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: FE Variants}}}}}}"]))
    lines.append(r"\addlinespace")
    lines.append(row(["", rf"\multicolumn{{{len(TAG_ORDER)}}}{{c}}{{Growth}}"]))
    lines.append(rf"\cmidrule(lr){{2-{len(TAG_ORDER)+1}}}")
    lines.append(row([""] + COL_LABELS))
    lines.append(MID)
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for tag in TAG_ORDER:
            sub = df.query("model_type=='IV' and outcome=='growth_rate_we' and fe_tag==@tag and param==@param")
            cells.append(cell(*sub.iloc[0][['coef','se','pval']]) if not sub.empty else "")
        lines.append(row(cells))
    lines.append(MID)
    lines.append(indicator_row("Time FE", TIME_FE_INCLUDED))
    lines.append(indicator_row("Firm FE", FIRM_FE_INCLUDED))
    lines.append(MID)
    lines.append(build_obs_row(df, TAG_ORDER, filter_expr="model_type=='IV' and outcome=='growth_rate_we' and fe_tag=='{k}'"))
    lines.append(build_kp_row(df, TAG_ORDER, filter_expr="model_type=='IV' and outcome=='growth_rate_we' and fe_tag=='{k}'"))
    return lines


def build_panel_base(df: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    lines.append(row([rf"\multicolumn{{{1 + len(OUTCOME_LABEL)}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: Base Specification}}}}}}"]))
    lines.append(r"\addlinespace")
    lines.append(row(["", rf"\multicolumn{{{len(OUTCOME_LABEL)}}}{{c}}{{Outcome}}"]))
    lines.append(rf"\cmidrule(lr){{2-{len(OUTCOME_LABEL)+1}}}")
    lines.append(row([""] + [OUTCOME_LABEL[o] for o in OUTCOME_LABEL]))
    lines.append(MID)
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for out in OUTCOME_LABEL:
            sub = df.query("model_type=='IV' and outcome==@out and param==@param")
            cells.append(cell(*sub.iloc[0][['coef','se','pval']]) if not sub.empty else "")
        lines.append(row(cells))
    lines.append(MID)
    lines.append(build_obs_row(df, list(OUTCOME_LABEL), filter_expr="model_type=='IV' and outcome=='{k}'"))
    lines.append(build_kp_row(df, list(OUTCOME_LABEL), filter_expr="model_type=='IV' and outcome=='{k}'"))
    return lines


def main() -> None:
    if not INPUT_BASE.exists():
        raise FileNotFoundError(INPUT_BASE)
    if not INPUT_ALT.exists():
        raise FileNotFoundError(INPUT_ALT)

    df_base = pd.read_csv(INPUT_BASE)
    df_alt = pd.read_csv(INPUT_ALT)

    col_fmt = r"@{}l@{\extracolsep{\fill}}" + "c" * N_COLS + r"@{}"

    lines: list[str] = []
    lines.append("% --------------------------------------------------------------")
    lines.append("%  Firm-Scaling: Two-panel IV results")
    lines.append("% --------------------------------------------------------------")
    lines.append("")
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(r"\caption{Firm Scaling IV}")
    lines.append(r"\label{tab:firm_scaling_iv}")
    lines.append(rf"\begin{{tabular*}}{{{TABLE_WIDTH}}}{{{col_fmt}}}")
    lines.append(TOP)
    lines.extend(build_panel_fe(df_alt))
    lines.append(r"\addlinespace")
    lines.extend(build_panel_base(df_base))
    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    lines.append(r"\end{table}")

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX.write_text("\n".join(lines) + "\n")
    print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")


if __name__ == "__main__":
    main()
