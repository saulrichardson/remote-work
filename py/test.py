#!/usr/bin/env python3
# partial_plot_growth_pyhdf.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pyhdfe               # pip install pyhdfe
from pathlib import Path

# ── Paths & Constants ────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).resolve().parent.parent
DATA_DIR      = PROJECT_ROOT / "data" / "samples"
OUTPUT_DIR    = PROJECT_ROOT / "results" / "figures"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

REMOTE_THRESH = 0.5
FIRM_N_BINS   = 10
COLOURS       = {True: "blue", False: "orange"}

# ── Helper: equal‐freq binscatter ────────────────────────────────────
def _binscatter_quantile(xs, ys, q):
    df2 = pd.DataFrame({"rx": xs, "ry": ys}).dropna()
    df2["bin"] = pd.qcut(df2["rx"], q=q, duplicates="drop")
    means   = df2.groupby("bin")["ry"].mean()
    mids    = [iv.mid for iv in means.index.categories]
    return mids, means.values

# ── Partial‐scatter via PyHDFE ───────────────────────────────────────
def _partial_plot_growth_pyhdf(
    firms: pd.DataFrame,
    x: str,
    y: str,
    fe_cols: list[str],
    split_col: str,
    q: int,
    xlabel: str,
    ylabel: str,
    title: str,
    file_stem: str,
):
    """
    Absorb fixed effects via PyHDFE, then binscatter residuals of y~x,
    split by split_col.
    """
    plt.figure(figsize=(10,6))

    for key, grp in firms.groupby(split_col):
        sub = grp.dropna(subset=[x, y] + fe_cols)
        if len(sub) < 3 or sub[x].nunique() < 2:
            print(key,
              "n =", len(sub),
              "uniq_x =", sub[x].nunique())
            continue

        # 1) Build the FE‐ID matrix and initialize PyHDFE
        #    each row is one observation, cols are firm_id & yh
        fe_ids = sub[fe_cols].to_numpy()
        alg    = pyhdfe.create(fe_ids)  #  [oai_citation:0‡PyHDFE](https://pyhdfe.readthedocs.io/en/stable/_api/pyhdfe.create.html) [oai_citation:1‡PyHDFE](https://pyhdfe.readthedocs.io/en/latest/_api/pyhdfe.Algorithm.residualize.html?utm_source=chatgpt.com)

        # 2) Residualize both x and y together
        mat    = sub[[x, y]].to_numpy()
        resids = alg.residualize(mat)   # returns array (n_obs, 2)  [oai_citation:2‡PyHDFE](https://pyhdfe.readthedocs.io/en/latest/_api/pyhdfe.Algorithm.residualize.html?utm_source=chatgpt.com)
        rx, ry = resids[:,0], resids[:,1]

        # 3) Quantile‐binscatter on the residuals
        xs, ys = _binscatter_quantile(rx, ry, q)

        colour = COLOURS.get(key, "black")
        label  = "Remote" if key else "Non-remote"
        plt.plot(xs, ys, "o-", lw=2, color=colour, label=label)

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"{file_stem}.png", dpi=500)
    plt.close()

# ── Main workflow ───────────────────────────────────────────────────
def main():
    firms = pd.read_csv(DATA_DIR / "firm_panel.csv")
    firms["is_remote"] = np.where(
        firms["remote"].isna(),
        np.nan,
        firms["remote"] > REMOTE_THRESH
    )
    post = firms[firms["covid"] == 1].copy()

    _partial_plot_growth_pyhdf(
        post,
        x="age",
        y="growth_rate_we",
        fe_cols=["firm_id", "yh"],                # same as absorb(firm_id yh)
        split_col="is_remote",
        q=FIRM_N_BINS,
        xlabel="Firm age (demeaned by FEs)",
        ylabel="Growth rate WE (demeaned by FEs)",
        title="Partial Binscatter: Age → Growth Rate (Post-COVID)",
        file_stem="firm_age_growth_partial_pyhdf",
    )

if __name__ == "__main__":
    main()
