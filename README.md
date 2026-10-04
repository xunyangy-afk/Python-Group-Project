# Module 6: Herculean Data Cleaning and Verification

This project cleans and validates the local Herculean prices, news, and filings tables for the Magnificent Seven: AAPL, AMZN, GOOGL, META, MSFT, NVDA, and TSLA. ADBE is excluded because it is outside the project scope.

## Submission information

- **Student:** Zack Ye
- **Individual branch:** `Zack-Work`
- **Branch URL:** https://github.com/xunyangy-afk/Python-Group-Project/tree/Zack-Work
- **Submitted analysis commit:** 2aef989b64c4cedfbbb20ae5b68e309e80e71f67

Use the same branch information and analysis commit ID in the individual PDF. The analysis commit identifies the code and results being reviewed; a later documentation-only commit may add that ID to this README.

## Project vision and question

**Vision:** Build a financial intelligence dashboard integrating market prices, news digests, and filing excerpts for the Magnificent Seven.

**Business question:** How do observed daily stock returns differ between company-days with and without recorded filing events among the Magnificent Seven?

The primary comparison is mean adjusted-close return on filing and non-filing days, with the number of nonmissing returns reported for each group. News coverage and trading volume provide additional context. All price days in the current snapshot have a news record, so this snapshot does not support a news-versus-no-news comparison.

## Data source and snapshot

- **Dataset:** [TheFinAI/Herculean](https://huggingface.co/datasets/TheFinAI/Herculean).
- **Attribution:** TheFinAI / Xueqing Peng, *Herculean* (2026).
- **Dataset license:** CC BY 4.0, as stated on the dataset card.
- **Inputs:** `data/prices.parquet`, `data/news.parquet`, and `data/filings.parquet`.
- **Version identification:** Local snapshot identified by each file's SHA256 hash. The program does not assume an upstream revision from filenames.

The pipeline writes filenames, byte sizes, row counts, SHA256 hashes, and first-inspection timestamps to `cleaning_outputs/local_source_manifest.json`. An inspection timestamp is not a download date. Retain the actual source revision or download date in your submission records if known.

The program reads existing local files only. It does not download data or modify the original Parquet files. If the raw files are not included in the repository, obtain the three tables from the linked dataset and place them in `data/`. To reproduce this exact snapshot, compare their hashes with the submitted manifest; the latest upstream files may differ.

## Project files

```text
Python-Group-Project/
├── data/
│   ├── prices.parquet
│   ├── news.parquet
│   └── filings.parquet
├── cleaning.py
├── Herculean_Mag7_Module6.ipynb
├── requirements.txt
├── requirements-notebook.txt
├── README.md
└── cleaning_outputs/                 # Created when the pipeline runs
```

The script and notebook implement the same pipeline and can run independently. Running both is optional. Keep their cleaning rules synchronized if you edit them.

## Setup and execution

Use Python 3.10 or later. Open a terminal in the project root and install the existing dependencies into your chosen Python environment.

### Run the standalone script

```sh
python -m pip install -r requirements.txt
python cleaning.py
```

The default input and output paths are relative to the script's directory. Optional paths can be supplied explicitly:

```sh
python cleaning.py --data-dir data --output-dir cleaning_outputs
```

### Run the notebook

```sh
python -m pip install -r requirements-notebook.txt
python -m jupyterlab
```

Open `Herculean_Mag7_Module6.ipynb` from the project root, using the Python environment where the dependencies were installed. Select **Restart Kernel and Run All**. The notebook resolves `data/` and `cleaning_outputs/` relative to its current working directory.

### Verify reproducibility

1. Complete one full execution to establish `output_hashes.json`.
2. Restart the notebook kernel and run all cells again, or run `python cleaning.py` again in a new process.
3. Confirm the message `PASS: outputs match previous complete run.` and save the notebook with its outputs.

The first run reports a saved baseline and leaves checklist item 13 unresolved. A matching subsequent run completes that check. Original source hashes are also checked for changes. Do not silently replace a failing baseline; investigate the inputs, code, and dependency versions. For intentional changes, preserve previous results and choose a new output directory. The observed environment is recorded in `environment.json`.

## Cleaning and verification rules

- Preserve source files and track original row positions with `_source_row`.
- Parse dates and numeric fields; count conversion failures. Preserve identifiers as strings.
- Trim text boundaries, normalize line endings, and uppercase symbol/form codes without rewriting narrative content.
- Count exact duplicates, repeated IDs, and logical duplicate keys separately. Remove exact duplicate records; quarantine conflicting price keys and invalid join keys.
- Retain nonidentical repeated news/filing keys for investigation and aggregate events before joining.
- Keep missing measurements missing. Replace impossible numeric values with missing and retain flags; do not impute prices or returns.
- Check OHLC consistency, zero volume, unusual returns, date gaps, missing text, and unexpected filing forms.
- Validate joins on `symbol,date`; report unmatched keys on both sides and check that joins do not multiply price rows or volume totals.
- Reconcile starting and final row counts and volume totals.
- Compute `adj_close[t] / adj_close[t-1] - 1` within each symbol, with no forward filling. The first observation and missing denominators produce missing returns.
- Verify all returns against an independent Decimal calculation and test missing-value behavior with a separately labeled artificial example.
- Predeclare five real-record expectations and compare them against actual outputs.

## Expected outputs

All generated files are written to `cleaning_outputs/` by default.

| Output | Purpose |
|---|---|
| `cleaned_prices.csv` / `.parquet` | Cleaned prices, return calculations, and flags |
| `cleaned_news.csv` / `.parquet` | Cleaned news digest records |
| `cleaned_filings.csv` / `.parquet` | Cleaned filing excerpts |
| `analysis_panel.csv` | Price-day panel with aggregated news and filing counts |
| `cleaned_sample_max50.csv` | At most 50 cleaned rows total across the three tables |
| `cleaning_log.csv` | Cleaning rules, actions, reasons, and checks |
| `checklist_14.csv` | Assignment checklist statuses and evidence references |
| `type_checks.csv`, `text_changes.csv` | Conversion results and text before/after evidence |
| `duplicates.csv`, `logical_duplicates_*.csv` | Duplicate counts and event-key detail |
| `missing_before_after.csv` | Missing counts before and after cleaning |
| `excluded_*.csv` | Excluded or quarantined records and their reasons |
| `suspicious.csv`, `flagged_*.csv`, `numeric_changes.csv` | Suspicious-value counts, flagged records, and numeric changes |
| `merge_audit.csv`, `unmatched_*_keys.csv` | Join cardinality and unmatched-key evidence |
| `row_reconciliation.csv`, `volume_reconciliation.csv` | Row and total reconciliation |
| `metrics.csv`, `descriptive_comparison.csv` | Metrics, valid denominators, and filing-day comparison |
| `record_check_plan.csv`, `record_checks.csv` | Five original/expected/actual record checks |
| `local_source_manifest.json` | Local snapshot identity and source hashes |
| `environment.json`, `output_hashes.json` | Environment metadata and reproducibility baseline |

For the current local snapshot, the expected scope-filtered row counts are:

| Table | Original | Excluded ADBE rows | Cleaned |
|---|---:|---:|---:|
| prices | 2,656 | 332 | 2,324 |
| news | 3,888 | 486 | 3,402 |
| filings | 73 | 10 | 63 |

Empty issue files represent zero detected issues, not a failure to generate evidence. Inspect actual outputs before describing checks as passed in the report.

## Sample selection

The sample contains up to 25 price rows, 15 news rows, and 10 filing rows, with at most 50 rows total. Selection prioritizes predeclared retained record checks, flagged observations, missing source fields, company coverage and first observations, then stable-order context. The first price observation illustrates a missing return because no prior price is available.

This is a purposive sample for reviewing cleaning decisions, not a representative statistical sample. Full text is retained, so some CSV cells are long. The sample is generated at `cleaning_outputs/cleaned_sample_max50.csv`; it is not placed inside `data/`.

## Limitations

- The seven-company universe and short observation window limit generalization.
- News records are summarized daily digests, not individual original articles; filing excerpts cover selected sections.
- Daily dates do not establish publication time or whether an event preceded the day's price movement. Comparisons describe associations, not causality.
- Weekend and out-of-window events can lack matching prices. Unmatched counts do not automatically indicate an erroneous join.
- An observed-row return can span multiple trading days if observations are missing. An exchange calendar and upstream price-adjustment methodology are not independently verified here.
- Missing or quarantined observations can affect coverage and estimates. Means use nonmissing return counts rather than treating missing returns as zero.

## Submission checklist

Commit the script, executed notebook, dependency files, this README, and the cleaned sample to your individual branch. Include compact verification evidence such as the cleaning log, checklist, record checks, reconciliation tables, and local source manifest. Full cleaned datasets can be regenerated and are not required in place of the requested sample.

The existing `.gitignore` excludes `data/`; verify that the sample and selected evidence are actually tracked. If you choose to ignore all of `cleaning_outputs/`, copy the sample and selected evidence into a tracked folder such as `samples/` or `evidence/` before committing.

Submit a separate individual PDF on Gradescope containing the 14-item checklist, decision log, five record checks, and an explanation of how a Codex suggestion was independently checked. Include the same individual branch name, branch URL, and submitted analysis commit ID in both the PDF and this README.