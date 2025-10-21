#!/usr/bin/env python3
from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw" / "het_pre_dispersion_precovid_2"
OUT = ROOT / "results" / "cleaned" / "user_pre_dispersion_table.tex"

PARAM_LABELS = {
    "var3": "$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) $",
    "var5": "$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) \\times \\text{Startup} $",
}

def starify(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""

def load():
    iv = pd.read_csv(RAW / "var5_pre_dispersion_base.csv")
    ols = pd.read_csv(RAW / "var5_pre_dispersion_base_ols.csv")
    # Format strings
    for df in (iv, ols):
        df["coef3_fmt"] = df.apply(
            lambda r: f"{r.coef3:.2f}{starify(r.pval3)}", axis=1
        )
        df["se3_fmt"] = df.se3.map(lambda s: f"({s:.2f})")
        df["coef5_fmt"] = df.apply(
            lambda r: f"{r.coef5:.2f}{starify(r.pval5)}", axis=1
        )
        df["se5_fmt"] = df.se5.map(lambda s: f"({s:.2f})")
    return iv, ols

def build_table(iv, ols):
    buckets = sorted(iv["bucket"].unique())
    avgmap = dict(zip(iv.bucket, iv.avg_msa))

    L = []
    L.append("\\begin{table}[H]")
    L.append("\\centering")
    L.append("\\caption{Productivity by Pre-Period Location Dispersion (2019 MSAs)}")
    L.append("\\begin{tabular}{l" + "c" * len(buckets) + "}")
    L.append("\\toprule")
    header_bins = " & ".join([f"Bin {b}" for b in buckets])
    L.append(" & " + header_bins + " " + ("\\"*2))
    avg_vals = " & ".join([f"{avgmap.get(b, float('nan')):.2f}" for b in buckets])
    L.append("Avg. MSAs (2019) & " + avg_vals + " " + ("\\"*2))
    L.append("\\midrule")

    def block(title, df, show_kp):
        L.append(f"\\multicolumn{{{len(buckets)+1}}}{{l}}{{\\textbf{{\\uline{{{title}}}}}}} " + ("\\"*2))
        L.append("\\addlinespace")
        # var3
        vals = [df.loc[df.bucket==b, "coef3_fmt"].values[0] for b in buckets]
        ses  = [df.loc[df.bucket==b, "se3_fmt"].values[0] for b in buckets]
        L.append(PARAM_LABELS["var3"] + " & " + " & ".join(vals) + " " + ("\\"*2))
        L.append(" & " + " & ".join(ses) + " " + ("\\"*2))
        # var5
        vals = [df.loc[df.bucket==b, "coef5_fmt"].values[0] for b in buckets]
        ses  = [df.loc[df.bucket==b, "se5_fmt"].values[0] for b in buckets]
        L.append(PARAM_LABELS["var5"] + " & " + " & ".join(vals) + " " + ("\\"*2))
        L.append(" & " + " & ".join(ses) + " " + ("\\"*2))
        # footer
        nvals = [f"{int(df.loc[df.bucket==b, 'nobs'].values[0]):,}" for b in buckets]
        L.append("N & " + " & ".join(nvals) + " " + ("\\"*2))
        if show_kp:
            kvals = [f"{df.loc[df.bucket==b, 'rkf'].values[0]:.2f}" for b in buckets]
            L.append("KP\\,rk Wald F & " + " & ".join(kvals) + " " + ("\\"*2))
        L.append("\\midrule")

    block("Panel A: OLS", ols, show_kp=False)
    block("Panel B: IV",  iv,  show_kp=True)

    L.append("\\bottomrule")
    L.append("\\end{tabular}")
    L.append("\\label{tab:user_pre_dispersion}")
    L.append("\\end{table}")

    # Outside-the-table note: test var5 equality across bins in IV
    note_lines = []
    if len(buckets) >= 2:
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

    return "\n".join(L + ["", *note_lines])

def main():
    iv, ols = load()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_table(iv, ols), encoding="utf-8")
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
