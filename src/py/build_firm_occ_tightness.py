"""Build company × 4-digit SOC × half-year panel enriched with OEWS tightness.

Pure DuckDB implementation – no external Parquet/Arrow dependency.  All
intermediate and final artefacts are written as **CSV**.

Defaults (when you simply run `python py/build_firm_occ_tightness.py`)
--------------------------------------------------------------------
• min-heads-per-metro = 3  →  keeps every CBSA with at least 3 heads in 2019-H2
• no fallback primary-CBSA  →  if every metro of a firm-SOC is below the
  threshold or lacks an OEWS tightness value, `tight_wavg` is left missing.

Outputs (written to data/processed/)
-----------------------------------
firm_occ_msa_heads_2019H2.csv   • audit head-counts after trim / fallback
tight_wavg_lookup.csv           • tightness per firm×SOC (static lookup)
firm_occ_panel_enriched.csv     • full LinkedIn panel incl. tight_wavg

results/qa_tight_wavg.log       • basic QA summary

Usage
-----
python py/build_firm_occ_tightness.py [--min-heads-per-metro 5] \
                                      [--no-fallback-primary]

Dependencies: DuckDB ≥0.8, pandas (only for CLI convenience – not used in the
pipeline itself).
"""

from __future__ import annotations

import argparse
from textwrap import dedent

import duckdb as dk  # type: ignore

from project_paths import DATA_PROCESSED, DATA_RAW, RESULTS_DIR, ensure_dir

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

# Inputs
PROC = DATA_PROCESSED
LINKEDIN_PATH = PROC / "linkedin_panel.parquet"
OEWS_PATH = DATA_RAW / "oews" / "processed_data" / "tight_occ_msa_y.csv"

# Output directories
RES = RESULTS_DIR

# CSV outputs
HEADS_CSV   = PROC / "firm_occ_msa_heads_2019H2.csv"
TIGHT_CSV   = PROC / "tight_wavg_lookup.csv"
PANEL_CSV   = PROC / "firm_occ_panel_enriched.csv"

QA_LOG = RES / "qa_tight_wavg.log"

# Half-year identifier for 2019-H2
YH_2019H2 = 2019 * 2 + 1  # 4039

# Defaults (can be overridden via CLI)
DEFAULT_MIN_HEADS   = 3   # default trim: require ≥3 heads per CBSA
DEFAULT_FALLBACK_CB = False  # no primary-CBSA fallback by default


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    ensure_dir(PROC)
    ensure_dir(RES)


def _log(msg: str) -> None:  # tiny logger to stderr
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build firm×SOC panel enriched with OEWS tightness (CSV outputs)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--min-heads-per-metro", type=int, default=DEFAULT_MIN_HEADS)

    p.add_argument(
        "--fallback-primary",
        dest="fallback_primary",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_FALLBACK_CB,
        help="When a firm–SOC loses all metros after trimming, restore its largest metro (weight=1) provided OEWS has tightness for that CBSA.",
    )

    return p.parse_args()


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def build_panel(min_heads_per_metro: int, *, fallback_primary: bool) -> None:  # noqa: C901
    """Run the four-phase build and write CSV artefacts."""

    _ensure_dirs()

    con = dk.connect()

    # ------------------------------------------------------------------
    # Phase A – 2019-H2 firm×SOC×CBSA head-counts (trim + optional fallback)
    # ------------------------------------------------------------------

    _log("Phase A – extracting 2019-H2 head-counts …")

    con.execute(
        dedent(
            f"""
            CREATE OR REPLACE TABLE heads_full AS
            SELECT
                lower(companyname)                               AS companyname,
                substr(soc6, 1, 4)                               AS soc4,
                lpad(CAST(cbsa AS INT)::VARCHAR, 5, '0')         AS cbsa,
                SUM(headcount)                                   AS heads
            FROM parquet_scan('{LINKEDIN_PATH.as_posix()}')
            WHERE yh = {YH_2019H2}
            GROUP BY 1,2,3;
            """
        )
    )

    # Trim tiny metros --------------------------------------------------
    con.execute(
        f"""
        CREATE OR REPLACE TABLE heads_trim AS
        SELECT * FROM heads_full WHERE heads >= {min_heads_per_metro};
        """
    )

    # OEWS tightness table ---------------------------------------------
    con.execute(
        dedent(
            f"""
            CREATE OR REPLACE TABLE oews AS
            SELECT lpad(CAST(msa AS INT)::VARCHAR,5,'0') AS cbsa,
                   soc4,
                   tight_occ
            FROM read_csv_auto('{OEWS_PATH.as_posix()}', header=True)
            WHERE year = 2019;
            """
        )
    )

    # Identify firm-SOC groups lost by trimming -------------------------
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

    # Write audit CSV ----------------------------------------------------
    con.execute(
        f"COPY heads TO '{HEADS_CSV.as_posix()}' (HEADER, DELIMITER ',');"
    )
    _log(
        f"  ✓ {HEADS_CSV.name} written  ("
        f"{con.execute('SELECT COUNT(*) FROM heads').fetchone()[0]:,} rows)"
    )

    # ------------------------------------------------------------------
    # Phase B – firm×SOC head-count-weighted tightness lookup
    # ------------------------------------------------------------------

    _log("Phase B – computing weighted tightness …")

    con.execute(
        """
        CREATE OR REPLACE TABLE tight_lookup AS
        SELECT
            h.companyname,
            h.soc4,
            SUM(h.heads * o.tight_occ) / SUM(h.heads) AS tight_wavg
        FROM heads h
        JOIN oews  o ON h.cbsa = o.cbsa AND h.soc4 = o.soc4
        GROUP BY 1,2;
        """
    )

    con.execute(
        f"COPY tight_lookup TO '{TIGHT_CSV.as_posix()}' (HEADER, DELIMITER ',');"
    )
    _log(
        f"  ✓ {TIGHT_CSV.name} written  ("
        f"{con.execute('SELECT COUNT(*) FROM tight_lookup').fetchone()[0]:,} rows)"
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
            GROUP BY 1,2,3;
            """
        )
    )

    # ------------------------------------------------------------------
    # Phase D – attach tight_wavg and persist panel
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

    con.execute(
        f"COPY panel_enriched TO '{PANEL_CSV.as_posix()}' (HEADER, DELIMITER ',');"
    )

    _log(
        f"  ✓ {PANEL_CSV.name} written  ("
        f"{con.execute('SELECT COUNT(*) FROM panel_enriched').fetchone()[0]:,} rows)"
    )

    # ------------------------------------------------------------------
    # QA summary
    # ------------------------------------------------------------------

    _log("Generating QA log …")

    total, missing = con.execute(
        "SELECT COUNT(*), SUM(CASE WHEN tight_wavg IS NULL THEN 1 ELSE 0 END) FROM panel_enriched;"
    ).fetchone()

    q_min, q_med, q_max = con.execute(
        "SELECT MIN(tight_wavg), APPROX_QUANTILE(tight_wavg,0.5), MAX(tight_wavg) FROM panel_enriched WHERE tight_wavg IS NOT NULL;"
    ).fetchone()

    qa_txt = dedent(
        f"""
        ================= QA – tight_wavg (CSV build) =================
        Rows in panel              : {total:,}
        Rows with missing tightness: {missing:,}  ({missing/total:.2%})

        tight_wavg distribution (non-missing):
            min    = {q_min:.4f}    
            median = {q_med:.4f}
            max    = {q_max:.4f}
        ==============================================================
        """
    )

    QA_LOG.write_text(qa_txt)
    _log(qa_txt)

    _log("✅ Finished – CSVs written to data/processed")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    cli = _parse_args()
    build_panel(cli.min_heads_per_metro, fallback_primary=cli.fallback_primary)
