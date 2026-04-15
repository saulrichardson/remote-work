#!/usr/bin/env python3
"""Build standalone LaTeX writeup for the LLM-equity PI follow-up package."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file

REQ_TABLES = [
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_firm_measure_software.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_firm_measure_count.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_firm_measure_topq.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_user_measure_software.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_user_measure_count.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_user_measure_topq.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_horse_race.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_sample.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_descriptives.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_firm_core.tex",
    RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_user_core.tex",
]

OUT_TEX = PROJECT_ROOT / "writeup" / "tex" / "llm_equity_pi_followups_note.tex"
USER_FOLLOWUP_RAW = RESULTS_RAW / "user_productivity_llm_equity_pi_followups_precovid" / "consolidated_results.csv"
FIRM_FOLLOWUP_RAW = RESULTS_RAW / "firm_scaling_llm_equity_pi_followups" / "consolidated_results.csv"
HORSE_USER_RAW = RESULTS_RAW / "user_mechanisms_with_growth_precovid" / "consolidated_results.csv"
NO_CB_USER_RAW = RESULTS_RAW / "user_productivity_llm_equity_no_cb_modes_precovid" / "consolidated_results.csv"
NO_CB_FIRM_RAW = RESULTS_RAW / "firm_scaling_llm_equity_no_cb_modes" / "consolidated_results.csv"

FOCUSED_MEASURES = ["any_software_strict", "count_raw", "share_top_quartile"]
FOCUSED_SPECS = [
    ("backfill", "core_pooled"),
    ("backfill_missing", "core_pooled_missing_ctrl"),
    ("backfill_decomp", "core_pooled_decomp_ctrl"),
]


def pick_value(
    df: pd.DataFrame,
    *,
    field: str,
    model_type: str,
    sample_mode: str | None = None,
    analysis_block: str | None = None,
    equity_measure: str | None = None,
    param: str = "var5",
    spec: str | None = None,
) -> float | None:
    mask = df["model_type"] == model_type
    if sample_mode is not None:
        mask &= df["sample_mode"] == sample_mode
    if analysis_block is not None:
        mask &= df["analysis_block"] == analysis_block
    if equity_measure is not None:
        mask &= df["equity_measure"] == equity_measure
    if param is not None:
        mask &= df["param"] == param
    if spec is not None:
        mask &= df["spec"] == spec
    hit = df.loc[mask].head(1)
    if hit.empty:
        return None
    value = hit.iloc[0].get(field)
    if value is None or pd.isna(value):
        return None
    return float(value)


def fmt_range(values: list[float], digits: int = 2) -> str:
    vals = [float(v) for v in values if v is not None and pd.notna(v)]
    if not vals:
        return "--"
    lo = min(vals)
    hi = max(vals)
    if abs(lo - hi) < 1e-12:
        return f"{lo:.{digits}f}"
    return f"{lo:.{digits}f} to {hi:.{digits}f}"


def fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{float(value):.{digits}f}"


def main() -> None:
    for p in REQ_TABLES:
        require_file(p, nonempty=True, purpose=f"required PI follow-up table ({p.name})")

    user_followup = pd.read_csv(require_file(USER_FOLLOWUP_RAW, nonempty=True, purpose="user follow-up results"))
    firm_followup = pd.read_csv(require_file(FIRM_FOLLOWUP_RAW, nonempty=True, purpose="firm follow-up results"))
    horse_user = pd.read_csv(require_file(HORSE_USER_RAW, nonempty=True, purpose="user horse-race results"))
    no_cb_user = pd.read_csv(require_file(NO_CB_USER_RAW, nonempty=True, purpose="user baseline anchor results"))
    no_cb_firm = pd.read_csv(require_file(NO_CB_FIRM_RAW, nonempty=True, purpose="firm baseline anchor results"))

    firm_anchor_ols = pick_value(
        no_cb_firm,
        field="coef",
        model_type="OLS",
        sample_mode="backfill",
        analysis_block="core_pooled",
        equity_measure="any",
        param="var5",
    )
    firm_anchor_iv = pick_value(
        no_cb_firm,
        field="coef",
        model_type="IV",
        sample_mode="backfill",
        analysis_block="core_pooled",
        equity_measure="any",
        param="var5",
    )
    user_anchor_ols = pick_value(
        no_cb_user,
        field="coef",
        model_type="OLS",
        sample_mode="backfill",
        analysis_block="core_pooled",
        equity_measure="any",
        param="var5",
    )
    user_anchor_iv = pick_value(
        no_cb_user,
        field="coef",
        model_type="IV",
        sample_mode="backfill",
        analysis_block="core_pooled",
        equity_measure="any",
        param="var5",
    )

    firm_main_ols_vals: list[float] = []
    firm_main_iv_vals: list[float] = []
    firm_all_ols_vals: list[float] = []
    firm_all_iv_vals: list[float] = []
    user_main_ols_vals: list[float] = []
    user_main_iv_vals: list[float] = []
    user_all_ols_vals: list[float] = []
    user_all_iv_vals: list[float] = []
    user_kp_vals: list[float] = []

    for measure in FOCUSED_MEASURES:
        # Main spec only.
        main_firm_ols = pick_value(
            firm_followup,
            field="coef",
            model_type="OLS",
            sample_mode="backfill",
            analysis_block="core_pooled",
            equity_measure=measure,
            param="var5",
        )
        main_firm_iv = pick_value(
            firm_followup,
            field="coef",
            model_type="IV",
            sample_mode="backfill",
            analysis_block="core_pooled",
            equity_measure=measure,
            param="var5",
        )
        if main_firm_ols is not None:
            firm_main_ols_vals.append(main_firm_ols)
        if main_firm_iv is not None:
            firm_main_iv_vals.append(main_firm_iv)

        main_user_ols = pick_value(
            user_followup,
            field="coef",
            model_type="OLS",
            sample_mode="backfill",
            analysis_block="core_pooled",
            equity_measure=measure,
            param="var5",
        )
        main_user_iv = pick_value(
            user_followup,
            field="coef",
            model_type="IV",
            sample_mode="backfill",
            analysis_block="core_pooled",
            equity_measure=measure,
            param="var5",
        )
        if main_user_ols is not None:
            user_main_ols_vals.append(main_user_ols)
        if main_user_iv is not None:
            user_main_iv_vals.append(main_user_iv)

        # All three displayed specs.
        for sample_mode, analysis_block in FOCUSED_SPECS:
            val_firm_ols = pick_value(
                firm_followup,
                field="coef",
                model_type="OLS",
                sample_mode=sample_mode,
                analysis_block=analysis_block,
                equity_measure=measure,
                param="var5",
            )
            val_firm_iv = pick_value(
                firm_followup,
                field="coef",
                model_type="IV",
                sample_mode=sample_mode,
                analysis_block=analysis_block,
                equity_measure=measure,
                param="var5",
            )
            if val_firm_ols is not None:
                firm_all_ols_vals.append(val_firm_ols)
            if val_firm_iv is not None:
                firm_all_iv_vals.append(val_firm_iv)

            val_user_ols = pick_value(
                user_followup,
                field="coef",
                model_type="OLS",
                sample_mode=sample_mode,
                analysis_block=analysis_block,
                equity_measure=measure,
                param="var5",
            )
            val_user_iv = pick_value(
                user_followup,
                field="coef",
                model_type="IV",
                sample_mode=sample_mode,
                analysis_block=analysis_block,
                equity_measure=measure,
                param="var5",
            )
            kp_val = pick_value(
                user_followup,
                field="rkf",
                model_type="IV",
                sample_mode=sample_mode,
                analysis_block=analysis_block,
                equity_measure=measure,
                param="var5",
            )
            if val_user_ols is not None:
                user_all_ols_vals.append(val_user_ols)
            if val_user_iv is not None:
                user_all_iv_vals.append(val_user_iv)
            if kp_val is not None:
                user_kp_vals.append(kp_val)

    low_kp_vals = [v for v in user_kp_vals if v < 5.0]
    low_kp_count = len(low_kp_vals)

    horse_baseline_iv = pick_value(
        horse_user,
        field="coef",
        model_type="IV",
        spec="baseline",
        param="var5",
    )
    horse_growth_iv = pick_value(
        horse_user,
        field="coef",
        model_type="IV",
        spec="growth_endog",
        param="var5",
    )
    horse_equity_iv = pick_value(
        horse_user,
        field="coef",
        model_type="IV",
        spec="equity",
        param="var5",
    )
    horse_both_iv = pick_value(
        horse_user,
        field="coef",
        model_type="IV",
        spec="growth_endog_equity",
        param="var5",
    )

    content = rf"""\documentclass{{article}}
\usepackage[margin=1.0in]{{geometry}}
\usepackage{{graphicx}}
\usepackage{{booktabs}}
\usepackage{{makecell}}
\usepackage{{float}}
\usepackage{{amsmath,amssymb,amsfonts}}
\usepackage{{dsfont}}
\usepackage[normalem]{{ulem}}
\usepackage{{setspace}}
\setstretch{{1.08}}

\newcommand{{\cleanedresultsdir}}{{../results/cleaned/tex}}
\newcommand{{\TableInput}}[2][\linewidth]{{\input{{#2}}}}

\begin{{document}}

\section*{{Result Story and Table Guide}}
This note answers one practical question: does the main startup effect after the shift to remote work stay in place once equity-offer measures are added in different ways.

\noindent The row to track in every regression table is
$ \text{{Remote}} \times \mathds{{1}}(\text{{Post}}) \times \text{{Startup}} $.
That is the main startup effect.

\begin{{enumerate}}
\item Tables 1--2 set context (sample and equity prevalence).
\item Tables 3--4 anchor the baseline startup effect before the focused equity-definition checks.
\item Tables 5--10 show the full coefficient set for each focused equity definition in firm and user outcomes.
\item Table 11 shows the mechanism comparison and asks whether equity controls reduce the main productivity effect in the same way growth controls do.
\end{{enumerate}}

\section*{{Context and Baseline}}
\noindent\textbf{{Purpose of Table 1.}} Confirm the size of the analysis sample.

\begin{{table}}[H]
  \centering
  \caption{{Sample accounting}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_anchor_sample.tex}}
\end{{table}}

\noindent\textbf{{Purpose of Table 2.}} Show how common equity mentions are in startup and non-startup firms.

\begin{{table}}[H]
  \centering
  \caption{{Startup vs non-startup equity prevalence}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_anchor_descriptives.tex}}
\end{{table}}

\noindent\textbf{{Purpose of Table 3.}} Set the firm baseline for the main startup effect before the focused definition checks.
In this baseline anchor, the startup effect is {fmt_num(firm_anchor_ols, 3)} in OLS and {fmt_num(firm_anchor_iv, 3)} in IV.

\begin{{table}}[H]
  \centering
  \caption{{Firm outcome baseline}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_anchor_firm_core.tex}}
\end{{table}}

\noindent\textbf{{Purpose of Table 4.}} Set the user baseline for the same startup effect.
In this baseline anchor, the startup effect is {fmt_num(user_anchor_ols, 2)} in OLS and {fmt_num(user_anchor_iv, 2)} in IV.

\begin{{table}}[H]
  \centering
  \caption{{User outcome baseline}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_anchor_user_core.tex}}
\end{{table}}

\section*{{Firm Outcome: Focused Equity Definitions}}
Across the three focused equity definitions, the main-spec startup effect stays in a tight band:
OLS {fmt_range(firm_main_ols_vals, 3)} and IV {fmt_range(firm_main_iv_vals, 3)}.
Across all three displayed spec columns, the range is still tight:
OLS {fmt_range(firm_all_ols_vals, 3)} and IV {fmt_range(firm_all_iv_vals, 3)}.

\noindent\textbf{{Purpose of Table 5.}} Firm outcome with software-role equity definition; all coefficients shown.

\begin{{table}}[H]
  \centering
  \caption{{Firm outcome: any equity mention (software roles only), full specification set}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_firm_measure_software.tex}}
\end{{table}}

\noindent\textbf{{Purpose of Table 6.}} Firm outcome with equity-mention count definition; all coefficients shown.

\begin{{table}}[H]
  \centering
  \caption{{Firm outcome: average number of equity mentions, full specification set}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_firm_measure_count.tex}}
\end{{table}}

\noindent\textbf{{Purpose of Table 7.}} Firm outcome with high-equity-share indicator; all coefficients shown.

\begin{{table}}[H]
  \centering
  \caption{{Firm outcome: high equity-share indicator (top quartile), full specification set}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_firm_measure_topq.tex}}
\end{{table}}

\section*{{User Outcome: Focused Equity Definitions}}
In the main-spec columns, the startup effect remains positive:
OLS {fmt_range(user_main_ols_vals, 2)} and IV {fmt_range(user_main_iv_vals, 2)}.
Across all three displayed spec columns, OLS stays in a narrow band ({fmt_range(user_all_ols_vals, 2)}), while IV has a wider range ({fmt_range(user_all_iv_vals, 2)}).

\noindent A key nuance is IV strength: {low_kp_count} of the user IV columns have a low strength statistic (below 5), which makes those specific IV columns noisy.

\noindent\textbf{{Purpose of Table 8.}} User outcome with software-role equity definition; all coefficients shown.

\begin{{table}}[H]
  \centering
  \caption{{User outcome: any equity mention (software roles only), full specification set}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_user_measure_software.tex}}
\end{{table}}

\noindent\textbf{{Purpose of Table 9.}} User outcome with equity-mention count definition; all coefficients shown.

\begin{{table}}[H]
  \centering
  \caption{{User outcome: average number of equity mentions, full specification set}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_user_measure_count.tex}}
\end{{table}}

\noindent\textbf{{Purpose of Table 10.}} User outcome with high-equity-share indicator; all coefficients shown.

\begin{{table}}[H]
  \centering
  \caption{{User outcome: high equity-share indicator (top quartile), full specification set}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_user_measure_topq.tex}}
\end{{table}}

\section*{{Mechanism Comparison}}
\noindent\textbf{{Purpose of Table 11.}} Compare one-at-a-time mechanism controls in the same style as the mini write-up.
For the user IV startup effect, the sequence is:
baseline {fmt_num(horse_baseline_iv, 2)},
growth controls {fmt_num(horse_growth_iv, 2)},
equity controls {fmt_num(horse_equity_iv, 2)},
growth + equity {fmt_num(horse_both_iv, 2)}.
This means the larger drop comes from growth controls, not from equity controls alone.

\begin{{table}}[H]
  \centering
  \caption{{Individual Productivity Mechanisms}}
  \TableInput{{\cleanedresultsdir/llm_equity_pi_followups_horse_race.tex}}
\end{{table}}

\section*{{Bottom Line}}
The full set of focused equity definitions keeps the main startup result in place, especially in OLS and in the firm outcome.
Equity controls add useful detail, but they do not consistently remove the startup effect.
The largest reduction in the user IV startup coefficient appears when growth controls are introduced.

\end{{document}}
"""

    ensure_dir(OUT_TEX.parent)
    OUT_TEX.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT_TEX}")


if __name__ == "__main__":
    main()
