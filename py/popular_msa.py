#!/usr/bin/env python3
# ---------------------------------------------------------------------------
#  Most-popular MSA per company × half-year  (counts every spell in each half)
#  Only MSAs that have a valid CBSA/FIPS code are considered.
# ---------------------------------------------------------------------------
#  pip install pandas tqdm pyarrow
# ---------------------------------------------------------------------------

import pandas as pd, argparse
from pathlib import Path
from collections import defaultdict, Counter
from tqdm import tqdm

# ── directories (match your Stata globals) ─────────────────────────────────
RAW_DIR       = Path("../data/raw")
PROC_DIR      = Path("../data/processed")
RES_DIR       = Path("../data/raw")

SPELL_CSV = RAW_DIR / "Scoop_workers_positions.csv"
ENRICH_CSV = PROC_DIR / "enriched_msa.csv"
OUT_CSV    = RES_DIR / "company_top_msa_by_half.csv"

# ── CLI flags ──────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--test_rows",  type=int, default=None,
                help="process only first N rows (debug)")
ap.add_argument("--chunk_rows", type=int, default=1_000_000,
                help="rows per pandas chunk (default 1e6)")
args = ap.parse_args()

print(f"test_rows = {args.test_rows or 'ALL'}   chunk_rows = {args.chunk_rows}")

# ── diagnostic counters ─────────────────────────────────────────────────---
invalid_date_rows = 0   # rows dropped because start_date invalid or missing
filled_end_rows  = 0    # rows where end_date filled with start_date
unknown_msa_rows = 0    # spells skipped due to unknown MSA → no CBSA code

# ── 1 ▸ enrichment lookup: msa-name → (cbsacode, lat, lon) ─────────────────
enrich = pd.read_csv(
    ENRICH_CSV,
    usecols=["msa", "cbsacode", "lat", "lon"],
    dtype={"msa": str}
)
enrich["cbsacode"] = pd.to_numeric(enrich["cbsacode"], errors="coerce").astype("Int64")
lookup = {
    row.msa: (row.cbsacode, row.lat, row.lon)
    for row in enrich.itertuples(index=False)
    if pd.notna(row.cbsacode)          # keep only MSAs with a real FIPS code
}
del enrich

# ── helper: iterate over every half-year a spell overlaps ──────────────────
def half_span(start: pd.Timestamp, end: pd.Timestamp):
    """Yield (year, half) tuples for all half-years overlapping [start,end]."""
    year, half = start.year, 1 if start.month <= 6 else 2
    while True:
        yield year, half
        # move to next half-year
        if half == 1:
            boundary = pd.Timestamp(year, 7, 1)
            if boundary > end:
                break
            half = 2
        else:
            boundary = pd.Timestamp(year + 1, 1, 1)
            if boundary > end:
                break
            year, half = year + 1, 1

# ── 2 ▸ stream spell file and accumulate counts ───────────────────────────
presence = defaultdict(Counter)   # key = (company, year, half) → Counter({cbsa: spells})

usecols = ["companyname", "msa", "start_date", "end_date"]
reader  = pd.read_csv(
    SPELL_CSV,
    usecols=usecols,
    parse_dates=["start_date", "end_date"],
    chunksize=args.chunk_rows,
    nrows=args.test_rows
)

total_chunks = (
    (args.test_rows + args.chunk_rows - 1) // args.chunk_rows
    if args.test_rows else None
)

for chunk in tqdm(reader, unit="chunk", total=total_chunks, desc="Reading"):
    # Drop obviously missing values first (company / MSA / start date)
    chunk = chunk.dropna(subset=["companyname", "msa", "start_date"])

    # Robustly ensure *start_date* / *end_date* are proper Timestamps.  If a
    # coercion fails (invalid string like "0000-00-00"), the row is removed.
    chunk["start_date"] = pd.to_datetime(chunk["start_date"], errors="coerce")
    chunk["end_date"]   = pd.to_datetime(chunk["end_date"],   errors="coerce")

    # Count and drop invalid start_date rows
    bad_mask = chunk["start_date"].isna()
    if bad_mask.any():
        invalid_date_rows += int(bad_mask.sum())
        chunk = chunk.loc[~bad_mask]

    # Replace missing *end_date* with *start_date* (single-day spells)
    na_end_mask = chunk["end_date"].isna()
    if na_end_mask.any():
        filled_end_rows += int(na_end_mask.sum())
        chunk.loc[na_end_mask, "end_date"] = chunk.loc[na_end_mask, "start_date"]

    for row in chunk.itertuples(index=False):
        info = lookup.get(row.msa)
        if info is None:
            unknown_msa_rows += 1
            continue                       # skip MSAs lacking a valid FIPS
        cbsa, *_ = info

        s, e = row.start_date, row.end_date
        if e < s:                          # guard bad rows
            e = s

        for yr, hf in half_span(s, e):
            presence[(row.companyname, yr, hf)][(cbsa, row.msa)] += 1
            # ↑ spell count; swap "+= 1" for "+= (e-s).days+1" to weight by days

# ── 3 ▸ pick the top MSA for each company × half-year ──────────────────────
rows = []
for (comp, yr, hf), counter in tqdm(presence.items(), desc="Selecting", unit="cmp"):
    (cbsa, msa_str), n = counter.most_common(1)[0]
    rows.append((comp, yr, hf, cbsa, msa_str, n))

# ── 4 ▸ save ----------------------------------------------------------------
RES_DIR.mkdir(parents=True, exist_ok=True)
pd.DataFrame(
    rows, columns=["companyname", "year", "half", "cbsacode", "msa", "spell_count"]
).to_csv(OUT_CSV, index=False)

print(f"✔  {len(rows):,} company-half observations written → {OUT_CSV}")

# ── diagnostic summary ─────────────────────────────────────────────────----
print("\nSummary of skipped/fixed rows:")
print(f"  • invalid start_date rows dropped : {invalid_date_rows:,}")
print(f"  • end_date filled with start_date : {filled_end_rows:,}")
print(f"  • unknown MSA (no CBSA) skipped   : {unknown_msa_rows:,}")

