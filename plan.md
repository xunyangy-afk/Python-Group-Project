# Dataset inspection and proposed cleaning rules

## Implementation status

The proposal below was implemented in `Evelyn_Herculean/clean_data.py` following the request to prepare the dataset for analysis and dashboard use. Generated Parquet/CSV tables and audit reports are in `Evelyn_Herculean/cleaned/`. All 6,617 rows remain; 146 filing excerpt cells were decoded/trimmed, with no news or price values changed. Four review flags preserve the unresolved cases. Six automated tests passed, including exact export round trips, reproducible reruns, and unchanged raw-file hashes. The existing notebook remains unchanged.

See `Evelyn_Herculean/README.md` for run/import instructions and `Evelyn_Herculean/cleaned/quality_report.json` for full actual results. The original inspection and proposed expectations below are retained for traceability.

## Inspection baseline

This document proposes cleaning rules; it does not apply them. Inspection covered every row of the three local Parquet tables. Text examples were reviewed selectively, and narrative factual accuracy was not independently verified. The original data and notebook must remain unchanged during this planning step.

- Source: `TheFinAI/Herculean`, `train` split.
- Recorded revision: `52d3ecb97e490a2392717935402cde283e8fa36e`.
- Inputs: `Evelyn_Herculean/data/{news,prices,filings}.parquet` and `Evelyn_Herculean/data/manifest.json`.
- The manifest records revision, row counts, and columns; it does not record a download timestamp.

| Dataset | Rows | Columns | Date coverage | Observed unit of observation |
| --- | ---: | ---: | --- | --- |
| News | 3,888 | 4 | 2024-12-01–2026-03-31 | One company/date news summary, potentially discussing multiple articles |
| Prices | 2,656 | 9 | 2024-12-02–2026-03-31 | One company/date daily price record |
| Filings | 73 | 6 | 2024-01-16–2026-03-25 | One company/date filing record containing document type and excerpts |

All tables contain AAPL, ADBE, AMZN, GOOGL, META, MSFT, NVDA, and TSLA. No columns contain nulls or blank strings. Each table has unique IDs, unique `(symbol, date)` pairs, and no exact duplicate rows. IDs are identifiers local to each table, not cross-table relationships. Filings also have unique `(symbol, date, document_type)` keys; retain document type when describing filing identity because the observed company/date uniqueness is not a guarantee for future data.

Dates load into pandas as object columns containing Python `date` objects, not strings. All dates parse successfully. Narrative and label columns load as strings. No tested whole-cell placeholders (`N/A`, `NA`, `null`, `none`, `nan`, `unknown`, `missing`, `-`, or `no news`/`no news available`, case-insensitive with optional final punctuation) were found. These checks do not establish that every narrative is substantively complete.

### Source-preservation baseline

Before and after any later cleaning, compare SHA-256 hashes against these inspected originals:

| File | SHA-256 |
| --- | --- |
| `prices.parquet` | `0001b983f1a302e2f7a2d2e6a6c407f44127de77e981b004fd5cce6e998a942a` |
| `news.parquet` | `9156b73a5c417057104abe9eeb0d9b3ea0dceea66260e5b8ef552bd182cec8e6` |
| `filings.parquet` | `2d9a93926e52d4e2f5f18e13d68fbdd60e14282f94df4e1c4a3f7b81daf6d95d` |

## Column-by-column rules

### News

| Column | Observed evidence | Proposed rule and intended type | Verification |
| --- | --- | --- | --- |
| `id` | `int32`; unique integers 1–3,888 | Preserve IDs and `int32`. Never renumber or use these IDs to join different tables. | Non-null, unique, and equal to source values. |
| `symbol` | Eight uppercase string labels; no outer whitespace; 486 rows each | Preserve strings. Validate the observed symbol set; flag unexpected labels without guessing replacements. | Values and per-symbol counts unchanged. |
| `date` | 486 consecutive calendar dates per company; no invalid values | Preserve date-only storage and calendar dates. If needed for pandas operations, strictly convert a working copy to timezone-naive datetime; do not invent publication times. | No failed conversions; round-trip to original dates; `(symbol, date)` remains unique. |
| `highlights` | Length 25–12,033 characters; all 3,888 distinct; no outer whitespace, HTML entities, or HTML tags; 301 rows contain repeated spaces, including bullet indentation | Preserve strings, wording, punctuation, capitalization, numbers, paragraphs, and indentation. Trim outer whitespace only if present; no current values require trimming. Flag incomplete or questionable summaries without rewriting, filling, or deleting them. | Current text remains exactly unchanged. Review flags do not remove rows or create nulls. |

Use fewer than 100 characters as a reproducible short-summary review trigger. It flags one current row. Length alone does not establish completeness or validity, and longer text can also be truncated.

| Record | Evidence | Proposed handling |
| --- | --- | --- |
| News ID 543, ADBE, 2025-01-26 | Entire text is `The article also includes` (25 characters). | Flag incomplete text and retain unchanged. |
| News ID 1005, AMZN, 2025-01-02 | Ends mid-sentence with `The second block, described as “`. | Flag apparent truncation and retain unchanged. |
| News ID 1489, GOOGL, 2024-12-31 | Explicitly states there are no substantive events to report from the supplied article. | Retain as meaningful text, not a missing-value placeholder. |
| News ID 2, AAPL, 2024-12-02 | Describes a December 1 closing price, although December 1 is Sunday and has no price row here. | Flag timing/factual uncertainty; do not automatically correct dates or prices in prose. |

The repeated spaces include nested bullet formatting, so global whitespace collapsing is not justified. Review flags are evidence for further investigation, not proof that all other summaries are factually correct.

### Prices

| Column | Observed evidence | Proposed rule and intended type | Verification |
| --- | --- | --- | --- |
| `id` | `int32`; unique integers 1–2,656 | Preserve IDs and `int32`. | Non-null, unique, and equal to source values. |
| `symbol` | Eight valid labels; 332 rows each | Preserve strings; apply the news symbol validation rule. | Labels and per-symbol counts unchanged. |
| `date` | 332 shared dates per company; all valid; no weekends | Preserve date-only values. Do not add rows or fill prices for absent dates. Use a strictly converted working copy only when needed for analysis. | Identical date sets before/after; unique `(symbol, date)`. |
| `open` | `float64`; finite and positive; approximately 87.46–791.15; all within daily range | Preserve full precision; require `low <= open <= high`. Flag failures without clipping or replacing. | Finite, positive, within range, and exactly unchanged. |
| `high` | `float64`; finite and positive; approximately 99.44–796.25 | Preserve full precision; require `high >= low`, `high >= open`, and `high >= close`. | All inequalities pass; values exactly unchanged. |
| `low` | `float64`; finite and positive; approximately 86.62–780.82 | Preserve full precision; require `low <= high`, `low <= open`, and `low <= close`. | All inequalities pass; values exactly unchanged. |
| `close` | `float64`; finite and positive; approximately 94.31–790.00; all within daily range | Preserve full precision; require `low <= close <= high`. | Finite, positive, within range, and exactly unchanged. |
| `adj_close` | `float64`; finite and positive; approximately 94.2878–788.1490; differs from `close` in 1,551 rows; outside daily low/high in 199 rows | Preserve independently of unadjusted prices. Do not constrain it to the daily range or replace it with `close`. | Finite, positive, and exactly unchanged; adjustment differences retained. |
| `volume` | `int64`; positive whole numbers; 1,166,500–818,830,900; no zeros | Preserve `int64`. Flag negative, fractional, missing, or nonfinite values. Retain and review any future zero rather than assuming missingness. | Integer values unchanged; sum remains 159,456,800,900. |

All current numeric validity checks pass. Floating-point tails are not evidence of incorrect prices; round only for display. Reported ranges above are descriptive, not bounds for rejecting future observations.

For review only, sort by symbol/date and calculate consecutive-observation adjusted-close returns using `pct_change(fill_method=None)`. Flag absolute returns greater than 20%; leave each company's first return missing and retain the previous observation date so gaps remain visible. This flags TSLA on 2025-04-09, ID 2412, approximately +22.69%. Retain it without winsorization or correction. This threshold is a screening default, not an established validity limit, and the calculation need not become a new price-table column.

### Filings

| Column | Observed evidence | Proposed rule and intended type | Verification |
| --- | --- | --- | --- |
| `id` | `int32`; unique integers 1–73 | Preserve IDs and `int32`. | Non-null, unique, and equal to source values. |
| `symbol` | Same eight string labels; ADBE has 10 records, others 9 | Preserve labels and unequal record counts. Do not fabricate records to balance companies. | Labels and per-symbol counts unchanged. |
| `date` | All valid; 32 records precede price coverage | Preserve all date-only values, including earlier filings. Do not assume these dates are acceptance timestamps or fiscal period ends. | Identical dates before/after; no automatic coverage filtering. |
| `document_type` | Consistent strings: 51 `10-Q`, 22 `10-K`; no outer whitespace | Preserve strings. Validate these observed categories; flag unexpected types without automatic mapping. | Categories and counts unchanged. |
| `mda_content` | All 73 strings have outer whitespace and HTML entities; lengths 15,930–76,907; all distinct | Apply `html.unescape(value).strip()` once. Preserve decoded Unicode, internal spacing, bullets, paragraphs, numbers, and section headings. | Each result equals the specified transformation; all 73 change; no new blanks or missing values. |
| `risk_content` | All 73 strings have outer whitespace; 68 contain HTML entities; lengths 333–196,794; 66 distinct texts | Apply the same decode-and-trim rule. Preserve repeated language and short cross-references to annual reports; do not deduplicate filings by text. | All 73 change through trimming and/or decoding; no new blanks; repeated narratives remain attached to their original records. |

Entity examples include `&#8217;` (curly apostrophe), `&#8220;`/`&#8221;` (quotation marks), `&#8226;` (bullet), `&#38;` (ampersand), and `&#160;` (nonbreaking space). Preserve decoded internal nonbreaking spaces rather than collapsing formatting. No HTML tags were detected, so tag stripping is unnecessary. A second HTML decode changes no current filing values.

There are seven repeated risk-text occurrences beyond the first, involving 11 records across distinct dates. Retain all of them: AMZN IDs 22, 23, 25, 26, 27; GOOGL IDs 34, 35, 36; TSLA IDs 66, 67, 68. Repeated excerpt text alone does not establish a duplicate filing.

## Cross-table handling and audit

- Keep the tables separate. No merge, imputation, deduplication, row removal, or numeric correction is currently justified.
- Preserve all 1,232 news records without a same-date price match, including 1,112 weekend records. Calendar coverage differences are not null cells in the source tables.
- Prices omit 15 weekdays within their coverage: 2024-12-25; 2025-01-01, 2025-01-09, 2025-01-20, 2025-02-17, 2025-04-18, 2025-05-26, 2025-06-19, 2025-07-04, 2025-09-01, 2025-11-27, 2025-12-25; 2026-01-01, 2026-01-19, 2026-02-16. Record these as coverage observations; do not declare missing trading sessions without an exchange-calendar check.
- If cleaning is implemented later, read fresh copies of the originals, preserve original schemas and column names, and save separate outputs. Put review flags in a separate audit table identified by source table, ID, column, and rule, with a reason and review status. Multiple flags may reference the same source cell.
- Unexpected conversion failures or key conflicts require investigation. Do not silently coerce values to null, drop rows, or choose a conflicting record. Distinguish source missingness, conversion failures, and any future merge-introduced missingness.
- Record each rule, affected-cell count, reason, verification result, and unresolved exceptions. Reconcile changes by source ID and count row removals only once if removal is justified in a future revision.
- News accuracy, truncated excerpts, filing-date meaning, and missing publication times remain unresolved. Formatting cleanup does not resolve these limitations. Any future predictive merge needs a separate information-availability rule before date alignment can be interpreted safely.

## Acceptance checks for future cleaning

These were the proposed acceptance checks. They now pass for the inspected snapshot; actual machine-readable evidence is recorded in `Evelyn_Herculean/cleaned/quality_report.json` and verified by `test_clean_data.py`.

- Row counts remain 3,888 news, 2,656 prices, and 73 filings.
- IDs, company/date keys, date coverage, document types, and all price/volume values remain unchanged.
- Total volume remains 159,456,800,900.
- Nulls, blanks, duplicate IDs, and duplicate company/date keys remain zero.
- News text remains unchanged under the proposed formatting rule.
- Filing text changes exactly match one HTML decode followed by outer trimming; repeating cleanup produces no further changes. Preserve internal paragraph boundaries and meaningful punctuation.
- Raw-file hashes remain equal to the source-preservation baseline.
- A fresh run from the originals reproduces the same schemas, values, counts, and audit findings.

### Traceable record checks

These expectations were written before implementation. Actual results were filled after validating the exported tables.

| Source record | Expected result | Reason | Actual result |
| --- | --- | --- | --- |
| News ID 543 | Text unchanged; incomplete-text review flag | Preserve evidence rather than invent missing prose. | Passed: text unchanged; `short_summary` flag records inspected incompleteness. |
| News ID 1005 | Text unchanged; apparent-truncation review flag | Mid-sentence ending cannot be repaired from this table alone. | Passed: text unchanged; `apparent_truncation` flag retained. |
| Filings ID 1 | Outer whitespace removed and entities decoded in both excerpt fields | Improve readability without changing content. | Passed: both fields exactly match decode-and-trim. |
| Filings ID 66 | Short annual-report risk cross-reference retained, with outer whitespace removed | A short cross-reference is meaningful; repeated text does not make the record redundant. | Passed: cross-reference retained after decode-and-trim. |
| Prices ID 4 | All numeric values unchanged, including adjusted close below daily low | Adjusted close need not lie within the unadjusted daily range. | Passed: entire record unchanged; adjusted close remains below low. |

The initial deliverable was this proposal only. Cleaned outputs and audit reports have now been produced under the subsequent analysis/dashboard preparation request. Editing the exploratory notebook, building a dashboard, joining tables, and independently verifying narrative claims remain outside the cleaning implementation.
