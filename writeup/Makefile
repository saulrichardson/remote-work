SHELL := /usr/bin/env bash
SRC        := tex
SCRIPTS   := $(SRC)/scripts
RESULTS_SRC := $(SRC)/results/raw-results.tex
BUILD  := build
FINAL  := final
 .PHONY: all report slides final final-results final-slides clean

all: report slides
   

report:
	@mkdir -p $(BUILD)
	@echo "Replacing variable names in TeX tables..."
	@python $(SCRIPTS)/replace_tex_variables.py
	@echo "Compiling results document..."
	@pdflatex -halt-on-error -interaction=nonstopmode \
	  -output-directory=$(BUILD) $(RESULTS_SRC)


final-raw: report
	@mkdir -p $(FINAL)
	@cp $(BUILD)/raw-results.pdf  $(FINAL)/

clean:
	rm -rf $(BUILD) $(FINAL)
