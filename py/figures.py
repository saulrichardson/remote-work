#!/usr/bin/env python3
"""make_core_figures.py

Generates **firm‑level** binscatter figures for the project.  All plots use
*quantile (equal‑frequency) bins* (Stata‑style `binscatter`) and are written to
`results/figures/`.

Relationships visualised
------------------------
1. **Firm age → remoteness score**  (full sample, age < 50, log‑age)
2. **Teleworkable index → remoteness score**  (single view, **no raw‑scatter backdrop**)
3. **Firm age → post‑COVID growth rate**, split remote vs non‑remote  (full, <50, log‑age)
4. **Firm age → post‑COVID productivity**  (mean worker Q100), split remote vs non‑remote  (full, <50, log‑age)

Inputs (CSV expected under `data/samples/`)
------------------------------------------
* `firm_panel.csv`   – must contain  
  `firm_id`, `age` (years since founding), `remote`, `teleworkable`,
  `growth_rate_we`, `covid`.
* `worker_panel.csv` – must contain  
  `firm_id`, `covid`, `total_contributions_q100`.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

###############################################################################
# 1) Project root: two levels up from this file
###############################################################################
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 2) Data directories
DATA_DIR   = PROJECT_ROOT / "data" / "samples"
OUTPUT_DIR = PROJECT_ROOT / "results" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)   # ensure path exists

# 3) File paths
WORKER_FILE = DATA_DIR / "worker_panel.csv"
FIRM_FILE   = DATA_DIR / "firm_panel.csv"

###############################################################################
# CONSTANTS
###############################################################################
REMOTE_THRESHOLD = 0.5          # firm considered remote if remote_score > 0.5
FIRM_N_BINS      = 10           # quantile bins in all firm‑level charts
COLOURS          = {True: "blue", False: "orange"}

###############################################################################
# HELPER FUNCTIONS
###############################################################################

def _binscatter_quantile(df: pd.DataFrame, x: str, y: str, q: int):
    """Return X‑midpoints and Y‑means for *q* equal‑frequency bins."""
    tmp = df[[x, y]].dropna().copy()
    tmp["bin"] = pd.qcut(tmp[x], q=q, duplicates="drop")
    means   = tmp.groupby("bin", observed=False)[y].mean()  # observed=False silences FutureWarning
    centres = [interval.mid for interval in means.index.categories]
    return centres, means.values


def _plot_bins_reg(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    q: int,
    xlabel: str,
    ylabel: str,
    title: str,
    file_stem: str,
    split_col: str | None = None,
):
    """Quantile‑binscatter with optional remote split and OLS overlay."""
    plt.figure(figsize=(10, 6))

    groups = data.groupby(split_col) if split_col else [("All", data)]
    for key, grp in groups:
        # skip groups with insufficient data points or variation
        grp_valid = grp.dropna(subset=[x, y])
        if len(grp_valid) < 3 or grp_valid[x].nunique() < 2:
            continue
        # adjust number of bins to avoid non-unique edges
        group_q = min(q, grp_valid[x].nunique() - 1)
        colour   = COLOURS.get(key, "black")
        xs, ys   = _binscatter_quantile(grp_valid, x, y, group_q)
        label_bs = (
            f"{'Remote' if key else 'Non‑remote'} (Binscatter)"
            if split_col else "Binscatter"
        )
        plt.plot(xs, ys, "o-", linewidth=2, color=colour, label=label_bs)

        model  = smf.ols(f"{y} ~ {x}", data=grp_valid).fit()
        x_vals = np.linspace(grp_valid[x].min(), grp_valid[x].max(), 100)
        y_vals = model.predict(pd.DataFrame({x: x_vals}))
        label_ols = (
            f"{'Remote' if key else 'Non‑remote'} (OLS)"
            if split_col else "OLS"
        )
        plt.plot(x_vals, y_vals, "--", linewidth=2, color=colour, label=label_ols)

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"{file_stem}.png", dpi=500)
    plt.close()

###############################################################################
# MAIN WORKFLOW
###############################################################################

def main():
    # ────────────────────────── READ DATA ────────────────────────────
    firms   = pd.read_csv(FIRM_FILE)
    workers = pd.read_csv(WORKER_FILE)

    # ────────────────── BUILD FIRM‑LEVEL PRODUCTIVITY ────────────────
    prod = (
        workers[workers["covid"] == 1]
        .groupby("firm_id", observed=False)["total_contributions_q100"]
        .mean()
        .rename("q100")
    )
    firms = firms.merge(prod, on="firm_id", how="left")

    # remote indicator used in several plots, preserve missingness
    firms["is_remote"] = np.where(
        firms["remote"].isna(),
        np.nan,
        firms["remote"] > REMOTE_THRESHOLD
    )

    # ───────── 1) Firm age → Remoteness (3 variants) ─────────
    # full sample age-based plot (all ages)
    _plot_bins_reg(
        firms,
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Remoteness score",
        title="Firm age vs Remoteness", file_stem="firm_age_remote_full",
    )
    # apply age < 100 cutoff for age-based plots
    _plot_bins_reg(
        firms[firms["age"] < 100],
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age (<100 years)", ylabel="Remoteness score",
        title="Firm age < 100 vs Remoteness", file_stem="firm_age_lt100_remote",
    )

    _plot_bins_reg(
        firms[firms["age"] < 50],
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Remoteness score",
        title="Firm age < 50 vs Remoteness", file_stem="firm_age_lt50_remote",
    )

    # log-age plot: drop non-positive and extreme ages before logging
    firms_log = firms[(firms["age"] > 0) & (firms["age"] < 100)].copy()
    firms_log["log_age"] = np.log(firms_log["age"])
    _plot_bins_reg(
        firms_log,
        x="log_age", y="remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Remoteness score",
        title="log(Firm age) vs Remoteness", file_stem="firm_logage_remote",
    )

    # ───────── 2) Teleworkable → Remoteness (single view, no raw scatter) ─────────
    _plot_bins_reg(
        firms,
        x="teleworkable", y="remote", q=FIRM_N_BINS,
        xlabel="Teleworkable index", ylabel="Remoteness score",
        title="Teleworkable vs Remoteness", file_stem="firm_teleworkable_remote",
    )

    # ───────── 3) Firm age → Growth rate (post‑COVID, split) ─────────
    post = firms[firms["covid"] == 1].copy()
    # full sample post-COVID age-based growth plot (all ages)
    _plot_bins_reg(
        post, x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Growth rate (WE)",
        title="Firm age vs Growth Rate (Post-COVID)", file_stem="firm_age_growth_full",
    )
    # apply age < 100 cutoff to post-COVID age-based growth plots
    _plot_bins_reg(
        post[post["age"] < 100], x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<100 years)", ylabel="Growth rate (WE)",
        title="Firm age < 100 vs Growth Rate (Post-COVID)", file_stem="firm_age_lt100_growth",
    )

    _plot_bins_reg(
        post[post["age"] < 50], x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Growth rate (WE)",
        title="Firm age < 50 vs Growth Rate (Post‑COVID)", file_stem="firm_age_lt50_growth",
    )

    # log-age plot for growth: drop non-positive ages before logging
    post_log = post[post["age"] > 0].copy()
    post_log["log_age"] = np.log(post_log["age"])
    _plot_bins_reg(
        post_log, x="log_age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Growth rate (WE)",
        title="log(Firm age) vs Growth Rate (Post-COVID)", file_stem="firm_logage_growth",
    )

    # ───────── 4) Firm age → Productivity (mean Q100, post‑COVID, split) ─────────
    prod_df = firms[firms["q100"].notna()].copy()  # firms with at least one worker obs post‑COVID
    # full sample post-COVID age-based productivity plot (all ages)
    _plot_bins_reg(
        prod_df, x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Mean worker Q100 (post-COVID)",
        title="Firm age vs Productivity (Post-COVID)", file_stem="firm_age_q100_full",
    )
    # apply age < 100 cutoff to productivity age-based plots
    _plot_bins_reg(
        prod_df[prod_df["age"] < 100], x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<100 years)", ylabel="Mean worker Q100 (post-COVID)",
        title="Firm age < 100 vs Productivity (Post-COVID)", file_stem="firm_age_lt100_q100",
    )

    _plot_bins_reg(
        prod_df[prod_df["age"] < 50], x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Mean worker Q100 (post‑COVID)",
        title="Firm age < 50 vs Productivity (Post‑COVID)", file_stem="firm_age_lt50_q100",
    )

    # log-age plot for productivity: drop non-positive ages before logging
    prod_log = prod_df[prod_df["age"] > 0].copy()
    prod_log["log_age"] = np.log(prod_log["age"])
    _plot_bins_reg(
        prod_log, x="log_age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Mean worker Q100 (post-COVID)",
        title="log(Firm age) vs Productivity (Post-COVID)", file_stem="firm_logage_q100",
    )

if __name__ == "__main__":
    main()

