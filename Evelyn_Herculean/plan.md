# Herculean cleaning plan

## Goal and scope

Plan a staged review of the three Herculean tables before revising the cleaning implementation. Establish a baseline, specify column-level rules, handle exceptions explicitly, and validate the results.

This is a planning document, not a new cleaning run or a completed assignment. Keep the existing notebook, scripts, raw data, cleaned outputs, project-level plan, and README unchanged at this stage. 

**Fill in before making analytical choices:**

- Project vision and business question: A junior equity research analyst on a technology-sector coverage team must decide which of the seven mega-cap technology stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA) to prioritize for this week's deep-dive research, based on relative price performance, volatility, trading-volume activity, and recent news or filing events. The question is : How company news relates to subsequent price changes and trading-volume？

- Main metric/comparison, units, and eligible observations: 
    - Adjusted close for each stock(7) from 2024-12-1 to 2026-3-31
    - Return_Rate_1d  = adjusted_close_t / adjusted_close_(t-1) - 1
    - Return_Rate_3d  = adjusted_close_t+2 / adjusted_close_(t-1) - 1
    - Return_Rate_5d  = adjusted_close_t+4 / adjusted_close_(t-1) - 1
    - abs_return_1d = abs(Return_Rate_1d)
    - Intraday range = (High-low)/open
    - Trade_volumn for each stock(7) from 2024-12-1 to 2026-3-31
        - volume_ratio = volume_(t+1) / average_volume_previous_20_days
        - volume_ratio = 1: Close to normal trading volume
        - volume_ratio > 1: Trading volume is higher than usual
        - volume_ratio < 1: Trading volume is lower than usual

- date scope: 2024-12-01  - 2026-03-01

## Baseline and evidence status

Source: `TheFinAI/Herculean`, revision `52d3ecb97e490a2392717935402cde283e8fa36e`, recorded in `data/manifest.json`. 
| Table | Manifest rows | Source columns | Candidate observation/key to verify |
| --- | ---: | ---: | --- |
| `prices` | 2,656 | 9 | One company/date price record; test `symbol` + `date` |
| `news` | 3,888 | 4 | One company/date news summary; confirm meaning and test `symbol` + `date` |
| `filings` | 73 | 6 | One filing with excerpts; test `symbol` + `date` + `document_type` |

IDs belong to their own tables. Use table name plus source ID for traceability; do not join different tables on matching ID numbers. If IDs are missing or repeated, retain an additional original row position for the audit.

The existing [project-level plan](../plan.md) and `cleaned/quality_report.json` report that an earlier implementation retained all 6,617 records, changed 146 filing excerpt cells, and left price/news values unchanged. They also report four review flags and total volume of 159,456,800,900. These are **prior reported results**, not fresh verification or predetermined outcomes of this revision. Recheck the originals before adopting their conclusions; do not overwrite those artifacts during planning.

## Overall rules

1. Preserve original files and original values. Make transformations only in separate working tables, and keep source hashes for comparison.
2. Retain rows by default. Before any removal, document the record keys, evidence, rule, reason, alternatives considered, and effect on coverage and metrics. Record analytical scope exclusions separately from invalid-record removals.
3. Flag suspicious values before deciding whether to correct, retain, exclude, or leave them unresolved. A flag is not proof of an error.
4. Preserve units, categories, numeric precision, and identifier meaning. Before any unit or category change, document the original meaning, target meaning, exact conversion or mapping, justification, affected records, and validation. No such change is currently proposed.
5. Do not invent values to reduce missingness. Recover a value only when reliable existing information determines it unambiguously; retain conflicting evidence.
6. Count exact duplicate rows, repeated IDs, and repeated business keys separately. Repeated text or the same company/date alone does not justify deletion.
7. Preserve narrative meaning, punctuation, capitalization, numbers, paragraphs, and meaningful spacing. Do not rewrite summaries or infer omitted claims.
8. After every major transformation, report what changed using the checkpoint template below, including zero changes. Investigate unexplained differences before continuing.

## Staged process

### 1. Inspect the originals and write the rules

Load fresh copies of the original Parquet files. Inventory every column's type, null/blank count, representative values, distinct labels, and relevant ranges. Record row counts, source hashes, date coverage and company counts, candidate-key uniqueness, exact duplicates, and meaningful totals. Count suspicious records without altering them.

**Expected checkpoint:** No source or working values changed. Save the baseline and proposed rules before applying them. Distinguish observations from assumptions and unanswered questions.

### 2. Review types, dates, identifiers, and labels

Use the column rules below. Convert only where a working operation needs a different representation. Compare original and converted values, count failures separately from pre-existing missing values, and retain failure examples. Do not silently replace failures with nulls or discard affected rows.

**Expected checkpoint:** Explain each type change; check calendar-date preservation, ID equality, key collisions, label counts, and newly missing values. Report any unit/category change explicitly, even if it is only a proposed label normalization.

### 3. Review text formatting, missingness, and duplicates

Examine before/after text examples before choosing a formatting rule. Distinguish missing cells, whitespace-only text, meaningful statements that no news occurred, and incomplete prose. Investigate duplicate groups and conflicting values before choosing any action.

**Expected checkpoint:** Count affected cells and records per rule; recount missingness and duplicates; explain every fill, correction, or removal. Preserve a record-level value-change log. No blanket missing-row deletion or narrative-based deduplication is proposed.

### 4. Review flags and decide how to handle exceptions

Create the review register described below before corrections or exclusions. Investigate suspicious numeric values, text, dates, and categories. Keep evidence and resolution history together. Label unsupported decisions as unresolved and explain the effect on analysis.

**Expected checkpoint:** Report flags created, retained, resolved, and still unresolved, plus distinct affected records. Multiple flags on one record must not be counted as multiple records removed.

### 5. Assess joins and calculations

Keep source tables separate unless the business question needs a combined table. Before merging, define its row meaning, keys, join type, expected relationship, date-alignment rule, and treatment of unmatched records. Test key uniqueness first. Record unmatched keys on both sides, counts before/after, and any row multiplication. Missing publication times may prevent a defensible predictive alignment; do not assume same-day text was available before a price observation.

Define each metric's units, contributing records, exclusions, missing-value behavior, missing-group-key handling, and denominator. Distinguish no observations from zero. If calculating price changes, select the price series deliberately, order within company, retain the previous observation date, and explain gaps and the first observation.

**Expected checkpoint:** Reconcile merge counts and important totals; report the contributing count for every metric/group; independently verify a small calculation. If no merge is needed, document why checklist item 9 is Not applicable.

### 6. Validate and prepare evidence

Reconcile all transformations, perform five record checks, and rerun from the unchanged originals in a fresh session. Compare the regenerated outputs with the submitted files. Confirm that a second cleaning pass makes no further changes and that source hashes remain unchanged. Do not claim these checks passed until they have actually been performed.

## Column-by-column rules to evaluate

These proposed rules cover every source column. Record measured issue counts and final decisions during inspection; a proposed check does not establish that a defect exists.

### Prices

| Column | Proposed handling | Verification / review trigger |
| --- | --- | --- |
| `id` | Preserve source identifier and representation; never regenerate it. | Missing/repeated IDs; source-to-output equality. |
| `symbol` | Preserve company labels; do not silently uppercase or map categories. | Whitespace, unexpected labels, collisions from any proposed normalization; company counts. |
| `date` | Preserve calendar dates; use a separate datetime representation only if needed. Do not add absent dates automatically. | Failed conversions, company/date duplicates, coverage and gaps; round-trip to original dates. |
| `open` | Preserve source unit and precision; flag nonfinite/nonpositive values or values outside the daily range. | `low <= open <= high`; count exceptions before any correction. |
| `high` | Preserve source unit and precision; flag invalid values or inconsistent ranges. | At least `low`, `open`, and `close`; finite and positive. |
| `low` | Preserve source unit and precision; flag invalid values or inconsistent ranges. | At most `high`, `open`, and `close`; finite and positive. |
| `close` | Preserve source unit and precision; investigate out-of-range values. | `low <= close <= high`; finite and positive. |
| `adj_close` | Preserve separately from unadjusted prices. Never replace with `close` merely because they differ. | Finite/positive values and unusually large changes; do not require it to lie inside the unadjusted daily range. |
| `volume` | Preserve source unit and integer meaning; do not fill missing values with zero. | Missing, negative, fractional, nonfinite, or unusual values; review zeros in context; reconcile totals overall and by company. |

Confirm the source meaning of price and volume units before interpreting or converting them. Do not infer currency or an adjustment convention solely from column names. Display rounding must not overwrite stored values.

### News

| Column | Proposed handling | Verification / review trigger |
| --- | --- | --- |
| `id` | Preserve table-local identifier and representation. | Nonmissing, unique, unchanged; never a cross-table join key. |
| `symbol` | Preserve labels; document any future mapping before applying it. | Label set, company counts, whitespace and unexpected categories. |
| `date` | Preserve calendar date without inventing publication time or moving weekend records. | Invalid dates, key conflicts, coverage; unmatched price dates reported separately from source missingness. |
| `highlights` | Preserve wording and formatting; investigate blank, short, incomplete, or inconsistent summaries. Trim outer whitespace only if observed and justified. | Before/after examples, changed-cell count, no lost negation/numbers/paragraphs; flags for apparent truncation or timing uncertainty. |

### Filings

| Column | Proposed handling | Verification / review trigger |
| --- | --- | --- |
| `id` | Preserve table-local identifier and representation. | Nonmissing, unique, unchanged. |
| `symbol` | Preserve labels and legitimate unequal filing counts. | Unexpected categories and company coverage; no fabricated records to balance groups. |
| `date` | Preserve dates, including records before price coverage. Verify what the source date means. | Invalid dates or conflicting keys; distinguish filing/publication dates from fiscal-period dates. |
| `document_type` | Preserve distinct categories such as `10-K` and `10-Q`; flag unexpected values. | Before/after category counts; no silent merging or recoding. |
| `mda_content` | Evaluate one HTML-entity decoding pass and outer-whitespace trimming. Preserve original text for comparison and retain internal formatting. | Count each operation's affected cells; inspect decoded examples; no new blank text or changed meaning; second pass unchanged. |
| `risk_content` | Evaluate the same formatting operations; retain repeated language and meaningful annual-report cross-references. | Before/after evidence, missingness, text retention, and second-pass stability; repeated text does not prove duplicate filings. |

## Exact recovery and exception handling

- **Missing values:** Separate source nulls, verified empty strings, conversion failures, and join-introduced gaps. Keep ambiguous placeholders visible until their meaning is established. Missing narrative content cannot be recovered by inventing prose.
- **Numeric corrections:** Do not clip outliers, replace prices, rescale volume, or round stored values without supporting evidence and a documented rule. An unusual return may be real.
- **Dates and coverage:** News on a non-trading date and earlier filings are not automatically erroneous. An absent weekday price needs a verified market-calendar interpretation before calling it a missing trading session.
- **Conflicting duplicates:** Keep the original records and flag the group until evidence supports a deterministic resolution. Before removing anything, write why it is redundant or invalid and reconcile the resulting counts and totals.
- **Text:** Decode formatting only where demonstrated. Do not globally collapse whitespace or strip content based on appearance alone. Recheck whether entity decoding followed by trimming loses meaningful boundary characters.
- **Review thresholds:** The earlier project plan used text length below 100 characters and absolute consecutive-observation adjusted-close returns above 20% as screening rules. These are prior choices to evaluate and justify, not universal validity limits or automatic deletion rules.

Suggested cases to reinspect from the prior plan: news IDs 543 and 1005 for incomplete prose, news ID 2 for timing uncertainty, price ID 2412 for a large return, and filing ID 66 for a short risk cross-reference. Verify those cases against the originals before repeating any finding.

## Required audit records and checkpoint report

Keep these records in this plan or dedicated audit outputs. Do not add cleaning rules or process documentation to the README.

**Decision log:** Rule ID, table/column, observed problem, proposed action, reason, alternatives, expected effect, verification method, actual result, and exceptions. Include decisions to retain values unchanged.

**Review register:** Table, stable source key, column, original value, flag rule, evidence, review status, decision, reason, and any replacement value. Record the flag before the action.

**Value-change log:** Stage/rule ID, table, source key, column, original value, new value, and reason. Preserve a separate exclusion/removal record if applicable, with impact on metrics. Every changed value or removed row must be traceable.

After **each major transformation**, fill in:

| Checkpoint field | Result to record |
| --- | --- |
| Stage and rule IDs | [ ] |
| Rows before / after / added / removed | [Counts and reasons; zero is a valid result] |
| Cells changed / distinct records affected | [Counts by column and rule; avoid double counting] |
| Missing values before / after | [Per affected column; distinguish failures from source nulls] |
| Exact duplicates / repeated IDs / business-key conflicts | [Before/after counts with counting definition] |
| Types, units, and categories | [Unchanged, or documented conversion/mapping and rationale] |
| Coverage and important totals | [Before/after by relevant group; explain every difference] |
| Review flags | [Created, resolved, unresolved; distinct affected records] |
| Example changes and validation | [Original → expected → actual; pass/fail and evidence location] |
| Decision before continuing | [Accept stage / investigate / revise rule; reason] |

No transformation is considered verified merely because the code executes.

## Validation and assignment evidence

- **Record preservation:** Default expectation is 2,656 prices, 3,888 news records, and 73 filings, with source columns and IDs retained. Any deviation needs record-level explanations and a count reconciliation.
- **Value preservation:** IDs, dates, price/volume values, and categories remain unchanged unless a specific justified rule says otherwise. Reconcile important totals to a freshly computed baseline; investigate disagreement with the prior volume total rather than forcing a match.
- **Completeness of checks:** Run schema, missingness, duplicate, numeric, date, and coverage checks on all relevant rows, not just examples. Explain all exceptions.
- **Five record checks:** Choose actual difficult cases plus a useful unchanged case. Write the expected result and reason before examining the cleaned result. Record source key, original, expected, actual, and match/follow-up.
- **Calculations and joins:** Validate denominators, group membership, missing-group handling, unmatched keys, and cardinality where applicable.
- **Reproducibility:** Restart and run all from raw data, record dependencies and run steps, verify outputs and raw hashes, and check a second pass produces no further changes.
- **Limitations:** Explain remaining uncertainty about dates, publication times, incomplete text, coverage, and factual accuracy where supported. Formatting cleanup does not establish factual accuracy.

Complete all 14 assignment checklist items with **Done / Not applicable / Unresolved**, evidence references, and an explanation for every Not applicable or Unresolved response:

| Item | Evidence to prepare |
| --- | --- |
| 1. Vision and question | Completed goal and metric |
| 2. One row | Table meanings and tested keys |
| 3. Preserve source | Revision, raw files, load steps, hash comparison |
| 4. Types | Type inventory, conversion rules and failure counts |
| 5. Text | Documented rules and before/after examples |
| 6. Duplicates | Separate counts, decisions, exceptions |
| 7. Missing data | Per-column before/after counts and handling |
| 8. Suspicious values | Flags recorded before decisions, with evidence |
| 9. Merges | Keys, relationship, unmatched records and counts, or justified Not applicable |
| 10. Reconciliation | Row-count and important-total audit after each stage |
| 11. Calculations | Metric definitions, denominators, missingness and group handling |
| 12. Records | Five original/expected/actual comparisons |
| 13. Reproducibility | Fresh-run and output-comparison evidence |
| 14. Limitations | Unresolved issues, effects, and information needed |