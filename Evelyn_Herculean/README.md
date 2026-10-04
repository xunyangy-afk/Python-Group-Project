# Herculean Stock Analysis

Explore news, stock returns, and trading volume for AAPL, MSFT, GOOGL, AMZN, NVDA, META, and TSLA from **2024-12-01 to 2026-03-31**.

Source: [TheFinAI/Herculean](https://huggingface.co/datasets/TheFinAI/Herculean), CC BY 4.0. The raw data includes an eighth stock, ADBE. The notebook excludes it only when calculating analysis metrics.

## Files

| File or folder | Purpose |
| --- | --- |
| `Cleaning_Evelyn.ipynb` | Data inspection, text cleaning, checklist checks, and stock metrics |
| `plan.md` | Proposed cleaning rules and checklist requirements; some details need updating |
| `clean_data.py` | Reproduce cleaned tables and quality reports |
| `test_clean_data.py` | Check cleaning rules, exports, and reproducibility |
| `download_herculean.py` | Download the source tables |
| `requirements.txt` | Download and notebook dependencies |
| `requirements-cleaning.txt` | Pinned cleaning dependencies |
| `data/` | Original Parquet files and `manifest.json` with the source revision |
| `cleaned/` | Cleaned tables, review flags, coverage, and quality reports |

Raw tables contain **2,656 prices, 3,888 news summaries, and 73 filings**. Cleaning retains all rows and formats 146 filing text cells using HTML decoding and `.strip()`. Price and news values stay unchanged.

## Run

Run from this folder. For a new environment:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-cleaning.txt
```

Open `Cleaning_Evelyn.ipynb`, select `.venv/bin/python`, and run cells in order. The notebook calculates 1-day and 3-day returns, absolute returns, intraday range, next-day volume ratio, and a 20-day price average. Results remain in memory; no merge is needed for these metrics.

To generate files and run checks:

```bash
.venv/bin/python clean_data.py
.venv/bin/python -m unittest discover -s . -p 'test_clean_data.py' -v
```

The script writes to `cleaned/` and uses the existing raw snapshot. Use `--output-dir /path/to/output` for another destination.

`download_herculean.py` downloads the latest revision and replaces `data/` files. The cleaning script requires the inspected snapshot and stops if its hashes differ.

## Outputs and limits

- Use `cleaned/*.parquet` in Python; equivalent CSV files support spreadsheet/dashboard imports.
- `quality_report.md` summarizes results; `quality_report.json` contains detailed checks and file hashes. Keep both.
- `review_flags.csv` identifies four retained records needing review; `coverage.csv` summarizes dates and counts by company.
- The 3-day return and volume ratio use future observations. News has no publication times, so news-to-price alignment still needs justification.
- Checklist write-ups and the Codex reflection remain unfinished. The notebook does not establish that all 14 items are complete.

Data, outputs, and `.venv/` stay local and are ignored by Git. Generated cache folders can be removed.
