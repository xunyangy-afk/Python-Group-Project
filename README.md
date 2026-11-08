# Magnificent Seven Data Workbench

**Live app:** [Open dashboard](https://python-group-project-axbyl7drczrarqhqkxbrtq.streamlit.app/)
**Demo video:** [Watch demo](https://youtu.be/rcjM6uIzBq8?si=R3smqC01dMyful57)

Prepare comparable prices, news digests, and filing excerpts for AAPL, AMZN, GOOGL, META, MSFT, NVDA, and TSLA. The intended user is a junior equity research analyst selecting 1–2 stocks for deeper research using price performance, volatility, trading volume, news, and filings. This project includes an interactive dashboard for comparing the seven companies, exploring price and trading volume, reviewing related news and filings, and exporting a research shortlist. The repository also provides data cleaning, analysis functions, cleaned datasets, and validation evidence. Use the live app and demo video links above to explore the dashboard and see the workflow in action.

The unified solution was merged through [PR #1](https://github.com/xunyangy-afk/Python-Group-Project/pull/1). [CLEANING_DECISIONS.md](CLEANING_DECISIONS.md) compares the six source branches and records adopted rules, reasons, and open questions. Rules without confirmed team agreement remain proposals.

## Run the dashboard locally

From the repository root, install dependencies and launch the app:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The dashboard loads the three complete cleaned datasets from `artifacts/`.
No additional row sampling is applied when loading these files. Company
and date selections filter the displayed analysis. Raw source files are
only needed to reproduce the cleaning pipeline, not to launch the dashboard.

## Repository

https://github.com/xunyangy-afk/Python-Group-Project

## Run the complete workflow

Use Python 3.13 from the repository root. Raw inputs are intentionally not stored in Git. Before running, place the complete `prices.parquet`, `news.parquet`, and `filings.parquet` snapshot in the ignored `sources/raw/` directory. Obtain the files from a team member holding this exact snapshot, or from an authorized source, and match all three SHA256 hashes in [sources/manifest.json](sources/manifest.json). Do not substitute samples or assume the latest upstream files are identical. Source access may require authentication; exact upstream revision remains unconfirmed.

After installing dependencies, `verify_cleaning.py` runs the risk tests, executes two full cleaning runs in fresh Python processes, and checks source preservation and output reproducibility.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe verify_cleaning.py
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python verify_cleaning.py
```

To run cleaning alone, use your environment's Python executable with:

```bash
python -m team_cleaning --raw-dir sources/raw --output-dir artifacts
```

Inputs must match the SHA256 hashes in `sources/manifest.json`. A new snapshot requires a reviewed manifest and fresh validation; do not bypass hash checks. Failures return a nonzero exit code. Old artifacts do not demonstrate that a failed run succeeded.

The recorded environment is Python 3.13.15, pandas 3.0.1, numpy 2.3.5, and pyarrow 25.0.0. `requirements.txt` pins direct and transitive dependencies. The pipeline does not install packages or replace source data at runtime. Byte-for-byte reproducibility was verified in this recorded environment.

## What is included in main

| Location | Contents |
|---|---|
| `team_cleaning/pipeline.py` | Reusable cleaning, scope filtering, quality flags, exclusions, reconciliation, exports, and join validation |
| `team_cleaning/analysis.py` | Adjusted-close returns and date-range-dependent normalization and interval metrics |
| `team_cleaning/__main__.py` | Command-line entry point |
| `tests/test_risks.py` | Eleven tests covering duplicates, conflicts, dates, missingness, text structure, numeric anomalies, calculations, joins, and source protection |
| `verify_cleaning.py` | Test runner and two-process full-snapshot reproducibility check |
| `sources/raw/` (local only; ignored) | Place the three complete source Parquet files here before running; these files are not included in Git |
| `sources/manifest.json` | Snapshot identity, attribution notes, byte sizes, SHA256 hashes, and provenance limitations |
| `sources/branch_revisions.json`, `sources/review_inventory.json` | Reviewed branch commits, file identities, and stored notebook execution inventory |
| `artifacts/*_clean.parquet` | Three complete formal Magnificent Seven tables |
| `artifacts/excluded_*.parquet` | Excluded ADBE records with source positions and reasons |
| `artifacts/validation_report.json`, `.md` | Actual full-data checks, counts, ranges, flags, reconciliation, and join results |
| `artifacts/verification.json`, `.md` | Executed test log and fresh-process reproducibility evidence |
| `artifacts/coverage.csv`, `text_changes.csv`, `unmatched_*.csv` | Company/date coverage, text-change audit, and unmatched event keys |
| `CLEANING_DECISIONS.md`, `PR_DESCRIPTION.md` | Integration decisions and the original PR description |
| `requirements.txt`, `.gitignore`, `.gitattributes` | Pinned dependencies, local-file exclusions, and stable text/binary handling |

Existing project notes were preserved. Individual notebooks, temporary review extracts, virtual environments, and the old local `data/` and `cleaning_outputs/` directories were not added by the integration.

## Data source and snapshot

Source: [TheFinAI/Herculean](https://huggingface.co/datasets/TheFinAI/Herculean). Individual branch documentation attributes the dataset to TheFinAI / Xueqing Peng, *Herculean*. Raw inputs stay on the local filesystem in the ignored `sources/raw/` directory; the original `data/` files were not modified. Git stores the source manifest and hashes, not the raw files.

The exact local version is `team-local-sha256-v1`. [sources/manifest.json](sources/manifest.json) records each file's full SHA256 and byte size. The hashes match Zack's local source manifest and the prefixes in Peter's reproducibility record.

**The upstream revision and original download date are unconfirmed.** Evelyn recorded different hashes and an upstream revision that cannot be assigned to these files. On October 18, 2026, a fixed-revision source README request required authentication. Individual documentation reports CC BY 4.0, but the upstream revision and redistribution terms were not independently confirmed. A member with source access should confirm the terms and retain the required attribution/license materials before public redistribution of derived data. Reproduction requires separately obtaining the complete local snapshot matching the manifest.

## Complete formal datasets

| File | Rows | Observation and keys |
|---|---:|---|
| [prices_clean.parquet](artifacts/prices_clean.parquet) | 2,324 | One company/date price observation; unique table ID and `symbol,date` |
| [news_clean.parquet](artifacts/news_clean.parquet) | 3,402 | One company/date news digest record; unique table ID; distinct same-day events are allowed |
| [filings_clean.parquet](artifacts/filings_clean.parquet) | 63 | One filing record with excerpts; unique table ID; candidate business key `symbol,date,document_type` |

These are full datasets, not 50-row samples. Together they occupy about 6.13 MB; the largest file is news at about 5.37 MB. Ordinary Git is sufficient for these cleaned outputs; Git LFS is not required. Raw input files are not tracked.

Formal tables, exclusions, provenance metadata, and audit evidence are tracked. `.gitignore` excludes raw inputs in `sources/raw/`, the pre-existing local `data/` and `cleaning_outputs/` directories, environments, caches, and temporary review files. Use access-controlled external storage for sharing raw snapshots, identified by the manifest hashes. If formal outputs become large, use Git LFS for those derived outputs. Do not replace complete deliverables with samples.

## Cleaning and analysis rules

- Keep only the seven target symbols in formal outputs. Preserve every ADBE record in an exclusion table with `_reason` and zero-based `_source_row`.
- Trim and uppercase symbol/form labels. Preserve date-only calendar values as timezone-naive `datetime64[ns]`; use string IDs, float64 prices, nullable Int64 volume, and stable sorting.
- Count exact duplicates separately from conflicting IDs and business keys. Quarantine conflicting price-key groups; retain and flag distinct same-day events, then aggregate before joins. IDs belong to their own tables and are not cross-table join keys.
- Apply one HTML decode and outer whitespace trim to filing excerpts, preserving paragraphs, punctuation, and internal spacing. Trim only news text boundaries. Preserve genuine missing values.
- Retain numeric observations and flag suspicious prices, large moves, zero volume, possible placeholder/truncated news, short risk excerpts, and repeated risk text. Thresholds are proposals, not proof of errors or automatic deletion rules.
- Save the three cleaned tables separately. Validate descriptive same-calendar-date event-count joins with explicit relationships and unchanged price rows/fields. Retain unmatched event keys.
- Keep analysis separate. Formal prices contain no precomputed returns, normalized prices, or volatility. A temporary return is used only for a quality flag.
- News has dates but no publication times. Neither same-day joins nor mapping to a later trading date establishes information availability or eliminates leakage. No predictive panel is provided.

`validation_report.json` records provenance, environment, missingness, conversions, duplicates, exclusions, flags, numeric ranges, volume reconciliation, joins, and output hashes. `text_changes.csv` records source positions, rules, and before/after text hashes; the original and transformed text remain recoverable from the Parquet files.

## Executed validation results

| Table | Raw | ADBE excluded | Other exclusions | Formal output |
|---|---:|---:|---:|---:|
| prices | 2,656 | 332 | 0 | 2,324 |
| news | 3,888 | 486 | 0 | 3,402 |
| filings | 73 | 10 | 0 | 63 |

The results naturally match historical comparison targets; the code does not add or remove rows to force those counts.

- Source fields have no missing values before or after cleaning. No exact duplicates, ID conflicts, price-key conflicts, invalid numeric domains, or OHLC inconsistencies were found in this snapshot.
- All 13,944 retained price/volume values are exactly preserved. Volume reconciles: 159,456,800,900 raw = 158,002,379,300 retained + 1,454,421,600 excluded ADBE shares.
- Filing formatting changed 146 source cells: 126 in the formal table and 20 in the ADBE exclusion table.
- Prices cover December 2, 2024–March 31, 2026, with 332 observations per company. News covers December 1, 2024–March 31, 2026, with 486 per company. Filings span January 26, 2024–February 25, 2026 overall, with nine per company; company-specific bounds are in `coverage.csv`.
- Retained flags include seven price moves exceeding 12%, seven placeholder/short news records, one possible truncated news record, nine short risk excerpts, and seven risk texts matching the preceding filing. All news records have unverified timing. Zero future-date detections does not establish absence of leakage.
- Both aggregated event joins preserve 2,324 price rows and every price field. The 1,078 unmatched news and 28 unmatched filing records remain available and audited.
- All 2,317 calculable adjusted-close returns match independent Decimal ratios; seven first-observation returns remain missing.
- Eleven risk tests passed. Two fresh-process full runs produced 12 byte-identical files, including formal datasets, exclusions, and validation reports. Source SHA256 hashes were unchanged.

See the [actual validation report](artifacts/validation_report.md) and [reproducibility record](artifacts/verification.md). Historical branch evidence is not counted as a newly executed check.

## Analysis interface

```python
import pandas as pd
from team_cleaning.analysis import interval_metrics

prices = pd.read_parquet("artifacts/prices_clean.parquet")
series, metrics = interval_metrics(prices, "2025-01-01", "2025-06-30")
```

The inclusive interval is selected before calculations. Normalized price starts at 100 using the interval's first actual observation, without skipping a missing endpoint. Returns use `adj_close` and `pct_change(fill_method=None)`, do not cross the interval's left boundary, and never forward-fill missing prices. Daily volatility is the sample standard deviation of valid returns (`ddof=1`); fewer than two returns yields missing volatility. Average volume uses valid observations only.

Open questions include screening thresholds, conflict handling, interval conventions, upstream revision/license, event-date meaning, and price adjustment methodology. Exchange-calendar completeness and news factual accuracy have not been independently verified. The 15 weekdays without observed prices are diagnostics, not certified exchange holidays.
