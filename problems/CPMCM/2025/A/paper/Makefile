PYTHON ?= python

.PHONY: assets figures tables

assets: figures tables

figures:
	$(PYTHON) figures/scripts/generate_figures.py

tables:
	$(PYTHON) tables/scripts/generate_tables.py
