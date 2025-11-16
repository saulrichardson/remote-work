# Minimal Makefile dedicated to the mini-writeup

SHELL := /usr/bin/env bash
.ONESHELL:
.SHELLFLAGS := -e -o pipefail -c

PYTHON ?= python
LATEXMK ?= latexmk

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

TABLE_SRC    := ../results/cleaned/tex
FIGURE_SRC   := ../results/cleaned/figures
IRF_SRC      := ../results/user_irfs_eng_vs_noneng_remote_hybrid

OVERLEAF_BASE := /Users/saulrichardson/Library/CloudStorage/Dropbox/Apps/Overleaf/WFH Startups/Current
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
  $(TABLE_SRC)/user_productivity_traits_dual_precovid_ols.tex \
  $(TABLE_SRC)/user_productivity_precovid_nonsoftware.tex \
  $(TABLE_SRC)/firm_scaling_location_ratios.tex \
  $(TABLE_SRC)/first_stage_summary.tex \
  $(TABLE_SRC)/user_productivity_precovid_restricted.tex \
  $(TABLE_SRC)/startup_cutoff_total_contributions_q100.tex \
  $(TABLE_SRC)/startup_cutoff_restricted_contributions_q100.tex \
  $(TABLE_SRC)/startup_cutoff_growth_rate_we.tex \
  $(TABLE_SRC)/startup_cutoff_join_rate_we.tex \
  $(TABLE_SRC)/startup_cutoff_leave_rate_we.tex \
  $(TABLE_SRC)/user_productivity_precovid_robustness_part1.tex \
  $(TABLE_SRC)/user_productivity_precovid_robustness_part2.tex

OVERLEAF_FIGURE_WHITELIST := \
  firm_teleworkable_remote.png \
  firm_age_lt100_remote.png \
  user_event_study_precovid_ols.png \
  firm_event_study_growth_ols.png \
  firm_event_study_join_rate_ols.png \
  firm_event_study_leave_rate_ols.png \
  firm_event_study_job_postings_ols.png \
  firm_event_study_hires_per_job_posting_ols.png \
  user_event_study_fullrem_precovid_ols.png \
  firm_event_study_fullrem_growth_ols.png \
  firm_event_study_fullrem_join_rate_ols.png \
  firm_event_study_fullrem_leave_rate_ols.png \
  firm_event_study_fullrem_job_postings_ols.png \
  firm_event_study_fullrem_hires_per_job_posting_ols.png \
  panelA_hybrid_engineer.png \
  panelA_hybrid_nonengineer.png \
  panelB_fullremote_engineer.png \
  panelB_fullremote_nonengineer.png \
  startup_cutoff_bars_total_contributions_q100.png \
  startup_cutoff_bars_growth_rate_we.png \
  top_employment_csa_remote_startup.png \
  top_employment_msa_remote_startup.png

.PHONY: mini-writeup mini-writeup-inputs mini-writeup-pdf clean
.PHONY: heterogeneity-pdf user-wage-fe-pdf firm-wage-log-pdf

mini-writeup-inputs:
	@echo "[1/2] Refreshing mini-writeup inputs"
	@$(PYTHON) ../src/py/build_table_of_means.py
	@MPLBACKEND=Agg $(PYTHON) ../src/py/figures.py
	@$(call RUN_PYSCRIPT,user_productivity/build_baseline_table.py,--variant precovid --outcome-set total)
	@$(call RUN_PYSCRIPT,user_productivity/build_panel_tables.py,--variant precovid --outcome-set total)
	@$(call RUN_PYSCRIPT,user_productivity/build_single_model_tables.py,--variant precovid --outcome-set total)
	@$(call RUN_PYSCRIPT,user_productivity/build_baseline_table.py,--variant precovid --outcome-set restricted)
	@$(call RUN_PYSCRIPT,user_productivity/build_fr_focus_table.py,--variant precovid)
	@$(call RUN_PYSCRIPT,user_productivity/build_traits_dual_table.py,)
	@$(call RUN_PYSCRIPT,user_productivity/build_wage_fe_tables.py,--variant precovid)
	@$(call RUN_PYSCRIPT,user_productivity/build_first_stage_table.py,)
	@$(call RUN_PYSCRIPT,user_productivity/build_mechanisms_with_growth_tables.py,--variant precovid)
	@$(call RUN_PYSCRIPT,startup_cutoff/build_robustness_tables.py,)
	@$(call RUN_PYSCRIPT,firm_scaling/build_growth_split_tables.py,)
	@$(call RUN_PYSCRIPT,firm_scaling/build_geography_table.py,)
	@$(call RUN_PYSCRIPT,firm_scaling/build_location_ratio_table.py,)
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/user_event_study_precovid/ols_total_contributions_q100.csv \
		--output ../results/cleaned/figures/user_event_study_precovid_ols.png \
		--ylabel "Contribution Rank" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study/ols_growth_rate_we.csv \
		--output ../results/cleaned/figures/firm_event_study_growth_ols.png \
		--xlabel "Year-half" --ylabel "Growth" --series ols \
		--limit-ols ../results/raw/firm_event_study/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study/ols_join_rate_we.csv \
		--output ../results/cleaned/figures/firm_event_study_join_rate_ols.png \
		--xlabel "Year-half" --ylabel "Join" --series ols \
		--limit-ols ../results/raw/firm_event_study/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study/ols_leave_rate_we.csv \
		--output ../results/cleaned/figures/firm_event_study_leave_rate_ols.png \
		--xlabel "Year-half" --ylabel "Leave" --series ols \
		--limit-ols ../results/raw/firm_event_study/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_vacancy_event_study/ols_vacancies_thousands.csv \
		--output ../results/cleaned/figures/firm_event_study_job_postings_ols.png \
		--xlabel "" --ylabel "Job postings (1,000s)" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_vacancy_event_study/ols_hires_to_vacancies_winsor.csv \
		--output ../results/cleaned/figures/firm_event_study_hires_per_job_posting_ols.png \
		--xlabel "" --ylabel "Hires per job posting" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/user_event_study_fullrem_precovid/ols_total_contributions_q100.csv \
		--output ../results/cleaned/figures/user_event_study_fullrem_precovid_ols.png \
		--ylabel "Contribution Rank" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study_fullrem/ols_growth_rate_we.csv \
		--output ../results/cleaned/figures/firm_event_study_fullrem_growth_ols.png \
		--xlabel "Year-half" --ylabel "Growth" --series ols \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study_fullrem/ols_join_rate_we.csv \
		--output ../results/cleaned/figures/firm_event_study_fullrem_join_rate_ols.png \
		--xlabel "Year-half" --ylabel "Join" --series ols \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_event_study_fullrem/ols_leave_rate_we.csv \
		--output ../results/cleaned/figures/firm_event_study_fullrem_leave_rate_ols.png \
		--xlabel "Year-half" --ylabel "Leave" --series ols \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_growth_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_join_rate_we.csv \
		--limit-ols ../results/raw/firm_event_study_fullrem/ols_leave_rate_we.csv
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_vacancy_event_study_fullrem/ols_vacancies_thousands.csv \
		--output ../results/cleaned/figures/firm_event_study_fullrem_job_postings_ols.png \
		--xlabel "" --ylabel "Job postings (1,000s)" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/plot_event_study.py \
		--ols ../results/raw/firm_vacancy_event_study_fullrem/ols_hires_to_vacancies_winsor.csv \
		--output ../results/cleaned/figures/firm_event_study_fullrem_hires_per_job_posting_ols.png \
		--xlabel "" --ylabel "Hires per job posting" --series ols
	@MPLBACKEND=Agg $(PYTHON) ./py/startup_cutoff/plot_cutoff_bars.py
	@MPLBACKEND=Agg $(PYTHON) ../src/py/plot_user_irfs_eng_noneng_remote.py
	@$(PYTHON) ../src/py/build_top_msa_list.py --panel-variant precovid --rank-half 2019h2 --top-n 30
	@MPLBACKEND=Agg $(PYTHON) ./py/user_productivity/plot_csa_cleveland.py \
		--panel-variant precovid \
		--output ../results/cleaned/figures/top_employment_csa_remote_startup.png \
		--sort-column csa_rank
	@MPLBACKEND=Agg $(PYTHON) ./py/user_productivity/plot_csa_cleveland.py \
		--input ../results/raw/user_productivity_msa_interactions_precovid/consolidated_results_by_msa.csv \
		--output ../results/cleaned/figures/top_employment_msa_remote_startup.png \
		--name-column msa_name \
		--sort-column msa_rank
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
	@$(LATEXMK) -pdf -interaction=nonstopmode -output-directory="$(BUILD)" "$(LATEX_SOURCE)"
	@mkdir -p "$(FINAL)"
	@cp "$(PDF_BUILD)" "$(FINAL)/"
	@mkdir -p "$(DEST_REPORTS)"
	@cp "$(PDF_FINAL)" "$(DEST_REPORTS)/"
	@echo "✓ mini-writeup.pdf copied to $(DEST_REPORTS)"

mini-writeup: mini-writeup-pdf

heterogeneity-pdf:
	@echo "Compiling heterogeneity tables PDF"
	@$(LATEXMK) -pdf -interaction=nonstopmode -output-directory="tex/build" "tex/heterogeneity_tables.tex"
	@echo "✓ heterogeneity_tables.pdf available at tex/build/"

user-wage-fe-pdf:
	@echo "Compiling user wage FE variants PDF"
	@$(LATEXMK) -pdf -interaction=nonstopmode -output-directory="tex/build" "tex/user_wage_fe_variants.tex"
	@echo "✓ user_wage_fe_variants.pdf available at tex/build/"

firm-wage-log-pdf:
	@echo "Compiling firm log wage PDF"
	@$(LATEXMK) -pdf -interaction=nonstopmode -output-directory="tex/build" "tex/firm_wage_log.tex"
	@echo "✓ firm_wage_log.pdf available at tex/build/"

clean:
	@rm -rf "$(BUILD)" "$(FINAL)"
