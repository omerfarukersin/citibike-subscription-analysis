PY ?= .venv/bin/python

.PHONY: all setup download ingest extract load analyze docs tableau clean lint test help

all: download ingest extract load analyze docs tableau

download:            ## trip files (sample + all Chicago months) and monthly report PDFs
	$(PY) src/download_trips.py
	$(PY) src/download_reports.py

ingest:              ## BTS, NOAA, survey
	$(PY) src/ingest_sources.py

extract:             ## report PDFs and pricing pages -> staging tables
	$(PY) src/extract_reports.py
	$(PY) src/extract_pricing.py

load:                ## build citibike.duckdb (ERD)
	$(PY) src/load.py

analyze:             ## KPI/hypothesis/QA views + Tableau CSVs
	$(PY) src/analyze.py

tableau:             ## Tableau workbook from the CSV marts (no database or Tableau install needed)
	$(PY) tableau/build_story.py

clean:               ## remove the database (the committed CSV marts are kept)
	rm -f citibike.duckdb

docs:                ## data dictionary + ERD (Mermaid source; PNG via mermaid-cli)
	$(PY) src/docs.py

setup:               ## create the Python environment (incl. pytest and ruff)
	python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

lint:                ## ruff (config in pyproject.toml)
	$(PY) -m ruff check src tableau tests

test:                ## unit tests, SQL compile on an empty DuckDB, checks on the committed QA outputs
	$(PY) -m pytest -q

help:                ## list the targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'
