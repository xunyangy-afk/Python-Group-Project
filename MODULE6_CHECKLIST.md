# Module 6: Checklist for inspecting and cleaning data

**Project:** Financial Agent Deployment (TheFinAI/Herculean)
**Team:** [team name / members]

> **DRAFT by Peter (data-fit).** Filled from the Peter-work cleaning so the team has a starting point.
> Items marked **[TEAM]** need the team's decision or the other members' results before submission.
> File references are to the `Peter-work` branch unless noted.

---

## Inspecting and cleaning

### 1. State the vision along with a specific analysis question
**Status:** Unresolved **[TEAM: choose vision]**
**Evidence or explanation:** `project-start.md` lists two candidate visions; the team has not yet confirmed one. The cleaned tables (prices, news, filings) are the inputs to weekly equity research reports, so they fit Vision B. Proposed wording if the team chooses B:

> A Head of Equity Research Operations at BlackRock must choose which agent and model configuration becomes the default for generating weekly equity research reports, meeting a minimum quality standard at acceptable cost and latency.
> **Analysis question:** for each company and week, what inputs did the agent have (price moves, news coverage, filing disclosures), and how complete and reliable were they?
> **Main metric:** share of usable input records per company and week (prices with a valid return, news that is not a placeholder or look-ahead, filings with new risk disclosure).

Note for the team: the report-quality, cost and latency results that Vision B ultimately compares are **not** in these three tables (see item 14).

### 2. Define one row
**Status:** Done
**Evidence or explanation:**

| Table | One row is | Unique key | Check |
|---|---|---|---|
| prices | one company on one trading day | (symbol, date); also id | 0 repeated keys in 2,656 rows |
| news | one LLM news summary for one company on one calendar day | (symbol, date); also id | 0 repeated keys in 3,888 rows |
| filings | one 10-K or 10-Q filing | (symbol, date); also id | 0 repeated keys in 73 rows |

Source: `outputs/validation_report.md`, Validation 1.

### 3. Preserve the source
**Status:** Done
**Evidence or explanation:** Source is TheFinAI/Herculean on Hugging Face, repository commit `52d3ecb`, retrieved 2026-10-04, license CC BY 4.0. The three parquet files sit unchanged in `data/raw/`; the code only reads them and writes to `data/clean/`. SHA-256 checksums before and after a full run are identical (`outputs/reproducibility_peter.md`). Download and reload steps: `README_peter.md`.

### 4. Inspect columns and types
**Status:** Done
**Evidence or explanation:**

| Column | Original type | Converted to | Failed conversions |
|---|---|---|---|
| date (all tables) | Python `datetime.date` objects (dtype object) | datetime64 | 0 of 6,617 |
| symbol (all tables) | text (object) | category | 0 |
| id (all tables) | int32 | int64 | 0 |
| document_type | text | category, allowed values {10-K, 10-Q} | 0 values outside the set |
| open, high, low, close, adj_close, volume | float64 / int64 | unchanged | not applicable |

No values failed, so no fallback rule was needed. Source: `clean_common` in `clean_peter.py`; notebook section 1.

### 5. Standardize text
**Status:** Done
**Evidence or explanation:**
- Filings text stored characters as HTML entities in all 73 MD&A sections and 68 of 73 risk sections. Decoded to the real characters (refinement 3, D8); 0 entities remain. News had none.
  - before: `' Item 2. Management&#8217;s Discussion and Analysis'`
  - after: `'Item 2. Management’s Discussion and Analysis'`
- Leading and trailing whitespace stripped in all 73 filings for both text columns; news needed none.
- Symbols were already uppercase with no spaces; standardization changed 0 values but stays in the code as a guard.
- Wording of news and filings is never edited. No identifiers have leading zeros (ids are integers, tickers are letters).

Source: `outputs/validation_report.md`, Step 3 and Validation 5; notebook section 6.

### 6. Investigate duplicates
**Status:** Done
**Evidence or explanation:** Exact duplicate rows: 0 in every table. Repeated id: 0. Repeated (symbol, date): 0. Nothing removed. One valid repetition found in content: 7 quarterly filings repeat the previous filing's risk section word for word (AMZN 3, GOOGL 2, TSLA 2). These are real filings saying "no change", so they are kept and marked `flag_risk_repeat`. Source: Validation 1 and 4.

### 7. Handle missing data
**Status:** Done
**Evidence or explanation:** No original column has missing values before or after cleaning (0 in all three tables). New missing values exist only in derived columns, by design:

| Field | Missing after | Decision | Business reason |
|---|---|---|---|
| prices.daily_return | 8 (first day of each symbol) | keep as NaN | no earlier price; filling 0 would invent a flat day |
| news.latest_date_mentioned | 482 | keep as NaT | the summary contains no explicit date, so there is nothing to compare |

Source: Validation 1.

---

## Validating the result

### 8. Check suspicious values
**Status:** Done
**Evidence or explanation:** Invalid dates 0; non-positive prices 0; zero volume 0; OHLC logic violations 0; no weekend price rows. Unusual but kept and flagged:

| Finding | Rows | Action | Why |
|---|---|---|---|
| daily move above 12% | 9 | kept, `flag_large_move` | match real events (2025-04-09 tariff pause rally, NVDA 2025-01-27 DeepSeek drop) |
| empty or fragment news summary | 8 | kept, `flag_placeholder` | it is what the agent received; dropping breaks one row per day |
| news mentions a later date | 1 | kept, `flag_lookahead` | ADBE 2025-02-15 mentions the 2025-02-25 Photoshop launch |
| risk section only refers to the 10-K | 9 | kept, `flag_risk_reference_only` | real filing, but no new risk text |

Two first-draft rules were too broad and revised after reading the flagged rows (placeholder 20 to 8, look-ahead 33 to 1); see `plan.md` section 7.

### 9. Verify merges
**Status:** Done
**Evidence or explanation:** No tables are merged in the cleaned output, but news is prepared for joining to prices. Join test: news (symbol, next_trading_date) to prices (symbol, date), expected many to one because weekend and holiday news share the next session. Rows before 3,888, after 3,888 (no multiplication; pandas `validate="many_to_one"` passed); unmatched news rows 0; price rows without news 0; at most 4 news rows map to one price row (a long weekend). Source: Validation 6; notebook section 8.

**[TEAM]** A plain merge on (symbol, date) would silently drop the 1,232 weekend and holiday news rows (1,112 weekend, 120 holiday). Any team code that joins on the raw date should use `next_trading_date` instead.

### 10. Reconcile changes
**Status:** Done
**Evidence or explanation:** prices 2,656 to 2,656; news 3,888 to 3,888; filings 73 to 73. No rows removed, so there is no difference to account for. Total volume is identical before and after (159,456,800,900 shares). Columns added: prices +2, news +6, filings +4 (all derived or flags). Source: Validation 1.

**[TEAM]** If the team adopts Jim's scope (7 companies, ADBE excluded), prices drop to 2,324, news to 3,402 and filings to 63; record that here.

### 11. Check calculations
**Status:** Done
**Evidence or explanation:**

| Metric | Records total | Records used | Excluded because |
|---|---|---|---|
| daily return and volatility per symbol | 2,656 | 2,648 | first trading day has no prior price |
| news coverage per symbol and day | 3,888 | 3,880 | placeholder or fragment |
| news free of look-ahead | 3,888 | 3,887 | mentions a later date |
| new risk disclosure per filing | 73 | 61 | repeated or reference-only risk section |

Averages use records used as the denominator and report it; excluded rows stay in the data with a flag rather than being dropped. Missing group keys (symbol or date): 0 in every table. Source: Validation 7, `outputs/metric_support_peter.csv`.

### 12. Verify individual records
**Status:** Done
**Evidence or explanation:** Five difficult records traced from original to cleaned; all five match. See the Five record checks section below and `outputs/record_checks_peter.csv`.

### 13. Test reproducibility
**Status:** Done (Peter-work) **[TEAM: repeat for the merged version]**
**Evidence or explanation:** `python3 reproduce_check_peter.py` copies the raw files and `clean_peter.py` into an empty folder, runs `python3 clean_peter.py` in a new process and compares every output: all 9 output files match the submitted version, raw checksums unchanged. Notebook procedure: Restart kernel, Run All; 0 errors. Source: `outputs/reproducibility_peter.md`.

### 14. Document remaining limitations
**Status:** Unresolved (documented)
**Evidence or explanation:**
1. **No outcome data for the vision.** These tables are the agents' inputs. Report-quality scores, cost and latency per agent and model are not in them. Without that data the main Vision B comparison cannot be made. Next step: check the dataset's `auditing_env/` folder, or budget API runs (open question 1 in `project-start.md`). **[TEAM]**
2. **Different time windows.** Filings start 2024-01-16 but prices and news start 2024-12; 32 of 73 filings fall before any price or news data.
3. **Flags are rule-based.** Placeholder detection uses phrasing and length, and look-ahead detection only catches explicit dates; a mention like "Q4 2025 results" is not caught. Counts may be slightly low.
4. **News are LLM summaries, not original articles**, so their accuracy depends on the summarizing model; 84 contain "N/A" or "n/a", for example for a missing sentiment score.
5. **Company scope.** Members disagree on whether ADBE is in scope (see Team reconciliation). **[TEAM]**

---

## Cleaning decision log

| # | Decision | Choice | Effect |
|---|---|---|---|
| D1 | Placeholder or fragment news | keep, flag | 8 rows flagged |
| D2 | Weekend and holiday news | keep, add `is_trading_day`, `next_trading_date` | 1,232 rows mapped |
| D3 | Look-ahead text | keep text unchanged, flag | 1 row flagged |
| D4 | Repeated or reference-only risk sections | keep, flag | 12 filings flagged |
| D5 | Daily moves above 12% | keep, flag | 9 rows flagged |
| D6 | Return basis | adj_close | dividends do not appear as drops |
| D7 | ADBE | keep (Peter); exclude (Jim) | **[TEAM]** |
| D8 | HTML entities in filings | decode | 73 MD&A and 68 risk sections |

Rule revisions: placeholder rule narrowed (20 to 8), look-ahead rule replaced (33 to 1), entity decoding added. Details and reasons: `plan.md` section 7.

## Five record checks

| # | Record | Case | Expected | Actual | Match |
|---|---|---|---|---|---|
| 1 | prices AAPL 2024-12-02 | first trading day | kept; close 239.59; return NaN; not flagged | same | Yes |
| 2 | prices NVDA 2025-01-27 | largest one-day drop | kept; return -0.1697 (hand calculation from adj_close); flagged | same | Yes |
| 3 | news ADBE 2025-01-26 | 25-character fragment, Sunday | kept; text unchanged; placeholder flag; next session 2025-01-27 | same | Yes |
| 4 | news ADBE 2025-02-15 | Saturday before Presidents Day, mentions later event | kept; look-ahead flag (2025-02-25); next session 2025-02-18 | same | Yes |
| 5 | filings TSLA 2024-07-23 | 10-Q risk section only points to the 10-K | kept; 333 to 329 characters after stripping; same as previous filing; both risk flags | same | Yes |

Why each expectation is right: `outputs/validation_report.md`, Validation 8.

## Team reconciliation **[TEAM]**

| Topic | Jim | Olivia | Peter | Team decision |
|---|---|---|---|---|
| Company scope | 7 companies, ADBE excluded | not stated | 8 companies | |
| Weekend and holiday news | [check] | prices merged with news on same date (weekend news drops out) | kept, mapped to next session | |
| Return basis | adj_close | [check] | adj_close | agree |
| Content flags (placeholder, look-ahead, risk repeat) | none found in code | none | yes | |
| HTML entities in filings | [check] | [check] | decoded | |
| Evelyn, Zack | [add results] | | | |

## Codex verification response **[TEAM]**

Give a fresh Codex session the repository and this checklist, ask it to verify every number against the code and outputs, and paste its response here.

Suggested prompt:
> Read MODULE6_CHECKLIST.md and the code on this branch. For each of the 14 items, rerun or inspect the code and tell me whether every number and claim matches the actual outputs. List anything that does not match or is not supported by evidence.
