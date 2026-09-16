PYTHON ?= python

.PHONY: assets figures tables diagrams

assets: figures tables diagrams

figures:
	$(PYTHON) figures/scripts/generate_figures.py

tables:
	$(PYTHON) tables/scripts/generate_tables.py

diagrams:
	$(PYTHON) diagrams/scripts/generate_diagrams.py
