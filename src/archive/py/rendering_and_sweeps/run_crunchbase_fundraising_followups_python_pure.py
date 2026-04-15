#!/usr/bin/env python3
"""Run Crunchbase fundraising follow-ups in Python (pure spec: Remote×Post only).

Why this exists
---------------
The repo’s canonical fundraising regressions are written in Stata (reghdfe /
ivreghdfe). In this environment we can re-estimate the same two-way FE models in
Python and validate them against the existing Stata exports already stored in
the repo.

This script mirrors the meeting follow-ups (age<10/20, no-zeros, ever-funded,
NY/SF splits + an interaction), but uses the *pure* RHS:

  y_it = b * var3_it + a_i + t_t + e_it

and instruments var3 with var6:

  var3_it = p * var6_it + a_i + t_t + u_it

Inputs
------
  - data/clean/firm_panel_with_cb_funding.csv
  - results/raw/firm_scaling_crunchbase_fundraising_pure/consolidated_results.csv
    (for baseline validation)

Outputs
-------
  - results/raw/firm_scaling_crunchbase_fundraising_followups_python_pure/
      consolidated_results.csv
      sample_sizes.csv
      validation_report.json
      diagnostics.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.py.project_paths import RESULTS_RAW, ensure_dir, require_file
from run_crunchbase_fundraising_followups_python import (  # type: ignore
    RegressionResult,
    SampleSize,
    compute_ever_round,
    load_panel,
    make_hq_state_ca_ny,
    make_hq_ny_sf,
    run_spec,
)


STATA_BASELINE = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_pure" / "consolidated_results.csv"
OUT_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_followups_python_pure"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help="Output directory under results/raw. Default: %(default)s",
    )
    p.add_argument(
        "--tol",
        type=float,
        default=1e-3,
        help="Absolute tolerance for baseline validation vs Stata. Default: %(default)s",
    )
    p.add_argument(
        "--max-iter",
        type=int,
        default=200,
        help="Max iterations for two-way demeaning. Default: %(default)s",
    )
    p.add_argument(
        "--tol-demean",
        type=float,
        default=1e-10,
        help="Convergence tolerance for two-way demeaning. Default: %(default)s",
    )
    return p.parse_args()


def load_stata_baseline() -> pd.DataFrame:
    require_file(
        STATA_BASELINE,
        nonempty=True,
        purpose="Stata pure baseline results (firm_scaling_crunchbase_fundraising_pure/consolidated_results.csv)",
    )
    df = pd.read_csv(STATA_BASELINE)
    need = {"sample_tag", "model_type", "outcome", "param", "coef", "se", "pval", "nobs"}
    missing = need - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns {sorted(missing)} in {STATA_BASELINE}.")
    return df


def _pull_stata_row(stata: pd.DataFrame, *, sample_tag: str, model: str, outcome: str, param: str) -> pd.Series:
    sub = stata[
        (stata["sample_tag"] == sample_tag)
        & (stata["model_type"] == model)
        & (stata["outcome"] == outcome)
        & (stata["param"] == param)
    ]
    if sub.empty:
        raise ValueError(f"Missing Stata row for {sample_tag}/{model}/{outcome}/{param}")
    return sub.iloc[0]


def validate_against_stata(
    results: list[RegressionResult],
    stata: pd.DataFrame,
    *,
    tol: float,
) -> dict:
    """Validate baseline matched-private pure spec against existing Stata pure results."""
    report: dict = {"checks": [], "passed": True}

    def _check(model: str) -> None:
        py = next(
            r
            for r in results
            if r.sample_tag == "matched_private"
            and r.spec_tag == "baseline"
            and r.model_type == model
            and r.outcome == "cb_log1p_raised_usd"
            and r.param == "var3"
        )
        st = _pull_stata_row(stata, sample_tag="private", model=model, outcome="cb_log1p_raised_usd", param="var3")

        coef_ok = abs(py.coef - float(st["coef"])) <= tol
        se_ok = abs(py.se - float(st["se"])) <= tol
        n_ok = int(py.nobs) == int(st["nobs"])

        chk = {
            "model": model,
            "param": "var3",
            "py": {"coef": py.coef, "se": py.se, "nobs": py.nobs},
            "stata": {"coef": float(st["coef"]), "se": float(st["se"]), "nobs": int(st["nobs"])},
            "tolerance": tol,
            "coef_ok": coef_ok,
            "se_ok": se_ok,
            "nobs_ok": n_ok,
        }
        report["checks"].append(chk)
        if not (coef_ok and se_ok and n_ok):
            report["passed"] = False

    _check("OLS")
    _check("IV")
    return report


def main() -> None:
    args = parse_args()
    ensure_dir(args.out_dir)

    panel = load_panel()

    # Baseline analysis sample: Crunchbase-matched + private.
    df = panel[(panel["cb_matched"] == 1) & (panel["public"] != 1)].copy()
    df["hq_ny_sf"] = make_hq_ny_sf(df).astype(int)
    df["hq_ca_ny"] = make_hq_state_ca_ny(df)
    df["ever_round"] = compute_ever_round(df).astype(int)

    # Run baseline spec first (for validation).
    all_results: list[RegressionResult] = []
    all_sizes: list[SampleSize] = []
    all_diags: dict[str, dict] = {}

    for outcome in ["cb_log1p_raised_usd", "cb_log_raised_usd"]:
        res, sz, diag = run_spec(
            df,
            sample_tag="matched_private",
            spec_tag="baseline",
            outcome=outcome,
            endog_cols=["var3"],
            exog_cols=[],
            instr_cols=["var6"],
            fe_cols=["firm_id", "yh_num"],
            cluster_col="firm_id",
            demean_tol=args.tol_demean,
            demean_max_iter=args.max_iter,
        )
        all_results.extend(res)
        all_sizes.append(sz)
        all_diags[f"{outcome}/baseline"] = diag

    stata = load_stata_baseline()
    validation = validate_against_stata(all_results, stata, tol=args.tol)
    (args.out_dir / "validation_report.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    if not validation["passed"]:
        raise RuntimeError(
            "Baseline validation against Stata (pure) failed. See "
            f"{args.out_dir}/validation_report.json for details."
        )

    # Follow-up variants (on key outcome only by default)
    outcome = "cb_log1p_raised_usd"

    variants: list[tuple[str, pd.DataFrame]] = []
    variants.append(("age_lt10", df[df["age"] < 10].copy()))
    variants.append(("age_lt20", df[df["age"] < 20].copy()))
    variants.append(("pos_usd_only", df[df["cb_raised_usd"] > 0].copy()))
    variants.append(("firms_ever_round", df[df["ever_round"] == 1].copy()))
    variants.append(("hq_ny_sf", df[df["hq_ny_sf"] == 1].copy()))
    variants.append(("hq_outside_ny_sf", df[df["hq_ny_sf"] == 0].copy()))

    # State-level (CA/NY) versions of the same geography checks.
    # NOTE: treat missing HQ state as missing; exclude from these splits.
    variants.append(("hq_ca_ny", df[df["hq_ca_ny"] == 1].copy()))
    variants.append(("hq_outside_ca_ny", df[df["hq_ca_ny"] == 0].copy()))

    # Interaction spec: var3 + var3_outside, instrumented by var6 + var6_outside.
    interaction = df.copy()
    outside = (interaction["hq_ny_sf"] == 0).astype(int)
    interaction["var3_outside"] = interaction["var3"] * outside
    interaction["var6_outside"] = interaction["var6"] * outside
    variants.append(("geo_interaction", interaction))

    # State-level interaction spec: Outside(CA/NY)
    interaction_state = df[df["hq_ca_ny"].notna()].copy()
    outside_state = (interaction_state["hq_ca_ny"] == 0).astype(int)
    interaction_state["var3_outside_ca_ny"] = interaction_state["var3"] * outside_state
    interaction_state["var6_outside_ca_ny"] = interaction_state["var6"] * outside_state
    variants.append(("geo_interaction_ca_ny", interaction_state))

    for spec_tag, vdf in variants:
        if spec_tag == "geo_interaction":
            endog = ["var3", "var3_outside"]
            instr = ["var6", "var6_outside"]
        elif spec_tag == "geo_interaction_ca_ny":
            endog = ["var3", "var3_outside_ca_ny"]
            instr = ["var6", "var6_outside_ca_ny"]
        else:
            endog = ["var3"]
            instr = ["var6"]

        res, sz, diag = run_spec(
            vdf,
            sample_tag="matched_private",
            spec_tag=spec_tag,
            outcome=outcome,
            endog_cols=endog,
            exog_cols=[],
            instr_cols=instr,
            fe_cols=["firm_id", "yh_num"],
            cluster_col="firm_id",
            demean_tol=args.tol_demean,
            demean_max_iter=args.max_iter,
        )
        all_results.extend(res)
        all_sizes.append(sz)
        all_diags[f"{outcome}/{spec_tag}"] = diag

    out_df = pd.DataFrame([asdict(r) for r in all_results])
    out_df.to_csv(args.out_dir / "consolidated_results.csv", index=False)

    sizes_df = pd.DataFrame([asdict(s) for s in all_sizes]).drop_duplicates(
        subset=["sample_tag", "spec_tag"]
    )
    sizes_df.to_csv(args.out_dir / "sample_sizes.csv", index=False)

    (args.out_dir / "diagnostics.json").write_text(json.dumps(all_diags, indent=2), encoding="utf-8")

    print(f"✓ Wrote {args.out_dir}/consolidated_results.csv")
    print(f"✓ Wrote {args.out_dir}/sample_sizes.csv")
    print(f"✓ Wrote {args.out_dir}/validation_report.json (passed={validation['passed']})")


if __name__ == "__main__":
    main()
