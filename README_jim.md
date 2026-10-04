# Module 6 — Individual Data Cleaning
Author: Hongkun (Jim) Dong

## Purpose
Prepare Herculean price, news, and filing data for comparing AAPL,
MSFT, GOOGL, AMZN, NVDA, META, and TSLA. The project supports
selecting companies for further equity research using adjusted-price
performance, daily return volatility, and trading volume.

## Data source
Dataset: TheFinAI/Herculean
Source: https://huggingface.co/datasets/TheFinAI/Herculean
Download date: October 3, 2026
Version: Files downloaded from the main revision on that date;
the exact upstream revision was not recorded.

Download prices.parquet, news.parquet, and filings.parquet from:
https://huggingface.co/datasets/TheFinAI/Herculean/tree/main/data

Place them in data/raw/. Keep these original files unchanged.

## Setup
Run these commands from the project root on macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements_jim.txt
```

## Run
```bash
.venv/bin/python cleaning_jim.py
```

Alternatively, open cleaning_jim.ipynb, select the project’s
.venv kernel, restart the kernel, and run all cells.

## Cleaning decisions
- Keep the seven companies in the project scope; exclude ADBE.
- Convert dates to pandas datetime values.
- Preserve original IDs and price and volume values.
- Decode HTML entities in filing text.
- Sort observations by company and date.
- Retain the missing first return for each company.

## Expected results
Cleaned row counts:
- Prices: 2,324
- News: 3,402
- Filings: 63

Files written to outputs/:
- prices_clean.parquet
- news_clean.parquet
- filings_clean.parquet
- prices_analysis.parquet
- stock_metrics.csv
- record_checks.csv

Files written to samples/:
- prices_sample.csv — 28 rows
- news_sample.csv — 7 rows
- filings_sample.csv — 7 rows

## Sample selection
The 42-row sample includes the first two and last two price
observations per company, plus the first news and filing observation
per company. Price examples cover missing first returns, first
calculable returns, and end-of-period observations.

## Verification
The code checks duplicates, missing values, date conversions,
positive prices, volume validity, and OHLC consistency.
It reconciles row counts and total volume, checks preservation
of retained values, verifies five selected records, and compares
one calculated return with an independent scalar calculation.

## Limitations
Trading-calendar completeness has not been verified. Returns use
consecutive available observations. Volatility is the sample
standard deviation of returns and is not annualized.
News highlights are AI-generated summaries; filings contain excerpts.
No tables are merged in this assignment.

## GitHub submission
Repository: https://github.com/xunyangy-afk/Python-Group-Project
Branch: Jim-Work
Branch URL: https://github.com/xunyangy-afk/Python-Group-Project/tree/Jim-Work
Verified code commit: To be added after committing.