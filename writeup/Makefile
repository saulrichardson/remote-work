SHELL := /usr/bin/env bash
# Source directories
SRC        := tex
REPORT_SRC := $(SRC)/consolidated-report.tex

# Build artefacts
BUILD  := build
FINAL  := final

.PHONY: all report clean deploy


all: clean report deploy          # Report target rebuilds paper only

clean:
	@rm -rf $(BUILD) $(FINAL) $(SRC)/_minted-README $(BUILD)/_minted-README

# Report document
report:
	@mkdir -p $(BUILD)
	@echo "Generating consolidated report tables..."
	# ------------------------------------------------------------------
# 1) Ensure raw Stata outputs exist (Lean mechanism extensions)
	# ------------------------------------------------------------------
	# ------------------------------------------------------------------
	#  Verify that required raw Stata outputs are present.  The Makefile
	#  no longer attempts to run any .do files automatically—if the
	#  expected artefacts are missing, we abort with an informative
	#  message so the user can generate them manually in Stata.
	# ------------------------------------------------------------------
	@for v in unbalanced balanced precovid balanced_pre; do \
	  if [ ! -f ../results/raw/user_mechanisms_lean_$${v}/consolidated_results.csv ]; then \
	    echo "ERROR: Missing ../results/raw/user_mechanisms_lean_$${v}/consolidated_results.csv. Please run spec/user_mechanisms_lean.do in Stata first."; \
	    exit 1; \
	  fi; \
	done
	@if [ ! -f ../results/raw/firm_mechanisms_lean/consolidated_results.csv ]; then \
	  echo "ERROR: Missing ../results/raw/firm_mechanisms_lean/consolidated_results.csv.  Please run spec/firm_mechanisms_lean.do in Stata first."; \
	  exit 1; \
	fi
	@python ../py/build_table_of_means.py
	@MPLBACKEND=Agg python ../py/figures.py
	@echo "Generating user mechanism tables..."
	@for v in unbalanced balanced precovid balanced_pre; do \
	  python py/create_user_mechanisms_table.py --variant $$v; \
	done
	@python py/create_firm_mechanisms_table.py
	@echo "Generating firm scaling tables..."
	@python py/create_firm_scaling_table.py --model-type ols
	@python py/create_firm_scaling_table.py --model-type iv
	@python py/create_firm_scaling_first_stage_table.py
	@python py/create_remote_first_stage_table.py
	# User productivity tables for each panel variant ----------------
	@for v in unbalanced balanced precovid balanced_pre; do \
	  python py/create_user_productivity_table.py --model-type ols --variant $$v; \
	  python py/create_user_productivity_table.py --model-type iv  --variant $$v; \
	  python py/create_user_productivity_first_stage_table.py --variant $$v; \
	done
	# Lean mechanism tables
	@echo "Generating lean user mechanism tables..."
	@for v in unbalanced balanced precovid balanced_pre; do \
	  python py/create_user_mechanisms_lean_table.py --variant $$v; \
	done
	@python py/create_firm_mechanisms_lean_table.py
	@echo "Compiling consolidated report..."
	@pdflatex -halt-on-error -interaction=nonstopmode \
	  -output-directory=$(BUILD) $(REPORT_SRC)
	@mkdir -p $(FINAL)
	@cp $(BUILD)/consolidated-report.pdf $(FINAL)/

# Finished compiling report

# -------------------------------------------------------------------------
#  Deploy: copy artefacts to Overleaf-synced Dropbox folder
# -------------------------------------------------------------------------

# Absolute destinations (contains spaces → wrap in quotes)
DEST_PAPER  := "/Users/saul/Dropbox/Apps/Overleaf/WFH Startups/Current/Paper"
DEST_TABLES := "/Users/saul/Dropbox/Apps/Overleaf/WFH Startups/Current/Tables"

# Source directory for cleaned LaTeX tables (relative to *this* Makefile)
TABLE_SRC   := ../results/cleaned

# Ensure report is up-to-date, then copy files.
deploy:
	@echo "Syncing artefacts to Overleaf Dropbox folder…"
	# Clear existing artefacts so the destination always mirrors the latest build
	@mkdir -p $(DEST_PAPER)
	@mkdir -p $(DEST_TABLES)
	@rm -rf $(DEST_TABLES)/*
	@cp $(FINAL)/consolidated-report.pdf $(DEST_PAPER)/
	# Exclude any tables explicitly marked as deprecated to avoid clutter on Overleaf
	@find $(TABLE_SRC) -maxdepth 1 -type f ! -name '*_deprecated.tex' -exec cp {} $(DEST_TABLES)/ \;
	@echo "→ PDF copied to $(DEST_PAPER)"
	@echo "→ Tables copied to $(DEST_TABLES)"
