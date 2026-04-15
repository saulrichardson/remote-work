SHELL := /usr/bin/env bash
.ONESHELL:
.SHELLFLAGS := -e -o pipefail -c

PROJECT_PYTHON ?= $(abspath bin/project-python)
STATA_BIN ?= $(abspath bin/stata)
STATA_BATCH_LOG_DIR ?= $(abspath log/batch)
PAPER_LANE ?= writeup/py/paper_support/paper_lane.py
UPSTREAM_ONTOLOGY ?= docs/upstream_data_ontology.md

.PHONY: help data specs paper \
	_data-lookups _data-stata-core _data-user _data-vacancy _data-crunchbase \
	_data-equity _paper-contract

help:
	@printf "Active Make targets:\\n\\n"
	@printf "  make data     Build the active local upstream data layer from repo-owned source boundaries plus heavy worker-position-derived inputs already materialized under data/clean/.\\n"
	@printf "  make specs    Run the active empirical Stata specs that feed the paper lane.\\n"
	@printf "  make paper    Render paper-facing tables and figures from results/raw/.\\n"
	@printf "\\nDocs:\\n\\n"
	@printf "  - %s\\n" "$(UPSTREAM_ONTOLOGY)"
	@printf "  - README.md\\n"
	@printf "  - src/py/README.md\\n"
	@printf "  - src/stata/README.md\\n"

_data-lookups:
	@"$(PROJECT_PYTHON)" src/py/build_user_location_lookup.py
	@"$(PROJECT_PYTHON)" src/py/build_csa_msa_top14_mapping.py

_data-stata-core:
	@mkdir -p "$(STATA_BATCH_LOG_DIR)"
	@"$(STATA_BIN)" -b do "$(abspath src/stata/build_firm_panel.do)"
	@"$(STATA_BIN)" -b do "$(abspath src/stata/build_all_user_panels.do)"

_data-user:
	@"$(PROJECT_PYTHON)" src/py/build_user_attributes.py
	@"$(PROJECT_PYTHON)" src/py/build_remote_hire_event_panel.py

_data-vacancy:
	@"$(PROJECT_PYTHON)" src/py/build_vacancy_halfyear_panel.py
	@"$(PROJECT_PYTHON)" src/py/build_vacancy_outcomes_panel.py

_data-crunchbase:
	@"$(PROJECT_PYTHON)" src/py/build_crunchbase_crosswalk.py
	@"$(PROJECT_PYTHON)" src/py/build_firm_panel_with_crunchbase.py
	@"$(PROJECT_PYTHON)" src/py/build_firm_panel_with_crunchbase_funding.py

_data-equity:
	@"$(PROJECT_PYTHON)" src/py/build_postings_equity_candidates.py export
	@"$(PROJECT_PYTHON)" src/py/build_postings_equity_firm_halfyear_panel.py

data: _data-lookups _data-stata-core _data-user _data-vacancy _data-crunchbase _data-equity

_paper-contract:
	@"$(PROJECT_PYTHON)" "$(PAPER_LANE)" render-contract

specs: _paper-contract
	@mkdir -p "$(STATA_BATCH_LOG_DIR)"
	@"$(PROJECT_PYTHON)" "$(PAPER_LANE)" run-stata --kind table
	@"$(PROJECT_PYTHON)" "$(PAPER_LANE)" run-stata --kind figure

paper: _paper-contract
	@"$(PROJECT_PYTHON)" "$(PAPER_LANE)" run-python --kind table
	@"$(PROJECT_PYTHON)" "$(PAPER_LANE)" run-python --kind figure
