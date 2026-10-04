# Column-Level Data Cleaning Plan

## Summary

This document records the raw data inspection results and proposed cleaning rules for the files in `data/raw/data`. The goal is to define the cleaning approach before making further changes to `clean_data.py`.

The plan covers:

- `prices.parquet`
- `news.parquet`
- `filings.parquet`

## Key Findings

Raw files inspected:

- `prices.parquet`: 2,656 rows, 9 columns
- `news.parquet`: 3,888 rows, 4 columns
- `filings.parquet`: 73 rows, 6 columns

Inspection results:

- No missing values were found in the raw files.
- No full-row duplicates were found.
- No duplicate business keys were found.
- Symbols are consistent across files: `AAPL`, `ADBE`, `AMZN`, `GOOGL`, `META`, `MSFT`, `NVDA`, `TSLA`.
- Price sanity checks passed: no negative volume, no non-positive prices, and no `high < low`.
- Filing document types are only `10-Q` and `10-K`.
- Text fields contain HTML entities and smart punctuation that should be normalized.

## Cleaning Governance Rules

- Do not drop rows without documenting the reason, the rule that caused the drop, and the number of rows affected.
- Flag suspicious values before deciding whether to keep, correct, or remove them.
- Do not change units or categories without documenting the original value, the new value, and why the change is appropriate.
- Preserve the original raw columns where practical when creating normalized or derived versions.
- After each major transformation, report what changed:
  - row count before and after
  - column count before and after
  - rows flagged
  - rows removed, if any
  - columns added or changed
  - categories or units changed
- Store transformation notes in a cleaning report so dashboard users can trace how the final data was produced.

## Shared Column Cleaning Rules

| Column | Cleaning Rule | Validation Rule |
| --- | --- | --- |
| `id` | Keep as an integer identifier. | Must be non-null and unique within each source table. |
| `symbol` | Trim whitespace and convert to uppercase; document this as category standardization, not a category meaning change. | Must be one of `AAPL`, `ADBE`, `AMZN`, `GOOGL`, `META`, `MSFT`, `NVDA`, `TSLA`. Unknown symbols should be flagged before any removal. |
| `date` | Convert from string/object to datetime; document the type conversion. | Invalid dates should be flagged before any removal. Use as the dashboard join key. |

## `prices.parquet` Cleaning Rules

| Column | Cleaning Rule | Validation Rule |
| --- | --- | --- |
| `id` | Keep as integer. | Must be non-null and unique within `prices.parquet`. |
| `symbol` | Trim whitespace and uppercase; document the category standardization. | Must be one of the 8 known ticker symbols. Unknown symbols should be flagged. |
| `date` | Convert to datetime; document the type conversion. | Must be valid and non-null. Invalid dates should be flagged. |
| `open` | Convert to numeric; keep the original stock-price unit. | Must be greater than 0. Non-positive values should be flagged. |
| `high` | Convert to numeric; keep the original stock-price unit. | Must be greater than 0 and greater than or equal to `low`. Violations should be flagged. |
| `low` | Convert to numeric; keep the original stock-price unit. | Must be greater than 0. Non-positive values should be flagged. |
| `close` | Convert to numeric; keep the original stock-price unit. | Must be greater than 0. Non-positive values should be flagged. |
| `adj_close` | Convert to numeric; keep the original stock-price unit. | Must be greater than 0. Non-positive values should be flagged. |
| `volume` | Convert to integer; keep the original share-count unit. | Must be greater than or equal to 0. Negative values should be flagged. |

Additional derived fields for analysis and dashboard use:

- `daily_return`: percent change in `adj_close` by symbol.
- `dollar_change`: difference in `adj_close` from the previous trading day by symbol.
- `intraday_range_pct`: `(high - low) / open`.
- `trading_year`: year extracted from `date`.
- `trading_month`: year-month extracted from `date`.

Sort cleaned prices by `symbol` and `date`.

After transforming prices, report numeric conversions, flagged price rows, derived columns added, and row-count changes.

## `news.parquet` Cleaning Rules

| Column | Cleaning Rule | Validation Rule |
| --- | --- | --- |
| `id` | Keep as integer. | Must be non-null and unique within `news.parquet`. |
| `symbol` | Trim whitespace and uppercase; document the category standardization. | Must be one of the 8 known ticker symbols. Unknown symbols should be flagged. |
| `date` | Convert to datetime; document the type conversion. | Must be valid and non-null. Invalid dates should be flagged. |
| `highlights` | HTML-unescape text, normalize smart punctuation, collapse repeated whitespace, and trim leading/trailing whitespace. | Cleaned text must be non-empty. Empty cleaned text should be flagged before deciding whether to remove the row. |

Additional derived field:

- `highlight_length`: character length of cleaned `highlights`.

Keep one row per `symbol` and `date`.

After transforming news, report text normalization changes, rows flagged for empty text, derived columns added, and row-count changes.

## `filings.parquet` Cleaning Rules

| Column | Cleaning Rule | Validation Rule |
| --- | --- | --- |
| `id` | Keep as integer. | Must be non-null and unique within `filings.parquet`. |
| `symbol` | Trim whitespace and uppercase; document the category standardization. | Must be one of the 8 known ticker symbols. Unknown symbols should be flagged. |
| `date` | Convert to datetime; document the type conversion. | Must be valid and non-null. Invalid dates should be flagged. |
| `document_type` | Trim whitespace and convert to uppercase; document the category standardization. | Must be `10-Q` or `10-K`. Unknown document types should be flagged before any category change or removal. |
| `mda_content` | HTML-unescape text, normalize punctuation, collapse repeated whitespace, and trim leading/trailing whitespace. | Cleaned text must be non-empty. Empty cleaned text should be flagged before deciding whether to remove the row. |
| `risk_content` | Apply the same cleaning as `mda_content`. | Cleaned text must be non-empty. Empty cleaned text should be flagged before deciding whether to remove the row. |

Additional derived fields:

- `mda_content_length`: character length of cleaned `mda_content`.
- `risk_content_length`: character length of cleaned `risk_content`.

Keep one row per `symbol`, `date`, and `document_type`.

After transforming filings, report document-type standardization, text normalization changes, rows flagged for suspicious content, derived columns added, and row-count changes.

## Dashboard-Ready Merge Rules

- Use cleaned prices as the base table because prices represent trading days.
- Left-join daily news by `symbol` and `date`.
- Left-join filings by `symbol` and `date`.
- Add `news_count`, `filing_count`, `has_news`, `has_filing`, and `filing_types`.
- Preserve rows without filings because filings are event-based and are not expected every trading day.
- After merging, report matched and unmatched row counts for news and filings.

## Test Plan

- Confirm each raw file can be read successfully.
- Confirm cleaned row counts match expectations unless rows are explicitly removed for documented reasons.
- Validate no duplicate keys:
  - Prices: `symbol`, `date`
  - News: `symbol`, `date`
  - Filings: `symbol`, `date`, `document_type`
- Validate price rules:
  - Prices are greater than 0.
  - Volume is greater than or equal to 0.
  - `high >= low`.
- Validate text fields are non-empty after cleaning.
- Validate suspicious values are flagged before rows are corrected or removed.
- Validate category and unit changes are documented.
- Validate each major transformation has a before-and-after report.
- Validate dashboard output has one row per `symbol` and trading `date`.
- Confirm only expected missing values remain: first-day returns per symbol.

## Assumptions

- This file should live at `Python-Group-Project/data-cleaning/plan.md`.
- Do not make further changes to `clean_data.py` until the cleaning rules in this file are reviewed.
- Keep both CSV and parquet as acceptable future cleaned output formats for dashboard use.
