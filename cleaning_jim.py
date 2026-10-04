# Cleaning and verification for the Herculean dataset
from IPython.display import display

import sys
import pandas as pd

print(sys.executable)

# Next notebook cell

from pathlib import Path
import pandas as pd

data_dir = Path("data/raw")

print("Notebook folder:", Path.cwd())
print("Data files:", [p.name for p in data_dir.glob("*.parquet")])

# Next notebook cell

print([p.name for p in data_dir.glob("*.parquet")])

# Next notebook cell

prices_raw = pd.read_parquet(data_dir / "prices.parquet")
news_raw = pd.read_parquet(data_dir / "news.parquet")
filings_raw = pd.read_parquet(data_dir / "filings.parquet")

print("Prices:", prices_raw.shape)
print("News:", news_raw.shape)
print("Filings:", filings_raw.shape)

# Next notebook cell

prices_raw.head()

# Next notebook cell

prices_raw.info()

# Next notebook cell

prices_raw["symbol"].value_counts(dropna=False)

# Next notebook cell

print("Exact duplicate rows:", prices_raw.duplicated().sum())

print("Repeated IDs:", prices_raw["id"].duplicated().sum())

print(
    "Repeated company-date pairs:",
    prices_raw.duplicated(subset=["symbol", "date"]).sum()
)

# Next notebook cell

dates_check = pd.to_datetime(prices_raw["date"], errors="coerce")

print("Original date value type:", type(prices_raw["date"].iloc[0]))
print("Failed date conversions:",
      (prices_raw["date"].notna() & dates_check.isna()).sum())
print("Earliest date:", dates_check.min())
print("Latest date:", dates_check.max())

# Next notebook cell

price_columns = ["open", "high", "low", "close", "adj_close"]

print("Zero or negative prices by column:")
print(prices_raw[price_columns].le(0).sum())

print("Negative volume:", prices_raw["volume"].lt(0).sum())
print("Zero volume:", prices_raw["volume"].eq(0).sum())

# Next notebook cell

selected_symbols = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"
]

prices_clean = prices_raw.loc[
    prices_raw["symbol"].isin(selected_symbols)
].copy()

prices_clean["date"] = pd.to_datetime(
    prices_clean["date"], errors="raise"
)

prices_clean = prices_clean.sort_values(
    ["symbol", "date"]
).reset_index(drop=True)

# Next notebook cell

print("Original rows:", len(prices_raw))
print("Excluded rows:", (~prices_raw["symbol"].isin(selected_symbols)).sum())
print("Final rows:", len(prices_clean))

print("\nRows per company:")
print(prices_clean["symbol"].value_counts())

print("\nMissing values:")
print(prices_clean.isna().sum())

print("\nRepeated company-date pairs:",
      prices_clean.duplicated(["symbol", "date"]).sum())

# Next notebook cell

original_retained = prices_raw.loc[
    prices_raw["symbol"].isin(selected_symbols)
].sort_values(["symbol", "date"]).reset_index(drop=True)

unchanged_columns = [
    "id", "symbol", "open", "high", "low",
    "close", "adj_close", "volume"
]

assert prices_clean[unchanged_columns].equals(
    original_retained[unchanged_columns]
)

assert prices_clean["date"].dt.date.equals(
    original_retained["date"]
)

print("Retained values and calendar dates are unchanged.")

# Next notebook cell

news_raw.info()
display(news_raw.head(3))

filings_raw.info()
display(filings_raw.head(3))

# Next notebook cell

for name, df in [("News", news_raw), ("Filings", filings_raw)]:
    dates = pd.to_datetime(df["date"], errors="coerce")

    print(f"\n{name}")
    print("Rows per company:")
    print(df["symbol"].value_counts(dropna=False))
    print("Exact duplicate rows:", df.duplicated().sum())
    print("Repeated IDs:", df["id"].duplicated().sum())
    print("Repeated company-date pairs:",
          df.duplicated(["symbol", "date"]).sum())
    print("Failed date conversions:",
          (df["date"].notna() & dates.isna()).sum())
    print("Date range:", dates.min(), "to", dates.max())

# Next notebook cell

print("Blank news highlights:",
      news_raw["highlights"].str.strip().eq("").sum())

for column in ["mda_content", "risk_content"]:
    print(f"Blank {column}:",
          filings_raw[column].str.strip().eq("").sum())

print("\nFiling types:")
print(filings_raw["document_type"].value_counts(dropna=False))

# Next notebook cell

import html

original_text = filings_raw.loc[0, "mda_content"]

print("BEFORE:")
print(original_text[:250])

print("\nAFTER:")
print(html.unescape(original_text)[:250])

# Next notebook cell

import html

news_clean = news_raw.loc[
    news_raw["symbol"].isin(selected_symbols)
].copy()

filings_clean = filings_raw.loc[
    filings_raw["symbol"].isin(selected_symbols)
].copy()

news_clean["date"] = pd.to_datetime(
    news_clean["date"], errors="raise"
)

filings_clean["date"] = pd.to_datetime(
    filings_clean["date"], errors="raise"
)

for column in ["mda_content", "risk_content"]:
    before = filings_clean[column].copy()
    filings_clean[column] = before.map(html.unescape)

    print(f"{column}: {(before != filings_clean[column]).sum()} records changed")

news_clean = news_clean.sort_values(
    ["symbol", "date"]
).reset_index(drop=True)

filings_clean = filings_clean.sort_values(
    ["symbol", "date", "id"]
).reset_index(drop=True)

# Next notebook cell

for name, raw, clean in [
    ("News", news_raw, news_clean),
    ("Filings", filings_raw, filings_clean)
]:
    print(f"\n{name}")
    print("Original rows:", len(raw))
    print("Excluded rows:", (~raw["symbol"].isin(selected_symbols)).sum())
    print("Final rows:", len(clean))
    print("Exact duplicates:", clean.duplicated().sum())
    print("Repeated IDs:", clean["id"].duplicated().sum())
    print("Missing values:")
    print(clean.isna().sum())

# Next notebook cell

for raw, clean, columns in [
    (news_raw, news_clean, ["symbol", "highlights"]),
    (filings_raw, filings_clean, ["symbol", "document_type"])
]:
    original = raw.set_index("id").loc[clean["id"]]
    cleaned = clean.set_index("id")

    assert original[columns].equals(cleaned[columns])
    assert pd.to_datetime(original["date"]).equals(cleaned["date"])

print("Retained IDs, unchanged fields, and calendar dates verified.")

# Next notebook cell

invalid_ohlc = (
    (prices_raw["high"] < prices_raw["low"])
    | (prices_raw["open"] > prices_raw["high"])
    | (prices_raw["open"] < prices_raw["low"])
    | (prices_raw["close"] > prices_raw["high"])
    | (prices_raw["close"] < prices_raw["low"])
)

print("Inconsistent price rows:", invalid_ohlc.sum())
display(prices_raw.loc[invalid_ohlc])

# Next notebook cell

prices_analysis = prices_clean.sort_values(
    ["symbol", "date"]
).copy()

prices_analysis["daily_return"] = (
    prices_analysis.groupby("symbol")["adj_close"]
    .pct_change(fill_method=None)
)

print("Missing daily returns:",
      prices_analysis["daily_return"].isna().sum())

display(
    prices_analysis[
        ["symbol", "date", "adj_close", "daily_return"]
    ].head()
)

# Next notebook cell

metrics = prices_analysis.groupby("symbol").agg(
    n_prices=("adj_close", "count"),
    n_returns=("daily_return", "count"),
    first_price=("adj_close", "first"),
    last_price=("adj_close", "last"),
    daily_volatility=("daily_return", "std"),
    average_volume=("volume", "mean"),
    n_volume=("volume", "count")
)

metrics["period_return"] = (
    metrics["last_price"] / metrics["first_price"] - 1
)

display(metrics)

# Next notebook cell

original_volume = int(prices_raw["volume"].sum())

excluded_volume = int(
    prices_raw.loc[
        ~prices_raw["symbol"].isin(selected_symbols), "volume"
    ].sum()
)

cleaned_volume = int(prices_clean["volume"].sum())

print("Original volume:", original_volume)
print("Excluded ADBE volume:", excluded_volume)
print("Cleaned volume:", cleaned_volume)

assert original_volume - excluded_volume == cleaned_volume
print("Volume reconciliation passed.")

# Next notebook cell

check_price = prices_raw.loc[
    prices_raw["symbol"].eq("AAPL")
].sort_values("date").iloc[0]

check_excluded = prices_raw.loc[
    prices_raw["symbol"].eq("ADBE")
].sort_values("date").iloc[0]

check_news = news_raw.loc[
    news_raw["symbol"].eq("AAPL")
].sort_values("date").iloc[0]

check_filing = filings_raw.loc[
    filings_raw["symbol"].eq("AAPL")
    & filings_raw["mda_content"].str.contains("&#8217;", regex=False)
].sort_values("date").iloc[0]

check_return = prices_raw.loc[
    prices_raw["symbol"].eq("AMZN")
].sort_values("date").iloc[0]

display(check_price)
display(check_excluded)
display(check_news)
print("Filing ID:", check_filing["id"])
print(check_filing["mda_content"][:250])
display(check_return)

# Next notebook cell

# Get the retained records using their original IDs
actual_price = prices_clean.set_index("id").loc[check_price["id"]]
actual_news = news_clean.set_index("id").loc[check_news["id"]]
actual_filing = filings_clean.set_index("id").loc[check_filing["id"]]
actual_return = prices_analysis.set_index("id").loc[check_return["id"]]

# 1. AAPL price: preserve all numeric values and the calendar date
numeric_columns = ["open", "high", "low", "close", "adj_close", "volume"]

price_pass = (
    actual_price["symbol"] == check_price["symbol"]
    and actual_price["date"].date() == check_price["date"]
    and all(
        actual_price[c] == check_price[c]
        for c in numeric_columns
    )
)

# 2. ADBE price: excluded from the analysis scope
excluded_pass = not prices_clean["id"].eq(check_excluded["id"]).any()

# 3. AAPL news: preserve text and calendar date
news_pass = (
    actual_news["symbol"] == check_news["symbol"]
    and actual_news["date"].date() == check_news["date"]
    and actual_news["highlights"] == check_news["highlights"]
)

# 4. Filing: check the expected decoded phrase
filing_pass = (
    "Management&#8217;s" in check_filing["mda_content"]
    and "Management’s" in actual_filing["mda_content"]
    and "Management&#8217;s" not in actual_filing["mda_content"]
)

# 5. AMZN: the first observation has no prior return
return_pass = (
    actual_return["symbol"] == "AMZN"
    and pd.isna(actual_return["daily_return"])
)

record_checks = pd.DataFrame({
    "record": [
        "Prices ID 1",
        "Prices ID 333",
        "News ID 1",
        "Filings ID 1",
        "Prices ID 665"
    ],
    "expected": [
        "Retained; numeric values and date unchanged",
        "Excluded",
        "Retained; highlights and date unchanged",
        "Management&#8217;s becomes Management’s",
        "Retained; first AMZN return is missing"
    ],
    "actual": [
        f"Date={actual_price['date'].date()}, "
        f"adj_close={actual_price['adj_close']}, "
        f"volume={actual_price['volume']}",
        f"Rows found: {prices_clean['id'].eq(check_excluded['id']).sum()}",
        f"Date={actual_news['date'].date()}, "
        f"text unchanged={actual_news['highlights'] == check_news['highlights']}",
        actual_filing["mda_content"][:100],
        f"daily_return={actual_return['daily_return']}"
    ],
    "matches_expected": [
        price_pass, excluded_pass, news_pass, filing_pass, return_pass
    ]
})

display(record_checks)
assert record_checks["matches_expected"].all()

# Next notebook cell

import math

aapl_original = prices_raw.loc[
    prices_raw["symbol"].eq("AAPL")
].sort_values("date")

previous_price = aapl_original.iloc[0]["adj_close"]
current_price = aapl_original.iloc[1]["adj_close"]

expected_return = current_price / previous_price - 1

actual_daily_return = prices_analysis.set_index("id").loc[
    aapl_original.iloc[1]["id"], "daily_return"
]

print("Previous adjusted close:", previous_price)
print("Current adjusted close:", current_price)
print("Expected return:", expected_return)
print("Actual return:", actual_daily_return)

assert math.isclose(
    expected_return, actual_daily_return,
    rel_tol=1e-12, abs_tol=1e-12
)

print("Numeric return check passed.")

# Next notebook cell

record_checks["original"] = [
    f"Date={check_price['date']}, "
    f"adj_close={check_price['adj_close']}, "
    f"volume={check_price['volume']}",
    f"Symbol={check_excluded['symbol']}, date={check_excluded['date']}",
    f"Date={check_news['date']}; {check_news['highlights'][:150]}",
    check_filing["mda_content"][:100],
    f"First AMZN observation: date={check_return['date']}, "
    f"adj_close={check_return['adj_close']}"
]

record_checks["reason"] = [
    "AAPL is in scope; preserve numeric values and calendar date.",
    "ADBE is outside the seven-company scope.",
    "Keep news even when there is no same-day price observation.",
    "Decode HTML punctuation for readability.",
    "The first observation has no previous price within its company."
]

record_checks = record_checks[
    ["record", "original", "expected", "reason", "actual", "matches_expected"]
]

# Next notebook cell

output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

prices_clean.to_parquet(output_dir / "prices_clean.parquet", index=False)
news_clean.to_parquet(output_dir / "news_clean.parquet", index=False)
filings_clean.to_parquet(output_dir / "filings_clean.parquet", index=False)

prices_analysis.to_parquet(
    output_dir / "prices_analysis.parquet", index=False
)

metrics.to_csv(output_dir / "stock_metrics.csv")
record_checks.to_csv(output_dir / "record_checks.csv", index=False)

print("Cleaned tables and evidence saved.")

# Next notebook cell

sample_dir = Path("samples")
sample_dir.mkdir(exist_ok=True)

price_sample = pd.concat([
    prices_analysis.groupby("symbol").head(2),
    prices_analysis.groupby("symbol").tail(2)
]).drop_duplicates("id").sort_values(["symbol", "date"])

news_sample = news_clean.groupby("symbol").head(1)
filings_sample = filings_clean.groupby("symbol").head(1)

price_sample.to_csv(sample_dir / "prices_sample.csv", index=False)
news_sample.to_csv(sample_dir / "news_sample.csv", index=False)
filings_sample.to_csv(sample_dir / "filings_sample.csv", index=False)

print("Price sample:", len(price_sample))
print("News sample:", len(news_sample))
print("Filings sample:", len(filings_sample))
print("Total:", len(price_sample) + len(news_sample) + len(filings_sample))
