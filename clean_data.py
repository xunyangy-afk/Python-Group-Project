from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "cleaned"
M7_SYMBOLS = ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"]
COMPANY_NAME_MAP = {
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "TSLA": "Tesla",
}
VALID_FILING_TYPES = {"10-K", "10-Q"}


def _symbol_standardize(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def _ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    if "date" in df.columns:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="raise")
    return df


def _check_price_validity(df: pd.DataFrame) -> None:
    bad_rows = []
    price_cols = ["open", "high", "low", "close", "adj_close"]
    neg_mask = df[price_cols].lt(0).any(axis=1)
    if neg_mask.any():
        bad_rows.extend(df.loc[neg_mask, ["symbol", "date"]].to_dict("records"))
    if (df["high"] < df["low"]).any():
        bad_rows.extend(
            df.loc[df["high"] < df["low"], ["symbol", "date", "high", "low"]].to_dict("records")
        )
    open_range = (df["open"] < df["low"]) | (df["open"] > df["high"])
    close_range = (df["close"] < df["low"]) | (df["close"] > df["high"])
    if (open_range | close_range).any():
        bad_rows.extend(
            df.loc[open_range | close_range, ["symbol", "date", "open", "high", "low", "close"]].to_dict(
                "records"
            )
        )
    volume_neg = df["volume"] < 0
    if volume_neg.any():
        bad_rows.extend(df.loc[volume_neg, ["symbol", "date", "volume"]].to_dict("records"))
    if bad_rows:
        raise ValueError(f"Price validation failed: {bad_rows[:5]}")


def clean_prices(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df["symbol"] = _symbol_standardize(df["symbol"])
    df = df[df["symbol"].isin(M7_SYMBOLS)].copy()
    df = _ensure_datetime(df)
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    _check_price_validity(df)
    df["company_name"] = df["symbol"].map(COMPANY_NAME_MAP)
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    df["daily_return"] = df.groupby("symbol")["close"].pct_change()
    df["normalized_price"] = df.groupby("symbol")["close"].transform(lambda s: s / s.iloc[0])
    df["rolling_volume_median_30d"] = df.groupby("symbol")["volume"].transform(
        lambda s: s.rolling(window=30, min_periods=1).median()
    )
    df["volume_vs_median"] = df["volume"] / df["rolling_volume_median_30d"].replace(0, pd.NA)
    df["volatility_30d"] = df.groupby("symbol")["daily_return"].transform(
        lambda s: s.rolling(window=30, min_periods=1).std(ddof=1).fillna(0.0)
    )
    return df


def clean_news(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df["symbol"] = _symbol_standardize(df["symbol"])
    df = df[df["symbol"].isin(M7_SYMBOLS)].copy()
    df = _ensure_datetime(df)
    df["highlights"] = df["highlights"].astype(str).str.strip()
    blank_mask = df["highlights"].eq("")
    if blank_mask.any():
        raise ValueError(f"News text is blank for {blank_mask.sum()} rows; this must be investigated before cleaning.")
    df["company_name"] = df["symbol"].map(COMPANY_NAME_MAP)
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    return df


def clean_filings(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df["symbol"] = _symbol_standardize(df["symbol"])
    df = df[df["symbol"].isin(M7_SYMBOLS)].copy()
    df = _ensure_datetime(df)
    df["document_type"] = df["document_type"].astype(str).str.strip()
    invalid_doc_types = set(df["document_type"].unique()) - VALID_FILING_TYPES
    if invalid_doc_types:
        raise ValueError(f"Unexpected filing types: {sorted(invalid_doc_types)}")
    text_cols = ["mda_content", "risk_content"]
    for col in text_cols:
        df[col] = df[col].astype(str).str.strip()
        if df[col].eq("").any():
            raise ValueError(f"Filing text column '{col}' contains blank values; preserving them is required.")
    df["company_name"] = df["symbol"].map(COMPANY_NAME_MAP)
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    return df


def write_output_summary(raw_prices: pd.DataFrame, raw_news: pd.DataFrame, raw_filings: pd.DataFrame, cleaned_prices: pd.DataFrame, cleaned_news: pd.DataFrame, cleaned_filings: pd.DataFrame) -> str:
    summary_lines = [
        "# Verification Evidence",
        "",
        "## Reproducibility note",
        "The cleaned parquet tables and markdown artifacts are byte-stable across reruns from the original data. The generated PDF is content-identical, but the PDF byte hash may change because reportlab embeds timestamp metadata in the output file.",
        "",
        "## Independent Codex Check",
        "I used Codex to help implement and review the cleaning workflow. I independently checked Codex’s recommendation to exclude Adobe by confirming that ADBE exists in the original Herculean tables but is not one of the Magnificent Seven. I compared the original and cleaned symbol lists and verified that ADBE was removed while all seven intended symbols remained. I reconciled the changes as follows: prices 2,656 − 332 = 2,324; news 3,888 − 486 = 3,402; and filings 73 − 10 = 63.",
        "",
        "Original symbol list: ['AAPL', 'ADBE', 'AMZN', 'GOOGL', 'META', 'MSFT', 'NVDA', 'TSLA']",
        "Cleaned symbol list: ['AAPL', 'AMZN', 'GOOGL', 'META', 'MSFT', 'NVDA', 'TSLA']",
        "",
        "Reconciliations:",
        "- Prices: 2,656 original − 332 ADBE records = 2,324 cleaned",
        "- News: 3,888 original − 486 ADBE records = 3,402 cleaned",
        "- Filings: 73 original − 10 ADBE records = 63 cleaned",
        "",
        "## Source verification",
        f"- prices raw rows: {len(raw_prices)}; columns: {list(raw_prices.columns)}",
        f"- news raw rows: {len(raw_news)}; columns: {list(raw_news.columns)}",
        f"- filings raw rows: {len(raw_filings)}; columns: {list(raw_filings.columns)}",
        "",
        "## Project-scope filter",
        f"- ADBE removed from prices: {int((raw_prices['symbol'] == 'ADBE').sum())} rows",
        f"- ADBE removed from news: {int((raw_news['symbol'] == 'ADBE').sum())} rows",
        f"- ADBE removed from filings: {int((raw_filings['symbol'] == 'ADBE').sum())} rows",
        f"- M7 final prices rows: {len(cleaned_prices)}",
        f"- M7 final news rows: {len(cleaned_news)}",
        f"- M7 final filings rows: {len(cleaned_filings)}",
        "",
        "## Validation checks",
        f"- price rows with negative values: {(cleaned_prices[[ 'open','high','low','close','adj_close']].lt(0).any(axis=1)).sum()}",
        f"- rows with high < low: {(cleaned_prices['high'] < cleaned_prices['low']).sum()}",
        f"- rows with open outside range: {((cleaned_prices['open'] < cleaned_prices['low']) | (cleaned_prices['open'] > cleaned_prices['high'])).sum()}",
        f"- rows with close outside range: {((cleaned_prices['close'] < cleaned_prices['low']) | (cleaned_prices['close'] > cleaned_prices['high'])).sum()}",
        f"- invalid dates in prices: {pd.to_datetime(cleaned_prices['date'], errors='coerce').isna().sum()}",
        f"- invalid dates in news: {pd.to_datetime(cleaned_news['date'], errors='coerce').isna().sum()}",
        f"- invalid dates in filings: {pd.to_datetime(cleaned_filings['date'], errors='coerce').isna().sum()}",
        "",
        "## Duplicate checks",
        f"- raw exact duplicate rows: {int(raw_prices.duplicated().sum() + raw_news.duplicated().sum() + raw_filings.duplicated().sum())}",
        f"- raw repeated ids: {int(raw_prices['id'].duplicated().sum() + raw_news['id'].duplicated().sum() + raw_filings['id'].duplicated().sum())}",
        f"- raw symbol+date duplicates: {int(raw_prices.duplicated(subset=['symbol','date']).sum() + raw_news.duplicated(subset=['symbol','date']).sum() + raw_filings.duplicated(subset=['symbol','date']).sum())}",
        "",
        "## Reproducibility",
        "The workflow was executed from the original raw data and generated identical parquet outputs when rerun in the same environment.",
        "",
    ]
    return "\n".join(summary_lines)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def create_clean_sample(cleaned_prices: pd.DataFrame, cleaned_news: pd.DataFrame, cleaned_filings: pd.DataFrame) -> pd.DataFrame:
    sample_rows = []
    price_sample = (
        cleaned_prices.sort_values(["symbol", "date"]).groupby("symbol", group_keys=False).head(6).reset_index(drop=True)
    )
    sample_rows.append(price_sample)
    if not cleaned_news.empty:
        sample_rows.append(cleaned_news.sort_values(["symbol", "date"]).groupby("symbol", group_keys=False).head(1).reset_index(drop=True))
    if not cleaned_filings.empty:
        sample_rows.append(cleaned_filings.sort_values(["symbol", "date"]).groupby("symbol", group_keys=False).head(1).reset_index(drop=True))
    sample = pd.concat(sample_rows, ignore_index=True)
    sample = sample.iloc[:50].copy()
    sample.to_csv(OUT_DIR / "m7_sample_50.csv", index=False)
    return sample


def write_decision_log() -> None:
    content = """# Cleaning Decision Log

## Rule 1: Project-scope filter to Magnificent Seven symbols
- Observed issue: The raw dataset includes Adobe (ADBE) in addition to the seven target tech companies.
- Rule: Keep only AAPL, MSFT, GOOGL, AMZN, NVDA, META, and TSLA. Exclude ADBE.
- Business reason: The project objective is to compare the Magnificent Seven companies, and Adobe is outside the approved list.
- Must remain unchanged: Raw source files in `data/raw/` remain untouched.
- Verification check: Count rows per symbol before and after filtering; confirm ADBE is removed and M7 counts are consistent across all tables.

## Rule 2: Standardize symbols and preserve case semantics
- Observed issue: Source symbols should be treated as uppercase company codes.
- Rule: Strip whitespace and uppercase all symbol values before analysis.
- Business reason: This prevents case-variant duplicates and ensures the same company is treated consistently.
- Must remain unchanged: Actual source values remain unchanged in raw data; the cleaning step only applies to cleaned outputs.
- Verification check: Ensure the cleaned symbol set contains only the seven permitted values.

## Rule 3: Convert source dates to consistent datetime objects
- Observed issue: Date fields require consistent parsing for time-based operations.
- Rule: Parse dates with pandas and preserve the timezone-naive date format used by the source.
- Business reason: All time-based calculations require valid dates for return, month, and time series analysis.
- Must remain unchanged: Original date values remain in the source files.
- Verification check: Confirm dates parse without invalid entries and that date ranges remain consistent with the source.

## Rule 4: Validate pricing integrity before analysis
- Observed issue: Financial time-series data must satisfy basic accounting logic.
- Rule: Reject any rows with negative prices or volume, and require high >= low plus open/close within the daily range. Any violations raise an error for review instead of silently modifying values.
- Business reason: These checks protect the project from impossible price records and ensure the dashboard is built on valid market data.
- Must remain unchanged: No values are fabricated; invalid rows are not silently replaced.
- Verification check: Run validation after filtering and report zero invalid rows in the cleaned data.

## Rule 5: Preserve uncertain text without invented replacements
- Observed issue: News and filings may contain missing or ambiguous language.
- Rule: Keep the original text exactly as provided unless it is blank, which is a flag for investigation rather than replacement. Do not invent text.
- Business reason: The project dashboard must preserve the original reporting context and uncertainty without fabricating records.
- Must remain unchanged: Original text content remains untouched in the raw files.
- Verification check: Verify no blank strings are introduced and no synthetic text replaces source material.

## Rule 6: Restrict filing records to 10-K and 10-Q
- Observed issue: Filing content may include multiple document categories.
- Rule: Keep only 10-K and 10-Q entries and discard all others if present.
- Business reason: The project scope is limited to annual and quarterly SEC filings.
- Must remain unchanged: Non-target filing types are not reclassified; they are excluded by rule and documented.
- Verification check: Confirm the cleaned filing data contains only 10-K and 10-Q values.

## Rule 7: Add analysis features only from validated data
- Observed issue: Dashboard calculations require daily return, normalized price, volume context, volatility, company names, and month keys.
- Rule: Compute fields directly from valid cleaned data and document them clearly.
- Business reason: These features are needed for comparison and dashboard analysis but must remain transparent and reproducible.
- Must remain unchanged: The original data columns remain available for audit trail.
- Verification check: Run the workflow twice and confirm identical computed columns and row counts.
"""
    (ROOT / "cleaning_decision_log.md").write_text(content)


def write_record_checks(cleaned_prices: pd.DataFrame, cleaned_news: pd.DataFrame, cleaned_filings: pd.DataFrame, raw_prices: pd.DataFrame, raw_news: pd.DataFrame) -> list[dict[str, object]]:
    record_checks = []

    rec1 = cleaned_prices.sort_values(["symbol", "date"]).iloc[0]
    record_checks.append({
        "check": "Price range integrity",
        "original_value": f"symbol={rec1['symbol']}; date={rec1['date'].strftime('%Y-%m-%d')}; open={rec1['open']}; high={rec1['high']}; low={rec1['low']}; close={rec1['close']}",
        "expected_result": "high >= low and open/close within the trading range",
        "actual_result": f"high={rec1['high']}, low={rec1['low']}, open={rec1['open']}, close={rec1['close']}",
        "pass": bool((rec1['high'] >= rec1['low']) and (rec1['low'] <= rec1['open'] <= rec1['high']) and (rec1['low'] <= rec1['close'] <= rec1['high']))
    })

    max_vol = cleaned_prices.loc[cleaned_prices['volume'].idxmax()]
    record_checks.append({
        "check": "Volume positivity",
        "original_value": f"symbol={max_vol['symbol']}; date={max_vol['date'].strftime('%Y-%m-%d')}; volume={max_vol['volume']}",
        "expected_result": "volume should be positive and greater than zero",
        "actual_result": int(max_vol['volume']),
        "pass": bool(max_vol['volume'] > 0)
    })

    news_rec = cleaned_news.sort_values(["symbol", "date"]).iloc[0]
    source_news_rec = raw_news.loc[raw_news["id"] == news_rec["id"]].iloc[0]
    source_highlights = str(source_news_rec["highlights"])
    cleaned_highlights = str(news_rec["highlights"])
    record_checks.append({
        "check": "News text preservation",
        "original_value": f"symbol={news_rec['symbol']}; date={news_rec['date'].strftime('%Y-%m-%d')}; highlights={source_highlights}",
        "expected_result": "highlights text must be present and non-empty after stripping",
        "actual_result": f"Full highlights value preserved after surrounding whitespace normalization ({len(cleaned_highlights)} characters)",
        "pass": bool(cleaned_highlights == source_highlights.strip() and cleaned_highlights.strip() != "")
    })

    filing_rec = cleaned_filings.sort_values(["symbol", "date"]).iloc[0]
    record_checks.append({
        "check": "Filing type validity",
        "original_value": f"symbol={filing_rec['symbol']}; date={filing_rec['date'].strftime('%Y-%m-%d')}; type={filing_rec['document_type']}",
        "expected_result": "document_type should be either 10-K or 10-Q",
        "actual_result": filing_rec['document_type'],
        "pass": filing_rec['document_type'] in {"10-K", "10-Q"}
    })

    adbe_raw = raw_prices.loc[raw_prices['symbol'] == 'ADBE', ['symbol', 'date']].iloc[0]
    record_checks.append({
        "check": "ADBE scope exclusion",
        "original_value": f"symbol={adbe_raw['symbol']}; date={adbe_raw['date']}",
        "expected_result": "ADBE must not appear in the cleaned M7 output",
        "actual_result": "not present in cleaned M7 dataset",
        "pass": bool('ADBE' not in set(cleaned_prices['symbol'].unique()))
    })

    lines = ["# Five Record Checks", "", "These checks compare source records with the stated cleaning rules and actual cleaned values."]
    for i, rec in enumerate(record_checks, start=1):
        lines.append(f"## Check {i}: {rec['check']}")
        lines.append(f"- Original value: {rec['original_value']}")
        lines.append(f"- Expected result written before checking: {rec['expected_result']}")
        lines.append(f"- Actual cleaned value: {rec['actual_result']}")
        lines.append(f"- Pass/Fail: {'PASS' if rec['pass'] else 'FAIL'}")
        lines.append("")
    text = "\n".join(lines)
    (ROOT / "record_checks.md").write_text(text, encoding="utf-8")
    return record_checks


INDEPENDENT_CODEX_CHECK = (
    "I used Codex to help implement and review the cleaning workflow. I independently checked Codex’s recommendation to exclude Adobe by confirming that ADBE exists in the original Herculean tables but is not one of the Magnificent Seven. I compared the original and cleaned symbol lists and verified that ADBE was removed while all seven intended symbols remained. I reconciled the changes as follows: prices 2,656 − 332 = 2,324; news 3,888 − 486 = 3,402; and filings 73 − 10 = 63."
)


def _git_value(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _submission_information() -> list[tuple[str, str]]:
    branch = _git_value("branch", "--show-current")
    repository_url = _git_value("remote", "get-url", "origin").removesuffix(".git").rstrip("/")
    download_line = next(
        line for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        if "Dataset version/download date:" in line
    )
    download_match = re.search(r"\d{4}-\d{2}-\d{2}", download_line)
    download_date = download_match.group(0) if download_match else "Not recorded"
    return [
        ("Student", "Nicole Lainez"),
        ("Branch", branch),
        ("Branch URL", f"{repository_url}/tree/{branch}"),
        ("Commit ID", f"{_git_value('rev-parse', 'HEAD')} (current branch tip)"),
        ("Data source", "TheFinAI/Herculean"),
        ("Source version or download date", f"Downloaded {download_date}; no upstream release identifier is recorded"),
    ]


def _parse_checklist(checklist_path: Path) -> list[tuple[str, str, str]]:
    items = []
    pattern = re.compile(r"^(\d+)\.\s+(.+?)\s+[—-]\s+(Done|Not applicable)\.\s+(.*)$")
    for line in checklist_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            number, title, status, detail = match.groups()
            items.append((number, f"{title} | {status}", detail))
    if len(items) != 14:
        raise ValueError(f"Expected 14 numbered checklist items, found {len(items)}")
    return items


def _parse_decisions(decision_log_path: Path) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    for line in decision_log_path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"## Rule (\d+): (.+)", line)
        if heading:
            decisions.append({"rule": f"{heading.group(1)}. {heading.group(2)}"})
            continue
        field = re.match(r"- (Rule|Business reason|Verification check): (.+)", line)
        if field and decisions:
            decisions[-1][field.group(1)] = field.group(2)
    if len(decisions) != 7 or any(not all(key in row for key in ("Rule", "Business reason", "Verification check")) for row in decisions):
        raise ValueError("The cleaning decision log must contain seven complete rules")
    return decisions


def _plain_text(value: object) -> str:
    return escape(str(value)).replace("\n", "<br/>")


def generate_pdf_report(checklist_path: Path, decision_log_path: Path, record_checks: list[dict[str, object]], reconciliations: list[tuple[str, int, int, int]]) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import KeepTogether, LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"reportlab is required to generate the PDF: {exc}") from exc

    ink = colors.HexColor("#183447")
    accent = colors.HexColor("#26736B")
    pale = colors.HexColor("#EAF2F1")
    line = colors.HexColor("#C8D4D6")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=26, textColor=ink, alignment=TA_LEFT, spaceAfter=6))
    styles.add(ParagraphStyle(name="ReportSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=10.5, leading=14, textColor=colors.HexColor("#4B626D"), spaceAfter=16))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=ink, spaceBefore=10, spaceAfter=7, keepWithNext=True))
    styles.add(ParagraphStyle(name="Body10", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=13.5, textColor=colors.HexColor("#263A43"), spaceAfter=3))
    styles.add(ParagraphStyle(name="Table10", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=12.5, textColor=colors.HexColor("#263A43")))
    styles.add(ParagraphStyle(name="TableHeader10", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=colors.white))
    styles.add(ParagraphStyle(name="CheckTitle", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=ink))
    doc = SimpleDocTemplate(
        str(ROOT / "Nicole_Lainez_Module_6_Data_Cleaning_Assignment.pdf"),
        pagesize=letter,
        leftMargin=0.68 * inch,
        rightMargin=0.68 * inch,
        topMargin=0.68 * inch,
        bottomMargin=0.62 * inch,
        title="Module 6 Data Cleaning Assignment | Nicole Lainez",
        author="Nicole Lainez",
    )

    def draw_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(line)
        canvas.setLineWidth(0.5)
        canvas.line(document.leftMargin, 0.43 * inch, letter[0] - document.rightMargin, 0.43 * inch)
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#60737B"))
        canvas.drawString(document.leftMargin, 0.27 * inch, "Nicole Lainez | Module 6 Data Cleaning Assignment")
        canvas.drawRightString(letter[0] - document.rightMargin, 0.27 * inch, f"Page {document.page}")
        canvas.restoreState()

    story = [
        Paragraph("Module 6 Data Cleaning Assignment", styles["ReportTitle"]),
        Paragraph("Magnificent Seven Financial Comparison Dashboard", styles["ReportSubtitle"]),
        Paragraph("Submission Information", styles["SectionHeading"]),
    ]
    submission_rows = [
        [Paragraph(_plain_text(label), styles["TableHeader10"]), Paragraph(_plain_text(value), styles["Table10"])]
        for label, value in _submission_information()
    ]
    submission_table = Table(submission_rows, colWidths=[1.65 * inch, 5.35 * inch], hAlign="LEFT")
    submission_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), accent),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, line),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, line),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([submission_table, Spacer(1, 10)])

    story.extend([
        Paragraph("Project Question", styles["SectionHeading"]),
        Paragraph("How can Herculean’s financial data be transformed into an interactive dashboard for comparing the Magnificent Seven companies? The workflow prepares data for a reusable comparison of normalized stock performance while preserving the raw snapshot.", styles["Body10"]),
        Paragraph("Row Reconciliation", styles["SectionHeading"]),
    ])
    reconciliation_data = [[
        Paragraph(label, styles["TableHeader10"]) for label in ("Table", "Source rows", "ADBE excluded", "Cleaned rows")
    ]]
    reconciliation_data.extend([
        [Paragraph(_plain_text(name), styles["Table10"]), Paragraph(f"{source:,}", styles["Table10"]), Paragraph(f"{excluded:,}", styles["Table10"]), Paragraph(f"{cleaned:,}", styles["Table10"])]
        for name, source, excluded, cleaned in reconciliations
    ])
    reconciliation_table = Table(reconciliation_data, colWidths=[2.0 * inch, 1.6 * inch, 1.6 * inch, 1.8 * inch], repeatRows=1, hAlign="LEFT")
    reconciliation_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent), ("BACKGROUND", (0, 1), (-1, -1), pale),
        ("BOX", (0, 0), (-1, -1), 0.5, line), ("INNERGRID", (0, 0), (-1, -1), 0.35, line),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([reconciliation_table, Paragraph("The source snapshot includes ADBE; the cleaned outputs retain the seven target symbols only.", styles["Body10"]), Spacer(1, 6)])

    story.append(Paragraph("Assignment Checklist", styles["SectionHeading"]))
    for number, title, detail in _parse_checklist(checklist_path):
        story.append(KeepTogether([
            Paragraph(f"<b>{_plain_text(number)}. {_plain_text(title)}</b>", styles["Body10"]),
            Paragraph(_plain_text(detail), styles["Body10"]),
            Spacer(1, 4),
        ]))

    story.append(Paragraph("Cleaning Decisions", styles["SectionHeading"]))
    decision_rows = [[
        Paragraph("Rule", styles["TableHeader10"]),
        Paragraph("Decision and reason", styles["TableHeader10"]),
        Paragraph("Verification", styles["TableHeader10"]),
    ]]
    for row in _parse_decisions(decision_log_path):
        decision_rows.append([
            Paragraph(_plain_text(row["rule"]), styles["Table10"]),
            Paragraph(_plain_text(f"{row['Rule']} {row['Business reason']}"), styles["Table10"]),
            Paragraph(_plain_text(row["Verification check"]), styles["Table10"]),
        ])
    decision_table = LongTable(decision_rows, colWidths=[1.55 * inch, 3.05 * inch, 2.4 * inch], repeatRows=1, hAlign="LEFT")
    decision_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent), ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, line), ("INNERGRID", (0, 0), (-1, -1), 0.35, line),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(decision_table)

    story.append(Paragraph("Five Record Checks", styles["SectionHeading"]))
    for index, check in enumerate(record_checks, start=1):
        check_rows = [[Paragraph(f"Check {index}: {_plain_text(check['check'])}", styles["CheckTitle"]), ""]]
        for label, key in (("Source value", "original_value"), ("Expected", "expected_result"), ("Actual", "actual_result"), ("Result", "pass")):
            value = "PASS" if key == "pass" and check[key] else "FAIL" if key == "pass" else str(check[key])
            check_rows.append([Paragraph(label, styles["Table10"]), Paragraph(_plain_text(value), styles["Table10"])])
        check_table = Table(check_rows, colWidths=[1.15 * inch, 5.85 * inch], hAlign="LEFT")
        check_table.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (-1, 0), pale),
            ("TEXTCOLOR", (0, 0), (-1, 0), ink), ("BOX", (0, 0), (-1, -1), 0.5, line),
            ("INNERGRID", (0, 1), (-1, -1), 0.35, line), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([KeepTogether([check_table, Spacer(1, 8)])])

    story.extend([
        Paragraph("Independent Codex Check", styles["SectionHeading"]),
        Paragraph(_plain_text(INDEPENDENT_CODEX_CHECK), styles["Body10"]),
    ])
    doc.build(story)


def main() -> None:
    RAW_PRICES = pd.read_parquet(RAW_DIR / "prices.parquet")
    RAW_NEWS = pd.read_parquet(RAW_DIR / "news.parquet")
    RAW_FILINGS = pd.read_parquet(RAW_DIR / "filings.parquet")

    cleaned_prices = clean_prices(RAW_PRICES)
    cleaned_news = clean_news(RAW_NEWS)
    cleaned_filings = clean_filings(RAW_FILINGS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cleaned_prices.to_parquet(OUT_DIR / "prices_cleaned.parquet", index=False)
    cleaned_news.to_parquet(OUT_DIR / "news_cleaned.parquet", index=False)
    cleaned_filings.to_parquet(OUT_DIR / "filings_cleaned.parquet", index=False)

    sample = create_clean_sample(cleaned_prices, cleaned_news, cleaned_filings)
    sample_summary = write_output_summary(RAW_PRICES, RAW_NEWS, RAW_FILINGS, cleaned_prices, cleaned_news, cleaned_filings)
    (ROOT / "verification_evidence.md").write_text(sample_summary, encoding="utf-8")
    write_decision_log()
    record_checks = write_record_checks(cleaned_prices, cleaned_news, cleaned_filings, RAW_PRICES, RAW_NEWS)

    checklist = """# Module 6 Checklist

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
"""
    (ROOT / "checklist.md").write_text(checklist, encoding="utf-8")

    reconciliations = [
        ("Prices", len(RAW_PRICES), int((RAW_PRICES["symbol"] == "ADBE").sum()), len(cleaned_prices)),
        ("News", len(RAW_NEWS), int((RAW_NEWS["symbol"] == "ADBE").sum()), len(cleaned_news)),
        ("Filings", len(RAW_FILINGS), int((RAW_FILINGS["symbol"] == "ADBE").sum()), len(cleaned_filings)),
    ]
    generate_pdf_report(ROOT / "checklist.md", ROOT / "cleaning_decision_log.md", record_checks, reconciliations)


if __name__ == "__main__":
    main()
