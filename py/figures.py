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
* `user_panel.csv` – must contain
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
WORKER_FILE = DATA_DIR / "user_panel.csv"   # worker-level sample
FIRM_FILE   = DATA_DIR / "firm_panel.csv"

###############################################################################
# CONSTANTS
###############################################################################
REMOTE_THRESHOLD = 0.5          # firm considered remote if remote_score > 0.5
FIRM_N_BINS      = 60           # quantile bins in all firm‑level charts
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
    file_stem: str,
    split_col: str | None = None,
):
    """Quantile‑binscatter with optional remote split and OLS overlay."""
    plt.figure(figsize=(10, 6))
    ax = plt.gca()

    if y in {"remote", "teleworkable"}:
        y_vals = data[y].dropna()
        if not y_vals.empty:
            y_min, y_max = y_vals.min(), y_vals.max()
            for level in np.linspace(y_min, y_max, 5):
                ax.axhline(
                    level,
                    color="gray",
                    linewidth=0.8,
                    alpha=0.4,
                    zorder=0,
                )

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
        plt.plot(xs, ys, "o", linewidth=2, color=colour, label=label_bs)

        model  = smf.ols(f"{y} ~ {x}", data=grp_valid).fit()
        slope = model.params[x]
        r2    = model.rsquared
        x_vals = np.linspace(grp_valid[x].min(), grp_valid[x].max(), 100)
        y_vals = model.predict(pd.DataFrame({x: x_vals}))
        label_ols = (
            f"{'Remote' if key else 'Non‑remote'} (OLS)"
            if split_col else "OLS"
        )
        plt.plot(x_vals, y_vals, linewidth=2, color=colour, label=label_ols)

        if x == "teleworkable" and y == "remote":
            slope = model.params[x]
            se    = model.bse[x]
            r2    = model.rsquared
            # Keep each line fully inside its own $…$ block; this avoids
            # mathtext errors in newer Matplotlib versions.
            anno_text = (
                rf"$\beta = {slope:.2f}\;({se:.2f})$"  # first line
                "\n"
                rf"$R^2 = {r2:.2f}$"                        # second line
            )

            if split_col is None:
                # pick corner with fewest nearby points
                x_mid, y_mid = grp_valid[x].median(), grp_valid[y].median()
                counts = {
                    "tl": ((grp_valid[x] < x_mid) & (grp_valid[y] > y_mid)).sum(),
                    "tr": ((grp_valid[x] > x_mid) & (grp_valid[y] > y_mid)).sum(),
                    "bl": ((grp_valid[x] < x_mid) & (grp_valid[y] < y_mid)).sum(),
                    "br": ((grp_valid[x] > x_mid) & (grp_valid[y] < y_mid)).sum(),
                }
                corner = min(counts, key=counts.get)
                corners = {
                    "tl": (0.05, 0.95, "left", "top"),
                    "tr": (0.95, 0.95, "right", "top"),
                    "bl": (0.05, 0.05, "left", "bottom"),
                    "br": (0.95, 0.05, "right", "bottom"),
                }
                base_x, base_y, ha, va = corners[corner]
            else:
                base_x, base_y = 0.05, 0.90
                if key:
                    base_y -= 0.10
                ha, va = "left", "top"

            ax.text(
                base_x,
                base_y,
                anno_text,
                transform=ax.transAxes,
                fontsize=11,
                horizontalalignment=ha,
                verticalalignment=va,
                color=colour,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="white",
                    alpha=0.6,
                    edgecolor=colour,
                ),
            )


    ax.tick_params(axis="both", labelsize=12)
    plt.xlabel(xlabel, fontsize=14)
    plt.ylabel(ylabel, fontsize=14)
    #plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"{file_stem}.png", dpi=500)
    plt.close()

###############################################################################
# MAIN WORKFLOW
###############################################################################

def main():
    # ────────────────────────── READ DATA ────────────────────────────
    firms   = pd.read_csv(FIRM_FILE)
    # keep a single observation per firm (sorted by yh) for remoteness plots
    firms_unique = firms.sort_values("yh").drop_duplicates("firm_id")
    # later growth/productivity figures use the full `firms` DataFrame
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

    # ───────── 1) Firm age → Remoteness (3 variants, unique firms) ─────────
    # full sample age-based plot (all ages)
    _plot_bins_reg(
        firms_unique,
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Remoteness score",
        file_stem="firm_age_remote_full",
    )
    # apply age < 100 cutoff for age-based plots
    _plot_bins_reg(
        firms_unique[firms_unique["age"] < 100],
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age", ylabel="Remoteness score",
        file_stem="firm_age_lt100_remote",
    )

    _plot_bins_reg(
        firms_unique[firms_unique["age"] < 50],
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Remoteness score",
        file_stem="firm_age_lt50_remote",
    )

    # log-age plot: drop non-positive and extreme ages before logging
    firms_log = firms_unique[(firms_unique["age"] > 0) & (firms_unique["age"] < 100)].copy()
    firms_log["log_age"] = np.log(firms_log["age"])
    _plot_bins_reg(
        firms_log,
        x="log_age", y="remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Remoteness score",
        file_stem="firm_logage_remote",
    )

    # ───────── 2) Teleworkable → Remoteness (single view, no raw scatter)
    #           (using the deduplicated firm set) ─────────
    _plot_bins_reg(
        firms_unique,
        x="teleworkable", y="remote", q=FIRM_N_BINS,
        xlabel="Teleworkable index", ylabel="Remoteness score",
        file_stem="firm_teleworkable_remote",
    )

"""
    # ───────── 3) Firm age → Growth rate (post‑COVID, split) ─────────
    post = firms[firms["covid"] == 1].copy()
    # full sample post-COVID age-based growth plot (all ages)
    _plot_bins_reg(
        post, x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Growth rate (WE)",
        file_stem="firm_age_growth_full",
    )
    # apply age < 100 cutoff to post-COVID age-based growth plots
    _plot_bins_reg(
        post[post["age"] < 100], x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<100 years)", ylabel="Growth rate (WE)",
        file_stem="firm_age_lt100_growth",
    )

    _plot_bins_reg(
        post[post["age"] < 50], x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Growth rate (WE)",
        file_stem="firm_age_lt50_growth",
    )

    # log-age plot for growth: drop non-positive ages before logging
    post_log = post[post["age"] > 0].copy()
    post_log["log_age"] = np.log(post_log["age"])
    _plot_bins_reg(
        post_log, x="log_age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Growth rate (WE)",
        file_stem="firm_logage_growth",
    )

    # ───────── 4) Firm age → Productivity (mean Q100, post‑COVID, split) ─────────
    prod_df = firms[firms["q100"].notna()].copy()  # firms with at least one worker obs post‑COVID
    # full sample post-COVID age-based productivity plot (all ages)
    _plot_bins_reg(
        prod_df, x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Mean worker Q100 (post-COVID)",
        file_stem="firm_age_q100_full",
    )
    # apply age < 100 cutoff to productivity age-based plots
    _plot_bins_reg(
        prod_df[prod_df["age"] < 100], x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<100 years)", ylabel="Mean worker Q100 (post-COVID)",
        file_stem="firm_age_lt100_q100",
    )

    _plot_bins_reg(
        prod_df[prod_df["age"] < 50], x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Mean worker Q100 (post‑COVID)",
        file_stem="firm_age_lt50_q100",
    )

    # log-age plot for productivity: drop non-positive ages before logging
    prod_log = prod_df[prod_df["age"] > 0].copy()
    prod_log["log_age"] = np.log(prod_log["age"])
    _plot_bins_reg(
        prod_log, x="log_age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Mean worker Q100 (post-COVID)",
        file_stem="firm_logage_q100",
    )

"""
if __name__ == "__main__":
    main()

