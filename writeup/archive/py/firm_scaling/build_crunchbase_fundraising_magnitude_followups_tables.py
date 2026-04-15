#!/usr/bin/env python3
"""Build TeX tables for PI follow-ups on Crunchbase fundraising magnitudes.

This script formats the Stata outputs produced by:
  - spec/stata/firm_scaling_crunchbase_fundraising_prepost.do
  - spec/stata/firm_scaling_crunchbase_fundraising_magnitude.do

Writes:
  - results/cleaned/tex/firm_scaling_crunchbase_fundraising_prepost.tex
  - results/cleaned/tex/firm_scaling_crunchbase_fundraising_magnitude_followups.tex
  - results/cleaned/tex/firm_scaling_crunchbase_fundraising_prior_significant.tex
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))
SCRIPTS_DIR = HERE.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore
from user_productivity.build_baseline_table import (  # type: ignore
    PREAMBLE_FLEX,
    STAR_RULES,
    TOP,
    MID,
    BOTTOM,
)


LB = r" \\"
INDENT = r"\hspace{1em}"

RAW_PREPOST_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_prepost"
RAW_PREPOST = RAW_PREPOST_DIR / "consolidated_results.csv"

RAW_MAG_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_magnitude"
RAW_MAG = RAW_MAG_DIR / "consolidated_results.csv"
RAW_MAG_DIAG = RAW_MAG_DIR / "outcome_diagnostics.csv"

OUT_PREPOST = RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_prepost.tex"
OUT_MAG = RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_magnitude_followups.tex"

RAW_PURE_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_pure"
RAW_PURE = RAW_PURE_DIR / "consolidated_results.csv"

OUT_PRIOR = RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_prior_significant.tex"


VAR3 = "var3"
VAR3_LABEL = r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"


def column_format_padded(n_numeric: int) -> str:
    return "l" + (r"@{\extracolsep{\fill}}c" * n_numeric)


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def _require_columns(df: pd.DataFrame, path: Path, required: set[str]) -> None:
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns {sorted(missing)} in {path}.")


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}.")
    return pd.read_csv(path)


def _pick(
    df: pd.DataFrame,
    *,
    outcome: str,
    model: str,
    param: str,
    sample_tag: str,
    spec_tag: str | None = None,
) -> pd.Series | None:
    sub = df[(df["sample_tag"] == sample_tag) & (df["outcome"] == outcome) & (df["model_type"] == model) & (df["param"] == param)]
    if spec_tag is not None:
        sub = sub[sub["spec_tag"] == spec_tag]
    sub = sub.head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


def _format_num(x: float, *, decimals: int) -> str:
    if abs(x) < 0.5 * (10 ** (-decimals)):
        x = 0.0
    return f"{x:.{decimals}f}"


def coef_cell(
    rec: pd.Series | None,
    *,
    outcome: str,
    decimals: int = 3,
    dollars_in_millions: bool = False,
) -> str:
    if rec is None:
        return "--"
    coef = rec.get("coef")
    se = rec.get("se")
    pval = rec.get("pval")
    if pd.isna(coef) or pd.isna(se) or pd.isna(pval) or float(se) == 0:
        return r"\makecell[c]{\textit{omitted}}"
    coef_f = float(coef)
    se_f = float(se)
    p_f = float(pval)

    if dollars_in_millions:
        coef_f /= 1e6
        se_f /= 1e6
        decimals = max(2, decimals)

    return rf"\makecell[c]{{{_format_num(coef_f, decimals=decimals)}{stars(p_f)}\\({_format_num(se_f, decimals=decimals)})}}"


def _fmt_scalar(x: float | None, *, decimals: int = 2) -> str:
    if x is None or pd.isna(x):
        return ""
    return _format_num(float(x), decimals=decimals)


def build_prepost_table(prepost: pd.DataFrame) -> str:
    _require_columns(
        prepost,
        RAW_PREPOST,
        {"sample_tag", "outcome", "model_type", "param", "coef", "se", "pval", "pre_mean", "rkf", "partialF", "nobs"},
    )

    sample = "matched_private"
    outcomes = [
        ("cb_sum_raised_usd", r"\makecell[c]{Sum USD\\(mil)}"),
        ("cb_avg_raised_usd", r"\makecell[c]{Avg USD/half-year\\(mil)}"),
    ]

    ncols = len(outcomes)
    headers = [""] + [lbl for _, lbl in outcomes]

    def _row(model: str, param: str, label: str) -> None:
        cells = [INDENT + label]
        for out, _ in outcomes:
            rec = _pick(prepost, outcome=out, model=model, param=param, sample_tag=sample)
            cells.append(coef_cell(rec, outcome=out, decimals=2, dollars_in_millions=True))
        lines.append(" & ".join(cells) + LB)

    # Summary stats: use first outcome record (same nobs across outcomes here)
    rec_ols = _pick(prepost, outcome=outcomes[0][0], model="OLS", param=VAR3, sample_tag=sample)
    nobs = None if rec_ols is None else rec_ols.get("nobs")
    nobs_i = None if nobs is None or pd.isna(nobs) else int(nobs)
    # In this collapsed design, usable observations come in firm×{pre,post} pairs
    nfirms_i = None if nobs_i is None else int(nobs_i // 2)

    # pre means per outcome
    pre_means: list[str] = []
    for out, _ in outcomes:
        rec = _pick(prepost, outcome=out, model="OLS", param=VAR3, sample_tag=sample)
        pm = None if rec is None else rec.get("pre_mean")
        pre_means.append(_fmt_scalar(None if pm is None or pd.isna(pm) else float(pm) / 1e6, decimals=2))

    # rkf per outcome (IV)
    rkf_vals: list[str] = []
    for out, _ in outcomes:
        rec = _pick(prepost, outcome=out, model="IV", param=VAR3, sample_tag=sample)
        rkf = None if rec is None else rec.get("rkf")
        rkf_vals.append(_fmt_scalar(None if rkf is None or pd.isna(rkf) else float(rkf), decimals=2))

    lines: list[str] = [
        PREAMBLE_FLEX + r"\small" + "\n",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(ncols)}}}",
        TOP,
        " & ".join(headers) + LB,
        r"\cmidrule(lr){2-" + f"{ncols + 1}" + r"}",
        " & " + " & ".join([f"({i})" for i in range(1, ncols + 1)]) + LB,
        MID,
        rf"\multicolumn{{{ncols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} {LB}",
        r"\addlinespace[2pt]",
    ]

    _row("OLS", VAR3, VAR3_LABEL)

    lines.extend(
        [
            MID,
            rf"\multicolumn{{{ncols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} {LB}",
            r"\addlinespace[2pt]",
        ]
    )
    _row("IV", VAR3, VAR3_LABEL)

    # Summary rows
    lines.append(MID)
    lines.append(" & ".join(["Pre-Covid Mean (mil)", *pre_means]) + LB)
    lines.append(" & ".join(["KP rk Wald F", *rkf_vals]) + LB)
    lines.append(" & ".join(["N (obs)", *([f"{nobs_i:,}" if nobs_i is not None else ""] * ncols)]) + LB)
    lines.append(" & ".join(["N (firms)", *([f"{nfirms_i:,}" if nfirms_i is not None else ""] * ncols)]) + LB)

    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def build_magnitude_followups_table(mag: pd.DataFrame, diag: pd.DataFrame) -> str:
    _require_columns(
        mag,
        RAW_MAG,
        {"sample_tag", "spec_tag", "model_type", "outcome", "param", "coef", "se", "pval", "pre_mean", "rkf", "partialF", "nobs"},
    )
    _require_columns(
        diag,
        RAW_MAG_DIAG,
        {"sample_tag", "spec_tag", "outcome", "mean_pre"},
    )

    sample = "matched_private"
    columns: list[tuple[str, str]] = [
        ("baseline", "Baseline"),
        ("baseline_pos_usd_only", r"\makecell[c]{Baseline\\USD$>0$}"),
        ("age_lt20", r"Age$<20$"),
        ("age_lt20_pos_usd_only", r"\makecell[c]{Age$<20$\\USD$>0$}"),
        ("age_lt10", r"Age$<10$"),
        ("age_lt10_pos_usd_only", r"\makecell[c]{Age$<10$\\USD$>0$}"),
        ("hq_ca_ny", r"\makecell[c]{HQ in\\CA/NY}"),
        ("hq_outside_ca_ny", r"\makecell[c]{HQ outside\\CA/NY}"),
    ]

    outcomes: list[tuple[str, str, dict]] = [
        # outcome, display label (used as a section header), formatting
        ("cb_any_raised", r"Any USD raised, USD$>0$", {"decimals": 3, "mil": False, "mean_decimals": 3}),
        ("cb_raised_usd", "USD raised", {"decimals": 2, "mil": True, "mean_decimals": 2}),
        ("cb_log_raised_usd", r"$\log(\mathrm{USD\ raised})$", {"decimals": 3, "mil": False, "mean_decimals": 3}),
        ("cb_raised_usd_q100", "USD raised percentile rank", {"decimals": 3, "mil": False, "mean_decimals": 2}),
    ]

    ncols = len(columns)
    headers = [""] + [lbl for _, lbl in columns]

    def _outcome_header(label: str) -> None:
        lines.append(r"\addlinespace[3pt]")
        # Use \boldmath so math-mode labels (e.g. $\log(\cdot)$) are visibly bold.
        lines.append(rf"\multicolumn{{{ncols + 1}}}{{@{{}}l}}{{{{\bfseries\boldmath {label}}}}} {LB}")
        lines.append(r"\addlinespace[1pt]")

    def _term_row(model: str, outcome: str, *, decimals: int, mil: bool) -> None:
        # Keep the first column as the *term* (what users expect in this project),
        # not the outcome name. Outcome names are rendered as section headers above.
        prefix = "OLS:" if model == "OLS" else "IV:"
        label = rf"{prefix} {VAR3_LABEL}"
        cells = [INDENT + label]
        for spec, _ in columns:
            rec = _pick(mag, outcome=outcome, model=model, param=VAR3, sample_tag=sample, spec_tag=spec)
            cells.append(coef_cell(rec, outcome=outcome, decimals=decimals, dollars_in_millions=mil))
        lines.append(" & ".join(cells) + LB)

    def _diag_val(spec: str, outcome: str, field: str) -> float | None:
        sub = diag[(diag["sample_tag"] == sample) & (diag["spec_tag"] == spec) & (diag["outcome"] == outcome)].head(1)
        if sub.empty:
            return None
        val = sub.iloc[0].get(field)
        if pd.isna(val):
            return None
        return float(val)

    def _pre_mean_row(outcome: str, *, mean_decimals: int, mil: bool) -> None:
        cells = [INDENT + "Pre-Covid mean"]
        for spec, _ in columns:
            mean_pre = _diag_val(spec, outcome, "mean_pre")
            if mean_pre is None:
                cells.append("")
                continue
            val = float(mean_pre)
            if mil:
                val /= 1e6
            cells.append(_format_num(val, decimals=mean_decimals))
        lines.append(" & ".join(cells) + LB)

    # Summary rows for cb_raised_usd only (zeros + scale diagnostics)
    def _nobs_for(spec: str, *, model: str = "OLS") -> int | None:
        rec = _pick(mag, outcome="cb_raised_usd", model=model, param=VAR3, sample_tag=sample, spec_tag=spec)
        if rec is None:
            return None
        n = rec.get("nobs")
        if pd.isna(n):
            return None
        return int(n)

    def _first_stage_f_for(spec: str) -> float | None:
        rec = _pick(mag, outcome="cb_raised_usd", model="IV", param=VAR3, sample_tag=sample, spec_tag=spec)
        if rec is None:
            return None
        f = rec.get("partialF")
        if pd.isna(f):
            return None
        return float(f)

    lines: list[str] = [
        PREAMBLE_FLEX + r"\scriptsize" + "\n",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(ncols)}}}",
        TOP,
        " & ".join(headers) + LB,
        MID,
    ]

    for out, label, fmt in outcomes:
        _outcome_header(label)
        _term_row("OLS", out, decimals=int(fmt["decimals"]), mil=bool(fmt["mil"]))
        _term_row("IV", out, decimals=int(fmt["decimals"]), mil=bool(fmt["mil"]))
        _pre_mean_row(out, mean_decimals=int(fmt["mean_decimals"]), mil=bool(fmt["mil"]))

    # Footer diagnostics (for cb_raised_usd).
    nobs_cells = ["N (obs, USD)"]
    f_cells = ["First-stage F (USD)"]
    for spec, _ in columns:
        nobs = _nobs_for(spec, model="OLS")
        f = _first_stage_f_for(spec)
        nobs_cells.append(f"{nobs:,}" if nobs is not None else "")
        f_cells.append(_fmt_scalar(f, decimals=2) if f is not None else "")

    lines.append(MID)
    lines.append(" & ".join(nobs_cells) + LB)
    lines.append(" & ".join(f_cells) + LB)

    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def build_prior_significant_table(
    *,
    pure: pd.DataFrame,
    mag: pd.DataFrame,
    diag: pd.DataFrame,
) -> str:
    """Appendix table: previously significant outcomes under the *same* restrictions as the main half-year table.

    The outcomes are selected from the baseline pure spec (results/raw/..._pure/),
    but coefficients are pulled from the half-year restriction runs (results/raw/..._magnitude/),
    i.e. the same column set as the main follow-up table:
      baseline, baseline_pos_usd_only, age_lt20, age_lt20_pos_usd_only, age_lt10, age_lt10_pos_usd_only.
    """
    _require_columns(
        pure,
        RAW_PURE,
        {"sample_tag", "model_type", "outcome", "param", "coef", "se", "pval"},
    )
    _require_columns(
        mag,
        RAW_MAG,
        {"sample_tag", "spec_tag", "model_type", "outcome", "param", "coef", "se", "pval", "partialF", "nobs"},
    )
    _require_columns(
        diag,
        RAW_MAG_DIAG,
        {"sample_tag", "spec_tag", "outcome", "mean_pre"},
    )

    # Column set: match the *main* magnitude follow-ups table.
    columns: list[tuple[str, str]] = [
        ("baseline", "Baseline"),
        ("baseline_pos_usd_only", r"\makecell[c]{Baseline\\USD$>0$}"),
        ("age_lt20", r"Age$<20$"),
        ("age_lt20_pos_usd_only", r"\makecell[c]{Age$<20$\\USD$>0$}"),
        ("age_lt10", r"Age$<10$"),
        ("age_lt10_pos_usd_only", r"\makecell[c]{Age$<10$\\USD$>0$}"),
        ("hq_ca_ny", r"\makecell[c]{HQ in\\CA/NY}"),
        ("hq_outside_ca_ny", r"\makecell[c]{HQ outside\\CA/NY}"),
    ]

    # Select outcomes that were significant in the *prior* pure spec (IV, var3, p<0.1).
    sig_outcomes = (
        pure[(pure["model_type"] == "IV") & (pure["param"] == VAR3) & (pure["pval"].notna()) & (pure["pval"] < 0.1)][
            "outcome"
        ]
        .drop_duplicates()
        .tolist()
    )

    # Keep a stable, interpretable ordering and drop the continuous rank outcome (user preference).
    preferred_order = [
        "cb_log1p_raised_usd",
        "cb_seriesAplus_round",
        "cb_seriesAplus_cum",
        "cb_log1p_cum_raised_usd",
    ]
    outcomes: list[tuple[str, str, dict]] = [
        ("cb_log1p_raised_usd", "log(1+USD raised)", {"decimals": 3, "mean_decimals": 3}),
        ("cb_seriesAplus_round", "Series A+ round", {"decimals": 3, "mean_decimals": 3}),
        ("cb_seriesAplus_cum", "Ever Series A+", {"decimals": 3, "mean_decimals": 3}),
        ("cb_log1p_cum_raised_usd", "log(1+cum USD raised)", {"decimals": 3, "mean_decimals": 3}),
    ]
    outcomes = [o for o in outcomes if o[0] in sig_outcomes]
    # Keep only outcomes we actually have in the magnitude export.
    mag_outcomes = set(mag["outcome"].dropna().unique().tolist())
    outcomes = [o for o in outcomes if o[0] in mag_outcomes]
    if not outcomes:
        raise RuntimeError(
            "No prior-significant outcomes are available in the magnitude (restriction) results. "
            "Did the Stata magnitude runner include the prior-significant outcomes?"
        )

    sample = "matched_private"
    ncols = len(columns)
    headers = [""] + [lbl for _, lbl in columns]

    def _outcome_header(label: str) -> None:
        lines.append(r"\addlinespace[3pt]")
        # Use \boldmath so math-mode labels (e.g. $\log(\cdot)$) are visibly bold.
        lines.append(rf"\multicolumn{{{ncols + 1}}}{{@{{}}l}}{{{{\bfseries\boldmath {label}}}}} {LB}")
        lines.append(r"\addlinespace[1pt]")

    def _term_row(model: str, outcome: str, *, decimals: int) -> None:
        prefix = "OLS:" if model == "OLS" else "IV:"
        label = rf"{prefix} {VAR3_LABEL}"
        cells = [INDENT + label]
        for spec, _ in columns:
            rec = _pick(mag, outcome=outcome, model=model, param=VAR3, sample_tag=sample, spec_tag=spec)
            cells.append(coef_cell(rec, outcome=outcome, decimals=decimals))
        lines.append(" & ".join(cells) + LB)

    def _diag_val(spec: str, outcome: str, field: str) -> float | None:
        sub = diag[(diag["sample_tag"] == sample) & (diag["spec_tag"] == spec) & (diag["outcome"] == outcome)].head(1)
        if sub.empty:
            return None
        val = sub.iloc[0].get(field)
        if pd.isna(val):
            return None
        return float(val)

    def _pre_mean_row(outcome: str, *, mean_decimals: int) -> None:
        cells = [INDENT + "Pre-Covid mean"]
        for spec, _ in columns:
            mean_pre = _diag_val(spec, outcome, "mean_pre")
            if mean_pre is None:
                cells.append("")
                continue
            cells.append(_format_num(float(mean_pre), decimals=mean_decimals))
        lines.append(" & ".join(cells) + LB)

    # Diagnostics footer: same as main magnitude table (for cb_raised_usd only).
    def _nobs_for(spec: str, *, model: str = "OLS") -> int | None:
        rec = _pick(mag, outcome="cb_raised_usd", model=model, param=VAR3, sample_tag=sample, spec_tag=spec)
        if rec is None:
            return None
        n = rec.get("nobs")
        if pd.isna(n):
            return None
        return int(n)

    def _first_stage_f_for(spec: str) -> float | None:
        rec = _pick(mag, outcome="cb_raised_usd", model="IV", param=VAR3, sample_tag=sample, spec_tag=spec)
        if rec is None:
            return None
        f = rec.get("partialF")
        if pd.isna(f):
            return None
        return float(f)

    lines: list[str] = [
        PREAMBLE_FLEX + r"\scriptsize" + "\n",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(ncols)}}}",
        TOP,
        " & ".join(headers) + LB,
        MID,
    ]

    for out, label, fmt in outcomes:
        _outcome_header(label)
        _term_row("OLS", out, decimals=int(fmt["decimals"]))
        _term_row("IV", out, decimals=int(fmt["decimals"]))
        _pre_mean_row(out, mean_decimals=int(fmt["mean_decimals"]))

    nobs_cells = ["N (obs, USD)"]
    f_cells = ["First-stage F (USD)"]
    for spec, _ in columns:
        nobs = _nobs_for(spec, model="OLS")
        f = _first_stage_f_for(spec)
        nobs_cells.append(f"{nobs:,}" if nobs is not None else "")
        f_cells.append(_fmt_scalar(f, decimals=2) if f is not None else "")

    lines.append(MID)
    lines.append(" & ".join(nobs_cells) + LB)
    lines.append(" & ".join(f_cells) + LB)

    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-prepost", type=Path, default=OUT_PREPOST)
    p.add_argument("--out-magnitude", type=Path, default=OUT_MAG)
    p.add_argument("--out-prior", type=Path, default=OUT_PRIOR)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    prepost = _load_csv(RAW_PREPOST)
    mag = _load_csv(RAW_MAG)
    diag = _load_csv(RAW_MAG_DIAG)
    pure = _load_csv(RAW_PURE)

    ensure_dir(args.out_prepost.parent)
    ensure_dir(args.out_magnitude.parent)
    ensure_dir(args.out_prior.parent)

    args.out_prepost.write_text(build_prepost_table(prepost), encoding="utf-8")
    print(f"Wrote pre/post table → {args.out_prepost}")

    args.out_magnitude.write_text(build_magnitude_followups_table(mag, diag), encoding="utf-8")
    print(f"Wrote magnitude follow-ups table → {args.out_magnitude}")

    args.out_prior.write_text(build_prior_significant_table(pure=pure, mag=mag, diag=diag), encoding="utf-8")
    print(f"Wrote prior-significant appendix table → {args.out_prior}")


if __name__ == "__main__":
    main()
