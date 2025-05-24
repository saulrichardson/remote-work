#!/usr/bin/env python3
# partial_binscatter.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

def partial_binscatter(
    df: pd.DataFrame,
    x: str,
    y: str,
    fe_cols: list[str],
    q: int = 20,
    xlabel: str | None = None,
    ylabel: str | None = None,
    title: str | None = None,
):
    """
    Frisch–Waugh–Lovell binscatter of y vs x, net of fixed effects.
    """
    fe_terms = " + ".join(f"C({c})" for c in fe_cols)
    df = df.copy()
    df["_rx"] = smf.ols(f"{x} ~ {fe_terms}", data=df).fit().resid
    df["_ry"] = smf.ols(f"{y} ~ {fe_terms}", data=df).fit().resid

    tmp = df[["_rx", "_ry"]].dropna()
    tmp["bin"] = pd.qcut(tmp["_rx"], q=q, duplicates="drop")
    mean_ry = tmp.groupby("bin")["_ry"].mean()
    mids    = [interval.mid for interval in mean_ry.index.categories]

    plt.figure(figsize=(8, 6))
    plt.plot(mids, mean_ry.values, "o", lw=2, label="Binscatter")

    coef, intercept = np.polyfit(tmp["_rx"], tmp["_ry"], 1)
    xs = np.linspace(tmp["_rx"].min(), tmp["_rx"].max(), 100)
    plt.plot(xs, coef * xs + intercept, "--", lw=2, label="OLS")

    plt.xlabel(xlabel or f"{x} (net of FEs)")
    plt.ylabel(ylabel or f"{y} (net of FEs)")
    # omit title for cleaner output
    plt.legend()
    plt.tight_layout()
    plt.show()

    return coef

if __name__ == "__main__":
    panel = pd.read_csv("../data/samples/user_panel.csv")

    slope = partial_binscatter(
        df=panel,
        x="var3",                         # your regressor
        y="total_contributions_q100",     # your outcome
        fe_cols=["user_id", "firm_id", "yh"],  # same absorbs() in Stata
        q=20,
        xlabel="Var3 (residualized)",
        ylabel="Productivity (residualized)",
    )

    print(f"Net OLS slope on var3 (matches reghdfe): {slope:.4f}")

