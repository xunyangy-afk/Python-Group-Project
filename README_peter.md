# Data cleaning: Peter-work

Individual Module 6 cleaning of the TheFinAI/Herculean dataset. The rules and decisions are in `plan.md`; the results are in `outputs/validation_report.md`.

## Source and version

| Item | Value |
|---|---|
| Dataset | TheFinAI/Herculean on Hugging Face: https://huggingface.co/datasets/TheFinAI/Herculean |
| Files used | `prices.parquet`, `news.parquet`, `filings.parquet` from the `data/` folder (Files and versions tab) |
| Version | repository commit `52d3ecb` (latest commit on `main` at retrieval) |
| Retrieved | 2026-10-04 |
| License | CC BY 4.0, so sharing cleaned data is permitted |
| Raw file checksums | listed in `outputs/reproducibility_peter.md` (SHA-256) |

The raw files are never modified. They live in `data/raw/`, which is excluded from git by `.gitignore`; download them again with the steps below.

## Setup

```
pip3 install -r requirements_peter.txt
mkdir -p data/raw
# download the three parquet files from the dataset's data/ folder into data/raw/
```

## Run

```
python3 clean_peter.py              # full cleaning, about 10 seconds
python3 reproduce_check_peter.py    # optional: reruns in a fresh folder and compares outputs
```

Notebook: open `check_cleaning_peter.ipynb`, select a Python kernel that has the packages above, then **Restart** the kernel and **Run All**. Every section ends with `assert` checks; reaching the last cell without an error means all checks passed.

## Expected outputs

| File | Contents |
|---|---|
| `data/clean/prices_clean.parquet` | 2,656 rows, 11 columns |
| `data/clean/news_clean.parquet` | 3,888 rows, 10 columns |
| `data/clean/filings_clean.parquet` | 73 rows, 10 columns |
| `samples_peter/*_sample_peter.csv` | 47 cleaned rows in total, all columns, each with a `sample_reason` |
| `outputs/validation_report.md` | before/after counts, flags, merge check, metric support, record checks |
| `outputs/record_checks_peter.csv` | five original-to-cleaned record checks |
| `outputs/metric_support_peter.csv` | records supporting each metric |
| `outputs/reproducibility_peter.md` | fresh-session rerun result |

The cleaned parquet files are not on GitHub (they rebuild in seconds from the raw data). They can be included in the Gradescope ZIP if needed.

## Files

| File | Role |
|---|---|
| `plan.md` | inspection findings, cleaning rules, decisions D1 to D7, refinements |
| `clean_peter.py` | all cleaning and validation functions, plus `run_pipeline()` |
| `check_cleaning_peter.ipynb` | calls each function on its own and checks the result |
| `reproduce_check_peter.py` | fresh-session reproducibility test |
| `requirements_peter.txt` | Python dependencies |

## How the sample was selected

The sample is weighted toward difficult cases: all 9 large price moves, the first trading day of each symbol (no return), all 8 placeholder news rows, the 1 look-ahead news row, a weekend and a holiday news row, all 12 filings with repeated or reference-only risk sections, ADBE's extra 10-K, and a few ordinary rows as controls. The checks themselves always run on the full data.
