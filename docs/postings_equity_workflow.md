# Postings-Description Equity Workflow

This runbook documents the active postings-description equity branch that feeds
the current paper lane.

## What This Branch Produces

Materialized branch outputs:

- [`../results/raw/postings_description_equity/equity_candidates.parquet`](../results/raw/postings_description_equity/equity_candidates.parquet)
- [`../results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv`](../results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv)
- [`../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv`](../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv)

Downstream paper consumers:

- [`../writeup/py/paper_support/table_of_means.py`](../writeup/py/paper_support/table_of_means.py)
- [`../spec/stata/tables/05_user_mechanisms_keep_remote_precovid.do`](../spec/stata/tables/05_user_mechanisms_keep_remote_precovid.do)

## Raw Source Boundary

The source posting shards are:

- [`../data/raw/postings_description/`](../data/raw/postings_description/)

These are treated as original source inputs.

## Accepted Manual Boundary

This branch contains one explicit manual external boundary:

- OpenAI Batch submission, polling, download, and posting-level merge

That means the local pipeline is:

- partly deterministic
- partly manual at the model-extraction step
- deterministic again after the downloaded outputs exist

## Stage 1. Deterministic Candidate Extraction

```bash
./bin/project-python src/py/build_postings_equity_candidates.py export
```

Primary output:

- [`../results/raw/postings_description_equity/equity_candidates.parquet`](../results/raw/postings_description_equity/equity_candidates.parquet)

## Stage 2. Prepare Batch Inputs

```bash
./bin/project-python src/py/run_postings_equity_batch.py prepare-candidates
```

This reads the candidate parquet and writes batch-input directories under:

- `results/raw/postings_description_equity/llm_batch_inputs/`

The current shared prompt lives in:

- [`../src/py/postings_equity_prompt_schema.py`](../src/py/postings_equity_prompt_schema.py)

The recovered historical core system prompt is also preserved as a first-class
raw prompt artifact:

- [`../data/raw/prompts/postings_equity_system_prompt.txt`](../data/raw/prompts/postings_equity_system_prompt.txt)

## Stage 3. Manual OpenAI Batch Step

Typical commands:

```bash
./bin/project-python src/py/run_postings_equity_batch.py submit-dir --input-dir <run_input_dir>
./bin/project-python src/py/run_postings_equity_batch.py status-dir --input-dir <run_input_dir>
./bin/project-python src/py/run_postings_equity_batch.py download-dir --input-dir <run_input_dir> --out-dir <run_output_dir>
```

This is the accepted manual external-model boundary in the active local
contract.

## Stage 4. Merge Downloaded LLM Outputs Back To Firms

```bash
./bin/project-python src/py/build_postings_equity_firm_merge.py \
  --run-input-dir <run_input_dir> \
  --run-output-dir <run_output_dir>
```

Primary output:

- [`../results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv`](../results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv)

This is the key materialized local boundary file for later deterministic reruns.

## Stage 5. Aggregate To Firm × Half-Year

```bash
./bin/project-python src/py/build_postings_equity_firm_halfyear_panel.py
```

Primary output:

- [`../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv`](../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv)

## Relation To `make data`

`make data` includes the deterministic pieces of this branch:

- candidate extraction
- firm-half-year panel rebuild from the materialized posting-level merge

It does not replace the manual Batch step itself.
