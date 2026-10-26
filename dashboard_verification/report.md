# Executed dashboard verification

Date: 2026-10-25 (America/Los_Angeles). Built on `Zack-Work`, based on merge commit `0708cf2`. The dashboard implementation was preserved in commit `e630f6823fd12bc11cf0525fab7dc9be59ff5eae`, which is the audited app version. Later documentation and screenshot-removal commits do not change that application. See `build.json` for the final HTML identity, environment, input shapes, source hashes and byte size.

## Result

- Seven dashboard Python tests passed.
- Eleven existing cleaning risk tests passed. This is a regression check, not a substitute for dashboard verification; cleaning itself was not rerun.
- Sixteen browser check groups passed in Chrome **155.0.8059.85**. The final browser run returned `PASS`, with zero JavaScript errors and zero external HTTP(S) requests. See `browser.json` for every group.
- Direct `file://` opening worked with external HTTP(S) requests blocked. All prices, news, filing excerpts, styles and Plotly code are embedded. No runtime source fetch or raw-data dependency exists.
- Before/after SHA256 values for all three Parquet inputs matched. Full payload counts are 2,324 prices, 3,402 news digests, and 63 filings; earlier filings remain embedded.

## Arithmetic evidence

The independent Python reference and browser metric module were compared before formatting on 20 synthetic cases and three real-data intervals (early history, mid-history and default range). Every metric, date-keyed series, count and null position was compared. Tolerance is 1e-10 for fractional metrics/index/relative-volume values and 1e-6 shares for volume values. Text and IDs compare exactly. `reference.json` stores the expected results.

Known-answer tests explicitly verify 100 → 120 → 90 gives −10% endpoint return, +20% and −25% consecutive returns, sample daily volatility 0.3181980515339464, and maximum drawdown 25%. Additional cases cover invalid baselines, missing interior prices, single/no observations, insufficient volume lookback, invalid/zero preceding volumes and current zero volume. A one-row dashboard interval reports unavailable return/drawdown without changing the original cleaning-analysis API.

Real AAPL evidence from the formal Parquet table (`real_data.json`):

| Check | Observed value |
|---|---:|
| Default inclusive range | 2026-01-05–2026-03-31 |
| Price observations per company | 60 |
| First AAPL adjusted close | 267.0101623535156 |
| Last AAPL adjusted close | 253.7899932861328 |
| Last AAPL volume | 49,598,100 shares |
| Direct endpoint ratio minus one | −0.04951185734226704 |
| UI interval return after formatting | −4.95% |

The final plotted adjusted close, shares and date matched these source values exactly. AAPL's actual 2026-03-31 news ID and latest in-range filing ID/full excerpts were compared with the rendered card text, including punctuation and paragraph breaks. Exact records are retained in `real_data.json` rather than paraphrased.

## Interactions and visual checks

- Actual mouse drags on both charts and a navigator handle updated the shared interval. A navigator range event and equivalent input dates produced identical metrics; rebasings used the new first interval row.
- Mode changes preserved comparison metrics and evidence state; relative volume had its 1× reference. A Plotly point-selection event focused its company and original date without altering the research range. Keyboard company/date controls provide the alternative to pointing.
- A weekend-only interval had zero price observations and unavailable price metrics while original-calendar-date news remained readable. The tested weekend digest ID is in `browser.json`.
- Each metric sorted in both directions. Invalid/reversed/out-of-coverage ranges retained the previous state.
- Shortlist tests covered frozen values after date/company changes, retaining a hidden company's entry, rejecting a third entry, removing/re-adding, and a real downloaded CSV. A standard CSV reader recovered commas, quotes and line breaks; formula-like reasons were escaped only in export. Numeric percentage-point units and column order matched the contract. `tested_shortlist.csv` is synthetic test output, not the student's research decision.
- Literal script/image markup in an in-memory event fixture remained inert, selectable text. Distinct same-day records remained readable. The synthetic fixture was removed by reloading.
- Keyboard checks covered controls, tab navigation, shortlist add/reason/remove and export availability. Reload cleared the shortlist.
- Desktop (1440×900 viewport) and mobile (390×844 viewport) full-page screenshots were captured and visually inspected during verification; they were later removed from the project folder at the student's request. No document-level horizontal overflow was measured. The comparison table retains its own horizontal scroll container. The longest available news/filing excerpts were checked at phone width for exact text and containment. Rerunning the browser-check script will generate fresh screenshots.

## Commands actually executed

```text
uv venv --python .venv/Scripts/python.exe .venv-dashboard
uv pip install --python .venv-dashboard/Scripts/python.exe pandas==3.0.1 numpy==2.3.5 pyarrow==25.0.0 python-dateutil==2.9.0.post0 six==1.17.0 tzdata==2026.5 plotly==6.9.0
.venv-dashboard/Scripts/python.exe build_dashboard.py
.venv-dashboard/Scripts/python.exe -m unittest discover -s tests/dashboard -p test_*.py -v
.venv-dashboard/Scripts/python.exe -m unittest discover -s tests -p test_*.py -v
uv venv --python .venv/Scripts/python.exe .review/dashboard-browser
uv pip install --python .review/dashboard-browser/Scripts/python.exe playwright
.review/dashboard-browser/Scripts/python.exe -u tests/dashboard/check_browser.py --html C:/Users/yexun/OneDrive/Desktop/Python-Group-Project/dashboard.html --chrome C:/Program Files/Google/Chrome/Application/chrome.exe
```

Browser tooling resolved Playwright 1.64.1, greenlet 3.5.6, pyee 14.0.0 and typing-extensions 4.16.0. The application environment and all resolved application package versions are recorded in `build.json`; `requirements-dashboard.txt` pins them.

## Corrections and limits

An initial browser run exposed a Plotly range-slider rendering error with a hidden x-axis; the navigator now retains an axis with hidden tick labels. Screenshot inspection then exposed slider clipping; reserved bottom space fixed it, and the final browser run checked the slider's bounding box plus actual handle dragging. A test harness call was also corrected to use Playwright's keyword argument. The final checks above passed after these corrections.

The first existing-test attempt was blocked from writing a system temporary directory. The unchanged suite passed when run with the required permission. No data or formulas were changed to make that test pass.

Verification covers local Chrome, two viewport sizes and the specified fixtures; it does not certify every browser, assistive technology or device. Screen-reader testing was not performed. The point-selection route was tested through the Plotly event handler, while chart interval selection and navigator handles were exercised with real mouse movement. Dataset factual accuracy, upstream revision, price-adjustment methodology and event availability times remain unverified, as documented in the specification. These implementation checks do not replace the student's personal audit or contribution statement.

The app's sidebar browser blocked a `file://` preview under its URL security policy. No workaround was used. The completed local file can be opened manually; the separate, explicitly authorized Chrome verification above successfully exercised the actual offline file.
