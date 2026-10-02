# Herculean Data Import

Source: [TheFinAI/Herculean](https://huggingface.co/datasets/TheFinAI/Herculean#loading), by Xueqing Peng, 2026. The tabular data is licensed under CC BY 4.0.

Three tables from the `train` split have been imported using the official Hugging Face Datasets loading method:

| File | Contents | Rows listed in the official documentation |
| --- | --- | ---: |
| `data/prices.parquet` | Daily stock prices and trading volume | 2,656 |
| `data/news.parquet` | News summaries | 3,888 |
| `data/filings.parquet` | Excerpts from 10-K / 10-Q filings | 73 |

`data/manifest.json` records the downloaded revision, row counts, and column names. This directory does not include the additional XBRL audit attachments in `auditing_env/`.

## Open the Notebook

Open `Cleaning_Evelyn.ipynb` and select this directory's `.venv/bin/python` as the Python kernel. This existing notebook reads raw local Parquet files and contains an exploratory checklist; the reproducible cleaning pipeline below produces the analysis outputs independently.

## Download the Data Again

Run the following commands from this directory:

```bash
uv venv .venv --cache-dir .uv-cache
uv pip install --python .venv/bin/python --cache-dir .uv-cache -r requirements.txt
.venv/bin/python download_herculean.py
```

The download script uses the latest dataset revision available when it runs and records that revision's commit SHA in the manifest. All three tables use the same revision.

## Use the Data in Python

```python
import pandas as pd

prices = pd.read_parquet("data/prices.parquet")
news = pd.read_parquet("data/news.parquet")
filings = pd.read_parquet("data/filings.parquet")
```

## Cleaned data for analysis and dashboards

The column-by-column decisions and inspection evidence are in [plan.md](../plan.md). From this directory, run:

```bash
.venv/bin/python clean_data.py
.venv/bin/python -m unittest discover -s . -p 'test_clean_data.py' -v
```

The script also works from the repository root with `Evelyn_Herculean/.venv/bin/python Evelyn_Herculean/clean_data.py`; paths resolve relative to the script. It uses the inspected local snapshot and requires no network access. For a fresh environment, install the pinned cleaning dependencies in `requirements-cleaning.txt`. The source snapshot must already be present. A source-hash mismatch stops the run and requires a new inspection rather than silently applying old decisions to a different download.

Generated files are written to `cleaned/` (ignored by Git). Use `--output-dir /path/to/separate/output` for another destination. Rerunning replaces the pipeline's generated files after validating staged exports. The raw files and notebook are never modified.

| Output | Purpose |
| --- | --- |
| `news.parquet`, `prices.parquet`, `filings.parquet` | Cleaned tables with original column names, types, IDs, date-only values, and row counts |
| `news.csv`, `prices.csv`, `filings.csv` | Equivalent UTF-8 exports for dashboard import; dates are `YYYY-MM-DD`, multiline text is quoted |
| `review_flags.csv` | Table-local record ID, symbol, date, affected column, rule, reason, and review status |
| `coverage.csv` | Row count and first/last date by table and company |
| `quality_report.json`, `quality_report.md` | Source/output hashes, column changes, checks, five record verifications, coverage gaps, and limitations |

All 6,617 rows are retained: 3,888 news, 2,656 prices, and 73 filings. Only the 146 filing excerpt cells change, through HTML decoding and outer-whitespace trimming. News and price values are unchanged. Four review flags identify three questionable news records and one large price return; flagged rows are retained. Flags do not certify unflagged news as factually accurate or complete.

For analysis, prefer Parquet because CSV does not store data types:

```python
from pathlib import Path
import pandas as pd

data = Path("cleaned")  # when working in Evelyn_Herculean
prices = pd.read_parquet(data / "prices.parquet")
news = pd.read_parquet(data / "news.parquet")
filings = pd.read_parquet(data / "filings.parquet")
flags = pd.read_csv(data / "review_flags.csv")
```

Import tables separately into a dashboard. Treat IDs as identifiers, dates as calendar dates, prices as decimal numbers, volume as an integer, and narrative fields as text. Relate a review flag using its table name plus ID; IDs across the three datasets are unrelated. Aggregate review flags by record before joining them so multiple flags cannot multiply data rows. Do not sum IDs or narrative text.

The datasets have different calendars and coverage: news includes weekends, prices contain observed market dates, and filings are occasional and include earlier periods. There are 1,232 news rows without same-date prices; this is not a reason to replace absent prices with zero. Use `coverage.csv` to show contributing row counts when comparing companies or tables. The pipeline deliberately creates no combined table or financial metrics.

Publication times and the precise meaning of filing dates are unavailable here. Same-day alignment does not establish that text was available before a price observation. Predictive or causal analysis needs a separately justified timing rule. Incomplete summaries remain visible through review flags; repeated risk passages and short annual-report cross-references are preserved.

Validation covers exact Parquet/CSV round trips, original schema preservation, unchanged price/news values, source hashes, idempotence, key uniqueness, numeric validity, volume totals, and deterministic reruns. Full current results are in `cleaned/quality_report.json`.
