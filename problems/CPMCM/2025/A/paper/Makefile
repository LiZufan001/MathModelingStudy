PYTHON ?= python
LATEXMK ?= latexmk

.PHONY: assets figures tables diagrams manuscript clean-manuscript

assets: figures tables diagrams

figures:
	$(PYTHON) figures/scripts/generate_figures.py

tables:
	$(PYTHON) tables/scripts/generate_tables.py

diagrams:
	$(PYTHON) diagrams/scripts/generate_diagrams.py

manuscript: assets
	cd manuscript && $(LATEXMK) -xelatex -file-line-error -halt-on-error -interaction=nonstopmode draft.tex

clean-manuscript:
	cd manuscript && $(LATEXMK) -C draft.tex
