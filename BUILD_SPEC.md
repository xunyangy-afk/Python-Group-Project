# BUILD_SPEC.md — Magnificent Seven Research Workbench

**Status: approved design specification; the dashboard has not been implemented or verified by writing this document.**

This document is the complete specification for a future implementation. When explicitly asked to implement it, build the application, run the checks, and report actual results. Reading or editing this specification alone does not authorize a build. The present deliverable is this document only.

No previous conversation, wildfire example, individual contributor notebook, or raw-data download is required to understand the design. The three cleaned Parquet inputs described below are the only data prerequisites. All paths are relative to the project root: use the current directory if it contains `artifacts/prices_clean.parquet`, `artifacts/news_clean.parquet`, and `artifacts/filings_clean.parquet`; otherwise use its `Python-Group-Project` child if those files exist there. Stop with a useful missing-input message if neither location matches. Do not substitute another contributor's outputs or sample data.

## 1. Current vision, user, and decision

A junior equity research analyst on a technology-sector coverage team must decide which of **AAPL, MSFT, GOOGL, AMZN, NVDA, META, and TSLA** to prioritize for this week's deep-dive research. The analyst compares relative price performance, historical return volatility, trading-volume activity, and news or filing excerpts, then records **one or two research candidates with a reason**.

Today, that comparison requires moving between separate price, news, and filing tables and repeating date filters and calculations. The workbench brings them into one coordinated view: compare companies, investigate a company and date, read the underlying excerpts, and record a research shortlist. Its output is a research-priority decision, not a buy/sell recommendation or an automatically scored stock ranking.

This is the current version of the project's vision. Earlier project notes about evaluating agent/model configurations are historical context, not requirements for this dashboard; leave those documents unchanged.

The supplied prices end on **March 31, 2026**. The workbench supports an analyst's research workflow using this historical snapshot. It must identify the data cutoff and the selected historical period; it must not label the snapshot as current-week or live market data.

## 2. Approved features and use cases

The following six features were individually approved. The offline HTML delivery, single-page layout, and default window of 60 observed price dates were also approved. Do not add other major features without a new request.

| ID | User selects / inputs | Dashboard shows | User decides | Feature and section |
|---|---|---|---|---|
| F1 | One or more companies and an inclusive date range, using date inputs or a timeline selection | Aligned adjusted-close and volume histories; adjusted close can be shown in source units or rebased to 100 | Which companies diverged, and which dates merit investigation | Linked price and volume charts |
| F2 | A comparison interval and a metric to sort by | A company comparison table with interval return, daily return volatility, and average daily volume | Which companies deserve closer examination | Company comparison table |
| F3 | A company/date point, a company row, or an event in the selected interval | News digest text and filing MD&A/risk excerpts with dates, IDs, and existing quality flags | What evidence needs reading or independent verification | Event reading panel |
| F4 | Raw-volume or relative-volume mode | Daily volume as shares or as a multiple of the company's preceding 20-observation average | Whether volume is unusually high or low relative to that company's own recent history | Volume-chart mode; 1× reference line |
| F5 | A comparison interval | The largest within-interval peak-to-trough adjusted-price decline, in the comparison table | Whether an interval's endpoint return conceals a substantial intervening decline | Maximum-drawdown column; no separate chart |
| F6 | Up to two companies and an analyst-written reason for each | A frozen snapshot of each selection's date range and metrics, plus an exportable CSV | Which one or two companies to prioritize for deeper research | Research shortlist |

Every major display element must serve these use cases. Filters and the timeline serve F1/F2; the reading panel serves F3; the two volume modes serve F1/F4; the shortlist serves F6. Data-coverage labels, source notes, and quality flags support interpretation of these same features.

Do not introduce valuation ratios, market-index comparisons, beta, Sharpe ratios, forecasts, sentiment scoring, generated news summaries, automated research recommendations, additional datasets, or live feeds. The inputs do not supply the complete data or approved definitions for those features.

## 3. Cleaned inputs and data contracts

### 3.1 Formal inputs and snapshot facts

Source attribution: the team's cleaned local snapshot of **TheFinAI/Herculean**, identified in the cleaning records as `team-local-sha256-v1`. Upstream revision and price-adjustment methodology remain unconfirmed. The cleaned files are sufficient for this dashboard; do not rerun cleaning or require `sources/raw/`.

| Input | Snapshot shape | Observation | Coverage | Rows per company |
|---|---|---|---|---:|
| `artifacts/prices_clean.parquet` | 2,324 rows × 16 columns | One company's price/volume observation on one calendar date | 2024-12-02 through 2026-03-31 | 332 |
| `artifacts/news_clean.parquet` | 3,402 rows × 11 columns | One company/date news digest record, not necessarily one individual article | 2024-12-01 through 2026-03-31 | 486 |
| `artifacts/filings_clean.parquet` | 63 rows × 13 columns | One filing document record containing excerpts | Overall 2024-01-26 through 2026-02-25; bounds differ by company | 9 |

These are complete tables, not samples. Formal outputs contain only the seven approved symbols. ADBE exclusion files are not dashboard inputs.

Current cleaned-file SHA256 values, for snapshot verification rather than display constants:

| File | SHA256 |
|---|---|
| `prices_clean.parquet` | `84a3c2c4eaab0977f98666cc431faafdf1eb39cbc20deff36579ab430060ae1e` |
| `news_clean.parquet` | `94fc868bb681c810999d861e40e3cfb402473bc77141554003c6f362f027ba0d` |
| `filings_clean.parquet` | `d56aa0d85cf96dc991f8e74bc06541479bc044c6652995cbfd3f81f582ab2a6c` |

Check these hashes and snapshot facts for the supplied production inputs. A mismatch requires an explicit report and a reviewed snapshot update; do not silently replace the input or manipulate records to hit the expected counts. Synthetic tests use separate in-memory or temporary fixtures and do not need the production hashes. Compute all visible counts, dates, and financial values from the loaded files.

### 3.2 Complete field dictionary

Shared by all three tables:

| Field | Type / meaning |
|---|---|
| `id` | String identifier, unique within its own table; not a cross-table join key |
| `symbol` | String ticker from the seven-company universe |
| `date` | Timezone-naive `datetime64[ns]` containing a date-only value; use its original calendar date |
| `_source_row` | Integer, zero-based row position in that table's raw source, for traceability |
| `flag_repeated_business_key` | Boolean review flag for a repeated candidate business key |

Prices additionally contain:

| Field | Type / meaning |
|---|---|
| `open`, `high`, `low`, `close` | Float64 unadjusted daily price fields; retained for source verification, not additional approved charts |
| `adj_close` | Float64 adjusted close; the price field for F1/F2/F5 calculations |
| `volume` | Nullable `Int64`, observed share volume |
| `flag_invalid_numeric` | Missing, nonfinite, or invalid price/volume domain detected during cleaning |
| `flag_ohlc` | Inconsistency among the unadjusted OHLC fields |
| `flag_zero_volume` | Observed volume equals zero |
| `flag_large_move` | Absolute adjusted-close return above the cleaning workflow's 12% review threshold |
| `flag_gap_gt4_calendar_days` | More than four calendar days since the preceding company observation |

News additionally contains:

| Field | Type / meaning |
|---|---|
| `highlights` | String news digest text; no separate article-title, URL, or publication-time column is supplied |
| `flag_empty_text` | Missing or empty digest |
| `flag_placeholder` | Short digest or possible placeholder wording identified by cleaning heuristics |
| `flag_future_date_mention` | Explicit date later than the record date detected in text; not a comprehensive leakage test |
| `flag_apparent_truncation` | Possible incomplete text identified by a textual heuristic |
| `flag_timing_unverified` | Publication/information-availability time has not been verified; true for every news record in this snapshot |

Filings additionally contain:

| Field | Type / meaning |
|---|---|
| `document_type` | String form label, usually `10-K` or `10-Q` |
| `mda_content` | String Management's Discussion and Analysis excerpt, not the entire filing |
| `risk_content` | String risk disclosure excerpt, not necessarily the full Risk Factors section |
| `flag_empty_mda_content` | Missing or empty MD&A excerpt |
| `flag_empty_risk_content` | Missing or empty risk excerpt |
| `flag_unexpected_form` | Form outside the cleaning workflow's expected 10-K/10-Q set |
| `flag_short_risk_text` | Risk excerpt below the cleaning workflow's 1,000-character review threshold |
| `flag_repeated_previous_risk` | Risk excerpt matches the preceding filing for the same company |

All flag fields are booleans. Interpret flags as review cues, not findings that prove an error. Do not recalculate their thresholds or discard a row solely because a flag is true.

### 3.3 Read-only validation and preservation

- Validate required fields, readable types, known symbols, date-only values, unique table IDs, and unique price `(symbol, date)` keys. News `(symbol, date)` and filing `(symbol, date, document_type)` are candidate business keys: different IDs on the same date must remain available.
- Require the supplied production snapshot to contain all seven symbols in all three tables. Price-date gaps or partial fixture coverage must not be filled with fabricated observations.
- Report schema/key failures with file, field, and record ID or source row where available. Fail clearly instead of emitting a plausible but incorrect dashboard.
- Sort derived working views deterministically by symbol, date, ID, and source position. Do not overwrite any input table, clean text again, decode HTML again, or alter source values.
- Preserve genuine missingness. Missing/nonfinite/nonpositive adjusted close is invalid for price calculations. Missing/nonfinite/negative volume is invalid for volume calculations; zero volume is a valid observed zero.
- Assess validity per required field: an OHLC flag must not automatically invalidate a valid adjusted close, and an invalid price must not invalidate an otherwise valid volume.
- Preserve paragraphs and punctuation in news and filing excerpts. Render text as text rather than executable HTML; serialize embedded data safely so source text cannot terminate a script element.
- Keep the complete event tables in the embedded payload, including records without a matching price date. Do not join events into the price table. The global research range is bounded by price coverage; earlier filings remain preserved but are outside that active range.

All source fields in this snapshot were reported nonmissing. The dashboard must nevertheless handle the missingness fixtures in the acceptance section rather than depend on that property forever.

## 4. Metric and visual contracts

### 4.1 Shared interval convention

The global research interval is inclusive: `start_date <= date <= end_date`. Use each company's actual rows within that interval in date order. Show its actual first and last observation dates and observation counts in the table's detail text or tooltip when those differ from the requested range.

Do not move the interval's endpoints to a nonmissing price. A company's first row means its first observed row within the interval, even if that row's adjusted close is missing or invalid. No return may cross a company boundary or the interval's left boundary.

Dates are date-only `YYYY-MM-DD` values. The browser must not shift them through local timezone conversion. Calendar gaps are not evidence of certified exchange holidays. The displayed daily volatility is calculated over consecutive observed price sessions; it is neither annualized nor a claim of independently verified exchange-calendar completeness.

### 4.2 Required measures

In the formulas below, `P_t` is a valid `adj_close` for one company and `V_t` is a valid observed volume. Formulas describe required behavior, not function implementations.

| Measure / visual | Question answered | Source and calculation | Filters and boundaries |
|---|---|---|---|
| Adjusted-close chart, source-units mode | How did reported adjusted price move? | Plot `adj_close` against `date`, one labeled line per selected company | Global companies and interval; invalid values are gaps; label `Adjusted close (source units)` because the tables have no currency field |
| Adjusted-close chart, base-100 mode | How did companies perform relative to their own interval starting points? | `100 × P_t / P_first`, using the interval's first actual row | Recompute the baseline after range changes; if the first price is invalid, the entire company's normalized series is unavailable; do not choose a later baseline |
| Interval return | Which companies rose or fell most over the requested interval? | `P_last / P_first − 1`, using actual first and last interval rows | At least two observed rows and valid endpoints; otherwise `N/A`; an invalid interior value does not invalidate a computable endpoint return |
| Daily return, supporting calculation | What were the observed session-to-session changes inside the interval? | `P_t / P_previous − 1` for adjacent rows of the same company | First interval row is missing; either invalid endpoint makes that pair missing; do not drop invalid rows first and bridge across them |
| Daily return volatility | How dispersed were the company's interval returns? | Sample standard deviation of valid interval daily returns, `ddof=1` | At least two valid returns; otherwise `N/A`; display as a percentage without annualization |
| Average daily volume | What was the typical observed share volume during the interval? | Arithmetic mean of valid `volume` observations, including observed zeros | Same company and interval; use valid-volume count as denominator; no valid observations means `N/A` |
| Raw volume chart | When was trading activity higher or lower? | Plot daily `volume`, one labeled line per selected company, on a separate axis/chart from price | Same selected interval and companies; units are shares, with millions formatting as needed |
| Relative volume chart | How active was a day relative to that company's own recent baseline? | `V_t / mean(V_previous_20)` using exactly the preceding 20 observed rows, excluding today | Compute with full preceding history before the display filter; require all 20 previous volumes valid, current volume valid, and positive denominator; otherwise `N/A`; a valid current zero gives 0× |
| Maximum drawdown | What was the largest observed peak-to-trough decline within the interval? | The maximum of `1 − P_t / H_t`, where `H_t` is the highest adjusted close from interval start through date `t` | At least two rows; display as a nonnegative percentage; an entirely nondecreasing valid series gives 0%; any invalid adjusted price in the interval makes this metric `N/A`, rather than silently bridging unknown history |

Daily volatility and maximum drawdown answer different questions and must retain distinct labels. The relative-volume lookback is the explicit exception to the interval-only calculation rule: it uses earlier observations, while interval returns and base-100 normalization do not.

Do not label adjusted-close change as verified total shareholder return. The snapshot does not establish the adjustment methodology. Do not multiply daily volatility by the square root of 252 or introduce rolling-volatility windows.

### 4.3 Event evidence and interpretation

- Match a selected company's events by the original calendar date or inclusive interval, depending on the panel mode. A digest is a digest, not a count of individual news articles.
- Provide separate News and Filings tabs within the reading panel. A filing card identifies the form and presents MD&A and Risk excerpt sections separately. Unexpected forms remain readable with their existing flag.
- List records newest date first, then ID lexicographically and source position ascending. Expand one record at a time for full text; the default expanded item is the first record in the active tab and mode.
- Each record shows company, original date, table-local ID, and active flags in readable language. Source position may appear in a small provenance detail. Text previews use the first 240 characters of the original text and an ellipsis only when truncated for display; the full original text remains expandable.
- Every news view explains once that publication timing is unverified. Do not repeat a large warning for every record. Other true flags appear beside the affected record; flags do not hide content.
- Empty states say `No news digest for this company and date` or the equivalent filing/interval message. They must not claim that no real-world event occurred.
- Weekend event records stay on their original dates. Do not create `reaction_date`, map events to the next trading session, infer publication time, or describe text as the established cause of a price movement.

## 5. Starting view and interaction behavior

### 5.1 Initial state

| Setting | Required initial value |
|---|---|
| Title | `Magnificent Seven Research Workbench` |
| Purpose sentence | `Compare historical price performance, trading activity, and company disclosures to choose one or two stocks for deeper research.` |
| Company selector order | AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA; all selected |
| Data cutoff | Maximum price date, computed from the data; 2026-03-31 in this snapshot |
| Range end | Maximum price date |
| Range start | The 60th distinct observed price date counted backward from the end across the full price table; use all available dates if fewer than 60 exist |
| Price mode | `Indexed to 100` |
| Volume mode | `Shares` |
| Sort metric and direction | `Interval return`, descending; ties by symbol ascending; missing values always last |
| Focus company | AAPL |
| Focus date | Latest price date in the initial interval |
| Event panel | `Selected date` mode, `News` tab |
| Shortlist | Empty |

The default range is determined before company filtering. Toggling a company must not silently reset it. A small source/coverage line states that the tool is a historical snapshot and gives the cutoff; no wall-clock-relative `this week` badge is permitted.

### 5.2 Global filters and comparison table

- Provide labeled start/end date inputs and an Apply control, company checkboxes, price-mode and volume-mode controls, and a metric selector. Available sort metrics are interval return, daily return volatility, average daily volume, and maximum drawdown.
- Applying a valid date range updates the one shared range state, all interval metrics, both chart ranges, and the interval event list. Reject reversed or out-of-price-coverage dates with an inline message and retain the last valid state. A valid weekend-only range is allowed even if it contains no prices.
- Keep at least one company selected; attempting to deselect the last one leaves it selected and shows a short explanation. Company filtering affects the table and both charts together.
- Table columns, in order: Company, Interval return, Daily volatility, Average daily volume, Maximum drawdown, Observations, and Research action. Expose actual first/last dates and valid-return count through accessible detail text or tooltips; they are context for F2, not extra performance metrics.
- The metric selector sorts descending initially for the selected metric; a column header can toggle direction and updates that same sort state. Equal values use symbol ascending, and `N/A` stays last in either direction. Sorting never adds/removes companies, changes their chart colors, or changes the focus company.
- Selecting a table row focuses that company in the event panel. The row's separate `Add to shortlist` control performs only the shortlist action.

### 5.3 Timeline and point selection

- Display two vertically stacked Plotly line charts with the same calendar-date x-axis range: adjusted close above volume. One line per selected company allows both charts to identify a company/date point; do not stack or sum company volumes.
- Provide a compact full-history date navigator below the charts with a draggable selection window. Its range and the date inputs use the same state. Navigator context shows selected-company full-history base-100 lines anchored at each company's first full-history observation; label this as overview context so it is not confused with the main chart's range-dependent baseline.
- A horizontal drag on either main chart selects a new global research interval, rather than creating a private chart zoom. Snap a chart drag to the first and last observed price dates enclosed by the drag. If it encloses none, retain the current interval and explain that no observed dates were selected. Navigator dragging follows the same rule.
- Date inputs provide the keyboard-accessible alternative to dragging and permit non-price dates within the price coverage bounds. Keep navigator handles synchronized. Use a `Full history` control on the navigator to restore the full available price range; it changes only the range, not companies or modes.
- A point click focuses its company and original date, switches the event scope to `Selected date`, and retains the active News/Filings tab. It does not change the research interval, sort state, or shortlist.
- A company removal that removes the focus company moves focus to the first remaining company in selector order. On range changes, retain the focus date if it is inside the new range; otherwise use the latest available focus-company price date inside the range, or the range end if there is no price observation. Row selection uses this same date rule.
- Invalid values render as gaps, never zeros. Align chart traces to the union of observed price dates for plotting and use null for a company missing a date in that union. Do not invent weekend price rows. Calculations continue to use original company observations, not plot-alignment placeholders.
- Company legend text is persistent and matches company colors throughout the page. Disable Plotly's independent legend-hide behavior; company visibility is controlled by the global selector so the table and charts cannot silently disagree.
- Main-chart hovers show company, date, mode-specific value, and original adjusted close or volume as appropriate. Clicking and keyboard controls must be usable without relying on hover alone.

The navigator is the range-selection control within approved F1, not an additional analytical feature. Its overview values do not feed the comparison table or shortlist calculations.

### 5.4 Event panel

- The panel heading identifies the current company and focused date. It has `Selected date` / `Selected interval` scope controls and `News` / `Filings` tabs, with matching-record counts.
- Clicking an interval event card opens that record and sets the focus date to its original date without shrinking the research range or changing panel scope. This also works for weekend dates without a price observation. A date guide may appear on the charts, but no price point is fabricated.
- Changing company or range rebuilds the applicable event list. Show only the focus company's events in this panel; the table and charts continue comparing all selected companies.
- Preserve scrollable, expandable long text with paragraphs. There is no generated headline, outbound article link, sentiment label, causal annotation, or automatic filing summary.

### 5.5 Research shortlist and CSV

- The user may add a company from the comparison table, then enter a free-text research reason. There is at most one entry per company and at most two companies. A third addition is blocked with an instruction to remove an existing entry first.
- At addition time, freeze the selected date range, actual observation endpoints, the four table metrics, price/return counts, and data cutoff. Later filtering, mode changes, or sorting must not rewrite that snapshot. Reasons remain editable. To capture a different interval for the same company, remove and re-add it explicitly.
- Keep entries for companies later hidden by the comparison filter. Label each card with its own frozen range so differing research contexts remain visible.
- No candidate is selected automatically. A shortlist may contain an unavailable metric, labeled `N/A`; do not replace it with zero.
- Export is enabled with one or two entries only when every entry has a non-whitespace reason. The text fields remain local to the page; no account, network service, or persistent browser storage is required. State clearly that a reload clears the current session and the CSV is the save mechanism.
- Export filename: `mag7_research_shortlist.csv`. Column order: `symbol`, `range_start`, `range_end`, `first_observation_date`, `last_observation_date`, `period_return_pct`, `daily_volatility_pct`, `average_daily_volume_shares`, `max_drawdown_pct`, `n_prices`, `n_returns`, `data_as_of`, `reason`.
- Percentage columns contain numeric percentage points (a 0.10 return becomes 10), without a percent sign; missing metrics are blank. Preserve available numeric precision rather than copying rounded UI text. Encode UTF-8 and correctly quote commas, quotes, and newlines in reasons. Text-only fields that would be interpreted as spreadsheet formulas must be escaped for spreadsheet-safe export, without changing the in-page reason.

## 6. Visual template and accessibility

This is a single-page research workbench, not a multi-page application. Use the following fixed template so a new implementer can reproduce the intended layout.

1. Full-width header with title, purpose, and data cutoff.
2. Filter panel containing company checkboxes, date controls, and display/sort selectors.
3. Full-width company comparison table.
4. Desktop workspace: price/volume/navigator stack on the left, event reading panel on the right.
5. Full-width research shortlist and CSV export below the workspace.
6. Compact source and metric-definition footer.

Desktop maximum content width is 1,440px with 24px outer padding and 20px section gaps. At widths of 900px and above, the workspace uses a 2:1 column ratio with a 320px minimum event-panel width. Use 340px for the main price chart, 240px for the volume chart, and 90px for the navigator. The event panel may scroll internally after 760px; expanded source text must remain readable.

Below 900px, stack the chart group above the event panel. Below 600px, use 14px outer padding, wrap controls, use 300px/240px/90px chart heights, and let the event panel flow vertically. The comparison table may scroll within its own labeled container; the entire document must not scroll horizontally. Keep its company column sticky within that container.

Use background `#F5F7FA`, white panels, text `#18252D`, secondary text `#536171`, borders `#DCE3EA`, and control accent `#245A81`. Panels have 10px corner radii and 18px padding. Use system sans-serif fonts only; no downloaded fonts or image assets. Body text is 14px, title 30px, section titles 18px, and source/metric notes at least 12px. Show positive returns with a `+` sign and negative returns with a minus sign; meaning must not depend on green/red coloring.

| Company | Stable series color |
|---|---|
| AAPL | `#0072B2` |
| MSFT | `#D55E00` |
| GOOGL | `#009E73` |
| AMZN | `#AA4499` |
| NVDA | `#946200` |
| META | `#56B4E9` |
| TSLA | `#444444` |

Use labeled legends and tooltips in addition to colors, and emphasize the focus-company line with a thicker stroke. The same company always has the same color across both charts, navigator, and table indicators.

Display prices and index values with two decimal places; returns, volatility, and drawdown with two percentage decimal places; relative volume with two decimals and `×`; raw volume as grouped shares in tooltips and compact millions on axes. Average daily volume can be rounded to whole shares for display. Use unrounded values for sorting, calculations, and export. Date labels use `YYYY-MM-DD` or an unambiguous month abbreviation plus year.

Give every input a visible label and keyboard operation. Provide visible focus outlines, accessible tab states, sortable-column state, and live announcements for an invalid range, a full shortlist, and completed exports. Expanded narrative text must wrap, preserve paragraph breaks, and remain selectable. Display footer explanations of adjusted-close changes, unannualized volatility, date-only events, and historical data coverage.

## 7. Architecture and component contracts

### 7.1 Separate responsibilities

Build a self-contained `dashboard.html` using Python and Plotly, with all data, CSS, scripts, and Plotly JavaScript embedded. Opening it through `file://` must require no server or internet connection. The source may be modular; the deliverable may not depend on external source files at runtime.

The architecture must isolate data validation, calculations, event retrieval, state transitions, rendering, and export. A formula change belongs in the calculation layer and its tests; a visual layout change belongs in the renderer/template. Neither change should require rewriting cleaning or event-query logic.

| Component | Input | Output / interface contract | Independent correctness check |
|---|---|---|---|
| Cleaned-data loader | Three Parquet paths | Validated tables plus source hashes, coverage, and source identity | Required schema, table IDs, price keys, symbols, dates, unchanged bytes |
| Python reference analysis | Validated price rows, company selection, inclusive range | Per-company chart series and summary metrics under Section 4 | Synthetic arithmetic, invalid endpoints, same results as existing analysis where contracts overlap |
| Embedded-data preparation | Validated tables and metadata | JSON-safe full-history price/event records and metadata | Exact retained values/text, date strings, null handling, all records retained |
| Browser metric module | Embedded price records, companies, inclusive range | The same analysis result contract as the Python reference | Numerical parity on fixtures and selected real intervals |
| Event-query module | Separate event records, focus company, date/range, event type | Deterministically ordered original event records | Correct IDs/text, same-day multiplicity, weekend records, empty matches |
| State controller | User actions plus current state | One next state for selected companies, range, modes, sort, focus, panel, and shortlist | Defined update boundaries and frozen shortlist snapshots |
| Renderers | Analysis/event results and state | Comparison table, charts, event panel, shortlist | Correct labels and display values; no duplicated financial aggregation |
| Shortlist export | Frozen candidates and reasons | CSV with the exact Section 5.5 columns | Snapshot preservation, numeric units, missing values, text escaping |
| Build entry point | Input paths and modular source assets | Standalone `dashboard.html` | Successful file generation and offline browser checks |

The common analysis result exposes each company's requested range, actual first/last observation dates, `n_prices`, `n_returns`, interval return, daily volatility, average volume, maximum drawdown, and date-keyed series for raw adjusted close, normalized price, daily return, volume, and relative volume. Use fractional units for returns/volatility/drawdown internally; formatting and CSV conversion occur at the presentation/export boundary. Missing values are JSON `null`, never `NaN` or infinity.

Event records keep their original table-local ID, symbol, date, source position, text, form where applicable, and quality flags. They must never be flattened into a price/event many-to-many join.

### 7.2 Existing analysis and new modules

The repository already has `team_cleaning.analysis.adjusted_returns(prices)` and `interval_metrics(prices, start, end)`. The latter returns a series table and company metrics containing actual start/end dates, counts, interval return, sample daily volatility, and average volume. Use it as a reference for the overlapping behavior.

Preserve those existing public functions and all cleaning files. A new dashboard analysis layer may reuse them, add relative volume and drawdown, and apply the approved dashboard presentation boundary: one observed price row gives `N/A` interval return/drawdown, even though the existing interval function can return zero for that one-row endpoint calculation. Test that adapter explicitly rather than silently changing cleaning-analysis behavior.

For future implementation, use new modules such as `dashboard_analysis.py` and `build_dashboard.py`, with separate source assets under `dashboard_assets/` for the template, styling, metrics, events, state, and renderers. Put new tests under `tests/dashboard/`. This is a responsibility layout, not permission to edit existing project files during the current document-only task.

Python must prepare full-history embedded data and reference expectations. Because the user can choose arbitrary intervals in a standalone file, browser JavaScript must calculate range-dependent results through one pure metric module; do not pretend that precomputing a few fixed annual summaries can satisfy this interaction. Relative-volume history can be prepared once because it does not depend on the displayed interval. If it is computed in the browser, use the identical full-history contract and parity tests.

Renderers must use the module's results rather than aggregate raw records independently in table cells, charts, or shortlist actions. Bundle scripts into the HTML without runtime module fetches. Use no CDN, API calls, remote fonts, database, credentials, or service worker.

### 7.3 Environment and future commands

Use Python 3.13. The current project has `requirements.txt`, not a dashboard-ready `uv.lock`. Preserve the existing requirements file. A future implementation must create a separate `requirements-dashboard.txt` containing these dependency pins:

| Package | Version |
|---|---|
| pandas | 3.0.1 |
| numpy | 2.3.5 |
| pyarrow | 25.0.0 |
| python-dateutil | 2.9.0.post0 |
| six | 1.17.0 |
| tzdata | 2026.5 |
| plotly | 6.9.0 |

The listed pandas/Parquet dependencies reproduce the recorded cleaned-data environment; Plotly supplies the embedded chart library. Record resolved transitive dependency versions in the implementation's verification report. No package installation takes place merely to write this specification.

Future macOS/Linux setup and build commands, from the project root:

```sh
python3.13 -m venv .venv-dashboard
.venv-dashboard/bin/python -m pip install -r requirements-dashboard.txt
.venv-dashboard/bin/python build_dashboard.py
.venv-dashboard/bin/python -m unittest discover -s tests/dashboard -p "test_*.py" -v
```

On Windows use `py -3.13 -m venv .venv-dashboard` and `.venv-dashboard\Scripts\python.exe` for the remaining commands. Resolve source, input, and output paths relative to the build script, not the caller's working directory. The build writes `dashboard.html` in the project root and prints its absolute path.

For browser checks, create a separate temporary Python environment, install Playwright there, and run a future `tests/dashboard/check_browser.py` script with `--html <absolute-path-to-dashboard.html>` and `--chrome <installed-Chrome-executable>`. That script must not import the project environment's analysis packages; read reference JSON generated by the Python tests instead. A representative macOS/Linux sequence is:

```sh
python3.13 -m venv /tmp/mag7-dashboard-browser
/tmp/mag7-dashboard-browser/bin/python -m pip install playwright
/tmp/mag7-dashboard-browser/bin/python tests/dashboard/check_browser.py --html /absolute/project/dashboard.html --chrome /absolute/path/to/chrome
```

Paths in the last command are explicit local substitutions, not dependencies on the original student's home directory. Browser-tool installation may need network permission; the built dashboard must run without network. Open the final HTML directly in the system browser using the platform's normal file-opening command or by double-clicking it. If browser tools are unavailable, report precisely which browser checks remain unverified.

## 8. Build order for a future implementation

1. Locate and validate the three complete cleaned inputs; verify snapshot identity and record hashes. Read only; do not invoke the cleaning pipeline.
2. Implement the independent analysis contracts and synthetic tests, including adapter behavior around the existing analysis API. Generate reference JSON for cross-language checks.
3. Prepare the full embedded payload with price and event data kept separate. Check safe text/date/null serialization and record counts.
4. Build the page shell, shared filters/state, and comparison table with the prescribed defaults.
5. Add the two linked charts, range navigator, display modes, and relative-volume behavior. Verify every range-control path reaches the same state and metric module.
6. Add the event reader and same-day/interval navigation. Verify real text and duplicate-day fixtures without altering price rows.
7. Add the manual shortlist, frozen snapshots, reason entry, and CSV export.
8. Complete responsive styling, keyboard alternatives, visible focus, source labels, and empty states. Run automated checks, open the local HTML, inspect screenshots, fix failures, and report actual results.

## 9. Concrete acceptance checks

These are requirements for the future dashboard. They have **not** been executed by creating this specification.

### A. Input and preservation

- Confirm the production input shapes, seven-symbol universe, date ranges, and hashes in Section 3. Compare the three files' hashes again after building; they must be unchanged.
- Confirm a normal build does not require raw inputs, individual member directories, a network data fetch, or the wildfire repository.
- Use temporary fixtures to reject a missing required column, duplicate table ID, conflicting price company/date key, malformed date, and unknown ticker with useful messages. Distinct same-day events with different IDs must remain readable.
- Confirm complete event records are embedded, including the earlier filings outside the price range. Out-of-range events must not be silently assigned to a price date.

### B. Arithmetic and edge cases

| Fixture / action | Required result |
|---|---|
| Three consecutive valid adjusted closes: 100, 120, 90 | Normalized prices 100, 120, 90; interval return −10%; daily returns missing, +20%, −25%; maximum drawdown 25% |
| The same three-price fixture | Sample daily volatility approximately 0.3181980515339464 internally, displayed as 31.82%; no annualization |
| Filter that fixture to its last two observations | Normalized prices 100 and 75; interval return −25%; volatility `N/A` because only one valid return exists |
| First observed adjusted close invalid, followed by valid prices | Entire normalized series and endpoint return `N/A`; do not select a later baseline |
| Prices 100, missing, 110 | No valid daily returns across the missing observation; endpoint return 10%; maximum drawdown `N/A` |
| Single valid price observation | Normalized value 100; interval return, volatility, and drawdown `N/A`; valid average volume can still be shown |
| No prices inside a valid date range | No fabricated points; zero observations and `N/A` metrics; matching weekend events can still be read |
| Previous 20 company volumes all 100, current volume 200 | Relative volume 2× |
| Fewer than 20 previous volumes, an invalid value within the preceding 20, or a zero mean | Relative volume `N/A`; do not extend the window backward to replace invalid rows |
| Current valid zero volume with a positive 20-observation mean | Relative volume 0× and valid contribution to average volume |
| Change the visible interval while retaining the same volume date | Relative volume for that date stays unchanged; its historical baseline does not restart at the visible boundary |

Compare Python and browser outputs before formatting, with absolute tolerance `1e-10` for fractional metrics and index/relative-volume values, and `1e-6` shares for average volume. IDs, dates, counts, null positions, and text must match exactly. Test an early-history interval, a mid-history interval, the default interval, and every arithmetic and edge-case fixture above on both sides where applicable.

### C. Real-data and interaction checks

- On first open, all seven companies are selected, the cutoff is 2026-03-31, and the interval contains the last 60 distinct price dates. Main-chart baseline values are 100 at each company's valid first interval observation.
- Independently read the actual AAPL price row for 2026-03-31 and compare its `adj_close` and `volume` with plotted/hover values. Compute AAPL's default interval return directly from its first and last interval rows and compare with the table. Record the values observed; do not invent constants in this document or the UI.
- Retrieve the actual AAPL news record(s) dated 2026-03-31, and the latest AAPL filing inside the default range. Record their real IDs and compare the expanded text with the Parquet values, including paragraphs and punctuation. If a future approved snapshot lacks a match, verify the stated empty-state behavior and choose another documented real record for the text check.
- Select AAPL and NVDA, narrow the range by dragging, then apply the same dates through inputs. The final state, company metrics, and plotted series must be identical. A range change recomputes base-100 prices, while a price-mode change leaves interval metrics and events unchanged.
- Change volume mode to relative volume; the price chart, comparison metrics, and event selection stay unchanged. Confirm the 1× reference line and N/A lookback period.
- Clicking a company/date point focuses the right event records without changing the research range. Selecting an interval weekend digest retains that original date and does not invent a price observation.
- Sorting by each metric affects only table ordering. Missing values remain last, ties use symbol ascending, and company colors do not change.
- Add a company to the shortlist, enter a reason, and change dates/companies/modes. The saved metrics, range, and reason remain unchanged. Reject a third entry, allow removal/re-addition, and verify exported numeric values against the frozen snapshot.
- Export one or two candidates, including reasons containing commas, quotes, and line breaks. Reload the CSV with a standard CSV reader and check columns, units, missing values, and text escaping. Reloading the dashboard clears the session shortlist as documented.

### D. Offline rendering and accessibility

- Open `dashboard.html` through `file://`, block external HTTP(S) requests, and exercise filters, selection, long-text expansion, and CSV export. No external requests or JavaScript errors should be required for successful use.
- Save and inspect screenshots at 1440×900 and 390×844. Check readable axes and legends, controls that wrap, the specified stack order, and no document-level horizontal overflow. Only the comparison table's own container may scroll sideways on narrow screens.
- Use the keyboard to select companies, change dates/modes/sort, open events, add/remove candidates, edit reasons, and export. Verify visible focus and meaningful labels; no required action may depend exclusively on dragging or hover.
- Expand the longest news and filing excerpts, verify paragraph preservation and usable scrolling, and test that literal markup in source text remains inert text.

### E. Future completion report

Save a dashboard-specific verification record under a new `dashboard_verification/` directory, separate from the existing cleaning reports. Include commands, environment/browser versions, source hashes, Python/browser parity results, one real CSV-equivalent Parquet-to-chart check, event ID/text evidence, screenshots, export checks, and remaining limitations.

Distinguish expected results from observed results. If a check fails, describe the corrective instruction, fix the implementation, and rerun affected checks. Do not describe successful cleaning tests as successful dashboard tests, and do not claim that attractive charts establish data accuracy or causation.

## 10. Design references and completion boundary

- [Schwab — Screener Plus column descriptions](https://help.streetsmart.schwab.com/edge/1.22/Content/Screener%20Plus%20Column%20Descriptions.htm) documents average-volume windows, including 20 days. This dashboard's exact preceding-20-observation, exclude-today ratio is the project's explicit choice; do not substitute another platform's definition of relative volume.
- [Fidelity — Drawdown](https://www.fidelity.com/learning-center/trading-investing/trading/what-is-drawdown-video) explains peak-to-trough decline as distinct from endpoint performance. Here it is measured on observed adjusted-close values within the selected interval, not on intraday prices or a simulated portfolio.
- [SEC — How to Read a 10-K](https://www.sec.gov/answers/reada10k.htm) explains the roles of MD&A and risk disclosures. The reader displays the supplied excerpts, not a complete filing or independently verified current disclosure.

These references explain design choices and are not runtime dependencies. The dataset source link is [TheFinAI/Herculean](https://huggingface.co/datasets/TheFinAI/Herculean); the dashboard build must use the provided cleaned files rather than download from that link.

No financial analysis function implementation belongs in this document. The formulas, component contracts, and behavioral examples specify what separate code must do. The present document-only task creates **only this `BUILD_SPEC.md`**; it does not install dependencies, create source modules, generate HTML, change other files, or claim that the future acceptance checks have passed.
