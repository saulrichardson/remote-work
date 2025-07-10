"""Build company × 4-digit SOC × half-year panel enriched with a
head-count-weighted OEWS occupation tightness measure.

The pipeline strictly follows the specification provided in *Notes from A–E*:

    Phase A   – Extract 2019-H2 (yh==4039) workers from the LinkedIn panel and
                 compute firm-occupation-metro head-counts.
    Phase B   – Merge those head-counts with the 2019 OEWS tightness index and
                 compute the head-count-weighted average  (tight_wavg)
                 per firm-occupation.
    Phase C   – Collapse the full LinkedIn panel to company × SOC-4 × half-year
                 (metro dimension removed).
    Phase D   – Attach tight_wavg to every half-year observation.

Three parquet artefacts are written under *data/processed*:

    • firm_occ_msa_heads_2019H2.parquet   (audit of Phase A)
    • tight_wavg_lookup.parquet           (one row per firm-SOC, Phase B)
    • firm_occ_panel_enriched.parquet     (final panel, Phase D)

A simple QA text log with row counts & tightness summary statistics is stored
to *results/qa_tight_wavg.log*.

Dependencies: DuckDB ≥0.8 (for COPY ... PARQUET).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from textwrap import dedent

import duckdb as dk  # type: ignore

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent  # project root (one level up)

# Inputs
LINKEDIN_PATH = ROOT / "data/processed/linkedin_panel.parquet"
OEWS_PATH = ROOT / "data/raw/oews/processed_data/tight_occ_msa_y.csv"

# Outputs
OUT_DIR_PROC = ROOT / "data/processed"
OUT_DIR_RES = ROOT / "results"

HEADS_OUT = OUT_DIR_PROC / "firm_occ_msa_heads_2019H2.parquet"
TIGHT_LKUP_OUT = OUT_DIR_PROC / "tight_wavg_lookup.parquet"
ENRICHED_OUT = OUT_DIR_PROC / "firm_occ_panel_enriched.parquet"

QA_LOG = OUT_DIR_RES / "qa_tight_wavg.log"

# Defaults – can be overridden via CLI
DEFAULT_MIN_HEADS = 5  # metro rows below this are trimmed
DEFAULT_FALLBACK = True  # use primary-CBSA fallback when group vanishes

# Half-year identifier for 2019-H2
YH_2019H2 = 2019 * 2 + 1  # 4039


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    OUT_DIR_PROC.mkdir(parents=True, exist_ok=True)
    OUT_DIR_RES.mkdir(parents=True, exist_ok=True)


def _log(msg: str) -> None:  # poor-man's logging
    print(msg)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build firm×SOC panel enriched with OEWS tightness.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--min-heads-per-metro",
        type=int,
        default=DEFAULT_MIN_HEADS,
        help="Drop CBSA rows with heads lower than this value before weighting.",
    )

    parser.add_argument(
        "--fallback-primary/--no-fallback-primary",
        dest="fallback_primary",
        default=DEFAULT_FALLBACK,
        action=argparse.BooleanOptionalAction,
        help="If all metros are dropped by the trim, fall back to the largest CBSA (weight=1) provided it has OEWS tightness.",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def build_enriched_panel(min_heads_per_metro: int = DEFAULT_MIN_HEADS, *, fallback_primary: bool = DEFAULT_FALLBACK) -> None:  # noqa: C901
    """Run the full pipeline.

    Parameters
    ----------
    min_heads_per_metro : int
        Threshold used to drop tiny metro rows before computing the weights.
    fallback_primary : bool
        Whether to restore the largest‐metro row (weight=1) when **all** rows
        of a firm×SOC are trimmed by the threshold and the primary metro has
        an OEWS tightness value.
    """

    _ensure_dirs()

    con = dk.connect()

    # ------------------------------------------------------------------
    # Phase A – 2019-H2 firm×occ×metro head-counts (with trim + fallback)
    # ------------------------------------------------------------------

    _log("Phase A – extracting 2019-H2 head-counts …")

    con.execute(
        dedent(
            f"""
            CREATE OR REPLACE TABLE heads_full AS
            SELECT
                lower(companyname)                              AS companyname,
                substr(soc6, 1, 4)                              AS soc4,
                lpad(CAST(cbsa AS INT)::VARCHAR, 5, '0')        AS cbsa,
                SUM(headcount)                                  AS heads
            FROM parquet_scan('{LINKEDIN_PATH.as_posix()}')
            WHERE yh = {YH_2019H2}
            GROUP BY 1, 2, 3;
            """
        )
    )

    # Trim tiny metros
    con.execute(
        f"""
        CREATE OR REPLACE TABLE heads_trim AS
        SELECT * FROM heads_full WHERE heads >= {min_heads_per_metro};
        """
    )

    # Bring OEWS into DuckDB (needed for fallback)
    con.execute(
        dedent(
            f"""
            CREATE OR REPLACE TABLE oews AS
            SELECT lpad(CAST(msa AS INT)::VARCHAR,5,'0') AS cbsa,
                   soc4,
                   tight_occ
            FROM read_csv_auto('{OEWS_PATH.as_posix()}', HEADER=TRUE)
            WHERE year = 2019;
            """
        )
    )

    # Identify groups that disappeared after trimming
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE groups_missing AS
        SELECT companyname, soc4
        FROM (SELECT DISTINCT companyname, soc4 FROM heads_full)
        EXCEPT
        SELECT DISTINCT companyname, soc4 FROM heads_trim;
        """
    )

    if fallback_primary:
        _log("  • Applying primary-CBSA fallback …")

        # Pick largest CBSA per missing group, keep only if OEWS has tightness
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE fallback AS
            SELECT hf.companyname, hf.soc4, hf.cbsa, hf.heads
            FROM (
                SELECT hf.*, ROW_NUMBER() OVER (
                    PARTITION BY companyname, soc4 ORDER BY heads DESC
                ) AS rn
                FROM heads_full hf
                JOIN groups_missing gm USING(companyname, soc4)
            ) hf
            JOIN oews o ON o.cbsa = hf.cbsa AND o.soc4 = hf.soc4
            WHERE rn = 1;
            """
        )

        # Merge fallback rows with trimmed heads
        con.execute(
            """
            CREATE OR REPLACE TABLE heads AS
            SELECT * FROM heads_trim
            UNION ALL
            SELECT * FROM fallback;
            """
        )
    else:
        con.execute("CREATE OR REPLACE TABLE heads AS SELECT * FROM heads_trim;")

    con.execute(f"COPY heads TO '{HEADS_OUT.as_posix()}' (FORMAT 'parquet');")
    _log(
        f"  ✓ {HEADS_OUT.name} written ({con.execute('SELECT COUNT(*) FROM heads').fetchone()[0]:,} rows)"
    )

    # ------------------------------------------------------------------
    # Phase B – firm×occ weighted tightness lookup
    # ------------------------------------------------------------------

    _log("Phase B – computing head-count-weighted tightness …")



    # Weighted average (exclude metros without tight_occ)
    con.execute(
        """
        CREATE OR REPLACE TABLE tight_lookup AS
        SELECT
            h.companyname,
            h.soc4,
            SUM(h.heads * o.tight_occ) / SUM(h.heads) AS tight_wavg
        FROM heads h
        JOIN oews  o ON h.cbsa = o.cbsa AND h.soc4 = o.soc4
        GROUP BY 1, 2;
        """
    )

    con.execute(f"COPY tight_lookup TO '{TIGHT_LKUP_OUT.as_posix()}' (FORMAT 'parquet');")
    _log(
        f"  ✓ {TIGHT_LKUP_OUT.name} written ({con.execute('SELECT COUNT(*) FROM tight_lookup').fetchone()[0]:,} rows)"
    )

    # ------------------------------------------------------------------
    # Phase C – collapse full LinkedIn panel to firm×SOC×yh
    # ------------------------------------------------------------------

    _log("Phase C – collapsing full LinkedIn panel …")

    con.execute(
        dedent(
            f"""
            CREATE OR REPLACE TABLE panel_collapsed AS
            SELECT
                lower(companyname)               AS companyname,
                substr(soc6, 1, 4)               AS soc4,
                yh,
                SUM(headcount)                   AS headcount,
                SUM(joins)                       AS joins,
                SUM(leaves)                      AS leaves
            FROM parquet_scan('{LINKEDIN_PATH.as_posix()}')
            GROUP BY 1, 2, 3;
            """
        )
    )

    # ------------------------------------------------------------------
    # Phase D – attach tight_wavg
    # ------------------------------------------------------------------

    _log("Phase D – merging tightness lookup …")

    con.execute(
        """
        CREATE OR REPLACE TABLE panel_enriched AS
        SELECT
            p.companyname,
            p.soc4,
            p.yh,
            p.headcount,
            p.joins,
            p.leaves,
            tl.tight_wavg
        FROM panel_collapsed p
        LEFT JOIN tight_lookup tl
          ON p.companyname = tl.companyname AND p.soc4 = tl.soc4;
        """
    )

    con.execute(f"COPY panel_enriched TO '{ENRICHED_OUT.as_posix()}' (FORMAT 'parquet');")

    _log(
        f"  ✓ {ENRICHED_OUT.name} written ({con.execute('SELECT COUNT(*) FROM panel_enriched').fetchone()[0]:,} rows)"
    )

    # ------------------------------------------------------------------
    # QA summary
    # ------------------------------------------------------------------

    _log("Generating QA log …")

    total, missing = con.execute(
        "SELECT COUNT(*), SUM(CASE WHEN tight_wavg IS NULL THEN 1 ELSE 0 END) FROM panel_enriched;"
    ).fetchone()

    # --------------------------------------------------------------
    # Detailed QA checks requested by the “sanity-check menu”
    # --------------------------------------------------------------

    # 1) Coverage pattern – missing tight_wavg by headcount bucket
    cov = con.execute(
        """
        WITH heads19 AS (
            SELECT companyname, soc4, SUM(heads) AS total_heads
            FROM heads
            GROUP BY 1,2
        ), tag AS (
            SELECT e.companyname, e.soc4, e.yh,
                   CASE WHEN tl.tight_wavg IS NULL THEN 1 ELSE 0 END AS miss,
                   h.total_heads
            FROM panel_enriched e
            LEFT JOIN tight_lookup tl USING(companyname,soc4)
            JOIN heads19 h USING(companyname,soc4)
            WHERE e.yh = {YH_2019H2}
        )
        SELECT
            CASE
                WHEN total_heads BETWEEN 1 AND 2 THEN '1-2'
                WHEN total_heads BETWEEN 3 AND 4 THEN '3-4'
                WHEN total_heads BETWEEN 5 AND 9 THEN '5-9'
                ELSE '10+'
            END AS bucket,
            COUNT(*)                       AS n_rows,
            SUM(miss)                      AS n_missing,
            ROUND(100.0*SUM(miss)/COUNT(*),2) AS pct_missing
        FROM tag
        GROUP BY 1 ORDER BY 1;
        """
    ).fetchall()

    # 2) Weight integrity – Σ weight and max(weight)
    wint = con.execute(
        """
        WITH denom AS (
            SELECT companyname,soc4,SUM(heads) AS denom
            FROM heads GROUP BY 1,2
        ), w AS (
            SELECT h.companyname,h.soc4,heads/denom AS w
            FROM heads h JOIN denom d USING(companyname,soc4)
        ), agg AS (
            SELECT companyname,soc4,SUM(w) AS s, MAX(w) AS mx
            FROM w GROUP BY 1,2
        )
        SELECT
            ROUND(100.0*SUM(CASE WHEN ABS(s-1)>1e-6 THEN 1 ELSE 0 END)/COUNT(*),4) AS pct_bad_sum,
            APPROX_QUANTILE(mx,0.5) AS median_max_w,
            APPROX_QUANTILE(mx,0.9) AS p90_max_w
        FROM agg;
        """
    ).fetchone()

    # 3) tight_wavg overall stats
    summary = con.execute(
        "SELECT MIN(tight_wavg), APPROX_QUANTILE(tight_wavg,0.5), MAX(tight_wavg) FROM panel_enriched WHERE tight_wavg IS NOT NULL"
    ).fetchone()

    # 4) Temporal constancy
    const_share = con.execute(
        """
        SELECT COUNT(*) FILTER (WHERE d=1)*1.0/COUNT(*)
        FROM (
          SELECT companyname,soc4,COUNT(DISTINCT tight_wavg) AS d
          FROM panel_enriched GROUP BY 1,2
        );
        """
    ).fetchone()[0]

    # 5) OEWS gaps weighted by heads
    gaps = con.execute(
        f"""
        WITH o AS (
            SELECT lpad(CAST(msa AS INT)::VARCHAR,5,'0') AS cbsa, soc4, tight_occ
            FROM read_csv_auto('{OEWS_PATH.as_posix()}', HEADER=TRUE) WHERE year=2019
        ), m AS (
            SELECT h.cbsa, h.soc4, h.heads, o.tight_occ
            FROM heads h LEFT JOIN o USING(cbsa,soc4)
        )
        SELECT SUM(CASE WHEN tight_occ IS NULL THEN heads ELSE 0 END)/SUM(heads) AS gap_share
        FROM m;
        """
    ).fetchone()[0]

    # build coverage lines
    cov_lines = "\n            ".join(
        f"{b:<4} {n:>9,} {m:>9,} {p:>7.2f}%" for b, n, m, p in cov
    )

    qa_txt = dedent(
        f"""
        ===================== QA ‑ tight_wavg =====================
        Rows in enriched panel      : {total:,}
        Rows with missing tightness : {missing:,}  ({missing/total:.2%})

        tight_wavg distribution (non-missing):
            min    = {summary[0]:.4f}
            median = {summary[1]:.4f}
            max    = {summary[2]:.4f}

        Coverage by 2019-H2 headcount bucket (rows):
            bucket     rows   missing   %missing
            {cov_lines}

        Weight integrity across metros (firm-SOC):
            groups with Σw ≠ 1     : {wint[0]:.4f}%
            median max(weight)     : {wint[1]:.3f}
            90th pct max(weight)   : {wint[2]:.3f}

        Temporal constancy (distinct tight_wavg per firm-SOC):
            share with single value: {const_share:.2%}

        OEWS lookup gap (head-weighted): {gap_share:.2%}
        ===========================================================
        """
    )


    QA_LOG.write_text(qa_txt)
    _log(qa_txt)

    _log("✅ Enriched firm-occ panel build complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    args = _parse_args()
    build_enriched_panel(
        min_heads_per_metro=args.min_heads_per_metro,
        fallback_primary=args.fallback_primary,
    )
