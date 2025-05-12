SHELL := /usr/bin/env bash
SRC        := tex
SCRIPTS   := $(SRC)/scripts
RESULTS_SRC := $(SRC)/results/results.tex
SLIDES_SRC := $(SRC)/slides/slides.tex
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

slides:
	mkdir -p $(BUILD)
	pdflatex -halt-on-error -interaction=nonstopmode \
	  -output-directory=$(BUILD) $(SLIDES_SRC)

final: final-results final-slides

final-results: report
	@mkdir -p $(FINAL)
	@cp $(BUILD)/results.pdf  $(FINAL)/

final-slides: slides
	@mkdir -p $(FINAL)
	@cp $(BUILD)/slides.pdf   $(FINAL)/

clean:
	rm -rf $(BUILD) $(FINAL)