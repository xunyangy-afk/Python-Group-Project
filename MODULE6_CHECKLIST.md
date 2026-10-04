# Module 6: Checklist for inspecting and cleaning data

**Project:** Financial Agent Deployment: weekly deep-dive prioritization for mega-cap tech stocks
**Team:** [team name / members]

> **DRAFT by Peter (data-fit).** Filled from the Peter-work cleaning so the team has a starting point.
> Items marked **[TEAM]** need the other members' results or a team check before submission.
> File references are to the `Peter-work` branch.

---

## Inspecting and cleaning

### 1. State the vision along with a specific analysis question
**Status:** Done
**Evidence or explanation:**
- **Vision:** A junior equity research analyst on a technology-sector coverage team must decide which of the seven mega-cap technology stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA) to prioritize for this week's deep-dive research, based on relative price performance, volatility, trading-volume activity, and recent news or filing events.
- **Business question:** How does company news relate to subsequent price changes and trading volume?
- **Main metrics:** the return and the volume ratio (volume divided by the previous 20-session average) of the session **after** each news day or filing, compared across the seven stocks and against each stock's normal level.
- **Data used:** prices (daily OHLC and volume), news (one LLM summary per stock per calendar day), filings (10-K and 10-Q text), TheFinAI/Herculean.

### 2. Define one row
**Status:** Done
**Evidence or explanation:**

| Table | One row is | Unique key | Check |
|---|---|---|---|
| prices | one stock on one trading session | (symbol, date); also id | 0 repeated keys in 2,324 rows |
| news | one LLM news summary for one stock on one calendar day | (symbol, date); also id | 0 repeated keys in 3,402 rows |
| filings | one 10-K or 10-Q filing | (symbol, date); also id | 0 repeated keys in 63 rows |

Source: `outputs/validation_report.md`, Validation 1.

### 3. Preserve the source
**Status:** Done
**Evidence or explanation:** Source is TheFinAI/Herculean on Hugging Face, repository commit `52d3ecb`, retrieved 2026-10-04, license CC BY 4.0. The three parquet files sit unchanged in `data/raw/`; the code only reads them and writes to `data/clean/`. SHA-256 checksums are identical before and after a full run (`outputs/reproducibility_peter.md`). Download and reload steps: `README_peter.md`.

### 4. Inspect columns and types
**Status:** Done
**Evidence or explanation:**

| Column | Original type | Converted to | Failed conversions |
|---|---|---|---|
| date (all tables) | Python `datetime.date` objects (dtype object) | datetime64 | 0 |
| symbol (all tables) | text (object) | category | 0 |
| id (all tables) | int32 | int64 | 0 |
| document_type | text | category, allowed values {10-K, 10-Q} | 0 values outside the set |
| open, high, low, close, adj_close, volume | float64 / int64 | unchanged | not applicable |

No values failed, so no fallback rule was needed. Source: `clean_common` in `clean_peter.py`; notebook section 2.

### 5. Standardize text
**Status:** Done
**Evidence or explanation:**
- Filings text stored characters as HTML entities in all 63 MD&A sections and 58 of 63 risk sections. Decoded to the real characters (D8); 0 entities remain. News had none.
  - before: `' Item 2. Management&#8217;s Discussion and Analysis'`
  - after: `'Item 2. Management’s Discussion and Analysis'`
- Leading and trailing whitespace stripped in all 63 filings for both text columns; news needed none.
- Symbols were already uppercase with no spaces; standardization changed 0 values but stays in the code as a guard.
- Wording of news and filings is never edited. No identifiers have leading zeros (ids are integers, tickers are letters).

Source: `outputs/validation_report.md`, Step 3 and Validation 5; notebook section 7.

### 6. Investigate duplicates
**Status:** Done
**Evidence or explanation:** Exact duplicate rows: 0 in every table. Repeated id: 0. Repeated (symbol, date): 0. No duplicates removed. One valid repetition in content: 7 quarterly filings repeat the previous filing's risk section word for word (AMZN 3, GOOGL 2, TSLA 2). These are real filings saying "no change", so they are kept and marked `flag_risk_repeat`. Source: Validation 1 and 4.

### 7. Handle missing data
**Status:** Done
**Evidence or explanation:** No original column has missing values before or after cleaning. New missing values exist only in derived columns, by design:

| Field | Missing after | Decision | Business reason |
|---|---|---|---|
| prices.daily_return | 7 (first session of each stock) | keep NaN | no earlier price; filling 0 would invent a flat day |
| prices.volume_ratio_20d | 140 (first 20 sessions of each stock) | keep NaN | no full 20-session baseline; a shorter window would not be comparable |
| news.reaction_date | 7 (news on 2026-03-31, the last session) | keep NaT | the next session is not in the data |
| news.latest_date_mentioned | 402 | keep NaT | the summary contains no explicit date |
| filings.reaction_date | 28 (filed before 2024-12-02) | keep NaT, `in_price_window` False | no price data after the filing |

Source: Validation 1.

---

## Validating the result

### 8. Check suspicious values
**Status:** Done
**Evidence or explanation:** Invalid dates 0; non-positive prices 0; zero volume 0; OHLC logic violations 0; no weekend price rows. Unusual but kept:

| Finding | Rows | Action | Why |
|---|---|---|---|
| daily move above 12% | 7 | kept, `flag_large_move` | real events: 2025-04-09 tariff pause rally (AAPL, META, NVDA, TSLA), NVDA 2025-01-27 DeepSeek drop, TSLA 2025-03-10 and 2025-06-05 |
| volume above 4x the 20-session average | 5 | kept | 4 of 5 are the session right after a filing in the data: META 2025-10-30 (7.2x), MSFT 2026-01-29 (4.9x), AMZN 2026-02-06 (4.0x), META 2026-01-29 (4.0x); the fifth is NVDA 2025-01-27 (4.1x, DeepSeek) |
| empty or fragment news summary | 7 | kept, `flag_placeholder` | it was published; dropping it breaks one row per day; excluded from news metrics by the flag |
| risk section only refers to the 10-K | 9 | kept, `flag_risk_reference_only` | real filing, but no new risk text |

Two first-draft rules were too broad and revised after reading the flagged rows (placeholder 20 to 8 rows, look-ahead 33 to 1, both on the full data); see `plan.md` section 7. In scope, the look-ahead flag finds 0 rows: the one leak was an ADBE row.

### 9. Verify merges
**Status:** Done
**Evidence or explanation:** Join used by the business question: news (symbol, reaction_date) to prices (symbol, date), where `reaction_date` is the first session after the news date (D9). Expected relationship many to one: Friday, weekend and holiday news share the next session.

| Check | Result |
|---|---|
| news rows before / after join | 3,402 / 3,402 (no multiplication; pandas `validate="many_to_one"` passed) |
| news with no next session | 7, all on 2026-03-31, expected |
| other unmatched news | 0 |
| most news rows on one price row | 4 (a long weekend) |

A plain merge on (symbol, date) would silently drop the 1,078 weekend and holiday news rows (973 weekend, 105 holiday) and would pair news with the same session instead of the subsequent one. Source: Validation 6; notebook section 9.

### 10. Reconcile changes
**Status:** Done
**Evidence or explanation:**

| Table | Start | Excluded: ADBE out of scope (D7) | Other rows removed | Final |
|---|---|---|---|---|
| prices | 2,656 | 332 | 0 | 2,324 |
| news | 3,888 | 486 | 0 | 3,402 |
| filings | 73 | 10 | 0 | 63 |

Total volume: 159,456,800,900 shares before; 158,002,379,300 after; the difference is exactly ADBE's 1,454,421,600 shares. Columns added: prices +3, news +7, filings +6 (derived values and flags only). Source: Step 0 and Validation 1.

### 11. Check calculations
**Status:** Done
**Evidence or explanation:**

| Metric | Records total | Records used | Excluded because |
|---|---|---|---|
| daily return and volatility per stock | 2,324 | 2,317 | first session has no prior price (7) |
| volume ratio vs previous 20 sessions | 2,324 | 2,184 | first 20 sessions per stock (140) |
| next-session return after news | 3,402 | 3,381 | placeholder (7), last day with no next session (7), next session is the first one with no return (7) |
| next-session volume ratio after news | 3,402 | 3,190 | placeholder, no next session, or next session inside the first 20 |
| price and volume reaction after a filing | 63 | 35 | filed before the price data starts |

Averages use records used as the denominator and state it; excluded rows stay in the data with a flag or NaN. Missing group keys (symbol or date): 0 in every table. Source: Validation 7, `outputs/metric_support_peter.csv`.

### 12. Verify individual records
**Status:** Done
**Evidence or explanation:** Six difficult records traced from original to cleaned; all six match. See the Record checks section below and `outputs/record_checks_peter.csv`.

### 13. Test reproducibility
**Status:** Done (Peter-work) **[TEAM: repeat for the final team version]**
**Evidence or explanation:** `python3 reproduce_check_peter.py` copies the raw files and `clean_peter.py` into an empty folder, runs `python3 clean_peter.py` in a new process and compares every output: all 9 output files match the submitted version and raw checksums are unchanged. Notebook procedure: Restart kernel, Run All; 0 errors. Source: `outputs/reproducibility_peter.md`.

### 14. Document remaining limitations
**Status:** Unresolved (documented)
**Evidence or explanation:**
1. **News exists every day for every stock.** There is no "no-news" day to compare against, so news presence alone cannot explain price moves. The analysis needs a measure of news content or importance (filing dates as discrete events, summary length, or a sentiment score added later). Without it, the answer to the business question is limited to filings and to qualitative reading of news.
2. **Association, not cause.** A news day followed by a big move does not show that the news caused it; market-wide days such as 2025-04-09 move all stocks at once. Comparing each stock with the others on the same day helps separate company news from market news.
3. **Timing inside the day is unknown.** Summaries are dated by calendar day, not time, so we use the next session (D9). This avoids crediting news with a move that happened before it, but can miss same-day reactions to morning news.
4. **Short window for filings.** 28 of 63 filings come before the price data starts (2024-12-02), leaving 35 filings with a measurable reaction, about 5 per stock.
5. **News are LLM summaries, not original articles.** 7 are empty placeholders and 51 contain "N/A" or "n/a", for example for a missing sentiment score. Placeholder detection is rule-based and may miss some.

---

## Cleaning decision log

| # | Decision | Choice | Effect |
|---|---|---|---|
| D1 | Placeholder or fragment news | keep, flag | 7 rows flagged |
| D2 | Weekend and holiday news | keep, add `is_trading_day`, `next_trading_date` | 1,078 rows aligned |
| D3 | Look-ahead text | keep text unchanged, flag | 0 rows in scope |
| D4 | Repeated or reference-only risk sections | keep, flag | 12 filings flagged |
| D5 | Daily moves above 12% | keep, flag | 7 rows flagged |
| D6 | Return basis | adj_close | dividends do not appear as drops |
| D7 | ADBE | exclude: not in the seven-stock vision | 828 rows removed and counted |
| D8 | HTML entities in filings | decode | 63 MD&A and 58 risk sections |
| D9 | Session that news relates to | first session after the news or filing date | `reaction_date` on news and filings |
| D10 | Unusual volume | volume / previous 20-session average | `volume_ratio_20d` on prices |

Rule revisions: placeholder rule narrowed, look-ahead rule replaced, entity decoding added, then scope and timing fields added once the team fixed the vision. Details and reasons: `plan.md` section 7.

## Record checks

| # | Record | Case | Expected | Actual | Match |
|---|---|---|---|---|---|
| 1 | prices AAPL 2024-12-02 | first session in the data | kept; close 239.59; return and volume ratio NaN | same | Yes |
| 2 | prices NVDA 2025-01-27 | largest one-day drop | kept; return -0.1697 and volume ratio 4.08 (hand calculation from raw); flagged | same | Yes |
| 3 | news GOOGL 2024-12-29 | placeholder summary on a Sunday | kept; text unchanged; placeholder flag; reaction session 2024-12-30 | same | Yes |
| 4 | news AAPL 2025-02-14 | Friday before a weekend and Presidents Day | kept; reaction session Tuesday 2025-02-18 | same | Yes |
| 5 | filings TSLA 2024-07-23 | 10-Q before the price window, risk section points to the 10-K | kept; 333 to 329 characters; same as previous filing; both risk flags; not in price window | same | Yes |
| 6 | news ADBE 2025-02-15 | stock outside the vision | in raw; absent from cleaned; counted as excluded | same | Yes |

Why each expectation is right: `outputs/validation_report.md`, Validation 8.

## Team reconciliation **[TEAM]**

| Topic | Jim | Olivia | Peter | Team decision |
|---|---|---|---|---|
| Company scope | 7 stocks, ADBE excluded | not stated | 7 stocks, ADBE excluded | 7 stocks (vision) |
| Return basis | adj_close | [check] | adj_close | adj_close |
| Weekend and holiday news | [check] | merged with prices on the same date (these rows drop out) | kept, mapped to the next session | |
| Which session news relates to | [check] | same date | next session (D9) | |
| Volume measure | [check] | [check] | ratio to previous 20 sessions (D10) | |
| Content flags (placeholder, risk repeat) | none in code | none | yes | |
| HTML entities in filings | [check] | [check] | decoded | |
| Evelyn, Zack | [add results] | | | |

## Codex verification response **[TEAM]**

Give a fresh Codex session the repository and this checklist, ask it to verify every number against the code and outputs, and paste its response here.

Suggested prompt:
> Read MODULE6_CHECKLIST.md and the code on this branch. For each of the 14 items, rerun or inspect the code and tell me whether every number and claim matches the actual outputs. List anything that does not match or is not supported by evidence.
