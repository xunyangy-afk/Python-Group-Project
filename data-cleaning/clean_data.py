"""Clean raw stock, news, and filing data with auditable transformation reports."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


RAW_DIR = Path("data/raw/data")
PROCESSED_DIR = Path("data/processed")
KNOWN_SYMBOLS = {"AAPL", "ADBE", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"}
KNOWN_DOCUMENT_TYPES = {"10-K", "10-Q"}
TEXT_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00a0": " ",
        "\uFFFD": "'",
    }
)


def clean_text(value: object) -> str:
    """Normalize raw text extracted from filings/news without changing meaning."""
    if pd.isna(value):
        return ""

    text = html.unescape(str(value))
    text = text.translate(TEXT_TRANSLATION)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def count_changed_values(before: pd.Series, after: pd.Series) -> int:
    before_text = before.fillna("").astype(str)
    after_text = after.fillna("").astype(str)
    return int((before_text != after_text).sum())


def date_range(df: pd.DataFrame) -> dict[str, str | None]:
    if "date" not in df.columns or df.empty:
        return {"min_date": None, "max_date": None}

    dates = df["date"].dropna()
    if dates.empty:
        return {"min_date": None, "max_date": None}

    return {
        "min_date": dates.min().strftime("%Y-%m-%d"),
        "max_date": dates.max().strftime("%Y-%m-%d"),
    }


def start_report(name: str, raw: pd.DataFrame) -> dict[str, Any]:
    return {
        "name": name,
        "rows_before": int(len(raw)),
        "columns_before": int(len(raw.columns)),
        "rows_after": None,
        "columns_after": None,
        "columns_added": [],
        "columns_changed": [],
        "flagged_rows": {},
        "removed_rows": {
            "total": 0,
            "reasons": {
                "full_row_duplicates": 0,
                "impossible_downstream_fields": 0,
            },
        },
        "category_changes": [],
        "unit_changes": [],
        "notes": [],
    }


def finish_report(report: dict[str, Any], cleaned: pd.DataFrame) -> dict[str, Any]:
    report["columns_added"] = sorted(set(report["columns_added"]))
    report["rows_after"] = int(len(cleaned))
    report["columns_after"] = int(len(cleaned.columns))
    report["duplicate_rows_after"] = int(cleaned.duplicated().sum())
    report["missing_values_after"] = {
        column: int(count) for column, count in cleaned.isna().sum().items()
    }
    report.update(date_range(cleaned))
    return report


def standardize_base(
    raw: pd.DataFrame, name: str, key_columns: list[str]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    report = start_report(name, raw)
    cleaned = raw.copy()
    original_columns = list(cleaned.columns)
    cleaned.columns = [column.strip().lower() for column in cleaned.columns]
    if original_columns != list(cleaned.columns):
        report["columns_changed"].append("standardized column names to lowercase")

    if "symbol" in cleaned.columns:
        original_symbol = cleaned["symbol"].copy()
        cleaned["symbol"] = cleaned["symbol"].astype(str).str.strip().str.upper()
        report["category_changes"].append(
            {
                "column": "symbol",
                "change": "trimmed whitespace and uppercased ticker symbols",
                "reason": "category standardization for joins",
                "changed_rows": count_changed_values(original_symbol, cleaned["symbol"]),
            }
        )
        cleaned["flag_invalid_symbol"] = ~cleaned["symbol"].isin(KNOWN_SYMBOLS)

    if "date" in cleaned.columns:
        original_date = cleaned["date"].copy()
        cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
        report["columns_changed"].append(
            {
                "column": "date",
                "change": "converted to datetime",
                "changed_rows": count_changed_values(
                    original_date, cleaned["date"].dt.strftime("%Y-%m-%d")
                ),
            }
        )
        cleaned["flag_invalid_date"] = cleaned["date"].isna()

    cleaned["flag_full_row_duplicate"] = cleaned.duplicated(keep=False)
    cleaned["flag_duplicate_key"] = cleaned.duplicated(key_columns, keep=False)

    for flag_column in [column for column in cleaned.columns if column.startswith("flag_")]:
        report["flagged_rows"][flag_column] = int(cleaned[flag_column].sum())

    report["columns_added"].extend(
        [column for column in cleaned.columns if column not in raw.columns]
    )
    report["notes"].append("No rows removed during base standardization.")
    return cleaned, report


def clean_prices(raw_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_parquet(raw_dir / "prices.parquet")
    prices, report = standardize_base(raw, "prices_clean", ["symbol", "date"])

    numeric_columns = ["open", "high", "low", "close", "adj_close", "volume"]
    for column in numeric_columns:
        before = prices[column].copy()
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
        report["columns_changed"].append(
            {
                "column": column,
                "change": "converted to numeric",
                "changed_rows": int((before != prices[column]).fillna(False).sum()),
            }
        )

    prices["flag_invalid_price"] = (
        prices[["open", "high", "low", "close", "adj_close"]].isna().any(axis=1)
        | (prices[["open", "high", "low", "close", "adj_close"]] <= 0).any(axis=1)
        | prices["volume"].isna()
        | (prices["volume"] < 0)
        | (prices["high"] < prices["low"])
    )

    prices = prices.sort_values(["symbol", "date"]).reset_index(drop=True)
    grouped = prices.groupby("symbol", group_keys=False)
    prices["daily_return"] = grouped["adj_close"].pct_change()
    prices["dollar_change"] = grouped["adj_close"].diff()
    prices["intraday_range_pct"] = (prices["high"] - prices["low"]) / prices["open"]
    prices["trading_year"] = prices["date"].dt.year
    prices["trading_month"] = prices["date"].dt.to_period("M").astype(str)

    report["flagged_rows"]["flag_invalid_price"] = int(prices["flag_invalid_price"].sum())
    report["columns_added"].extend(
        [
            "flag_invalid_price",
            "daily_return",
            "dollar_change",
            "intraday_range_pct",
            "trading_year",
            "trading_month",
        ]
    )
    report["unit_changes"].append(
        {
            "columns": ["open", "high", "low", "close", "adj_close", "volume"],
            "change": "none",
            "reason": "stock-price and share-count units are preserved",
        }
    )
    report["notes"].append("No price rows removed; suspicious values are flagged.")
    return prices, finish_report(report, prices)


def clean_news(raw_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_parquet(raw_dir / "news.parquet")
    news, report = standardize_base(raw, "news_clean", ["symbol", "date"])

    before_text = news["highlights"].copy()
    news["highlights"] = news["highlights"].map(clean_text)
    news["flag_empty_text"] = news["highlights"] == ""
    news["highlight_length"] = news["highlights"].str.len()

    report["columns_changed"].append(
        {
            "column": "highlights",
            "change": "HTML-unescaped, punctuation-normalized, whitespace-collapsed, trimmed",
            "changed_rows": count_changed_values(before_text, news["highlights"]),
        }
    )
    report["flagged_rows"]["flag_empty_text"] = int(news["flag_empty_text"].sum())
    report["columns_added"].extend(["flag_empty_text", "highlight_length"])
    report["notes"].append("No news rows removed; empty cleaned text is flagged.")

    news = news.sort_values(["symbol", "date", "id"]).reset_index(drop=True)
    return news, finish_report(report, news)


def clean_filings(raw_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_parquet(raw_dir / "filings.parquet")
    filings, report = standardize_base(
        raw, "filings_clean", ["symbol", "date", "document_type"]
    )

    original_document_type = filings["document_type"].copy()
    filings["document_type"] = filings["document_type"].astype(str).str.strip().str.upper()
    filings["flag_unknown_document_type"] = ~filings["document_type"].isin(
        KNOWN_DOCUMENT_TYPES
    )
    report["category_changes"].append(
        {
            "column": "document_type",
            "change": "trimmed whitespace and uppercased filing document type",
            "reason": "category standardization for validation and grouping",
            "changed_rows": count_changed_values(
                original_document_type, filings["document_type"]
            ),
        }
    )

    text_flag_columns = []
    for column in ["mda_content", "risk_content"]:
        before_text = filings[column].copy()
        filings[column] = filings[column].map(clean_text)
        length_column = f"{column}_length"
        flag_column = f"flag_empty_{column}"
        filings[length_column] = filings[column].str.len()
        filings[flag_column] = filings[column] == ""
        text_flag_columns.append(flag_column)
        report["columns_changed"].append(
            {
                "column": column,
                "change": "HTML-unescaped, punctuation-normalized, whitespace-collapsed, trimmed",
                "changed_rows": count_changed_values(before_text, filings[column]),
            }
        )
        report["columns_added"].extend([length_column, flag_column])
        report["flagged_rows"][flag_column] = int(filings[flag_column].sum())

    filings["flag_empty_text"] = filings[text_flag_columns].any(axis=1)
    report["flagged_rows"]["flag_unknown_document_type"] = int(
        filings["flag_unknown_document_type"].sum()
    )
    report["flagged_rows"]["flag_empty_text"] = int(filings["flag_empty_text"].sum())
    report["columns_added"].extend(["flag_unknown_document_type", "flag_empty_text"])
    report["notes"].append("No filing rows removed; suspicious filing values are flagged.")

    filings = filings.sort_values(["symbol", "date", "document_type"]).reset_index(
        drop=True
    )
    return filings, finish_report(report, filings)


def build_dashboard_daily(
    prices: pd.DataFrame, news: pd.DataFrame, filings: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    report = start_report("dashboard_daily", prices)
    valid_news = news[~news["flag_invalid_symbol"] & ~news["flag_invalid_date"]]
    valid_filings = filings[
        ~filings["flag_invalid_symbol"]
        & ~filings["flag_invalid_date"]
        & ~filings["flag_unknown_document_type"]
    ]

    news_daily = (
        valid_news.groupby(["symbol", "date"], as_index=False)
        .agg(
            news_count=("id", "count"),
            highlights=("highlights", lambda values: " | ".join(values)),
            avg_highlight_length=("highlight_length", "mean"),
        )
    )

    filings_daily = (
        valid_filings.groupby(["symbol", "date"], as_index=False)
        .agg(
            filing_count=("id", "count"),
            filing_types=("document_type", lambda values: ", ".join(sorted(set(values)))),
        )
    )

    dashboard = prices.merge(news_daily, on=["symbol", "date"], how="left")
    dashboard = dashboard.merge(filings_daily, on=["symbol", "date"], how="left")

    dashboard["news_count"] = dashboard["news_count"].fillna(0).astype(int)
    dashboard["filing_count"] = dashboard["filing_count"].fillna(0).astype(int)
    dashboard["has_news"] = dashboard["news_count"] > 0
    dashboard["has_filing"] = dashboard["filing_count"] > 0
    dashboard["highlights"] = dashboard["highlights"].fillna("")
    dashboard["filing_types"] = dashboard["filing_types"].fillna("")

    report["columns_added"].extend(
        [
            "news_count",
            "highlights",
            "avg_highlight_length",
            "filing_count",
            "filing_types",
            "has_news",
            "has_filing",
        ]
    )
    report["merge_match_counts"] = {
        "price_rows": int(len(prices)),
        "rows_with_news": int(dashboard["has_news"].sum()),
        "rows_without_news": int((~dashboard["has_news"]).sum()),
        "rows_with_filings": int(dashboard["has_filing"].sum()),
        "rows_without_filings": int((~dashboard["has_filing"]).sum()),
        "news_rows_available_for_merge": int(len(valid_news)),
        "filing_rows_available_for_merge": int(len(valid_filings)),
    }
    report["notes"].append(
        "Prices are the base table; unmatched news/filings are preserved as empty join fields."
    )

    dashboard = dashboard.sort_values(["symbol", "date"]).reset_index(drop=True)
    return dashboard, finish_report(report, dashboard)


def write_outputs(
    prices: pd.DataFrame,
    news: pd.DataFrame,
    filings: pd.DataFrame,
    dashboard: pd.DataFrame,
    reports: dict[str, dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    datasets = {
        "prices_clean": prices,
        "news_clean": news,
        "filings_clean": filings,
        "dashboard_daily": dashboard,
    }

    for name, df in datasets.items():
        df.to_parquet(output_dir / f"{name}.parquet", index=False)
        df.to_csv(output_dir / f"{name}.csv", index=False)

    report = {
        "source_of_truth": "plan.md",
        "outputs": {name: str(output_dir / f"{name}.parquet") for name in datasets},
        "transformations": reports,
    }

    (output_dir / "cleaning_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def print_step_summary(report: dict[str, Any]) -> None:
    flagged = sum(report.get("flagged_rows", {}).values())
    removed = report.get("removed_rows", {}).get("total", 0)
    print(
        f"{report['name']}: "
        f"{report['rows_before']} -> {report['rows_after']} rows, "
        f"{report['columns_before']} -> {report['columns_after']} columns, "
        f"{flagged} flags, {removed} rows removed"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean raw parquet files into dashboard-ready datasets."
    )
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prices, prices_report = clean_prices(args.raw_dir)
    print_step_summary(prices_report)

    news, news_report = clean_news(args.raw_dir)
    print_step_summary(news_report)

    filings, filings_report = clean_filings(args.raw_dir)
    print_step_summary(filings_report)

    dashboard, dashboard_report = build_dashboard_daily(prices, news, filings)
    print_step_summary(dashboard_report)

    reports = {
        "prices_clean": prices_report,
        "news_clean": news_report,
        "filings_clean": filings_report,
        "dashboard_daily": dashboard_report,
    }
    write_outputs(prices, news, filings, dashboard, reports, args.output_dir)
    print(f"Wrote cleaned outputs and cleaning_report.json to {args.output_dir}")


if __name__ == "__main__":
    main()
