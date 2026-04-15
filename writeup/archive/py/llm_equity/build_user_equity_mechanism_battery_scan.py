#!/usr/bin/env python3
"""Scan the user-productivity equity mechanism *battery* for attenuation of var5.

This script is intentionally diagnostic:
  - It ranks specifications by how much they attenuate the baseline IV `var5`
    (Remote × Post × Startup) coefficient within each sample mode.
  - It writes a tidy CSV with baseline + deltas.
  - It optionally writes a small LaTeX snippet listing the top-N attenuating
    specs per sample mode (for quick inclusion in notes).

Assumptions / conventions
-------------------------
- The underlying Stata spec uses the repo convention "backfill = 0" (missing/
  unobserved equity measures coded as 0).
- "Attenuation" is defined as a *reduction in magnitude* of the IV var5 point
  estimate relative to the baseline within the same sample_mode.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file

PRIMARY_OUTCOME: Final[str] = "total_contributions_q100"
PRIMARY_PARAM: Final[str] = "var5"
PRIMARY_MODEL: Final[str] = "IV"
BASELINE_KEY: Final[str] = "baseline"

STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cutoff, mark in STAR_RULES:
        if p < cutoff:
            return mark
    return ""


def fmt_num(x: float) -> str:
    ax = abs(x)
    if ax >= 1e4 or (0 < ax < 1e-2):
        return f"{x:.2e}"
    return f"{x:.2f}"


def coef_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{fmt_num(coef)}{stars(pval)}\\({fmt_num(se)})}}"


@dataclass(frozen=True)
class ScanConfig:
    panel_variant: str
    input_csv: Path
    out_csv: Path
    out_tex: Path | None
    top_n: int


def parse_args() -> ScanConfig:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel-variant", default="precovid", help="User panel variant (default: precovid).")
    p.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help="Path to consolidated_results.csv (defaults to the battery output for --panel-variant).",
    )
    p.add_argument(
        "--out-csv",
        type=Path,
        default=None,
        help="Output CSV path (defaults to <raw_results_dir>/var5_attenuation_scan.csv).",
    )
    p.add_argument(
        "--out-tex",
        type=Path,
        default=None,
        help="Optional LaTeX snippet path (defaults to results/cleaned/tex/llm_equity_user_battery_top.tex).",
    )
    p.add_argument("--top-n", type=int, default=10, help="Top-N attenuating variants per sample_mode.")
    args = p.parse_args()

    panel_variant = str(args.panel_variant)
    default_dir = RESULTS_RAW / f"user_productivity_llm_equity_mechanism_battery_{panel_variant}"
    input_csv = args.input_csv or (default_dir / "consolidated_results.csv")
    out_csv = args.out_csv or (default_dir / "var5_attenuation_scan.csv")
    out_tex = args.out_tex
    if out_tex is None:
        out_tex = RESULTS_CLEANED_TEX / "llm_equity_user_battery_top.tex"

    return ScanConfig(
        panel_variant=panel_variant,
        input_csv=input_csv,
        out_csv=out_csv,
        out_tex=out_tex,
        top_n=int(args.top_n),
    )


def build_scan_frame(df: pd.DataFrame) -> pd.DataFrame:
    need = {
        "model_type",
        "sample_mode",
        "spec_variant",
        "outcome",
        "param",
        "coef",
        "se",
        "pval",
        "rkf",
        "nobs",
    }
    missing = need.difference(df.columns)
    if missing:
        raise RuntimeError(f"Input is missing required columns: {sorted(missing)}")

    work = df.copy()
    work = work[(work["outcome"] == PRIMARY_OUTCOME) & (work["param"] == PRIMARY_PARAM)].copy()
    if work.empty:
        raise RuntimeError(f"No rows for outcome={PRIMARY_OUTCOME} param={PRIMARY_PARAM}")

    # Baseline per (sample_mode, model_type)
    base = work[work["spec_variant"] == BASELINE_KEY][
        ["sample_mode", "model_type", "coef", "se", "pval", "rkf", "nobs"]
    ].rename(
        columns={
            "coef": "baseline_coef",
            "se": "baseline_se",
            "pval": "baseline_pval",
            "rkf": "baseline_rkf",
            "nobs": "baseline_nobs",
        }
    )
    if base.empty:
        raise RuntimeError(f"Missing baseline rows (spec_variant={BASELINE_KEY})")

    merged = work.merge(base, on=["sample_mode", "model_type"], how="left", validate="m:1")
    if merged["baseline_coef"].isna().any():
        bad = merged.loc[merged["baseline_coef"].isna(), ["sample_mode", "model_type"]].drop_duplicates()
        raise RuntimeError(f"Unable to attach baseline rows for: {bad.to_dict(orient='records')}")

    merged["delta_coef"] = merged["coef"] - merged["baseline_coef"]
    merged["pct_change"] = (merged["coef"] / merged["baseline_coef"] - 1.0) * 100.0
    # "attenuation" = negative pct change when baseline > 0; keep sign as-is.
    return merged


def build_latex_top(df_scan: pd.DataFrame, *, top_n: int) -> str:
    lines: list[str] = []
    lines.append(r"{\centering")
    lines.append(r"\begin{tabular*}{\linewidth}{@{}l@{\extracolsep{\fill}}lcccc@{}}")
    lines.append(r"\toprule")
    lines.append(r"Sample & Spec Variant & IV var5 & $\Delta$ vs. baseline & \% change & $p$-value & N \\")
    lines.append(r"\midrule")

    df_iv = df_scan[df_scan["model_type"] == PRIMARY_MODEL].copy()
    for sample_mode, g in df_iv.groupby("sample_mode", sort=True):
        g = g[g["spec_variant"] != BASELINE_KEY].copy()
        g = g.sort_values(["pct_change", "pval"], ascending=[True, True]).head(top_n)
        if g.empty:
            continue
        lines.append(rf"\multicolumn{{7}}{{@{{}}l}}{{\textbf{{{sample_mode}}}}} \\")
        for _, r in g.iterrows():
            coef = float(r["coef"])
            se = float(r["se"])
            pval = float(r["pval"]) if pd.notna(r["pval"]) else 1.0
            delta = float(r["delta_coef"])
            pct = float(r["pct_change"])
            nobs = int(r["nobs"]) if pd.notna(r["nobs"]) else 0
            spec = str(r["spec_variant"])
            lines.append(
                " & ".join(
                    [
                        "",
                        spec.replace("_", r"\_"),
                        coef_cell(coef, se, pval),
                        fmt_num(delta),
                        f"{pct:.2f}",
                        f"{pval:.3f}",
                        f"{nobs:,}",
                    ]
                )
                + r" \\"
            )
        lines.append(r"\addlinespace[4pt]")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")
    lines.append(r"}")
    return "\n".join(lines) + "\n"


def main() -> None:
    cfg = parse_args()
    ensure_dir(cfg.out_csv.parent)
    ensure_dir(RESULTS_CLEANED_TEX)

    df = pd.read_csv(require_file(cfg.input_csv, nonempty=True, purpose="battery consolidated_results.csv"))
    scan = build_scan_frame(df)
    scan.to_csv(cfg.out_csv, index=False)
    print(f"Wrote {cfg.out_csv}")

    if cfg.out_tex is not None:
        tex = build_latex_top(scan, top_n=cfg.top_n)
        cfg.out_tex.write_text(tex, encoding="utf-8")
        print(f"Wrote {cfg.out_tex}")


if __name__ == "__main__":
    main()

