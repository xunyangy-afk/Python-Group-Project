# Team change requests

Copy this template into the top folder of your team's app repository if `change-requests.md` is missing. If it already exists, add to it; do not replace your teammates' work. Keep your individual evidence and conclusions in `my-audit.md`.

## Claims

Add your name and what you will audit. Choose a different scope from your teammates, or explain the new evidence you will contribute.

| Author | Feature | Number | Distinct scope or new evidence |
| --- | --- | --- | --- |
| Zack Ye | Shared company/date filtering, interval rebasing, news boundaries, invalid ranges and single-observation chart visibility | AAPL adjusted-close interval return, 2026-03-02 to 2026-03-31; additional NVDA comparison | Written before/after observations, a rejected-range state comparison, original-date news endpoint IDs, a separate pandas/Decimal source calculation included in my-audit.md, and a single-point display finding. No teammate claims exist in this checkout; overlap on other branches is unverified. This claim was recorded after the manual checks, not pre-registered. |

## Requests

Copy this block for each actionable finding and choose a unique ID. Reference that ID in your individual audit. A check that finds no defect belongs in your audit; do not invent a bug to fill a request.

### AUDIT-ZY-01 Make single-observation price and volume values visible

- Author: Zack Ye
- Status: open
- App version or commit checked: `e630f6823fd12bc11cf0525fab7dc9be59ff5eae` on `Zack-Work`.
- Feature or number and its intended behavior or definition: F1 linked adjusted-price/volume charts. `BUILD_SPEC.md` Section 9 states that one valid price observation has a normalized value of 100, while interval return, volatility and drawdown are unavailable. Valid volume remains available. Users should be able to see the existing observation rather than infer that the interval has no data.
- Inputs and steps to reproduce: open the audited HTML; select only AAPL and NVDA; retain `Indexed to 100` and `Shares`; apply start `2026-03-01`, end `2026-03-02`. The source has one March 2 price/volume observation per company in this interval.
- Expected result: each company's indexed observation at 100 and its actual volume are visibly represented, with company/date identification; the table has one observation, no return/volatility/drawdown estimate, and available average volume.
- Actual result: the manually observed table showed one observation per company, zero valid returns, unavailable return/volatility/drawdown, and average volumes 41,827,900 (AAPL) and 209,095,300 (NVDA), but no visible data marks in the two main charts. The table's one-row treatment is appropriate; the lack of visible chart marks is the requested change.
- Evidence (including file, function, and relevant lines if code was checked): the formal source table has AAPL row ID 311 and NVDA row ID 2303 on 2026-03-02, with adjusted closes 264.7200012207031 / 182.4701232910156 and volumes 41,827,900 / 209,095,300. The observed applied interval was 2026-03-01 to 2026-03-02 and the table retained one row per company while the charts appeared empty. At the audited commit, `dashboard_assets/render.js`, `trace()`, line 85, contains `type:'scatter', mode:'lines'`, without markers. `my-audit.md` Check F4 records the UI context, and Section 3 includes executable source-check code directly in the document. No screenshot, JSON attachment or local-file hyperlink is required to read this evidence; rerunning the code requires the project's formal Parquet data.
- Likely cause, if established, and remaining uncertainty: line-only traces cannot draw a connecting segment for an isolated observation; the renderer supplies no marker fallback. This is supported by the recorded UI behavior and code inspection. Exact hover behavior, all isolated-gap cases and a corrected rendering have not been verified. A separate axis/extent contribution has not been excluded.
- Requested change: display markers for isolated valid observations in the main charts, preserve series colors and company/date/value identification, and ensure points at a selected interval boundary are visible. Keep all defined metric conventions and source values unchanged.
- Verification check and expected result: on a new fix commit, apply 2026-03-01 to 2026-03-02 with AAPL/NVDA. See the March 2 base-100 observations and volumes 41,827,900 / 209,095,300, including accessible exact-value context. The table remains one observation/zero returns with unavailable return/volatility/drawdown. Repeat with a single-day March 2 interval and regression-check the multi-row March 2-31 range; AAPL/NVDA returns remain -4.13% / -4.42%. Record actual results and screenshots before marking resolved.
- Implementation commit and verification result, if resolved: none; no dashboard fix was made during this audit.

Record findings without undoing a teammate's work. Mark a request resolved only after verifying the change.

## Template provenance

Copied from the course [09-audit change-requests.md template](https://github.com/USC-DSO-576-YA/09-audit/blob/main/change-requests.md) on October 25, 2026. Retrieved template Git blob SHA: `a6b445639fcf0e9514ca1a2c11f1e71707ad66cd`. The Claims entry and actionable request above are additions for Zack's audit; no pre-existing team file or teammate entry was overwritten. Passing date/return checks are recorded in `my-audit.md`, rather than invented as change requests.

