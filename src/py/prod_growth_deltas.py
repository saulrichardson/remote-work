#!/usr/bin/env python3
"""Build firm-level productivity and growth deltas for diagnostics.

Outputs:
  - results/diagnostics/prod_growth_diff_balanced.dta
  - results/diagnostics/prod_growth_diff_balanced.csv

Computation (aligned with discussion):
  • For each user–firm, compute pre/post mean contribution rank and the within-user delta.
  • At the firm level, take the median and mean of user deltas + the user count.
  • Compute firm-level pre/post mean growth_rate_we and take the delta.
  • Keep remote/startup flags from the firm panel; remote_flag = (remote ≥ 1) is hard-coded.

Notes:
  - Pre period: yh < 120 (pre-2020H1); Post: yh >= 120, matching Stata scripts.
  - Uses only existing processed panels; no raw inputs required.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from project_paths import DATA_PROCESSED, RESULTS_DIR, ensure_dir


COVID_CUTOFF_DATE = pd.Timestamp("2020-01-01")


def build_deltas(
    user_panel: Path,
    firm_panel: Path,
    remote_threshold: float = 1.0,
    out_dir: Path | None = None,
) -> tuple[pd.DataFrame, Path, Path]:
    out_dir = ensure_dir(out_dir or RESULTS_DIR / "diagnostics")

    # ---------- User-side: within-user rank deltas ----------
    user_cols = ["user_id", "firm_id", "yh", "total_contributions_q100"]
    users = pd.read_stata(user_panel, columns=user_cols)
    users = users.dropna(subset=user_cols)
    users["yh_dt"] = pd.to_datetime(users["yh"], errors="coerce")
    users = users.dropna(subset=["yh_dt"])

    pre_users = (
        users.loc[users["yh_dt"] < COVID_CUTOFF_DATE]
        .groupby(["user_id", "firm_id"], as_index=False)["total_contributions_q100"]
        .mean()
        .rename(columns={"total_contributions_q100": "rank_pre"})
    )
    post_users = (
        users.loc[users["yh_dt"] >= COVID_CUTOFF_DATE]
        .groupby(["user_id", "firm_id"], as_index=False)["total_contributions_q100"]
        .mean()
        .rename(columns={"total_contributions_q100": "rank_post"})
    )

    deltas = pre_users.merge(post_users, on=["user_id", "firm_id"], how="inner")
    deltas = deltas.dropna(subset=["rank_pre", "rank_post"])
    deltas["delta_rank"] = deltas["rank_post"] - deltas["rank_pre"]

    firm_rank = (
        deltas.groupby("firm_id")
        .agg(
            d_rank_med=("delta_rank", "median"),
            d_rank_mean=("delta_rank", "mean"),
            n_users=("delta_rank", "size"),
        )
        .reset_index()
    )

    # drop firms with no balanced users
    firm_rank = firm_rank.dropna(subset=["d_rank_med", "d_rank_mean"]).reset_index(drop=True)

    # ---------- User-side: firm-level mean rank levels (composition-inclusive) ----------
    pre_level = (
        users.loc[users["yh_dt"] < COVID_CUTOFF_DATE]
        .groupby("firm_id")["total_contributions_q100"]
        .mean()
        .rename("rank_pre_all")
    )
    post_level = (
        users.loc[users["yh_dt"] >= COVID_CUTOFF_DATE]
        .groupby("firm_id")["total_contributions_q100"]
        .mean()
        .rename("rank_post_all")
    )

    firm_level = pre_level.to_frame().join(post_level, how="outer")
    firm_level["diff_rank_level"] = firm_level["rank_post_all"] - firm_level["rank_pre_all"]
    n_users_all = users.groupby("firm_id")["user_id"].nunique().rename("n_users_all")
    firm_level = firm_level.join(n_users_all, how="left").reset_index()

    # ---------- Firm-side: growth deltas ----------
    firm_cols = ["firm_id", "yh", "growth_rate_we", "startup", "remote"]
    firms = pd.read_stata(firm_panel, columns=firm_cols)
    firms = firms.dropna(subset=["firm_id", "yh", "growth_rate_we"])
    firms["yh_dt"] = pd.to_datetime(firms["yh"], errors="coerce")
    firms = firms.dropna(subset=["yh_dt"])

    g_pre = (
        firms.loc[firms["yh_dt"] < COVID_CUTOFF_DATE]
        .groupby("firm_id")["growth_rate_we"]
        .mean()
        .rename("g_pre")
    )
    g_post = (
        firms.loc[firms["yh_dt"] >= COVID_CUTOFF_DATE]
        .groupby("firm_id")["growth_rate_we"]
        .mean()
        .rename("g_post")
    )
    basics = firms.groupby("firm_id").agg(startup=("startup", "first"), remote=("remote", "first"))

    growth = basics.join(g_pre, how="left").join(g_post, how="left").reset_index()
    growth["diff_growth"] = growth["g_post"] - growth["g_pre"]
    # Remote-only: flag true only for fully remote firms. Threshold is fixed at 1.0.
    growth["remote_flag"] = growth["remote"] >= remote_threshold

    growth = growth.dropna(subset=["g_pre", "g_post", "diff_growth"])

    # ---------- Merge & export ----------
    merged = firm_rank.merge(firm_level, on="firm_id", how="inner")
    merged = merged.merge(growth, on="firm_id", how="inner")
    merged = merged.dropna(subset=["d_rank_med", "diff_growth", "diff_rank_level"])

    out_dta = out_dir / "prod_growth_diff_balanced.dta"
    out_csv = out_dir / "prod_growth_diff_balanced.csv"

    merged.to_stata(out_dta, write_index=False)
    merged.to_csv(out_csv, index=False)

    return merged, out_dta, out_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Remote threshold is fixed at 1.0 (fully remote). CLI override removed to avoid drift.
    args = parser.parse_args([])

    user_panel = DATA_PROCESSED / "user_panel_precovid.dta"
    firm_panel = DATA_PROCESSED / "firm_panel.dta"

    merged, out_dta, out_csv = build_deltas(
        user_panel=user_panel,
        firm_panel=firm_panel,
        remote_threshold=1.0,
        out_dir=RESULTS_DIR / "diagnostics",
    )

    print(f"Wrote {len(merged)} firm rows to:\n  {out_dta}\n  {out_csv}")


if __name__ == "__main__":
    main()
