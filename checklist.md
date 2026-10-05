# Module 6 Checklist

1. STATE THE PROJECT VISION AND QUESTION — Done. The project vision is to build an interactive Magnificent Seven financial comparison dashboard using Herculean data. The business question is: how can the raw financial data be transformed into a reusable comparison tool for the seven major technology companies? The main metric is normalized stock performance for trend and comparison analysis.

2. DEFINE ONE ROW — Done. One price row is a single company-date observation; one news row is a single company-date story; one filing row is a single company-document-date filing record. The natural key for prices is (symbol, date). For news and filings, the natural keys are (symbol, date) and (symbol, date, document_type), respectively.

3. PRESERVE THE SOURCE — Done. Source data remain in `data/raw/` and are read only. The exact data source is TheFinAI/Herculean on Hugging Face.

4. INSPECT COLUMNS AND TYPES — Done. The raw prices table has 9 columns: id, symbol, date, open, high, low, close, adj_close, volume. News has 4 columns; filings has 6 columns. Date fields were parsed to datetime during cleaning, and all expected columns were inspected.

5. STANDARDIZE TEXT — Done. Symbol values were normalized to uppercase and whitespace was trimmed. No identifier values were altered beyond this formatting standardization; all other raw text is retained.

6. INVESTIGATE DUPLICATES — Done. Raw datasets had zero exact duplicate rows, zero repeated IDs, and zero repeated symbol-date combinations. No deduplication was required beyond the project-scope filter.

7. HANDLE MISSING DATA — Done. There were zero missing values in raw tables and the filtered M7 dataset. No imputation was required; missing values were retained as missing only if encountered in future data, with no fabricated replacement.

8. CHECK SUSPICIOUS VALUES — Done. The price validation checks resulted in zero negative prices, zero negative volume rows, zero case of high < low, and zero open/close values outside the daily range. News and filings were checked for blank text and invalid filing types; no invalid values were found.

9. VERIFY MERGES — Not applicable. The workflow does not merge the three tables for the cleaning step because each table is cleaned and analyzed independently before downstream dashboard assembly. If a later dashboard step merges tables, the merge keys are symbol and date.

10. RECONCILE CHANGES — Done. Starting totals were 2656 price rows, 3888 news rows, and 73 filing rows. After removing ADBE, final totals were 2324 price rows, 3402 news rows, and 63 filing rows. The differences are exactly the Adobe rows removed for scope.

11. CHECK CALCULATIONS — Done. Daily return is computed as close.pct_change(); normalized price is close / first close in each symbol series; rolling volume median is the 30-day median; volatility is the 30-day standard deviation of daily return; period is year-month; missing values in daily return or feature calculations remain as missing or zero only when a formula requires it. No fabricated values were introduced.

12. VERIFY INDIVIDUAL RECORDS — Done. The five record checks are included in the PDF and evidence summary; they cover difficult values and validation decisions.

13. TEST REPRODUCIBILITY — Done. The script was run from the original raw data and regenerated the same outputs in a second execution. The outputs were checked for row counts and hashes, and they matched.

Independent Codex Check — Done. I used Codex to help implement and review the cleaning workflow. I independently checked Codex’s recommendation to exclude Adobe by confirming that ADBE exists in the original Herculean tables but is not one of the Magnificent Seven. I compared the original and cleaned symbol lists and verified that ADBE was removed while all seven intended symbols remained. I reconciled the changes as follows: prices 2,656 − 332 = 2,324; news 3,888 − 486 = 3,402; and filings 73 − 10 = 63.

14. DOCUMENT REMAINING LIMITATIONS — Done. The project data are valid and internally consistent for the M7 scope. The remaining limitation is that the assignment is based on the static raw source snapshot rather than a live market feed; additional data and a broader time horizon would be needed for future live dashboard updates.
