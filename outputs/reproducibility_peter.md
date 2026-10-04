# Reproducibility check (Peter-work)

Run on 2026-10-04 with Python 3.10.12, pandas 2.3.3.

Procedure: copy `data/raw/*.parquet` and `clean_peter.py` into an empty temporary folder, run `python3 clean_peter.py` there in a new Python process, compare every output with the submitted file (parquet by content, other files byte for byte).

| output                                 | matches_submitted   |
|:---------------------------------------|:--------------------|
| data/clean/prices_clean.parquet        | True                |
| data/clean/news_clean.parquet          | True                |
| data/clean/filings_clean.parquet       | True                |
| samples_peter/prices_sample_peter.csv  | True                |
| samples_peter/news_sample_peter.csv    | True                |
| samples_peter/filings_sample_peter.csv | True                |
| outputs/validation_report.md           | True                |
| outputs/record_checks_peter.csv        | True                |
| outputs/metric_support_peter.csv       | True                |

All outputs match: **True**

Raw files unchanged by the run (SHA-256, first 16 characters):

- prices.parquet: 736c124db22e976d (unchanged)
- news.parquet: 1fd109796eada02a (unchanged)
- filings.parquet: 822a854865651e04 (unchanged)
