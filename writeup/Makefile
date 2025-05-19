SHELL := /usr/bin/env bash
SRC        := tex
REPORT_SRC := $(SRC)/results/consolidated-report.tex
BUILD  := build
FINAL  := final
.PHONY: all report clean

all: report

clean:
	@rm -rf $(BUILD) $(FINAL)

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
	@python py/create_user_productivity_ols_table.py
	@python py/create_user_productivity_iv_table.py
	@echo "Compiling consolidated report..."
	@pdflatex -halt-on-error -interaction=nonstopmode \
	  -output-directory=$(BUILD) $(REPORT_SRC)
	@mkdir -p $(FINAL)
	@cp $(BUILD)/consolidated-report.pdf $(FINAL)/
