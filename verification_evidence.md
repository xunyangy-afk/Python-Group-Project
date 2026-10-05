# Verification Evidence

## Reproducibility note
The cleaned parquet tables and markdown artifacts are byte-stable across reruns from the original data. The generated PDF is content-identical, but the PDF byte hash may change because reportlab embeds timestamp metadata in the output file.

## Independent Codex Check
I used Codex to help implement and review the cleaning workflow. I independently checked Codex’s recommendation to exclude Adobe by confirming that ADBE exists in the original Herculean tables but is not one of the Magnificent Seven. I compared the original and cleaned symbol lists and verified that ADBE was removed while all seven intended symbols remained. I reconciled the changes as follows: prices 2,656 − 332 = 2,324; news 3,888 − 486 = 3,402; and filings 73 − 10 = 63.

Original symbol list: ['AAPL', 'ADBE', 'AMZN', 'GOOGL', 'META', 'MSFT', 'NVDA', 'TSLA']
Cleaned symbol list: ['AAPL', 'AMZN', 'GOOGL', 'META', 'MSFT', 'NVDA', 'TSLA']

Reconciliations:
- Prices: 2,656 original − 332 ADBE records = 2,324 cleaned
- News: 3,888 original − 486 ADBE records = 3,402 cleaned
- Filings: 73 original − 10 ADBE records = 63 cleaned

## Source verification
- prices raw rows: 2656; columns: ['id', 'symbol', 'date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']
- news raw rows: 3888; columns: ['id', 'symbol', 'date', 'highlights']
- filings raw rows: 73; columns: ['id', 'symbol', 'date', 'document_type', 'mda_content', 'risk_content']

## Project-scope filter
- ADBE removed from prices: 332 rows
- ADBE removed from news: 486 rows
- ADBE removed from filings: 10 rows
- M7 final prices rows: 2324
- M7 final news rows: 3402
- M7 final filings rows: 63

## Validation checks
- price rows with negative values: 0
- rows with high < low: 0
- rows with open outside range: 0
- rows with close outside range: 0
- invalid dates in prices: 0
- invalid dates in news: 0
- invalid dates in filings: 0

## Duplicate checks
- raw exact duplicate rows: 0
- raw repeated ids: 0
- raw symbol+date duplicates: 0

## Reproducibility
The workflow was executed from the original raw data and generated identical parquet outputs when rerun in the same environment.
