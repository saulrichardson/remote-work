SHELL := /usr/bin/env bash
SRC        := tex
REPORT_SRC := $(SRC)/results/consolidated-report.tex
README_SRC := $(SRC)/README.tex

BUILD  := build
FINAL  := final
.PHONY: all report clean deploy
README_PDF := README.pdf          # final artefact at project root

.PHONY: readme


all: clean report deploy          # report target already rebuilds README

# ---------------------------------------------------------------------
# README document
#   – compile LaTeX into writeup/build
#   – copy resulting PDF to repository root
# ---------------------------------------------------------------------
readme:
	@mkdir -p $(BUILD)
	@echo "Compiling README.pdf…"
	@(cd $(BUILD) && pdflatex -shell-escape -halt-on-error -interaction=nonstopmode \
	  ../$(SRC)/README.tex)
	@cp $(BUILD)/README.pdf ../$(README_PDF)
	@echo "→ PDF copied to project root ($(README_PDF))"


clean:
	@rm -rf $(BUILD) $(FINAL) ../README.pdf $(SRC)/_minted-README $(BUILD)/_minted-README

# Report document
report:
	@mkdir -p $(BUILD)
	@echo "Generating consolidated report tables..."
	@python ../py/build_table_of_means.py
	@python py/create_user_mechanisms_table.py
	@python py/create_firm_mechanisms_table.py
	@echo "Generating firm scaling tables..."
	@python py/create_firm_scaling_ols_table.py
	@python py/create_firm_scaling_iv_table.py
	@python py/create_firm_scaling_first_stage_table.py
	@python py/create_user_productivity_ols_table.py
	@python py/create_user_productivity_iv_table.py
	@python py/create_user_productivity_first_stage_table.py
	@echo "Compiling consolidated report..."
	@pdflatex -halt-on-error -interaction=nonstopmode \
	  -output-directory=$(BUILD) $(REPORT_SRC)
	@mkdir -p $(FINAL)
	@cp $(BUILD)/consolidated-report.pdf $(FINAL)/

# Also regenerate README so that both PDFs are up-to-date with one command
	@$(MAKE) readme

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
	@cp $(TABLE_SRC)/* $(DEST_TABLES)/
	@echo "→ PDF copied to $(DEST_PAPER)"
	@echo "→ Tables copied to $(DEST_TABLES)"
