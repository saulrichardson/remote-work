#!/usr/bin/env python3
"""Run Crunchbase fundraising follow-ups end-to-end in Python (FE + clustered SE).

Why this exists
---------------
The repo’s canonical fundraising regressions are written in Stata (reghdfe /
ivreghdfe). In this environment we cannot execute Stata, but we *can*:
  - run the follow-up sample restrictions (age<10/20, no-zeros, ever-funded, NY/SF splits)
  - estimate the same two-way FE models in Python
  - validate our implementation by matching the existing Stata baseline results
    already stored under results/raw/firm_scaling_crunchbase_fundraising/

Inputs
------
  - data/clean/firm_panel_with_cb_funding.csv
  - results/raw/firm_scaling_crunchbase_fundraising/consolidated_results.csv (for validation)

Outputs
-------
  - results/raw/firm_scaling_crunchbase_fundraising_followups_python/
      consolidated_results.csv
      sample_sizes.csv
      validation_report.json

Model (mirrors Stata spec)
--------------------------
Two-way fixed effects (firm + half-year), clustered SE by firm:
  y_it = b * var3_it + g * var4_it + a_i + t_t + e_it

IV variant (2SLS), instrumenting var3 with var6:
  var3_it = p * var6_it + d * var4_it + a_i + t_t + u_it

Notes
-----
This script intentionally focuses on one key outcome (cb_log1p_raised_usd) plus
the intensive-margin log dollars outcome (cb_log_raised_usd), because those are
the outcomes discussed in the transcript asks.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

from src.py.project_paths import DATA_CLEAN, RESULTS_RAW, ensure_dir, require_file


PANEL_CSV = DATA_CLEAN / "firm_panel_with_cb_funding.csv"
STATA_BASELINE = RESULTS_RAW / "firm_scaling_crunchbase_fundraising" / "consolidated_results.csv"
OUT_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_followups_python"


@dataclass(frozen=True)
class RegressionResult:
    sample_tag: str
    spec_tag: str
    model_type: str  # OLS | IV
    outcome: str
    param: str
    coef: float
    se: float
    pval: float
    pre_mean: float
    rkf: float | None
    partialF: float | None
    nobs: int


@dataclass(frozen=True)
class SampleSize:
    sample_tag: str
    spec_tag: str
    n_obs: int
    n_firms: int


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


def _require_columns(df: pd.DataFrame, cols: Iterable[str], *, context: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing columns in {context}: {missing}")


def _as_numeric(df: pd.DataFrame, cols: Iterable[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")


def load_panel() -> pd.DataFrame:
    require_file(
        PANEL_CSV,
        nonempty=True,
        purpose="Crunchbase-augmented firm panel (firm_panel_with_cb_funding.csv)",
    )
    df = pd.read_csv(PANEL_CSV, low_memory=False)
    required = [
        "firm_id",
        "yh_num",
        "covid",
        "public",
        "age",
        "hqcity",
        "hqstate",
        "cb_matched",
        "cb_round_count",
        "cb_raised_usd",
        "cb_log1p_raised_usd",
        "var3",
        "var4",
        "var6",
    ]
    _require_columns(df, required, context=str(PANEL_CSV))
    _as_numeric(
        df,
        [
            "yh_num",
            "covid",
            "public",
            "age",
            "cb_matched",
            "cb_round_count",
            "cb_raised_usd",
            "cb_log1p_raised_usd",
            "var3",
            "var4",
            "var6",
        ],
    )

    # Derived intensive-margin outcome (avoid np.where eager evaluation warnings).
    df["cb_log_raised_usd"] = np.nan
    pos = df["cb_raised_usd"] > 0
    df.loc[pos, "cb_log_raised_usd"] = np.log(df.loc[pos, "cb_raised_usd"])
    return df


def _encode_groups(values: pd.Series) -> np.ndarray:
    codes, _ = pd.factorize(values, sort=True)
    if (codes < 0).any():
        raise ValueError("Found missing group ids after factorize; drop missings before encoding.")
    return codes.astype(np.int64)


def _group_demean_inplace(x: np.ndarray, g: np.ndarray, n_groups: int) -> None:
    """Subtract within-group mean from each column of x (in place)."""
    counts = np.bincount(g, minlength=n_groups).astype(np.float64)
    if (counts == 0).any():
        raise ValueError("Encountered empty groups in group ids.")

    # For k small, loop over columns: bincount is fast.
    for j in range(x.shape[1]):
        sums = np.bincount(g, weights=x[:, j], minlength=n_groups).astype(np.float64)
        means = sums / counts
        x[:, j] -= means[g]


def twoway_demean(x: np.ndarray, g1: np.ndarray, g2: np.ndarray, *, tol: float, max_iter: int) -> tuple[np.ndarray, int, float]:
    """Iteratively absorb two additive fixed effects via alternating projections.

    Returns (x_resid, n_iter, final_max_abs_update).
    """
    # Empirically, on this environment (numpy/pandas stack), running the
    # alternating-projections loop on a *multi-column* array can behave
    # pathologically (non-convergence / exploding values). Since our use-case has
    # very small k (≤2), we robustly demean each column independently.
    if x.ndim == 2 and x.shape[1] > 1:
        out = np.empty_like(x, dtype=np.float64)
        it_max = 0
        delta_max = 0.0
        for j in range(x.shape[1]):
            col, it, delta = twoway_demean(x[:, j], g1, g2, tol=tol, max_iter=max_iter)
            out[:, j] = col.ravel()
            it_max = max(it_max, it)
            delta_max = max(delta_max, float(delta))
        return out, it_max, delta_max

    if x.ndim == 1:
        x = x.reshape(-1, 1)
    x = x.astype(np.float64, copy=True)
    n1 = int(g1.max()) + 1
    n2 = int(g2.max()) + 1

    last_delta = np.inf
    for it in range(1, max_iter + 1):
        prev = x.copy()
        _group_demean_inplace(x, g1, n1)
        _group_demean_inplace(x, g2, n2)
        delta = float(np.max(np.abs(x - prev)))
        last_delta = delta
        if delta <= tol:
            return x, it, delta
    return x, max_iter, float(last_delta)


def ols_cluster(y: np.ndarray, X: np.ndarray, clusters: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """OLS with cluster-robust SE (one-way clustering). Returns (b, se, pval)."""
    y = y.astype(np.float64)
    X = X.astype(np.float64)
    n, k = X.shape

    # Coefs / residuals. We silence floating warnings from BLAS-backed matmul
    # but explicitly fail if we ever generate non-finite values.
    with np.errstate(all="ignore"):
        XtX = X.T @ X
        Xty = X.T @ y
        b = np.linalg.solve(XtX, Xty)
        u = y - X @ b

    if not np.isfinite(b).all():
        raise FloatingPointError("OLS produced non-finite coefficients (singular or ill-conditioned X'X).")
    if not np.isfinite(u).all():
        raise FloatingPointError("OLS produced non-finite residuals.")

    # Cluster meat
    uniq = np.unique(clusters)
    G = int(len(uniq))
    meat = np.zeros((k, k), dtype=np.float64)
    for g in uniq:
        idx = clusters == g
        Xg = X[idx, :]
        ug = u[idx]
        xug = Xg.T @ ug
        meat += np.outer(xug, xug)

    bread = np.linalg.inv(XtX)
    V = bread @ meat @ bread

    # Small-sample adjustment (Stata-style)
    if G > 1 and (n - k) > 0:
        V *= (G / (G - 1)) * ((n - 1) / (n - k))

    se = np.sqrt(np.diag(V))
    t = b / se
    df = max(G - 1, 1)
    pval = 2 * stats.t.sf(np.abs(t), df)
    return b, se, pval


def iv2sls_cluster(
    y: np.ndarray,
    X_endog: np.ndarray,
    X_exog: np.ndarray,
    Z_excl: np.ndarray,
    clusters: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """2SLS with cluster-robust SE.

    Returns (b, se, pval, first_stage_F_per_endog).
    """
    y = y.astype(np.float64)
    X_endog = X_endog.astype(np.float64)
    X_exog = X_exog.astype(np.float64)
    Z_excl = Z_excl.astype(np.float64)

    # Stack matrices
    X = np.column_stack([X_endog, X_exog])
    Z = np.column_stack([Z_excl, X_exog])

    n, k = X.shape
    l = Z.shape[1]

    with np.errstate(all="ignore"):
        ZtZ = Z.T @ Z
        W = np.linalg.inv(ZtZ)
        XZ = X.T @ Z
        M = XZ @ W @ XZ.T  # k x k
        invM = np.linalg.inv(M)
        b = invM @ (XZ @ W @ (Z.T @ y))
        e = y - X @ b

    if not np.isfinite(b).all():
        raise FloatingPointError("IV produced non-finite coefficients (singular or ill-conditioned matrices).")
    if not np.isfinite(e).all():
        raise FloatingPointError("IV produced non-finite residuals.")

    # Cluster S = Σ (Z_g' e_g)(Z_g' e_g)'
    uniq = np.unique(clusters)
    G = int(len(uniq))
    S = np.zeros((l, l), dtype=np.float64)
    for g in uniq:
        idx = clusters == g
        Zg = Z[idx, :]
        eg = e[idx]
        zge = Zg.T @ eg
        S += np.outer(zge, zge)

    V = invM @ (XZ @ W @ S @ W @ XZ.T) @ invM
    if G > 1 and (n - k) > 0:
        V *= (G / (G - 1)) * ((n - 1) / (n - k))

    se = np.sqrt(np.diag(V))
    t = b / se
    df = max(G - 1, 1)
    pval = 2 * stats.t.sf(np.abs(t), df)

    # First-stage F (one per endogenous regressor): regress endog on Z_excl + X_exog
    # For a single excluded instrument per endogenous, F = t^2 on that instrument.
    fs_F = np.full(X_endog.shape[1], np.nan, dtype=np.float64)
    for j in range(X_endog.shape[1]):
        xj = X_endog[:, j : j + 1]
        Zj = np.column_stack([Z_excl, X_exog])
        bj, sej, _ = ols_cluster(xj.ravel(), Zj, clusters)
        # Excluded instruments are the first columns of Zj (same count as Z_excl)
        if Z_excl.shape[1] == 1:
            t_inst = bj[0] / sej[0] if sej[0] != 0 else np.nan
            fs_F[j] = t_inst * t_inst
        else:
            # Wald F on excluded instrument block (cluster-robust)
            # Simple fallback: report NaN to avoid misleading numbers.
            fs_F[j] = np.nan

    return b, se, pval, fs_F


def make_hq_ny_sf(df: pd.DataFrame) -> pd.Series:
    city = df["hqcity"].astype(str).str.strip().str.lower()
    state = df["hqstate"].astype(str).str.strip().str.upper()
    return ((city == "new york") & (state == "NY")) | ((city == "san francisco") & (state == "CA"))


def make_hq_state_ca_ny(df: pd.DataFrame) -> pd.Series:
    """HQ is in CA or NY by *state* (not NYC/SF city-level)."""
    state = df["hqstate"].astype("string").str.strip().str.upper()
    is_ca_ny = state.isin(["CA", "NY"])
    # Keep missing as missing (so callers can explicitly drop unknown HQ states).
    return is_ca_ny.where(state.notna() & (state != ""), pd.NA)


def compute_ever_round(df: pd.DataFrame) -> pd.Series:
    # firm-level ever round (in panel window)
    firm_max = df.groupby("firm_id")["cb_round_count"].max()
    return df["firm_id"].map((firm_max > 0).astype(int))


def run_spec(
    df: pd.DataFrame,
    *,
    sample_tag: str,
    spec_tag: str,
    outcome: str,
    endog_cols: list[str],
    exog_cols: list[str],
    instr_cols: list[str],
    fe_cols: list[str],
    cluster_col: str,
    demean_tol: float,
    demean_max_iter: int,
) -> tuple[list[RegressionResult], SampleSize, dict]:
    cols = [outcome] + endog_cols + exog_cols + instr_cols + fe_cols + [cluster_col, "covid"]
    # De-duplicate while preserving order (pandas allows duplicate col names;
    # selecting them can create ambiguous 2D objects later).
    cols_unique: list[str] = []
    seen: set[str] = set()
    for c in cols:
        if c not in seen:
            cols_unique.append(c)
            seen.add(c)

    sub = df[cols_unique].copy()
    sub = sub.dropna()

    n_obs = int(len(sub))
    if n_obs == 0:
        raise ValueError(f"Empty sample for {sample_tag}/{spec_tag}/{outcome}")

    firm_ct = int(pd.Series(sub[cluster_col]).nunique())
    size = SampleSize(sample_tag=sample_tag, spec_tag=spec_tag, n_obs=n_obs, n_firms=firm_ct)

    # Pre mean is computed on the raw sample (pre period), matching Stata scripts.
    pre_mean = float(sub.loc[sub["covid"] == 0, outcome].mean())

    # Encode FE and cluster groups.
    g1 = _encode_groups(sub[fe_cols[0]])
    g2 = _encode_groups(sub[fe_cols[1]])
    clusters = _encode_groups(sub[cluster_col])

    # Residualize y and regressors/instruments w.r.t. the same fixed effects.
    y_raw = sub[outcome].to_numpy(dtype=np.float64)
    y_resid, it_y, delta_y = twoway_demean(y_raw, g1, g2, tol=demean_tol, max_iter=demean_max_iter)
    y_resid = y_resid.ravel()

    X_endog_raw = sub[endog_cols].to_numpy(dtype=np.float64)
    X_endog_resid, it_xe, delta_xe = twoway_demean(
        X_endog_raw, g1, g2, tol=demean_tol, max_iter=demean_max_iter
    )

    if exog_cols:
        X_exog_raw = sub[exog_cols].to_numpy(dtype=np.float64)
        X_exog_resid, it_xx, delta_xx = twoway_demean(
            X_exog_raw, g1, g2, tol=demean_tol, max_iter=demean_max_iter
        )

        # After absorbing firm + time FE, some controls can become perfectly collinear
        # (e.g., in an all-startup subsample, var4 == covid is absorbed by time FE).
        # To avoid nonsensical huge coefficients from near-singular matrices, we
        # explicitly drop near-zero regressors post-demeaning and mark them omitted.
        exog_keep = np.linalg.norm(X_exog_resid, axis=0) > 1e-12
        kept_exog_cols = [c for c, keep in zip(exog_cols, exog_keep, strict=True) if keep]
        dropped_exog_cols = [c for c, keep in zip(exog_cols, exog_keep, strict=True) if not keep]
        X_exog_resid = X_exog_resid[:, exog_keep]
    else:
        X_exog_resid = np.empty((n_obs, 0), dtype=np.float64)
        it_xx = 0
        delta_xx = 0.0
        kept_exog_cols = []
        dropped_exog_cols = []

    Z_raw = sub[instr_cols].to_numpy(dtype=np.float64)
    Z_resid, it_z, delta_z = twoway_demean(Z_raw, g1, g2, tol=demean_tol, max_iter=demean_max_iter)

    # OLS (treat endog_cols as regular regressors)
    X_ols = np.column_stack([X_endog_resid, X_exog_resid]) if X_exog_resid.size else X_endog_resid
    b_ols, se_ols, p_ols = ols_cluster(y_resid, X_ols, clusters)

    results: list[RegressionResult] = []
    params = endog_cols + kept_exog_cols
    for j, p in enumerate(params):
        results.append(
            RegressionResult(
                sample_tag=sample_tag,
                spec_tag=spec_tag,
                model_type="OLS",
                outcome=outcome,
                param=p,
                coef=float(b_ols[j]),
                se=float(se_ols[j]),
                pval=float(p_ols[j]),
                pre_mean=pre_mean,
                rkf=None,
                partialF=None,
                nobs=n_obs,
            )
        )

    # Record omitted exogenous regressors (match Stata "omitted" behavior).
    for p in dropped_exog_cols:
        results.append(
            RegressionResult(
                sample_tag=sample_tag,
                spec_tag=spec_tag,
                model_type="OLS",
                outcome=outcome,
                param=p,
                coef=float("nan"),
                se=float("nan"),
                pval=float("nan"),
                pre_mean=pre_mean,
                rkf=None,
                partialF=None,
                nobs=n_obs,
            )
        )

    # IV (2SLS)
    b_iv, se_iv, p_iv, fs_F = iv2sls_cluster(y_resid, X_endog_resid, X_exog_resid, Z_resid, clusters)
    for j, p in enumerate(params):
        # Attach first-stage F only to endogenous coefficients (var3 / var3_out etc.)
        partialF = float(fs_F[j]) if j < len(endog_cols) and np.isfinite(fs_F[j]) else None
        rkf = partialF  # for just-identified single-instrument case this matches Stata output pattern
        results.append(
            RegressionResult(
                sample_tag=sample_tag,
                spec_tag=spec_tag,
                model_type="IV",
                outcome=outcome,
                param=p,
                coef=float(b_iv[j]),
                se=float(se_iv[j]),
                pval=float(p_iv[j]),
                pre_mean=pre_mean,
                rkf=rkf,
                partialF=partialF if p in endog_cols else None,
                nobs=n_obs,
            )
        )

    for p in dropped_exog_cols:
        results.append(
            RegressionResult(
                sample_tag=sample_tag,
                spec_tag=spec_tag,
                model_type="IV",
                outcome=outcome,
                param=p,
                coef=float("nan"),
                se=float("nan"),
                pval=float("nan"),
                pre_mean=pre_mean,
                rkf=None,
                partialF=None,
                nobs=n_obs,
            )
        )

    diag = {
        "demean_iterations": {
            "y": it_y,
            "X_endog": it_xe,
            "X_exog": it_xx,
            "Z": it_z,
        },
        "demean_final_max_abs_update": {
            "y": delta_y,
            "X_endog": delta_xe,
            "X_exog": delta_xx,
            "Z": delta_z,
        },
        "n_obs": n_obs,
        "n_firms": firm_ct,
        "dropped_exog_cols": dropped_exog_cols,
    }
    return results, size, diag


def load_stata_baseline() -> pd.DataFrame:
    require_file(
        STATA_BASELINE,
        nonempty=True,
        purpose="Stata baseline results (firm_scaling_crunchbase_fundraising/consolidated_results.csv)",
    )
    df = pd.read_csv(STATA_BASELINE)
    req = ["sample_tag", "model_type", "outcome", "param", "coef", "se", "pval", "nobs"]
    _require_columns(df, req, context=str(STATA_BASELINE))
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
    """Validate baseline private spec against existing Stata results."""
    report: dict = {"checks": [], "passed": True}

    def _check(model: str, param: str) -> None:
        py = next(
            r
            for r in results
            if r.sample_tag == "matched_private"
            and r.spec_tag == "baseline"
            and r.model_type == model
            and r.outcome == "cb_log1p_raised_usd"
            and r.param == param
        )
        st = _pull_stata_row(stata, sample_tag="private", model=model, outcome="cb_log1p_raised_usd", param=param)

        coef_ok = abs(py.coef - float(st["coef"])) <= tol
        se_ok = abs(py.se - float(st["se"])) <= tol
        n_ok = int(py.nobs) == int(st["nobs"])

        chk = {
            "model": model,
            "param": param,
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

    _check("OLS", "var3")
    _check("OLS", "var4")
    _check("IV", "var3")
    _check("IV", "var4")
    return report


def main() -> None:
    args = parse_args()
    ensure_dir(args.out_dir)

    panel = load_panel()

    # Baseline analysis sample: Crunchbase-matched + private.
    df = panel[(panel["cb_matched"] == 1) & (panel["public"] != 1)].copy()
    df["hq_ny_sf"] = make_hq_ny_sf(df).astype(int)
    df["ever_round"] = compute_ever_round(df).astype(int)

    # Run baseline spec first (for validation).
    all_results: list[RegressionResult] = []
    all_sizes: list[SampleSize] = []
    all_diags: dict[str, dict] = {}

    for outcome in ["cb_log1p_raised_usd", "cb_log_raised_usd"]:
        # Baseline
        res, sz, diag = run_spec(
            df,
            sample_tag="matched_private",
            spec_tag="baseline",
            outcome=outcome,
            endog_cols=["var3"],
            exog_cols=["var4"],
            instr_cols=["var6"],
            fe_cols=["firm_id", "yh_num"],
            cluster_col="firm_id",
            demean_tol=args.tol_demean,
            demean_max_iter=args.max_iter,
        )
        all_results.extend(res)
        all_sizes.append(sz)
        all_diags[f"{outcome}/baseline"] = diag

    # Validate cb_log1p_raised_usd baseline vs Stata results already in repo.
    stata = load_stata_baseline()
    validation = validate_against_stata(all_results, stata, tol=args.tol)
    (args.out_dir / "validation_report.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    if not validation["passed"]:
        raise RuntimeError(
            "Baseline validation against Stata failed. See "
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

    # Interaction spec: var3 + var3_outside, instrumented by var6 + var6_outside.
    interaction = df.copy()
    outside = (interaction["hq_ny_sf"] == 0).astype(int)
    interaction["var3_outside"] = interaction["var3"] * outside
    interaction["var6_outside"] = interaction["var6"] * outside
    variants.append(("geo_interaction", interaction))

    for spec_tag, vdf in variants:
        if spec_tag == "geo_interaction":
            endog = ["var3", "var3_outside"]
            instr = ["var6", "var6_outside"]
        else:
            endog = ["var3"]
            instr = ["var6"]

        res, sz, diag = run_spec(
            vdf,
            sample_tag="matched_private",
            spec_tag=spec_tag,
            outcome=outcome,
            endog_cols=endog,
            exog_cols=["var4"],
            instr_cols=instr,
            fe_cols=["firm_id", "yh_num"],
            cluster_col="firm_id",
            demean_tol=args.tol_demean,
            demean_max_iter=args.max_iter,
        )
        all_results.extend(res)
        all_sizes.append(sz)
        all_diags[f"{outcome}/{spec_tag}"] = diag

    # Persist outputs (CSV schemas match Stata consolidated_results where possible).
    out_rows = [asdict(r) for r in all_results]
    out_df = pd.DataFrame(out_rows)
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
