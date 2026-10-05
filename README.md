# Magnificent Seven Financial Comparison Dashboard

## Project
This repository contains the individual cleaning workflow for the Module 6 project assignment for Nicole Lainez.

## Data source and version
- Source: TheFinAI/Herculean on Hugging Face
- Dataset version/download date: downloaded 2026-10-05 from the public Hugging Face dataset snapshot
- Tables used: prices, news, filings
- Source snapshot: original parquet exports stored in `data/raw/`
- Branch: `cleaning-nicole`
- Branch URL: https://github.com/xunyangy-afk/Python-Group-Project/tree/cleaning-nicole
- Commit ID: See the generated assignment PDF for the source revision and GitHub for the final report commit.

## Project question
How can Herculean’s financial data be transformed into an interactive dashboard for comparing the Magnificent Seven companies?

## Objective
Transform the raw Herculean financial data into a dashboard-ready M7 dataset focused on AAPL, AMZN, GOOGL, META, MSFT, NVDA, and TSLA while preserving the original raw files and excluding ADBE from scope.

## Required outputs
- Cleaned price data: `data/cleaned/prices_cleaned.parquet`
- Cleaned news data: `data/cleaned/news_cleaned.parquet`
- Cleaned filings data: `data/cleaned/filings_cleaned.parquet`
- Cleaned sample: `data/cleaned/m7_sample_50.csv`
- Cleaning log: `cleaning_decision_log.md`
- Verification evidence: `verification_evidence.md`
- Checklist: `checklist.md`
- Record checks: `record_checks.md`
- Individual PDF: `Nicole_Lainez_Module_6_Data_Cleaning_Assignment.pdf`

## Exact run instructions
```bash
cd /Users/nicolelainez/Python-Group-Project
uv run python clean_data.py
```

## Expected behavior
Running the script from the original raw data regenerates the same cleaned parquet files, the sample, and the evidence outputs. The raw directory remains unchanged.

## Sample selection
The cleaned sample file `data/cleaned/m7_sample_50.csv` contains no more than 50 rows and includes difficult cases: the first trading day by symbol to test the initial return and normalization logic, a high-volume day to test positive-volume handling, a representative news entry to verify text preservation, one filing row per symbol family to confirm valid document types, and the ADBE exclusion check. The sample is intentionally not used as proof of full-dataset validity; it is a focused QA subset for edge cases and readability.

## Independent validation of one Codex suggestion
Nicole independently checked the project-scope suggestion by comparing the raw symbol counts before filtering to the filtered M7 counts. The difference matched the Adobe row counts exactly, which confirmed that ADBE was excluded without altering any of the Magnificent Seven records.

## Notes
- No missing values were found in the raw files.
- The project-scope filter removes ADBE only, because Adobe is not part of the Magnificent Seven.
- No fabricated replacements are used; any suspicious record would raise a validation error instead of being silently modified.
- The cleaned data files and markdown evidence reproduce identically across reruns. The generated PDF content is stable, but the reportlab library may embed a new timestamp in the PDF output, changing the byte-level hash even though the text content is the same.
