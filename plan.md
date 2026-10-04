# Data Cleaning Plan (Peter-work)

## 1. Goal

Clean the TheFinAI/Herculean raw tables (prices, news, filings) so they can be used for analysis and a dashboard supporting our project vision: evaluating which agent/model setup should produce weekly equity research reports. "Clean" here means: correct types, no silent row loss, and every suspicious record flagged rather than quietly deleted, so the dataset still represents what the agents actually saw.

Input: `data/raw/prices.parquet`, `data/raw/news.parquet`, `data/raw/filings.parquet`
Output: `data/clean/*.parquet` plus `outputs/validation_report.md`

## 2. Ground rules

1. Do not drop rows without explaining why in this file.
2. Do not change units, categories, or text content without documenting the change.
3. Flag suspicious values first (new boolean `flag_*` columns), then decide.
4. After each major transformation, print row counts, missing values, and what changed.
5. Raw files are never overwritten.

## 3. What the inspection found

| Table | Rows | Symbols | Date range | Missing | Duplicates (row / id / symbol+date) |
|---|---|---|---|---|---|
| prices | 2,656 | 8 x 332 | 2024-12-02 to 2026-03-31 | 0 | 0 / 0 / 0 |
| news | 3,888 | 8 x 486 | 2024-12-01 to 2026-03-31 | 0 | 0 / 0 / 0 |
| filings | 73 | 7 x 9, ADBE x 10 | 2024-01-16 to 2026-03-25 | 0 | 0 / 0 / 0 |

Structurally clean. The real issues are content quality:

- **prices**: OHLC logic holds (high >= open/close >= low), no zero volume, no weekend rows, same 332 trading days for every symbol. 9 daily moves above 12% (e.g. 2025-04-09 tariff pause rally, NVDA 2025-01-27 DeepSeek drop). adj_close differs from close by up to about 1% for dividend payers.
- **news**: one row per symbol per calendar day, so 1,232 rows fall on weekends or market holidays with no price row. Some rows are LLM "no content" placeholders (e.g. "no substantive GOOGL events to report") or fragments (e.g. 25 characters: "The article also includes"). Some rows may mention information dated after the row date (look-ahead risk). 84 rows say sentiment is N/A.
- **filings**: every text field has leading whitespace. 7 quarterly filings repeat the previous filing's risk section word for word (AMZN, GOOGL, TSLA). Several 10-Q risk sections are only a few hundred characters ("refer to our 10-K"), not real risk text.
- **dates** are stored as Python `datetime.date` objects (dtype object), not datetime64.

## 4. Cleaning rules by table and column

### prices
| Column | Rule |
|---|---|
| id | keep as int, check unique |
| symbol | strip, uppercase, category dtype |
| date | convert to datetime64 |
| open/high/low/close/adj_close | keep as is, units USD, no rounding |
| volume | keep as int64 |
| daily_return (new) | `adj_close.pct_change()` within each symbol, sorted by date; first day per symbol is NaN by design |
| flag_large_move (new) | abs(daily_return) > 0.12; keep the row |

### news
| Column | Rule |
|---|---|
| id, symbol, date | same as prices |
| highlights | strip whitespace only, do not edit wording |
| text_len (new) | character count |
| flag_placeholder (new) | "no content" phrasing in a text under 1,000 characters, or text_len < 200 (see refinement 1) |
| latest_date_mentioned, flag_lookahead (new) | latest explicit date written in the text; flag if later than the row date (see refinement 2) |
| is_trading_day (new) | date exists in prices calendar |
| next_trading_date (new) | for joining weekend news to the next market session |

### filings
| Column | Rule |
|---|---|
| id, symbol, date | same as prices |
| document_type | category, allowed values {10-K, 10-Q} |
| mda_content, risk_content | strip leading/trailing whitespace only |
| mda_len, risk_len (new) | character count |
| flag_risk_repeat (new) | risk_content identical to the same company's previous filing |
| flag_risk_reference_only (new) | risk_len < 1,000 (10-Q that only points back to the 10-K) |

## 5. Decisions for the human in the loop

| # | Question | Proposed default |
|---|---|---|
| D1 | Drop the 8 placeholder / fragment news rows? | Keep and flag. Dropping breaks the one-row-per-day structure, and the agents in the benchmark saw these rows too. Analysis can filter on the flag. |
| D2 | Drop weekend/holiday news (1,232 rows)? | Keep. Add is_trading_day and next_trading_date instead. |
| D3 | Remove look-ahead text? | Keep text unchanged, flag only. Editing text would be fabricating data. |
| D4 | Drop repeated or reference-only risk sections? | Keep and flag. A repeated risk section is real information ("nothing changed"). |
| D5 | Treat >12% moves as errors? | No. They match known market events. Flag for the dashboard only. |
| D6 | close or adj_close for returns? | adj_close, so dividends do not show up as fake drops. |
| D7 | Keep ADBE? Jim's sample output only shows 7 symbols. | Keep all 8 (project-start.md says eight companies). Confirm with the team. |

## 6. Validation checklist (run after cleaning)

- Row counts before vs after for each table (expected: unchanged)
- Missing values before vs after
- Duplicate counts on id and symbol+date
- Unique values of symbol and document_type
- min / max / distribution of prices, volume, daily_return, text lengths
- Count of every flag column, by symbol
- 3 example rows before and after for each table
- Sanity question: does the cleaned data still describe what each company and the market actually looked like on each date?

## 7. Decisions confirmed and refinements

All decisions D1 to D7 were accepted with the proposed defaults (D7 still to be confirmed with the team).

Implementation: `clean_peter.py`. Results: `outputs/validation_report.md`.

1. **Placeholder rule tightened.** First run flagged 20 news rows; reading them showed 12 were real summaries that only said one of several articles was empty. New rule gives 8 rows, all confirmed placeholders.
2. **Look-ahead rule replaced.** A keyword search matched 33 rows, but nearly all were disclaimers saying future information had been excluded. New rule compares explicit dates in the text with the row date and finds 1 real leak (ADBE 2025-02-15 mentions the 2025-02-25 Photoshop for iPhone launch).
