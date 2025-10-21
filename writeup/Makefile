# Minimal Makefile dedicated to the mini-writeup

SHELL := /usr/bin/env bash
.ONESHELL:
.SHELLFLAGS := -e -o pipefail -c

PYTHON ?= python

# Resolve scripts from ./py (writeup-specific) or ../scripts (shared helpers)
define RUN_PYSCRIPT
  if [ -f ./py/$(1) ]; then \
      SCRIPT=./py/$(1); \
  elif [ -f ../scripts/$(1) ]; then \
      SCRIPT=../scripts/$(1); \
  else \
      echo "✖ Missing script $(1)"; \
      exit 1; \
  fi; \
  echo "→ $$SCRIPT $(2)"; \
  $(PYTHON) $$SCRIPT $(2)
endef

SRC          := tex
BUILD        := build
FINAL        := final
LATEX_SOURCE := $(SRC)/mini-writeup.tex
PDF_BUILD    := $(BUILD)/mini-writeup.pdf
PDF_FINAL    := $(FINAL)/mini-writeup.pdf

TABLE_SRC    := ../results/cleaned
FIGURE_SRC   := ../results/figures
IRF_SRC      := ../results/user_irfs_eng_vs_noneng_remote_hybrid

OVERLEAF_BASE := /Users/saul/Dropbox/Apps/Overleaf/WFH Startups/Current
DEST_REPORTS  := $(OVERLEAF_BASE)/Reports
DEST_RESULTS  := $(OVERLEAF_BASE)/Results
DEST_TABLES   := $(DEST_RESULTS)/Tables
DEST_FIGURES  := $(DEST_RESULTS)/Figures

# Whitelist of cleaned LaTeX tables that may be synced to Overleaf.
OVERLEAF_TABLE_WHITELIST := \
  $(TABLE_SRC)/table_of_means.tex \
  $(TABLE_SRC)/user_productivity_precovid_total.tex \
  $(TABLE_SRC)/user_productivity_precovid_restricted.tex \
  $(TABLE_SRC)/user_productivity_fr_focus_precovid.tex \
  $(TABLE_SRC)/user_productivity_pairwise_precovid.tex \
  $(TABLE_SRC)/user_mechanisms_with_growth_precovid_iv.tex \
  $(TABLE_SRC)/first_stage_summary.tex \
  $(TABLE_SRC)/firm_scaling_precovid.tex

OVERLEAF_FIGURE_WHITELIST := \
  firm_teleworkable_remote.png \
  firm_age_lt100_remote.png \
  user_event_study_precovid_ols.png \
  firm_event_study_growth_ols.png \
  firm_event_study_join_rate_ols.png \
  firm_event_study_leave_rate_ols.png \
  firm_event_study_job_postings_ols.png \
  firm_event_study_hires_per_job_posting_ols.png \
  irf_remote_eng.png \
  irf_hybrid_eng.png

.PHONY: mini-writeup mini-writeup-inputs mini-writeup-pdf clean

mini-writeup-inputs:
	@echo "[1/2] Refreshing mini-writeup inputs"
	@$(PYTHON) ../scripts/build_table_of_means.py
	@MPLBACKEND=Agg $(PYTHON) ../scripts/figures.py
	@$(call RUN_PYSCRIPT,create_user_productivity_table.py,--variant precovid --outcome-set total)
	@$(call RUN_PYSCRIPT,create_user_productivity_table.py,--variant precovid --outcome-set restricted)
	@$(call RUN_PYSCRIPT,create_user_productivity_fr_focus_table.py,--variant precovid)
	@$(call RUN_PYSCRIPT,create_user_productivity_pairwise_table.py,--variant precovid)
	@$(call RUN_PYSCRIPT,create_first_stage_summary_table.py,)
	@$(call RUN_PYSCRIPT,create_user_mechanisms_with_growth_table.py,--variant precovid)
	@$(call RUN_PYSCRIPT,create_firm_scaling_vacancies_styled_table.py,)
	@$(call RUN_PYSCRIPT,create_firm_scaling_role_group_table.py,)
	@$(call RUN_PYSCRIPT,create_firm_scaling_role_table.py,)
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/cleaned/user_event_study_precovid/ols_total_contributions_q100.csv \
		--output ../results/figures/user_event_study_precovid_ols.png \
		--ylabel "Contribution Rank" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/cleaned/ols_growth_rate_we.csv \
		--output ../results/figures/firm_event_study_growth_ols.png \
		--xlabel "Year-half" --ylabel "Growth rate" --series ols \
		--title "Event study: firm growth (OLS)" \
		--limit-ols ../results/cleaned/ols_growth_rate_we.csv \
		--limit-ols ../results/cleaned/ols_join_rate_we.csv \
		--limit-ols ../results/cleaned/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/cleaned/ols_join_rate_we.csv \
		--output ../results/figures/firm_event_study_join_rate_ols.png \
		--xlabel "Year-half" --ylabel "Join rate" --series ols \
		--title "Event study: join rate (OLS)" \
		--limit-ols ../results/cleaned/ols_growth_rate_we.csv \
		--limit-ols ../results/cleaned/ols_join_rate_we.csv \
		--limit-ols ../results/cleaned/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/cleaned/ols_leave_rate_we.csv \
		--output ../results/figures/firm_event_study_leave_rate_ols.png \
		--xlabel "Year-half" --ylabel "Leave rate" --series ols \
		--title "Event study: leave rate (OLS)" \
		--limit-ols ../results/cleaned/ols_growth_rate_we.csv \
		--limit-ols ../results/cleaned/ols_join_rate_we.csv \
		--limit-ols ../results/cleaned/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ../scripts/plot_user_irfs_remote_hybrid.py
	@echo "[2/2] Syncing whitelisted artefacts to Overleaf"
	@mkdir -p "$(DEST_RESULTS)" "$(DEST_TABLES)" "$(DEST_FIGURES)"
	@for src in $(OVERLEAF_TABLE_WHITELIST); do \
		if [ ! -f "$$src" ]; then \
			echo "✖ Missing expected table $$src"; \
			exit 1; \
		fi; \
		base=$$(basename $$src); \
		rm -f "$(DEST_TABLES)/$$base"; \
		cp "$$src" "$(DEST_TABLES)/$$base"; \
	done
	@for name in $(OVERLEAF_FIGURE_WHITELIST); do \
		if [ -f "$(FIGURE_SRC)/$$name" ]; then \
			src="$(FIGURE_SRC)/$$name"; \
		elif [ -f "$(IRF_SRC)/$$name" ]; then \
			src="$(IRF_SRC)/$$name"; \
		else \
			echo "✖ Missing expected figure $$name"; \
			exit 1; \
		fi; \
		rm -f "$(DEST_FIGURES)/$$name"; \
		cp "$$src" "$(DEST_FIGURES)/$$name"; \
	done
	@echo "✓ Tables copied to $(DEST_TABLES)"
	@echo "✓ Figures copied to $(DEST_FIGURES)"

mini-writeup-pdf:
	@echo "Compiling mini-writeup PDF"
	@mkdir -p "$(BUILD)"
	@latexmk -pdf -interaction=nonstopmode -output-directory="$(BUILD)" "$(LATEX_SOURCE)"
	@mkdir -p "$(FINAL)"
	@cp "$(PDF_BUILD)" "$(FINAL)/"
	@mkdir -p "$(DEST_REPORTS)"
	@cp "$(PDF_FINAL)" "$(DEST_REPORTS)/"
	@echo "✓ mini-writeup.pdf copied to $(DEST_REPORTS)"

mini-writeup: mini-writeup-pdf

clean:
	@rm -rf "$(BUILD)" "$(FINAL)"
