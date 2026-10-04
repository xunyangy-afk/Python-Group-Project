"""
Data cleaning for the TheFinAI/Herculean dataset (Peter-work).
Implements the rules and decisions in plan.md.

Each step is a function that takes DataFrames in and returns DataFrames out,
so it can be checked on its own in check_cleaning_peter.ipynb.

Input : data/raw/{prices,news,filings}.parquet   (download from Hugging Face)
Output: data/clean/{prices,news,filings}_clean.parquet
        outputs/validation_report.md
Run   : python3 clean_peter.py
"""
from pathlib import Path
import re
import pandas as pd

RAW = Path("data/raw")
CLEAN = Path("data/clean")
OUT = Path("outputs")

LARGE_MOVE = 0.12           # D5: flag only, never drop
SHORT_TEXT = 200            # D1: news shorter than this is a fragment
PLACEHOLDER_MAX_LEN = 1000  # D1: placeholder phrasing only counts in short texts (refinement 1)
RISK_REFERENCE_ONLY = 1000  # D4: 10-Q risk section that only points to the 10-K

PLACEHOLDER_PATTERN = (
    r"no substantive|cannot be (?:identified|constructed)|no basis to summarize"
    r"|I can.t provide|could not be retrieved|no (?:actual )?[A-Z]{3,5}[- ]related"
    r"|no [A-Z]{3,5} (?:content|coverage|news)|data-availability limitation"
    r"|does not contain any actual"
)
MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December"
          "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec")
ISO_DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
TEXT_DATE = re.compile(r"\b(" + MONTHS + r")\.? (\d{1,2}),? (20\d\d)\b")


# ------------------------------------------------------------------ loading
def load_raw(raw_dir=RAW):
    """Read the three raw parquet files. Returns (prices_raw, news_raw, filings_raw)."""
    raw_dir = Path(raw_dir)
    return (
        pd.read_parquet(raw_dir / "prices.parquet"),
        pd.read_parquet(raw_dir / "news.parquet"),
        pd.read_parquet(raw_dir / "filings.parquet"),
    )


# ------------------------------------------------------------------ shared
def clean_common(df):
    """Rules shared by all three tables: id to int64, symbol stripped/uppercase/category,
    date to datetime64, rows sorted by symbol then date. Never drops rows."""
    df = df.copy()
    df["id"] = df["id"].astype("int64")
    df["symbol"] = df["symbol"].str.strip().str.upper().astype("category")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def latest_date_mentioned(text):
    """Latest explicit calendar date written in the text (ISO or 'Month D, YYYY'), else NaT."""
    found = [pd.to_datetime(d, errors="coerce") for d in ISO_DATE.findall(text)]
    found += [pd.to_datetime(f"{m} {d} {y}", errors="coerce") for m, d, y in TEXT_DATE.findall(text)]
    found = [d for d in found if pd.notna(d)]
    return max(found) if found else pd.NaT


# ------------------------------------------------------------------ prices
def clean_prices(prices_raw):
    """Clean prices. Adds daily_return (from adj_close, D6) and flag_large_move (D5)."""
    prices = clean_common(prices_raw)
    prices["daily_return"] = prices.groupby("symbol", observed=True)["adj_close"].pct_change()
    prices["flag_large_move"] = prices["daily_return"].abs() > LARGE_MOVE
    return prices


def trading_calendar(prices):
    """Sorted Series of unique trading dates taken from the cleaned prices table."""
    return pd.Series(sorted(prices["date"].unique()), name="trading_date")


# ------------------------------------------------------------------ news
def clean_news(news_raw, trading_days):
    """Clean news. Wording is never edited (D3). Adds text_len, flag_placeholder (D1),
    latest_date_mentioned, flag_lookahead (D3), is_trading_day and next_trading_date (D2)."""
    news = clean_common(news_raw)
    news["highlights"] = news["highlights"].str.strip()
    news["text_len"] = news["highlights"].str.len()

    # Refinement 1: placeholder phrasing only counts in short texts; long summaries that
    # mention one empty article are real content.
    phrase_hit = news["highlights"].str.contains(PLACEHOLDER_PATTERN, case=False, regex=True)
    news["flag_placeholder"] = (
        (phrase_hit & (news["text_len"] < PLACEHOLDER_MAX_LEN))
        | (news["text_len"] < SHORT_TEXT)
    )

    # Refinement 2: compare explicit dates in the text with the row date (keyword search
    # mostly caught disclaimers saying future info was excluded).
    news["latest_date_mentioned"] = news["highlights"].map(latest_date_mentioned)
    news["flag_lookahead"] = news["latest_date_mentioned"] > news["date"]

    calendar = pd.DataFrame({"next_trading_date": trading_days.values})
    news["is_trading_day"] = news["date"].isin(calendar["next_trading_date"])
    aligned = pd.merge_asof(
        news[["date"]].reset_index().sort_values("date"),
        calendar.assign(date=calendar["next_trading_date"]),
        on="date",
        direction="forward",
    ).set_index("index").sort_index()
    news["next_trading_date"] = aligned["next_trading_date"]
    return news


# ------------------------------------------------------------------ filings
def clean_filings(filings_raw):
    """Clean filings. Strips whitespace in text only. Adds mda_len, risk_len,
    flag_risk_repeat and flag_risk_reference_only (D4)."""
    filings = clean_common(filings_raw)
    for col in ["mda_content", "risk_content"]:
        filings[col] = filings[col].str.strip()
    filings["document_type"] = filings["document_type"].str.strip().astype("category")
    filings["mda_len"] = filings["mda_content"].str.len()
    filings["risk_len"] = filings["risk_content"].str.len()
    prev_risk = filings.groupby("symbol", observed=True)["risk_content"].shift()
    filings["flag_risk_repeat"] = filings["risk_content"] == prev_risk
    filings["flag_risk_reference_only"] = filings["risk_len"] < RISK_REFERENCE_ONLY
    return filings


# ------------------------------------------------------------------ validation
def profile(df, name):
    """One-row summary of a table: rows, missing, duplicates, symbols."""
    return {
        "table": name,
        "rows": len(df),
        "missing": int(df.isna().sum().sum()),
        "dup_id": int(df["id"].duplicated().sum()),
        "dup_symbol_date": int(df.duplicated(["symbol", "date"]).sum()),
        "symbols": df["symbol"].nunique(),
    }


def compare_profiles(raw_tables, clean_tables):
    """Before/after DataFrame for {name: df} dicts with the same keys."""
    rows = []
    for name in raw_tables:
        b, a = profile(raw_tables[name], name), profile(clean_tables[name], name)
        rows.append({"table": name, **{f"{k}_before": b[k] for k in b if k != "table"},
                     **{f"{k}_after": a[k] for k in a if k != "table"}})
    return pd.DataFrame(rows).set_index("table")


def ohlc_violations(prices):
    """Number of rows where high/low are inconsistent with open/close."""
    bad = ((prices["high"] < prices[["open", "close", "low"]].max(axis=1))
           | (prices["low"] > prices[["open", "close", "high"]].min(axis=1)))
    return int(bad.sum())


def flag_summary(prices, news, filings):
    """Flag counts by symbol across the three cleaned tables, with a TOTAL row."""
    flags = pd.concat([
        prices.groupby("symbol", observed=True)["flag_large_move"].sum(),
        news.groupby("symbol", observed=True)[["flag_placeholder", "flag_lookahead"]].sum(),
        news.groupby("symbol", observed=True)["is_trading_day"]
            .apply(lambda s: int((~s).sum())).rename("non_trading_news"),
        filings.groupby("symbol", observed=True)[["flag_risk_repeat", "flag_risk_reference_only"]].sum(),
    ], axis=1).astype(int)
    flags.loc["TOTAL"] = flags.sum()
    return flags


# ------------------------------------------------------------------ output
def save_clean(prices, news, filings, clean_dir=CLEAN):
    clean_dir = Path(clean_dir)
    clean_dir.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(clean_dir / "prices_clean.parquet", index=False)
    news.to_parquet(clean_dir / "news_clean.parquet", index=False)
    filings.to_parquet(clean_dir / "filings_clean.parquet", index=False)


def build_report(raw, clean):
    """Markdown validation report. raw and clean are {name: df} dicts."""
    prices, news, filings = clean["prices"], clean["news"], clean["filings"]
    filings_raw = raw["filings"]
    r = []
    add = r.append

    add("# Validation Report (Peter-work)\n")
    add("Generated by `clean_peter.py`. Rules and decisions come from `plan.md`. "
        "Each function is checked in `check_cleaning_peter.ipynb`.\n")

    add("## Step 1: prices")
    add(f"- Converted date to datetime64, symbol to category. Rows {len(raw['prices'])} -> {len(prices)}.")
    add(f"- Added daily_return from adj_close (D6). NaN by design on first day of each symbol: "
        f"{int(prices['daily_return'].isna().sum())} rows.")
    add(f"- flag_large_move (|return| > {LARGE_MOVE:.0%}, D5): {int(prices['flag_large_move'].sum())} rows, kept.\n")

    add("## Step 2: news")
    phrase_hit = int(news["highlights"].str.contains(PLACEHOLDER_PATTERN, case=False, regex=True).sum())
    add("- Stripped whitespace only; wording untouched (D3).")
    add(f"- Placeholder phrasing found in {phrase_hit} rows; only short ones count (refinement 1).")
    add(f"- flag_placeholder (D1): {int(news['flag_placeholder'].sum())} rows, kept.")
    add(f"- flag_lookahead (D3): {int(news['flag_lookahead'].sum())} row(s) mention an explicit later date, kept (refinement 2).")
    add(f"- Non-trading-day rows (D2): {int((~news['is_trading_day']).sum())}, kept; mapped to next_trading_date "
        f"(missing after mapping: {int(news['next_trading_date'].isna().sum())}).\n")

    add("## Step 3: filings")
    for col in ["mda_content", "risk_content"]:
        n = int((filings_raw[col] != filings_raw[col].str.strip()).sum())
        add(f"- Stripped leading/trailing whitespace in {col}: {n} rows.")
    bad_types = set(filings["document_type"].unique()) - {"10-K", "10-Q"}
    add(f"- document_type values outside {{10-K, 10-Q}}: {sorted(bad_types) or 'none'}.")
    add(f"- flag_risk_repeat (D4): {int(filings['flag_risk_repeat'].sum())} rows, kept.")
    add(f"- flag_risk_reference_only (D4): {int(filings['flag_risk_reference_only'].sum())} rows, kept.\n")

    add("## Validation 1: rows, missing values, duplicates (before -> after)\n")
    add("| Table | Rows | Missing | Dup id | Dup symbol+date | Symbols |")
    add("|---|---|---|---|---|---|")
    comp = compare_profiles(raw, clean)
    for name, c in comp.iterrows():
        add(f"| {name} | {c.rows_before} -> {c.rows_after} | {c.missing_before} -> {c.missing_after} | "
            f"{c.dup_id_before} -> {c.dup_id_after} | {c.dup_symbol_date_before} -> {c.dup_symbol_date_after} | "
            f"{c.symbols_before} -> {c.symbols_after} |")
    add("\nThe 8 new missing values in prices are the first-day daily_return of each symbol (expected). "
        f"The {int(news['latest_date_mentioned'].isna().sum())} new missing values in news are NaT in "
        "latest_date_mentioned for texts that contain no explicit date (expected). "
        "No original column gained or lost missing values.\n")

    add("## Validation 2: categorical columns\n")
    add(f"- symbol: {', '.join(prices['symbol'].cat.categories)}")
    for name, df in clean.items():
        add(f"- rows per symbol, {name}: {df['symbol'].value_counts().sort_index().to_dict()}")
    add(f"- document_type: {filings['document_type'].value_counts().to_dict()}\n")

    add("## Validation 3: numeric ranges\n")
    num = prices[["open", "high", "low", "close", "adj_close", "volume", "daily_return"]].describe().T
    add(num[["min", "50%", "max"]].round(4).to_markdown() + "\n")
    add(f"- OHLC logic violations: {ohlc_violations(prices)}")
    add(f"- news text_len min / median / max: {news['text_len'].min()} / {int(news['text_len'].median())} / {news['text_len'].max()}")
    add(f"- filings risk_len min / median / max: {filings['risk_len'].min()} / {int(filings['risk_len'].median())} / {filings['risk_len'].max()}\n")

    add("## Validation 4: flag counts by symbol\n")
    add(flag_summary(prices, news, filings).to_markdown() + "\n")

    add("## Validation 5: example rows\n")
    add("Large moves (kept, flagged):\n")
    add(prices.loc[prices["flag_large_move"], ["symbol", "date", "close", "daily_return"]]
        .assign(date=lambda d: d["date"].dt.date, daily_return=lambda d: d["daily_return"].round(4))
        .to_markdown(index=False) + "\n")
    add("Placeholder news (all, text truncated):\n")
    add(news.loc[news["flag_placeholder"], ["symbol", "date", "text_len", "highlights"]]
        .assign(date=lambda d: d["date"].dt.date,
                highlights=lambda d: d["highlights"].str.replace("\n", " ").str[:90] + "...")
        .to_markdown(index=False) + "\n")
    add("Look-ahead news (all):\n")
    add(news.loc[news["flag_lookahead"], ["symbol", "date", "latest_date_mentioned"]]
        .assign(date=lambda d: d["date"].dt.date, latest_date_mentioned=lambda d: d["latest_date_mentioned"].dt.date)
        .to_markdown(index=False) + "\n")
    add("Weekend news mapped to next trading day (first 3):\n")
    add(news.loc[~news["is_trading_day"], ["symbol", "date", "next_trading_date"]].head(3)
        .assign(date=lambda d: d["date"].dt.date, next_trading_date=lambda d: d["next_trading_date"].dt.date)
        .to_markdown(index=False) + "\n")
    raw_sorted = filings_raw.sort_values(["symbol", "date"]).reset_index(drop=True)
    add("Filings before vs after (first 3 characters of mda_content):\n")
    add(f"- before: {[raw_sorted['mda_content'].iloc[i][:3] for i in range(3)]}")
    add(f"- after : {[filings['mda_content'].iloc[i][:3] for i in range(3)]}\n")

    add("## Refinements made after the first validation run\n")
    add("1. **Placeholder news.** The first rule flagged 20 rows. Reading them showed 12 were long, real "
        "summaries that only said one of several articles was empty. The rule now requires the placeholder "
        "phrasing in a short text (< 1,000 characters) or a fragment (< 200 characters). Result: 8 rows, all "
        "confirmed by reading.")
    add("2. **Look-ahead news.** A keyword search matched 33 rows, but nearly all were disclaimers stating "
        "that future information had been excluded, the opposite of a leak. The rule now compares explicit "
        "dates written in the text with the row date. Result: 1 row (ADBE 2025-02-15 mentions the "
        "2025-02-25 Photoshop for iPhone launch), a real leak.\n")

    add("## Conclusion: does the cleaned data still represent reality?\n")
    add("Yes. No rows were dropped and no original values or wording were changed beyond whitespace, so every "
        "price, news summary, and filing is still what the benchmark agents actually received. Prices pass all "
        "logic checks, and the 9 large moves line up with known events (2025-04-09 tariff pause rally, NVDA "
        "DeepSeek drop on 2025-01-27). The quality problems are now visible through flags instead of hidden: "
        "8 empty news rows, 1 look-ahead leak, 1,232 non-trading-day news rows aligned to the next session, "
        "and 16 filings whose risk section is repeated or only refers to the 10-K. Anyone analysing agent "
        "report quality should filter or control for these flags rather than treat all rows as equal.")
    return "\n".join(r) + "\n"


# ------------------------------------------------------------------ pipeline
def run_pipeline(raw_dir=RAW, clean_dir=CLEAN, out_dir=OUT):
    """Full run: load, clean, save, write report. Returns the cleaned tables as a dict."""
    prices_raw, news_raw, filings_raw = load_raw(raw_dir)
    prices = clean_prices(prices_raw)
    news = clean_news(news_raw, trading_calendar(prices))
    filings = clean_filings(filings_raw)

    raw = {"prices": prices_raw, "news": news_raw, "filings": filings_raw}
    clean = {"prices": prices, "news": news, "filings": filings}
    save_clean(prices, news, filings, clean_dir)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "validation_report.md").write_text(build_report(raw, clean), encoding="utf-8")
    return clean


if __name__ == "__main__":
    run_pipeline()
    print("Saved data/clean/*.parquet and outputs/validation_report.md")
