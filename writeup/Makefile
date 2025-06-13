# Use bash with strict mode so missing commands abort immediately and we can
# emit clearer error messages below.
SHELL := /usr/bin/env bash

# Bash strict mode for every recipe line
.ONESHELL:
.SHELLFLAGS := -e -o pipefail -c

# Resolve usable Python interpreter once (prefer python3, otherwise python)
# Use the python executable available on PATH. Assumes the user activated the
# desired environment beforehand.
PYTHON := python
# Helper scripts live in *two* places:
#   • Top-level  ../py               (figures.py, build_table_of_means.py …)
#   • Report-specific ./py           (create_*_table.py helpers)
# We'll pick whichever path contains the requested file.

define RUN_PYSCRIPT
  if [ -f ./py/$(1) ]; then \
      SCRIPT=./py/$(1); \
  elif [ -f ../py/$(1) ]; then \
      SCRIPT=../py/$(1); \
  else \
      echo "⚠️  Skipping $(1) – script not found"; \
      SCRIPT=""; \
  fi; \
  if [ -n "$$SCRIPT" ]; then \
      if ! $(PYTHON) $$SCRIPT $(2); then \
          echo "‼️  $$SCRIPT failed (missing raw results?)"; \
      fi; \
  fi \

endef

# Abort early with a helpful hint if no interpreter is found
ifeq ($(PYTHON),)
$(error "Neither 'python3' nor 'python' found in PATH – install Python or adjust PYTHON in writeup/Makefile")
endif
# Source directories
SRC        := tex
REPORT_SRC := $(SRC)/consolidated-report.tex

# Build artefacts
BUILD  := build
FINAL  := final

.PHONY: all report mini clean deploy deploy-mini mini-report


all: clean report deploy          # Report target rebuilds paper only

# -------------------------------------------------------------------------
#  Mini consolidated report (Pre-COVID only)
# -------------------------------------------------------------------------

mini: clean mini-report deploy-mini     # Build & sync the mini-report

# -------------------------------------------------------------------------
#  Build the *mini* report – only Pre-COVID variant tables
# -------------------------------------------------------------------------

mini-report:
	@mkdir -p $(BUILD)
	@echo "Generating tables for mini report (Pre-COVID only)..."
	# ------------------------------------------------------------------
	#  Verify that required raw Stata outputs exist for the variants we use.
	# ------------------------------------------------------------------
	@for d in \
	  ../results/raw/user_mechanisms_lean_precovid \
	  ../results/raw/user_mechanisms_precovid \
	  ../results/raw/firm_mechanisms_lean \
	  ../results/raw/firm_mechanisms; do \
	    if [ ! -f $$d/consolidated_results.csv ]; then \
	      echo "ERROR: Missing $$d/consolidated_results.csv.  Please regenerate the Stata outputs."; \
	      exit 1; \
	    fi; \
	  done

	# ------------------------------------------------------------------
	#  1) Descriptive table of means
	# ------------------------------------------------------------------
	@echo "[1/7] Table of means"
	@$(PYTHON) ../py/build_table_of_means.py || { echo "✖ Failed: build_table_of_means.py"; exit 1; }

	# ------------------------------------------------------------------
	#  2) Firm scaling results (OLS, IV, first-stage) + Remote→Teleworkable
	# ------------------------------------------------------------------
	@echo "[2/7] Firm scaling tables"
	@$(call RUN_PYSCRIPT,create_firm_scaling_table.py,--model-type ols)
	@$(call RUN_PYSCRIPT,create_firm_scaling_table.py,--model-type iv)
	@$(call RUN_PYSCRIPT,create_firm_scaling_first_stage_table.py,)
	@$(call RUN_PYSCRIPT,create_remote_first_stage_table.py,)

	# ------------------------------------------------------------------
	#  3) Firm mechanisms (baseline & lean)
	# ------------------------------------------------------------------
	@echo "[3/7] Firm mechanisms tables"
	@$(call RUN_PYSCRIPT,create_firm_mechanisms_table.py,--exclude Wage)
	@$(call RUN_PYSCRIPT,create_firm_mechanisms_lean_table.py,--exclude Wage)

	# ------------------------------------------------------------------
	#  4) User productivity tables (OLS, IV, first-stage) – Pre-COVID
	# ------------------------------------------------------------------
	@echo "[4/7] User productivity tables – Pre-COVID"
	@$(call RUN_PYSCRIPT,create_user_productivity_table.py,--model-type ols --variant precovid)
	@$(call RUN_PYSCRIPT,create_user_productivity_table.py,--model-type iv --variant precovid)
	@$(call RUN_PYSCRIPT,create_user_productivity_first_stage_table.py,--variant precovid)

	# ------------------------------------------------------------------
	#  5) Lean user mechanisms – Pre-COVID
	# ------------------------------------------------------------------
	@echo "[5/7] Lean user mechanisms – Pre-COVID (excluding Wage)"
	@$(call RUN_PYSCRIPT,create_user_mechanisms_lean_table.py,--variant precovid --exclude Wage)

	# ------------------------------------------------------------------
	#  6) Full user mechanisms – Pre-COVID
	# ------------------------------------------------------------------
	@echo "[6/7] Full user mechanisms – Pre-COVID (excluding Wage)"
	@$(call RUN_PYSCRIPT,create_user_mechanisms_table.py,--variant precovid --exclude Wage)

	# ------------------------------------------------------------------
	#  7) Compile PDF
	# ------------------------------------------------------------------
	@echo "[7/7] Compiling LaTeX PDF"
	@pdflatex -halt-on-error -interaction=nonstopmode \
	  -output-directory=$(BUILD) $(SRC)/mini-report.tex
	# Second run for TOC / cross-refs
	@pdflatex -halt-on-error -interaction=nonstopmode \
	  -output-directory=$(BUILD) $(SRC)/mini-report.tex
	@mkdir -p $(FINAL)
	@cp $(BUILD)/mini-report.pdf $(FINAL)/

# -------------------------------------------------------------------------
#  Deploy mini-report to Overleaf-synced Dropbox folder
# -------------------------------------------------------------------------

deploy-mini:
	@echo "Syncing mini report to Overleaf Dropbox folder…"
	@mkdir -p $(DEST_PAPER)
	@cp $(FINAL)/mini-report.pdf $(DEST_PAPER)/
	@echo "→ mini-report.pdf copied to $(DEST_PAPER)"

clean:
	@rm -rf $(BUILD) $(SRC)/_minted-README $(BUILD)/_minted-README

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
	@echo "[1/8] Python table_of_means"
	@$(PYTHON) ../py/build_table_of_means.py || { echo "✖ Failed: build_table_of_means.py"; exit 1; }
	@echo "[2/8] Python figures"
	@MPLBACKEND=Agg $(PYTHON) ../py/figures.py || { echo "✖ Failed: figures.py"; exit 1; }
	@echo "Generating user mechanism tables..."
	@for v in unbalanced balanced precovid balanced_pre; do \
	  echo "  – create_user_mechanisms_table ($$v)"; \
	  $(call RUN_PYSCRIPT,create_user_mechanisms_table.py,--variant $$v); \
	done
	@echo "[3] firm_mechanisms_table"
	@$(call RUN_PYSCRIPT,create_firm_mechanisms_table.py,)
	@echo "Generating firm scaling tables..."
	@$(call RUN_PYSCRIPT,create_firm_scaling_table.py,--model-type ols)
	@$(call RUN_PYSCRIPT,create_firm_scaling_table.py,--model-type iv)
	@$(call RUN_PYSCRIPT,create_firm_scaling_first_stage_table.py,)
	@$(call RUN_PYSCRIPT,create_remote_first_stage_table.py,)
	# User productivity tables for each panel variant ----------------
	@for v in unbalanced balanced precovid balanced_pre; do \
	  echo "  – user_productivity tables ($$v)"; \
	  $(call RUN_PYSCRIPT,create_user_productivity_table.py,--model-type ols --variant $$v); \
	  $(call RUN_PYSCRIPT,create_user_productivity_table.py,--model-type iv --variant $$v); \
	  $(call RUN_PYSCRIPT,create_user_productivity_first_stage_table.py,--variant $$v); \
	done
	# Lean mechanism tables
	@echo "Generating lean user mechanism tables..."
	@for v in unbalanced balanced precovid balanced_pre; do \
	  echo "  – lean user mechanisms ($$v)"; \
	  $(call RUN_PYSCRIPT,create_user_mechanisms_lean_table.py,--variant $$v); \
	done
	@$(call RUN_PYSCRIPT,create_firm_mechanisms_lean_table.py,)
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
