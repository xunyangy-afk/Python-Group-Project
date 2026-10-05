# Five Record Checks

These checks compare source records with the stated cleaning rules and actual cleaned values.
## Check 1: Price range integrity
- Original value: symbol=AAPL; date=2024-12-02; open=237.27000427246097; high=240.7899932861328; low=237.16000366210935; close=239.58999633789065
- Expected result written before checking: high >= low and open/close within the trading range
- Actual cleaned value: high=240.7899932861328, low=237.16000366210935, open=237.27000427246097, close=239.58999633789065
- Pass/Fail: PASS

## Check 2: Volume positivity
- Original value: symbol=NVDA; date=2025-01-27; volume=818830900
- Expected result written before checking: volume should be positive and greater than zero
- Actual cleaned value: 818830900
- Pass/Fail: PASS

## Check 3: News text preservation
- Original value: symbol=AAPL; date=2024-12-01; highlights=Apple’s December 1, 2024 coverage centers on its fiscal first quarter 2024 results, with Shacknews reporting that the company generated revenue of $119.6 billion and earned $2.18 per share, figures that surpassed the consensus estimates of $118 billion in revenue and $2.10 in EPS. This framing positions the quarter as a positive earnings execution relative to expectations, highlighting a solid top-line and bottom-line performance.

The article additionally draws market context from Statmuse, which is cited for stock-market data and related context around Apple on that date. This sourcing implies a broader market narrative surrounding Apple, incorporating how the stock had been moving and how the year-to-date trajectory was interacting with the earnings release, though the piece does not provide explicit price figures or forward-looking guidance within its summary.

Regarding sentiment, the article itself does not assign an official sentiment score (noted as N/A in the source). Nevertheless, the reported earnings beat on both revenue and EPS is presented in a manner that implies a favorable view of Apple’s quarterly execution, at least in the immediate aftermath of the results.

Key themes that emerge from the article include the emphasis on quarterly earnings strength and the integration of multiple data sources to frame Apple’s performance within the broader market context. The developments highlight how Apple’s Q1 results are being communicated alongside market data to give readers a snapshot of both financial performance and investor awareness on that date.
- Expected result written before checking: highlights text must be present and non-empty after stripping
- Actual cleaned value: Full highlights value preserved after surrounding whitespace normalization (1586 characters)
- Pass/Fail: PASS

## Check 4: Filing type validity
- Original value: symbol=AAPL; date=2024-02-01; type=10-Q
- Expected result written before checking: document_type should be either 10-K or 10-Q
- Actual cleaned value: 10-Q
- Pass/Fail: PASS

## Check 5: ADBE scope exclusion
- Original value: symbol=ADBE; date=2024-12-02
- Expected result written before checking: ADBE must not appear in the cleaned M7 output
- Actual cleaned value: not present in cleaned M7 dataset
- Pass/Fail: PASS
