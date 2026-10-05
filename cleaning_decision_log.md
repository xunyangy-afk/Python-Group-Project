# Cleaning Decision Log

## Rule 1: Project-scope filter to Magnificent Seven symbols
- Observed issue: The raw dataset includes Adobe (ADBE) in addition to the seven target tech companies.
- Rule: Keep only AAPL, MSFT, GOOGL, AMZN, NVDA, META, and TSLA. Exclude ADBE.
- Business reason: The project objective is to compare the Magnificent Seven companies, and Adobe is outside the approved list.
- Must remain unchanged: Raw source files in `data/raw/` remain untouched.
- Verification check: Count rows per symbol before and after filtering; confirm ADBE is removed and M7 counts are consistent across all tables.

## Rule 2: Standardize symbols and preserve case semantics
- Observed issue: Source symbols should be treated as uppercase company codes.
- Rule: Strip whitespace and uppercase all symbol values before analysis.
- Business reason: This prevents case-variant duplicates and ensures the same company is treated consistently.
- Must remain unchanged: Actual source values remain unchanged in raw data; the cleaning step only applies to cleaned outputs.
- Verification check: Ensure the cleaned symbol set contains only the seven permitted values.

## Rule 3: Convert source dates to consistent datetime objects
- Observed issue: Date fields require consistent parsing for time-based operations.
- Rule: Parse dates with pandas and preserve the timezone-naive date format used by the source.
- Business reason: All time-based calculations require valid dates for return, month, and time series analysis.
- Must remain unchanged: Original date values remain in the source files.
- Verification check: Confirm dates parse without invalid entries and that date ranges remain consistent with the source.

## Rule 4: Validate pricing integrity before analysis
- Observed issue: Financial time-series data must satisfy basic accounting logic.
- Rule: Reject any rows with negative prices or volume, and require high >= low plus open/close within the daily range. Any violations raise an error for review instead of silently modifying values.
- Business reason: These checks protect the project from impossible price records and ensure the dashboard is built on valid market data.
- Must remain unchanged: No values are fabricated; invalid rows are not silently replaced.
- Verification check: Run validation after filtering and report zero invalid rows in the cleaned data.

## Rule 5: Preserve uncertain text without invented replacements
- Observed issue: News and filings may contain missing or ambiguous language.
- Rule: Keep the original text exactly as provided unless it is blank, which is a flag for investigation rather than replacement. Do not invent text.
- Business reason: The project dashboard must preserve the original reporting context and uncertainty without fabricating records.
- Must remain unchanged: Original text content remains untouched in the raw files.
- Verification check: Verify no blank strings are introduced and no synthetic text replaces source material.

## Rule 6: Restrict filing records to 10-K and 10-Q
- Observed issue: Filing content may include multiple document categories.
- Rule: Keep only 10-K and 10-Q entries and discard all others if present.
- Business reason: The project scope is limited to annual and quarterly SEC filings.
- Must remain unchanged: Non-target filing types are not reclassified; they are excluded by rule and documented.
- Verification check: Confirm the cleaned filing data contains only 10-K and 10-Q values.

## Rule 7: Add analysis features only from validated data
- Observed issue: Dashboard calculations require daily return, normalized price, volume context, volatility, company names, and month keys.
- Rule: Compute fields directly from valid cleaned data and document them clearly.
- Business reason: These features are needed for comparison and dashboard analysis but must remain transparent and reproducible.
- Must remain unchanged: The original data columns remain available for audit trail.
- Verification check: Run the workflow twice and confirm identical computed columns and row counts.
