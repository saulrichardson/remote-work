#!/usr/bin/env python3
# ---------------------------------------------------------------------------
#  Company-level dispersion (2019 baseline)
#    • filtered_msa_cnt     – MSAs that meet ABS (≥3 spells) and REL (≥10%) floors **and** have cbsa
#    • avgdist_km           – average km between those MSAs
#    • core MSAs (new)      – long-form table of every CBSA that satisfies the filters
#  MSAs lacking a valid FIPS/cbsa are dropped automatically.
# ---------------------------------------------------------------------------
#  CLI:
#     --test_rows N     read only first N rows   (debug)
#     --chunk_rows C    pandas chunk size        (default 1 000 000)
# ---------------------------------------------------------------------------

import pandas as pd, argparse
from pathlib import Path
from collections import defaultdict, Counter
from haversine import haversine_vector, Unit
from tqdm import tqdm

# ── folders ────────────────────────────────────────────────────────────────
RAW_DIR       = Path("../data/raw")
PROC_DIR      = Path("../data/cleaned")
RES_DIR       = Path("../data/raw")

SPELL_CSV  = RAW_DIR / "Scoop_workers_positions.csv"
ENRICH_CSV = PROC_DIR / "enriched_msa.csv"
OUT_CSV    = RES_DIR / "company_dispersion_2019.csv"
OUT_CORES  = RES_DIR / "company_core_msas_by_half.csv"

# ── constants ──────────────────────────────────────────────────────────────
CUTOFF    = "2019-12-31"
ABS_FLOOR = 3
REL_FLOOR = 0.10
MSA_COL   = "msa"          # metro name in spell file

# ── CLI ────────────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--test_rows",  type=int, default=None)
ap.add_argument("--chunk_rows", type=int, default=1_000_000)
args = ap.parse_args()

print(f"test_rows={args.test_rows or 'ALL'}   chunk_rows={args.chunk_rows}")

# ── diagnostic counters ─────────────────────────────────────────────────---
invalid_date_rows = 0
filled_end_rows  = 0
unknown_msa_rows = 0

# ── 1 ▸ load enrichment & keep ONLY rows with a real cbsa code ─────────────
enrich = pd.read_csv(ENRICH_CSV,
                     usecols=[MSA_COL, "cbsacode", "lat", "lon"],
                     dtype={MSA_COL: str})
enrich["cbsacode"] = pd.to_numeric(enrich["cbsacode"], errors="coerce").astype("Int64")
enrich = enrich.dropna(subset=["cbsacode"])        # ← <-- filter right here
lookup = {
    row.msa: (row.cbsacode, row.lat, row.lon)
    for row in enrich.itertuples(index=False)
}
del enrich

# ── helper: every half-year a spell overlaps --------------------------------
def half_span(start, end):
    y, h = start.year, 1 if start.month <= 6 else 2
    while True:
        yield y, h
        if h == 1:
            nxt = pd.Timestamp(y, 7, 1)
            if nxt > end: break
            h = 2
        else:
            nxt = pd.Timestamp(y + 1, 1, 1)
            if nxt > end: break
            y, h = y + 1, 1

# ── 2 ▸ stream spells, ignore ones w/out cbsa, count per company×half×cbsa ─
presence = defaultdict(Counter)
reader = pd.read_csv(
    SPELL_CSV,
    usecols=["companyname", MSA_COL, "start_date", "end_date"],
    parse_dates=["start_date", "end_date"],
    chunksize=args.chunk_rows,
    nrows=args.test_rows,
)

for chunk in tqdm(reader, total=None, desc="Reading", unit="chunk"):
    # Only keep rows with required fields
    chunk = chunk.dropna(subset=["companyname", MSA_COL, "start_date"])

    # Robust datetime coercion – invalid strings become NaT
    chunk["start_date"] = pd.to_datetime(chunk["start_date"], errors="coerce")
    chunk["end_date"]   = pd.to_datetime(chunk["end_date"],   errors="coerce")

    bad_mask = chunk["start_date"].isna()
    if bad_mask.any():
        invalid_date_rows += int(bad_mask.sum())
        chunk = chunk.loc[~bad_mask]

    # Missing end -> fill
    mask_endna = chunk["end_date"].isna()
    if mask_endna.any():
        filled_end_rows += int(mask_endna.sum())
        chunk.loc[mask_endna, "end_date"] = chunk.loc[mask_endna, "start_date"]

    for row in chunk.itertuples(index=False):
        info = lookup.get(row.msa)             # None if no cbsa → skip
        if info is None:
            unknown_msa_rows += 1
            continue
        cbsa, lat, lon = info
        s, e = row.start_date, max(row.start_date, row.end_date)

        for yr, hf in half_span(s, e):
            presence[(row.companyname, yr, hf)][(cbsa, row.msa, lat, lon)] += 1

# ── 3 ▸ apply ABS/REL filters and compute metrics ---------------------------
rows = []
core_rows = []
for (comp, yr, hf), counter in tqdm(presence.items(), desc="Computing", unit="cmp"):
    total = sum(counter.values())
    coords = []
    for (cbsa, msa_name, lat, lon), n in counter.items():
        share = n / total if total else 0.0
        if n >= ABS_FLOOR and share >= REL_FLOOR:
            coords.append((lat, lon))
            core_rows.append(
                (
                    comp,
                    yr,
                    hf,
                    int(cbsa),
                    msa_name,
                    int(n),
                    float(share),
                )
            )

    k = len(coords)
    avg_km = 0.0
    if k >= 2:
        dvec  = haversine_vector(coords, coords, Unit.KILOMETERS, comb=True)
        avg_km = float(dvec.mean())

    rows.append((comp, yr, hf, k, avg_km))

# ── 4 ▸ save ---------------------------------------------------------------
RES_DIR.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows,
             columns=["companyname", "year", "half",
                      "filtered_msa_cnt", "avgdist_km"]
            ).to_csv(OUT_CSV, index=False)

pd.DataFrame(core_rows,
             columns=["companyname", "year", "half",
                      "cbsa", "msa", "spell_count", "spell_share"]
            ).to_csv(OUT_CORES, index=False)

print(f"✔  {len(rows):,} company-half rows written → {OUT_CSV}")
print(f"✔  {len(core_rows):,} core MSA records written → {OUT_CORES}")

# ── diagnostics ────────────────────────────────────────────────────────────
print("\nSummary of skipped/fixed rows:")
print(f"  • invalid start_date rows dropped : {invalid_date_rows:,}")
print(f"  • end_date filled with start_date : {filled_end_rows:,}")
print(f"  • unknown MSA (no CBSA) skipped   : {unknown_msa_rows:,}")
