# Offline research dashboard

Open `dashboard.html` directly in Chrome or Edge. It is a standalone file: no server, account, package installation, or internet connection is needed to use it. The file embeds Plotly and all three complete formal tables (about 30.6 MB of HTML including narrative text). Keep the entire file when sharing it.

The default view compares all seven companies over the final 60 observed price dates: **2026-01-05–2026-03-31**. The data are historical, with a **2026-03-31** price cutoff.

## Use

1. Select companies and apply inclusive start/end dates. At least one company stays selected. Drag horizontally on either chart or move the overview handles to select observed dates; date inputs also allow weekend-only intervals.
2. Sort the comparison table by any of its four metrics. Click a company to focus its evidence. A chart-point click focuses its company/date without changing the comparison interval.
3. Switch between adjusted-close/indexed prices and shares/relative volume. Relative volume uses exactly 20 preceding full-history observations, excluding today.
4. Read News or Filings for the selected date or interval. A weekend digest stays on its original date. Expand cards for the original full text and quality flags.
5. Add up to two companies to the research shortlist, give each a reason, and export CSV. Each entry freezes its metrics and range when added. Reload clears the session; CSV is the save mechanism.

## Rebuild

Use Python 3.13 and a separate environment. The existing cleaning requirements and public analysis functions are unchanged.

Windows, first-time setup (with Python 3.13 available as `python`):

```powershell
python -m venv .venv-dashboard
.venv-dashboard\Scripts\python.exe -m pip install -r requirements-dashboard.txt
```

For this checkout the environment is already installed. Build and run the dashboard tests:

```powershell
.venv-dashboard\Scripts\python.exe build_dashboard.py
.venv-dashboard\Scripts\python.exe -m unittest discover -s tests/dashboard -p "test_*.py" -v
```

On macOS/Linux use `python3.13` for environment creation and `.venv-dashboard/bin/python` thereafter. Builds resolve inputs and assets relative to `build_dashboard.py`, not the caller's working directory. Only the three formal `artifacts/*_clean.parquet` files are inputs; raw data are not needed. A snapshot hash mismatch stops the build.

## Architecture

| File | Responsibility |
|---|---|
| `dashboard_analysis.py` | Read-only input validation, original-value serialization and independent Python metric reference |
| `build_dashboard.py` | Embed validated data, Plotly and local assets; verify unchanged input hashes; write standalone HTML and build evidence |
| `dashboard_assets/metrics.js` | Pure full-history/range-dependent browser calculations |
| `dashboard_assets/events.js` | Original-calendar-date event query and flag labels |
| `dashboard_assets/state.js` | Shared filters/focus, frozen shortlist and spreadsheet-safe CSV |
| `dashboard_assets/render.js` | Controls, table, linked charts, event reader and shortlist rendering |
| `dashboard_assets/template.html`, `style.css` | Accessible page structure and responsive visual layout |
| `tests/dashboard/` | Arithmetic, schema, reference-parity and browser checks |
| `dashboard_verification/` | Executed evidence and reference values; screenshots were removed at the student's request; separate from cleaning verification |

Browser verification uses an independent environment with Playwright and an installed Chrome executable. It reads JSON references rather than importing analysis packages:

```powershell
.review\dashboard-browser\Scripts\python.exe tests/dashboard/check_browser.py --html "C:/absolute/path/dashboard.html" --chrome "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

See `dashboard_verification/report.md` for observed results, limitations and the exact local commands. These are implementation checks; they are not a claim that the student's personal audit has been completed.
