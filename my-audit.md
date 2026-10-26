# Individual app audit - Zack Ye

- Course: DSO 576, Module 9
- Audit date: October 25, 2026
- Individual branch: `Zack-Work`
- App version checked: **`e630f6823fd12bc11cf0525fab7dc9be59ff5eae`** (`e630f68`)
- App: the standalone `dashboard.html` built from the team's `BUILD_SPEC.md` and formal cleaned Parquet tables.
- Feature audited: shared company/date filtering, interval-dependent price rebasing and comparison metrics, and related news filtering, including invalid-range and single-observation boundaries.
- Number audited: AAPL adjusted-close interval return for **2026-03-02 through 2026-03-31**, with NVDA as an additional comparison.
- Change request: **AUDIT-ZY-01**, open, for invisible single-observation chart values.

## 1. Intended user, task and requirement

The intended user is a junior technology-sector equity research analyst comparing seven companies and choosing one or two for deeper research. The analyst needs the table, price/volume charts and company evidence to use a consistent selected interval. Otherwise, comparisons could mix different periods or include evidence outside the period being investigated.

I used `BUILD_SPEC.md` Sections 4.1-4.3, 5.2-5.4 and 9 as the requirement. Company filtering should affect the comparison table and both main charts together. Date inputs are inclusive. Applying a valid range should recompute base-100 prices from each company's first actual row in that range, update interval metrics and rebuild the applicable interval event list. A reversed range should show a message and retain the previous valid research state. Date-only news stays on its original calendar date.

For a single valid price observation, Section 9 expects a normalized value of 100, unavailable interval return/volatility/drawdown, and available average volume where the source volume is valid. A chart that appears empty despite a recorded observation can mislead the user about data availability.

## 2. Evidence and reproducible feature checks

I manually operated the dashboard and recorded the observations below. This submission does not require screenshot attachments or local-file links: the inputs, expected behavior, actual values and reproducible calculation are included in this document. Screenshots were used during the audit and later removed from the project folder at my request; the written observations below preserve the relevant findings. E01-E07 identify observation records, not attached images or capture timestamps.

| Record | Check | Recorded observation |
|---|---|---|
| E01 | Default view | All seven companies; requested interval 2026-01-05 to 2026-03-31; AAPL return -4.95%, 60 observations |
| E02 | Two-company filter | Only AAPL and NVDA checked; only those companies remain in the table and chart legends/lines |
| E03 | Valid March interval | Requested/applied interval 2026-03-02 to 2026-03-31; 22 observations and 21 valid returns per company; AAPL -4.13%, NVDA -4.42%; indexed lines start at 100 |
| E04 | Rejected reversed range | Entered start 2026-03-02, end 2026-03-01; error shown; applied range, values and plots retain the valid March interval |
| E05 | News upper boundary | AAPL news cards include 2026-03-31 (ID 486), followed by earlier March dates |
| E06 | News lower boundary | Bottom of the list contains 2026-03-02, ID 457, source row 456 |
| E07 | Single-observation display | Applied interval label 2026-03-01 to 2026-03-02; one observation per company and valid average volumes, but no visible data points in the two main charts |

### Check F1: companies and valid date changes

Reproduction:

1. Open the audited `dashboard.html`. The initial seven-company interval is 2026-01-05 to 2026-03-31 (E01).
2. Uncheck MSFT, GOOGL, AMZN, META and TSLA, leaving AAPL and NVDA. Keep `Indexed to 100` and `Shares` (E02).
3. Enter start `2026-03-02`, end `2026-03-31`, and click `Apply dates` (E03).

Expected: the table and both main charts compare the same two companies and interval; indexed prices restart at 100 at the first interval observation; observation counts and metrics recalculate.

Actual: E02 shows two companies in the table and charts. E03 shows the new interval, 22 observations/21 valid returns for each company, AAPL -4.13% and NVDA -4.42%, and indexed chart lines starting at the 100 gridline. AAPL's earlier default result was -4.95% with 60 observations. The range and source endpoint check in Section 3 support the change in return.

Conclusion: **pass for these company/date examples**. The visual observation supports rebasing; I did not record a tooltip displaying an unrounded baseline of exactly 100, and do not treat visual alignment with the gridline as numerical proof of every chart point.

### Check F2: reversed dates preserve the prior valid research state

Reproduction:

1. Apply the valid March interval in F1.
2. Change only the end input to `2026-03-01`, leaving start `2026-03-02`, and click `Apply dates`.

Expected: reject the reversed range with an inline explanation and keep the prior valid results.

Actual: E04 shows the explanation, "Choose a start on or before the end, within 2024-12-02 to 2026-03-31." The inputs show the rejected dates, while the applied table range remains 2026-03-02 to 2026-03-31. The table retains AAPL -4.13%, NVDA -4.42% and 22 observations each, and the charts remain consistent with E03.

Conclusion: **pass for the tested reversed range**. The rejected input values remaining visible are distinct from the retained applied state; retaining those results is the specified behavior.

### Check F3: news interval boundaries

Reproduction: restore/apply the valid March interval, focus AAPL, select `Selected interval` and `News`, then scroll to the top and bottom of the list.

Expected: original-date AAPL digests within the inclusive interval, newest first, without assigning weekend news to a trading date.

Actual: E05 shows the upper boundary, 2026-03-31, ID 486, with subsequent March records; E06 shows the lower boundary, 2026-03-02, ID 457. The independent source query produces **30 expected AAPL digest records**, with those same endpoint dates and IDs. Visible weekend entries such as March 28 and 29 retain their original dates.

Conclusion: **the sampled ordering and two boundaries agree with the requirement and source data**. I did not record the panel's displayed total count or enumerate every UI record. Therefore these observations do not establish exact equality of all 30 rendered records or all full texts.

### Check F4: one observed price row is not visibly plotted

Reproduction for the display issue: select AAPL and NVDA, apply start `2026-03-01`, end `2026-03-02`, with `Indexed to 100` and `Shares`.

Expected: one visible indexed point at 100 per company and visible source-volume observations on March 2; unavailable interval return/volatility/drawdown is appropriate with only one price row.

Actual: E07 shows applied interval 2026-03-01 to 2026-03-02, one observation per company, zero valid returns, and the appropriate unavailable return/volatility/drawdown. Average volumes are 41,827,900 for AAPL and 209,095,300 for NVDA. The main charts appear empty of data marks. The independent source check confirms one March 2 price row and those volumes for each company. The renderer at the audited version uses `mode:'lines'` for all traces (`dashboard_assets/render.js`, line 85), without single-point markers.

E07 was recorded after a subsequent reversed-date attempt, so the input boxes showed 2026-03-02 to 2026-03-01. The applied range label and retained one-row table identify the previously accepted interval. This observation is not used to prove the separate March 2-31 preservation check in F2.

Conclusion: **a display defect is supported by the recorded UI behavior, source-row check and renderer code**. It affects visibility of available data, not the audited March 2-31 return formula. The likely cause is line-only rendering of isolated observations. Exact hover/hit-testing and a corrected rendering have not been verified. Requested change and future acceptance check are in **AUDIT-ZY-01**; no fix was applied during this audit.

## 3. Number definition and independent check

### Meaning, units, denominator and assumptions

The number is the **adjusted-close interval return**, not an annualized rate, sum of daily returns, investment recommendation or independently verified total shareholder return.

```text
fractional return = last actual interval adj_close / first actual interval adj_close - 1
displayed percentage = fractional return * 100
```

The denominator is the first actual price observation inside the inclusive interval, not the requested calendar start if that date has no price row. The company needs at least two observed rows with finite, positive endpoint prices. Invalid endpoints should produce an unavailable result, rather than selecting a later nonmissing baseline. For positive valid endpoints the return is greater than -100%, and it has no finite upper bound. A reported negative return is reasonable when the last adjusted close is below the first.

Interior price changes do not enter this endpoint ratio. That makes it different from maximum drawdown, which measures intervening declines. The selected company and period must be identical in the source check and UI. Publication timing and price-adjustment methodology are not established by this arithmetic.

### Small known-answer case

For prices 100, 120 and 90, the endpoint return is `90 / 100 - 1 = -0.10`, or **-10%**. Adding the two daily percentage changes would instead give -5%, which is not the interval endpoint return. The independent check includes the endpoint calculation as a known-answer assertion.

### Source values and observed UI

I used the complete formal `artifacts/prices_clean.parquet`, filtered to each company and 2026-03-02 to 2026-03-31, sorted by date. Codex helped write and run a separate pandas/Decimal check; it imports no dashboard metric functions and does not call browser calculations. This is a different calculation path, not an independent human or different-agent review. It recalculates the formula from source rows and compares to my recorded UI values.

| Company | First date / row ID | First adjusted close | Last date / row ID | Last adjusted close | Source rows | Independently calculated return | Observed UI (E03) |
|---|---|---:|---|---:|---:|---:|---:|
| AAPL | 2026-03-02 / 311 | 264.7200012207031 | 2026-03-31 / 332 | 253.7899932861328 | 22 | -4.128893881901165% | -4.13% |
| NVDA | 2026-03-02 / 2303 | 182.4701232910156 | 2026-03-31 / 2324 | 174.39999389648438 | 22 | -4.422712742765256% | -4.42% |

For the primary AAPL check:

```text
253.7899932861328 / 264.7200012207031 - 1
= -0.04128893881901165151...
= -4.128893881901165151...%
=> -4.13% at two percentage decimal places
```

Expected and actual display values agree. The difference between the full-precision calculation and the two-decimal UI is rounding, not a discovered calculation error. Decimal arithmetic uses the stored floating-point values converted to decimal strings; it does not recover more accurate upstream prices.

### Reproduce the numeric evidence

The complete calculation below is included so no separate script or JSON attachment is required. Save it as `audit_check.py` in a checkout of the audited project and run it from the repository root with Python 3.13 and the project's pandas/Parquet dependencies installed. The audited project's formal Parquet data are still necessary to reproduce source-based checks; they are not embedded in these two Markdown submissions.

```powershell
.venv-dashboard\Scripts\python.exe audit_check.py
```

On macOS/Linux use `.venv-dashboard/bin/python`. Dependencies are pinned in `requirements-dashboard.txt`. This code prints results without writing to any project file or importing dashboard functions:

```python
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
import pandas as pd

paths = [Path('artifacts/prices_clean.parquet'),
         Path('artifacts/news_clean.parquet')]
before = {str(p): sha256(p.read_bytes()).hexdigest() for p in paths}
prices, news = (pd.read_parquet(p) for p in paths)

with localcontext() as context:
    context.prec = 40
    assert Decimal('90') / Decimal('100') - 1 == Decimal('-0.10')
    for symbol, observed_pct in [('AAPL', '-4.13'), ('NVDA', '-4.42')]:
        rows = prices.loc[
            prices.symbol.eq(symbol)
            & prices.date.between('2026-03-02', '2026-03-31')
        ].sort_values('date')
        first, last = rows.iloc[0], rows.iloc[-1]
        first_price = Decimal(str(first.adj_close))
        last_price = Decimal(str(last.adj_close))
        assert len(rows) == 22 and first_price > 0 and last_price > 0
        result_pct = (last_price / first_price - 1) * 100
        assert result_pct.quantize(Decimal('0.01')) == Decimal(observed_pct)
        print(symbol, first.date.date(), first_price,
              last.date.date(), last_price, 'rows', len(rows),
              'return_pct', result_pct, 'observed_pct', observed_pct)

events = news.loc[
    news.symbol.eq('AAPL')
    & news.date.between('2026-03-02', '2026-03-31')
].sort_values(['date', 'id', '_source_row'])
assert len(events) == 30
assert str(events.iloc[0].id) == '457'
assert str(events.iloc[-1].id) == '486'
print('Expected source news count:', len(events),
      'first:', events.iloc[0].date.date(), events.iloc[0].id,
      'last:', events.iloc[-1].date.date(), events.iloc[-1].id)

single = prices.loc[
    prices.symbol.isin(['AAPL', 'NVDA'])
    & prices.date.between('2026-03-01', '2026-03-02')
].sort_values(['symbol', 'date'])
assert single.groupby('symbol').size().to_dict() == {'AAPL': 1, 'NVDA': 1}
print('Single-observation source rows:')
print(single[['symbol', 'date', 'id', 'adj_close', 'volume']].to_string(index=False))
assert before == {str(p): sha256(p.read_bytes()).hexdigest() for p in paths}
print('PASS: source bytes unchanged; UI returns agree at display precision.')
```

Observed output includes AAPL return `-4.128893881901165151...%`, NVDA return `-4.422712742765255863...%`, expected source news count 30 with endpoint IDs 457 and 486, and one March 2 source row per company for the single-observation interval. These are source checks, not automatic verification of the UI's complete news list or chart rendering.

Source SHA256 identities:

```text
prices_clean.parquet  84a3c2c4eaab0977f98666cc431faafdf1eb39cbc20deff36579ab430060ae1e
news_clean.parquet    94fc868bb681c810999d861e40e3cfb402473bc77141554003c6f362f027ba0d
```

## 4. Conclusion, uncertainty and requested change

The tested two-company filter, March date change and reversed-range protection behaved as specified. AAPL's March interval return agrees with a separate source-row endpoint calculation, with NVDA providing an additional matching comparison. The sampled news boundaries agree with the requested interval. A separate one-observation display issue is recorded as **AUDIT-ZY-01**, open.

These checks do not establish that every feature, arbitrary interval, company, tooltip or event record is correct. In particular, this personal audit does not independently certify volatility, maximum drawdown, relative volume, filings, shortlist/export, all chart values, full news-list membership/text, keyboard/screen-reader behavior or every browser. Existing automated implementation checks are supplementary background, not my personal execution evidence. Dataset factual accuracy, upstream revision, adjustment methodology and information-availability timing also remain unverified.

The audited application was not modified to demonstrate or resolve a finding. After a future fix, retain this original version/evidence and record a new implementation commit and verification result in the change request.

## 5. Personal contribution and AI use

I manually selected companies, changed dates, applied valid and reversed ranges, inspected the resulting table/charts, scrolled the news list and supplied the screenshots used here. The explicit before/after screenshots were added after an earlier screenshot did not establish which valid range preceded the rejected input.

Codex implemented the dashboard before this audit, including fixing construction-time rendering issues, and created the app's automated verification records. During this audit it suggested check cases, read my screenshots, helped write/run the separate Decimal calculation, checked the renderer code, organized evidence files and drafted this report and the change request. I did not personally author the check script or perform a separate different-agent review. I do not claim the automated construction checks as my own manual audit.

This report distinguishes observed manual evidence, AI-assisted source checks and remaining uncertainty. I am responsible for reviewing the calculations, limitations and conclusions before submitting my individual report, including explaining why the endpoint ratio and its denominator match the intended metric. This work does not claim a teammate's audit or confirmed exclusive scope across other branches.
