#!/usr/bin/env python3
from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw" / "user_prod_expost_breadth_split_precovid"
OUT = ROOT / "results" / "cleaned" / "user_expost_breadth_table.tex"
DELTA = ROOT / "data" / "processed" / "firm_msa_delta.csv"

PARAM_LABELS = {
    "var3": "Remote x Post",
    "var5": "Remote x Post x Startup",
}

def starify(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""

def load():
    iv = pd.read_csv(RAW / "iv_by_expansion.csv")
    ols = pd.read_csv(RAW / "ols_by_expansion.csv")
    # format
    for df in (iv, ols):
        df["coef3_fmt"] = df.apply(lambda r: f"{r.coef3:.2f}{starify(r.pval3)}", axis=1)
        df["se3_fmt"]   = df.se3.map(lambda s: f"({s:.2f})")
        df["coef5_fmt"] = df.apply(lambda r: f"{r.coef5:.2f}{starify(r.pval5)}", axis=1)
        df["se5_fmt"]   = df.se5.map(lambda s: f"({s:.2f})")
    return iv, ols

def build_table(iv: pd.DataFrame, ols: pd.DataFrame) -> str:
    buckets = sorted(iv["bucket"].unique())
    L = []
    L.append("\\begin{table}[H]")
    L.append("\\centering")
    L.append("\\caption{Productivity by Ex-Post CBSA Expansion (2 user bins)}")
    L.append("\\begin{tabular}{l" + "c" * len(buckets) + "}")
    L.append("\\hline")
    header_bins = " & ".join([f"Bin {int(b)}" for b in buckets])
    L.append("Variable & " + header_bins + " \\")
    

    def block(title: str, df: pd.DataFrame, show_kp: bool):
        # No explicit panel row; keep panels separated by hlines
        # var3
        vals = [df.loc[df.bucket==b, "coef3_fmt"].values[0] for b in buckets]
        ses  = [df.loc[df.bucket==b, "se3_fmt"].values[0] for b in buckets]
        L.append(PARAM_LABELS["var3"] + " & " + " & ".join(vals) + " \\")
        L.append(" & " + " & ".join(ses) + " \\")
        # var5
        vals = [df.loc[df.bucket==b, "coef5_fmt"].values[0] for b in buckets]
        ses  = [df.loc[df.bucket==b, "se5_fmt"].values[0] for b in buckets]
        L.append(PARAM_LABELS["var5"] + " & " + " & ".join(vals) + " \\")
        L.append(" & " + " & ".join(ses) + " \\")
        # footer
        nvals = [f"{int(df.loc[df.bucket==b, 'nobs'].values[0]):,}" for b in buckets]
        L.append("N & " + " & ".join(nvals) + " \\")
        if show_kp and "rkf" in df.columns:
            kvals = [f"{df.loc[df.bucket==b, 'rkf'].values[0]:.2f}" for b in buckets]
            L.append("KP Wald F & " + " & ".join(kvals) + " \\")
        L.append("\\hline")

    block("Panel A: OLS", ols, show_kp=False)
    block("Panel B: IV",  iv,  show_kp=True)

    # Notes: difference, and minimal prose + summary stats
    note_lines = []
    try:
        b1 = float(iv.loc[iv.bucket==buckets[0], 'coef5'].values[0])
        s1 = float(iv.loc[iv.bucket==buckets[0], 'se5'].values[0])
        b2 = float(iv.loc[iv.bucket==buckets[1], 'coef5'].values[0])
        s2 = float(iv.loc[iv.bucket==buckets[1], 'se5'].values[0])
        diff = b2 - b1
        z = diff / math.sqrt(s1*s1 + s2*s2) if (s1>0 and s2>0) else float('nan')
        p = math.erfc(abs(z)/math.sqrt(2)) if math.isfinite(z) else float('nan')
        note_lines.append(f"\\noindent Var5 (IV) difference, Bin 2$-$Bin 1: {diff:.2f}, p={p:.3f}")
    except Exception:
        pass

    # Minimal prose on dispersion construction and summary stats
    try:
        d = pd.read_csv(DELTA)
        dpos = (pd.to_numeric(d['delta_hc5r1'], errors='coerce') > 0).mean()
        dmean = pd.to_numeric(d['delta_hc5r1'], errors='coerce').mean()
        dmed = pd.to_numeric(d['delta_hc5r1'], errors='coerce').median()
        note_lines.append("\\smallskip")
        note_lines.append("\\noindent Notes: CBSA$\\equiv$MSA. Dispersion per half-year is the number of CBSAs with headcount $\\ge 5$ and share $\\ge 1\\%$ of firm headcount (\\emph{hc5r1}). Bins are two equal user quantiles of $\\Delta=$ average(post) $-$ average(pre).")
        note_lines.append(f"\\noindent Summary: $\\Delta_{{hc5r1}}$ mean = {dmean:.2f}, median = {dmed:.2f}, share($>0$) = {100*dpos:.1f}\\%.")
    except Exception:
        pass

    L.append("\\hline")
    L.append("\\end{tabular}")
    L.append("\\label{tab:user_expost_breadth}")
    L.append("\\end{table}")
    return "\n".join(L + ["", *note_lines])

def main():
    iv, ols = load()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_table(iv, ols), encoding="utf-8")
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
