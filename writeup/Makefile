# Minimal Makefile dedicated to the mini-writeup

SHELL := /usr/bin/env bash
.ONESHELL:
.SHELLFLAGS := -e -o pipefail -c

PYTHON ?= python

# Resolve scripts from ./py (writeup-specific) or ../src/py (shared helpers)
define RUN_PYSCRIPT
  if [ -f ./py/$(1) ]; then \
      SCRIPT=./py/$(1); \
  elif [ -f ../src/py/$(1) ]; then \
      SCRIPT=../src/py/$(1); \
  else \
      echo "✖ Missing script $(1)"; \
      exit 1; \
  fi; \
  echo "→ $$SCRIPT $(2)"; \
  $(PYTHON) $$SCRIPT $(2)
endef

SRC          := tex
BUILD        := $(SRC)/build
FINAL        := $(SRC)/final
LATEX_SOURCE := $(SRC)/mini-writeup.tex
PDF_BUILD    := $(BUILD)/mini-writeup.pdf
PDF_FINAL    := $(FINAL)/mini-writeup.pdf

TABLE_SRC    := ../results/final/tex
FIGURE_SRC   := ../results/final/figures
IRF_SRC      := ../results/user_irfs_eng_vs_noneng_remote_hybrid

OVERLEAF_BASE := /Users/saul/Dropbox/Apps/Overleaf/WFH Startups/Current
DEST_REPORTS  := $(OVERLEAF_BASE)/Reports
DEST_RESULTS  := $(OVERLEAF_BASE)/Results
DEST_TABLES   := $(DEST_RESULTS)/Tables
DEST_FIGURES  := $(DEST_RESULTS)/Figures

# Whitelist of cleaned LaTeX tables that may be synced to Overleaf.
OVERLEAF_TABLE_WHITELIST := \
  $(TABLE_SRC)/table_of_means.tex \
  $(TABLE_SRC)/user_productivity_precovid_total_ols_single.tex \
  $(TABLE_SRC)/user_productivity_precovid_total_iv_single.tex \
  $(TABLE_SRC)/firm_scaling_precovid_cols1_4.tex \
  $(TABLE_SRC)/firm_scaling_precovid_cols5_6.tex \
  $(TABLE_SRC)/user_mechanisms_with_growth_precovid.tex \
  $(TABLE_SRC)/user_wage_fe_variants_precovid_log_salary.tex \
  $(TABLE_SRC)/user_productivity_fr_focus_precovid.tex \
  $(TABLE_SRC)/first_stage_summary.tex \
  $(TABLE_SRC)/user_productivity_precovid_restricted.tex

OVERLEAF_FIGURE_WHITELIST := \
  firm_teleworkable_remote.png \
  firm_age_lt100_remote.png \
  user_event_study_precovid_ols.png \
  firm_event_study_growth_ols.png \
  firm_event_study_join_rate_ols.png \
  firm_event_study_leave_rate_ols.png \
  firm_event_study_job_postings_ols.png \
  firm_event_study_hires_per_job_posting_ols.png

.PHONY: mini-writeup mini-writeup-inputs mini-writeup-pdf clean
.PHONY: heterogeneity-pdf user-wage-fe-pdf firm-wage-log-pdf

mini-writeup-inputs:
	@echo "[1/2] Refreshing mini-writeup inputs"
	@$(PYTHON) ../src/py/build_table_of_means.py
	@MPLBACKEND=Agg $(PYTHON) ../src/py/figures_binsreg.py
	@$(call RUN_PYSCRIPT,create_user_productivity_table.py,--variant precovid --outcome-set total)
	@$(call RUN_PYSCRIPT,create_user_productivity_panel_tables.py,--variant precovid --outcome-set total)
	@$(call RUN_PYSCRIPT,create_user_productivity_split_tables.py,--variant precovid --outcome-set total)
	@$(call RUN_PYSCRIPT,create_user_productivity_table.py,--variant precovid --outcome-set restricted)
	@$(call RUN_PYSCRIPT,create_user_productivity_fr_focus_table.py,--variant precovid)
	@$(call RUN_PYSCRIPT,create_user_wage_tables.py,--variant precovid)
	@$(call RUN_PYSCRIPT,create_first_stage_summary_table.py,)
	@$(call RUN_PYSCRIPT,create_user_mechanisms_with_growth_table.py,--variant precovid)
	@$(call RUN_PYSCRIPT,create_firm_scaling_split_tables.py,)
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/user_event_study_precovid/ols_total_contributions_q100.csv \
		--output ../results/final/figures/user_event_study_precovid_ols.png \
		--ylabel "Contribution Rank" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study/ols_growth_rate_we.csv \
		--output ../results/final/figures/firm_event_study_growth_ols.png \
		--xlabel "Year-half" --ylabel "Growth" --series ols \
		--limit-ols ../results/raw/firm_event_study/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study/ols_join_rate_we.csv \
		--output ../results/final/figures/firm_event_study_join_rate_ols.png \
		--xlabel "Year-half" --ylabel "Join" --series ols \
		--limit-ols ../results/raw/firm_event_study/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study/ols_leave_rate_we.csv \
		--output ../results/final/figures/firm_event_study_leave_rate_ols.png \
		--xlabel "Year-half" --ylabel "Leave" --series ols \
		--limit-ols ../results/raw/firm_event_study/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_vacancy_event_study/ols_vacancies_thousands.csv \
		--output ../results/final/figures/firm_event_study_job_postings_ols.png \
		--xlabel "" --ylabel "Job postings (1,000s)" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_vacancy_event_study/ols_hires_to_vacancies_winsor.csv \
		--output ../results/final/figures/firm_event_study_hires_per_job_posting_ols.png \
		--xlabel "" --ylabel "Hires per job posting" --series ols
	@if [ -f ../src/py/plot_user_irfs_remote_hybrid.py ]; then \
		MPLBACKEND=Agg $(PYTHON) ../src/py/plot_user_irfs_remote_hybrid.py; \
	else \
		echo "⚠ Skipping plot_user_irfs_remote_hybrid.py (script not found)"; \
	fi
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

mini-writeup-pdf: mini-writeup-inputs
	@echo "Compiling mini-writeup PDF"
	@mkdir -p "$(BUILD)"
	@latexmk -pdf -interaction=nonstopmode -output-directory="$(BUILD)" "$(LATEX_SOURCE)"
	@mkdir -p "$(FINAL)"
	@cp "$(PDF_BUILD)" "$(FINAL)/"
	@mkdir -p "$(DEST_REPORTS)"
	@cp "$(PDF_FINAL)" "$(DEST_REPORTS)/"
	@echo "✓ mini-writeup.pdf copied to $(DEST_REPORTS)"

mini-writeup: mini-writeup-pdf

heterogeneity-pdf:
	@echo "Compiling heterogeneity tables PDF"
	@latexmk -pdf -interaction=nonstopmode -output-directory="tex/build" "tex/heterogeneity_tables.tex"
	@echo "✓ heterogeneity_tables.pdf available at tex/build/"

user-wage-fe-pdf:
	@echo "Compiling user wage FE variants PDF"
	@latexmk -pdf -interaction=nonstopmode -output-directory="tex/build" "tex/user_wage_fe_variants.tex"
	@echo "✓ user_wage_fe_variants.pdf available at tex/build/"

firm-wage-log-pdf:
	@echo "Compiling firm log wage PDF"
	@latexmk -pdf -interaction=nonstopmode -output-directory="tex/build" "tex/firm_wage_log.tex"
	@echo "✓ firm_wage_log.pdf available at tex/build/"

clean:
	@rm -rf "$(BUILD)" "$(FINAL)"
