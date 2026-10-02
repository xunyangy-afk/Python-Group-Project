"""Reproduce the conservative cleaning rules in ../plan.md from local originals."""

import argparse
from datetime import date
import hashlib
import html
import json
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parent
TABLES = ("news", "prices", "filings")
SYMBOLS = {"AAPL", "ADBE", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"}
BASELINE = {
    "news": (3888, "9156b73a5c417057104abe9eeb0d9b3ea0dceea66260e5b8ef552bd182cec8e6"),
    "prices": (2656, "0001b983f1a302e2f7a2d2e6a6c407f44127de77e981b004fd5cce6e998a942a"),
    "filings": (73, "2d9a93926e52d4e2f5f18e13d68fbdd60e14282f94df4e1c4a3f7b81daf6d95d"),
}
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close"]
AUDIT_COLUMNS = ["table", "id", "symbol", "date", "column", "rule", "reason", "status"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(name, frame):
    """Reject structural/numeric defects; never silently drop or fill records."""
    require(not frame.isna().any().any(), f"{name}: null values")
    require(frame.id.is_unique, f"{name}: duplicate IDs")
    require(not frame.duplicated(["symbol", "date"]).any(), f"{name}: duplicate company/date")
    require(frame.symbol.isin(SYMBOLS).all(), f"{name}: unexpected symbol")
    require(frame.id.dtype == np.dtype("int32"), f"{name}: ID type changed")
    require(frame.date.map(lambda value: type(value) is date).all(), f"{name}: expected date-only values")
    parsed = pd.to_datetime(frame.date, errors="raise")
    require(parsed.dt.date.equals(frame.date), f"{name}: date conversion changed values")
    for column in frame.select_dtypes(include=["str", "object"]):
        if column != "date":
            require(frame[column].map(lambda value: isinstance(value, str)).all(), f"{name}.{column}: non-string")
            require(frame[column].str.strip().ne("").all(), f"{name}.{column}: blank text")
    if name == "filings":
        require(frame.document_type.isin(["10-K", "10-Q"]).all(), "filings: unexpected document type")
    if name == "prices":
        require(all(frame[c].dtype == np.dtype("float64") for c in PRICE_COLUMNS), "prices: price type changed")
        require(np.isfinite(frame[PRICE_COLUMNS]).all().all(), "prices: nonfinite price")
        require(frame[PRICE_COLUMNS].gt(0).all().all(), "prices: nonpositive price")
        require(((frame.low <= frame.open) & (frame.open <= frame.high)
                 & (frame.low <= frame.close) & (frame.close <= frame.high)).all(), "prices: invalid OHLC range")
        require(frame.volume.dtype == np.dtype("int64"), "prices: volume must be int64")
        require(frame.volume.ge(0).all(), "prices: negative volume")


def clean_table(name, frame):
    result = frame.copy(deep=True)
    if name == "news":
        result["highlights"] = result.highlights.str.strip()
    elif name == "filings":
        for column in ["mda_content", "risk_content"]:
            result[column] = result[column].map(lambda value: html.unescape(value).strip())
    return result


def review_flags(tables):
    flags = []

    def add(name, row, column, rule, reason):
        flags.append(dict(table=name, id=int(row.id), symbol=row.symbol, date=row.date,
                          column=column, rule=rule, reason=reason, status="needs_review"))

    news = tables["news"]
    for row in news[news.highlights.str.len() < 100].itertuples():
        add("news", row, "highlights", "short_summary", "Fewer than 100 characters; ID 543 was inspected and is incomplete. Retained unchanged.")
    # These are manual findings from the pinned snapshot, not a general detector.
    for record_id, rule, reason in [
        (1005, "apparent_truncation", "Inspected text ends mid-sentence with an opening quotation mark. Retained unchanged."),
        (2, "timing_uncertainty", "Inspected summary describes a Sunday closing price absent from the price table. Factual accuracy unresolved."),
    ]:
        row = next(news[news.id == record_id].itertuples())
        add("news", row, "highlights", rule, reason)
    prices = tables["prices"].sort_values(["symbol", "date"])
    returns = prices.groupby("symbol").adj_close.pct_change(fill_method=None)
    previous_dates = prices.groupby("symbol").date.shift()
    for index in prices.index[returns.abs() > 0.20]:
        add("prices", prices.loc[index], "adj_close", "large_return",
            f"Adjusted-close return {returns.loc[index]:.8%} since {previous_dates.loc[index]}; exceeds 20% review threshold. Retained unchanged.")
    for row in prices[prices.volume == 0].itertuples():
        add("prices", row, "volume", "zero_volume", "Zero volume retained for investigation.")
    return pd.DataFrame(flags, columns=AUDIT_COLUMNS).sort_values(["table", "id", "rule"]).reset_index(drop=True)


def verify_records(raw, cleaned, flags):
    checks = []
    for name, record_id, expectation in [
        ("news", 543, "Unchanged text with short/incomplete-summary flag"),
        ("news", 1005, "Unchanged text with apparent-truncation flag"),
        ("filings", 1, "Both excerpts equal one HTML decode followed by outer trimming"),
        ("filings", 66, "Short risk cross-reference retained after decode/trim"),
        ("prices", 4, "All values unchanged; adjusted close remains below daily low"),
    ]:
        before = raw[name].set_index("id").loc[record_id]
        after = cleaned[name].set_index("id").loc[record_id]
        if name == "news":
            passed = before.equals(after) and ((flags.table == name) & (flags.id == record_id)).any()
        elif name == "filings":
            passed = all(after[c] == html.unescape(before[c]).strip() for c in ["mda_content", "risk_content"])
        else:
            passed = before.equals(after) and after.adj_close < after.low
        require(passed, f"Record verification failed: {name} ID {record_id}")
        checks.append(dict(table=name, id=record_id, expected=expectation, passed=bool(passed)))
    return checks


def run(output_dir=ROOT / "cleaned"):
    source = ROOT / "data"
    output = Path(output_dir).resolve()
    require(not output.is_relative_to(source.resolve()) and not source.resolve().is_relative_to(output),
            "Output must be separate from the raw data directory and its ancestors")
    manifest_path = source / "manifest.json"
    manifest_hash = sha256(manifest_path)
    source_manifest = json.loads(manifest_path.read_text())
    raw, cleaned, schemas, stats = {}, {}, {}, {}
    for name in TABLES:
        rows, expected_hash = BASELINE[name]
        path = source / f"{name}.parquet"
        require(sha256(path) == expected_hash, f"{name}: snapshot differs from plan.md; inspect it before changing the baseline")
        arrow = pq.read_table(path)
        schemas[name] = arrow.schema
        raw[name] = arrow.to_pandas()
        require(len(raw[name]) == rows, f"{name}: unexpected row count")
        require(source_manifest["tables"][name]["rows"] == rows
                and source_manifest["tables"][name]["columns"] == list(raw[name]), f"{name}: manifest mismatch")
        validate(name, raw[name])
        cleaned[name] = clean_table(name, raw[name])
        validate(name, cleaned[name])
        pd.testing.assert_frame_equal(cleaned[name], clean_table(name, cleaned[name]), check_exact=True)
        editable = {"news": {"highlights"}, "prices": set(), "filings": {"mda_content", "risk_content"}}[name]
        preserved = [c for c in raw[name] if c not in editable]
        pd.testing.assert_frame_equal(raw[name][preserved], cleaned[name][preserved], check_exact=True)
        changed = {c: int(raw[name][c].ne(cleaned[name][c]).sum()) for c in raw[name]}
        require(sum(changed.values()) == (146 if name == "filings" else 0), f"{name}: unexpected changed-cell count")
        stats[name] = dict(rows_before=rows, rows_after=len(cleaned[name]), rows_removed=0,
                           changed_cells=changed, nulls=cleaned[name].isna().sum().astype(int).to_dict(),
                           duplicate_ids=int(cleaned[name].id.duplicated().sum()),
                           duplicate_company_dates=int(cleaned[name].duplicated(["symbol", "date"]).sum()),
                           schema={field.name: str(field.type) for field in schemas[name]})
    require(source_manifest["revision"] == "52d3ecb97e490a2392717935402cde283e8fa36e", "Unexpected source revision")
    require(int(cleaned["prices"].volume.sum()) == 159456800900, "Volume total changed")
    flags = review_flags(cleaned)
    record_checks = verify_records(raw, cleaned, flags)
    coverage = pd.concat([
        frame.groupby("symbol").agg(rows=("id", "size"), first_date=("date", "min"), last_date=("date", "max"))
        .reset_index().assign(table=name)[["table", "symbol", "rows", "first_date", "last_date"]]
        for name, frame in cleaned.items()
    ], ignore_index=True)
    prices, news, filings = (cleaned[n] for n in ["prices", "news", "filings"])
    price_keys = set(zip(prices.symbol, prices.date))
    absent_news = sum(key not in price_keys for key in zip(news.symbol, news.date))
    price_dates = pd.DatetimeIndex(prices.date.unique())
    weekday_gaps = pd.bdate_range(price_dates.min(), price_dates.max()).difference(price_dates)
    report = dict(
        source=source_manifest, source_sha256={n: BASELINE[n][1] for n in TABLES},
        source_manifest_sha256=manifest_hash,
        environment=dict(pandas=pd.__version__, pyarrow=pa.__version__, numpy=np.__version__),
        tables=stats, review_flags=flags.groupby("rule").size().astype(int).to_dict(),
        record_checks=record_checks, volume_total=int(prices.volume.sum()),
        coverage=dict(news_without_same_date_price=int(absent_news),
                      weekend_news=int(pd.to_datetime(news.date).dt.dayofweek.ge(5).sum()),
                      filings_before_prices=int((filings.date < prices.date.min()).sum()),
                      weekdays_without_prices=weekday_gaps.strftime("%Y-%m-%d").tolist()),
        limitations=["News factual accuracy and completeness are not certified; flags include selected manual findings, not exhaustive text review.",
                     "Date-only news lacks publication times; filing-date meaning is unverified. No predictive/as-of join is provided.",
                     "Absent price dates have not been checked against an exchange calendar; no price rows are imputed.",
                     "Repeated filing risk text and short annual-report cross-references are retained."],
        checks=dict(raw_preserved=True, schema_preserved=True, idempotent=True,
                    untouched_columns_equal=True, parquet_roundtrip=True, csv_roundtrip=True),
    )
    # Stage and verify all exports before publishing any of them.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cleaning-", dir=output.parent) as temp:
        stage = Path(temp)
        for name, frame in cleaned.items():
            table = pa.Table.from_pandas(frame, schema=schemas[name], preserve_index=False).replace_schema_metadata(schemas[name].metadata)
            pq.write_table(table, stage / f"{name}.parquet")
            exported = pq.read_table(stage / f"{name}.parquet")
            require(exported.schema.equals(schemas[name], check_metadata=True), f"{name}: exported schema changed")
            pd.testing.assert_frame_equal(frame, exported.to_pandas(), check_exact=True)
            frame.to_csv(stage / f"{name}.csv", index=False)
            csv_types = {c: frame[c].dtype for c in frame if c != "date"}
            csv = pd.read_csv(stage / f"{name}.csv", dtype=csv_types, keep_default_na=False, float_precision="round_trip")
            csv["date"] = pd.to_datetime(csv.date, format="%Y-%m-%d", errors="raise").dt.date
            pd.testing.assert_frame_equal(frame, csv, check_exact=True)
        flags.to_csv(stage / "review_flags.csv", index=False)
        coverage.to_csv(stage / "coverage.csv", index=False)
        for name in TABLES:
            require(sha256(source / f"{name}.parquet") == BASELINE[name][1], f"{name}: raw file changed during run")
        require(sha256(manifest_path) == manifest_hash, "Source manifest changed during run")
        report["output_sha256"] = {p.name: sha256(p) for p in sorted(stage.iterdir())}
        (stage / "quality_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        (stage / "quality_report.md").write_text(
            "# Cleaning results\n\n"
            "All 6,617 source rows retained. No joins, imputations, numeric corrections, or row removals.\n\n"
            "| Table | Rows | Changed cells |\n| --- | ---: | ---: |\n"
            + "".join(f"| {n} | {len(cleaned[n]):,} | {sum(stats[n]['changed_cells'].values())} |\n" for n in TABLES)
            + f"\nDecoded HTML entities and trimmed outer whitespace in 146 filing excerpt cells. "
            f"News and prices are unchanged. There are {len(flags)} review flags; all flagged records are retained.\n\n"
            "Raw hashes, schemas, unchanged columns, cleanup idempotence, all five record checks, "
            "and exact Parquet/CSV round trips passed. Total volume: 159,456,800,900.\n\n"
            "## Usage and limits\n\n"
            "Use Parquet to retain date and numeric types; CSV exports use ISO dates and quoted multiline text. "
            "Import each table separately. IDs are unique within each table only. See review_flags.csv, coverage.csv, "
            "and quality_report.json for record-level review flags, company coverage, and full validation details.\n\n"
            + "\n".join(f"- {item}" for item in report["limitations"]) + "\n"
        )
        output.mkdir(parents=True, exist_ok=True)
        for path in stage.iterdir():
            require(not (output / path.name).is_symlink(), "Refusing to replace a symlink output")
        for path in stage.iterdir():
            path.replace(output / path.name)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "cleaned")
    args = parser.parse_args()
    result = run(args.output_dir)
    print(f"Wrote cleaned Parquet/CSV tables and audit reports to {args.output_dir.resolve()}")
    print(f"Retained 6,617 rows; changed 146 filing cells; {sum(result['review_flags'].values())} review flags.")
