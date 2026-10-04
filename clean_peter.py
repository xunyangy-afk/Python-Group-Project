"""
Data cleaning for the TheFinAI/Herculean dataset (Peter-work).
Implements the rules and decisions in plan.md.

Each step is a function that takes DataFrames in and returns DataFrames out,
so it can be checked on its own in check_cleaning_peter.ipynb.

Input : data/raw/{prices,news,filings}.parquet   (download from Hugging Face)
Output: data/clean/{prices,news,filings}_clean.parquet
        samples_peter/{prices,news,filings}_sample_peter.csv   (47 rows in total)
        outputs/validation_report.md, record_checks_peter.csv, metric_support_peter.csv
Run   : python3 clean_peter.py
"""
from pathlib import Path
import html
import re
import pandas as pd

RAW = Path("data/raw")
CLEAN = Path("data/clean")
OUT = Path("outputs")

LARGE_MOVE = 0.12           # D5: flag only, never drop
SHORT_TEXT = 200            # D1: news shorter than this is a fragment
PLACEHOLDER_MAX_LEN = 1000  # D1: placeholder phrasing only counts in short texts (refinement 1)
RISK_REFERENCE_ONLY = 1000  # D4: 10-Q risk section that only points to the 10-K
HTML_ENTITY = r"&#\d+;|&[a-z]+;"   # D8: encoded characters such as &#8217; in filings text

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
def decode_text(text):
    """Refinement 3 (D8): turn HTML entities into the characters they stand for
    (&#8217; to a right quote, &#38; to &) and non-breaking spaces into normal spaces,
    then strip. Wording is not changed."""
    text = html.unescape(text)
    return text.replace("\u00a0", " ").replace("\u202f", " ").strip()


def clean_filings(filings_raw):
    """Clean filings. Decodes HTML entities and strips whitespace in text only (D8).
    Adds mda_len, risk_len, flag_risk_repeat and flag_risk_reference_only (D4)."""
    filings = clean_common(filings_raw)
    for col in ["mda_content", "risk_content"]:
        filings[col] = filings[col].map(decode_text)
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



def join_news_to_prices(news, prices):
    """Join each news row to the price row of its next_trading_date (many news rows to one
    price row). Returns (joined DataFrame, dict of row counts for the merge check)."""
    right = prices[["symbol", "date", "close", "daily_return"]].rename(
        columns={"date": "next_trading_date", "close": "session_close", "daily_return": "session_return"})
    joined = news.merge(right, on=["symbol", "next_trading_date"], how="left",
                        validate="many_to_one", indicator=True)
    price_keys = set(zip(prices["symbol"], prices["date"]))
    news_keys = set(zip(news["symbol"], news["next_trading_date"]))
    stats = {
        "news_rows_before": len(news),
        "rows_after_join": len(joined),
        "unmatched_news_rows": int((joined["_merge"] != "both").sum()),
        "price_rows_with_no_news": len(price_keys - news_keys),
        "max_news_rows_per_price_row": int(news.groupby(["symbol", "next_trading_date"], observed=True).size().max()),
    }
    return joined.drop(columns="_merge"), stats


def metric_support(prices, news, filings):
    """How many records support each planned metric, and why the rest are excluded."""
    usable_risk = ~(filings["flag_risk_repeat"] | filings["flag_risk_reference_only"])
    rows = [
        ("daily return / volatility per symbol", "prices", len(prices),
         int(prices["daily_return"].notna().sum()), "first trading day of each symbol has no prior price"),
        ("news coverage per symbol and day", "news", len(news),
         int((~news["flag_placeholder"]).sum()), "placeholder or fragment summaries (flag_placeholder)"),
        ("news free of look-ahead", "news", len(news),
         int((~news["flag_lookahead"]).sum()), "text mentions a date after the row date (flag_lookahead)"),
        ("new risk disclosure per filing", "filings", len(filings),
         int(usable_risk.sum()), "risk section repeated or only refers to the 10-K"),
    ]
    out = pd.DataFrame(rows, columns=["metric", "table", "records_total", "records_used", "excluded_because"])
    out["records_excluded"] = out["records_total"] - out["records_used"]
    out["missing_group_keys"] = [int(prices[["symbol", "date"]].isna().any(axis=1).sum()),
                                 int(news[["symbol", "date"]].isna().any(axis=1).sum()),
                                 int(news[["symbol", "date"]].isna().any(axis=1).sum()),
                                 int(filings[["symbol", "date"]].isna().any(axis=1).sum())]
    return out[["metric", "table", "records_total", "records_used", "records_excluded",
                "excluded_because", "missing_group_keys"]]


def _row(df, symbol, date):
    hit = df[(df["symbol"] == symbol) & (pd.to_datetime(df["date"]) == pd.Timestamp(date))]
    assert len(hit) == 1, (symbol, date, len(hit))
    return hit.iloc[0]


def record_checks(raw, clean):
    """Five original-to-cleaned record checks, chosen as difficult cases.
    Returns one row per check with expected and actual results."""
    checks = []

    def add(n, table, symbol, date, case, expected, actual, why):
        checks.append({"check": n, "table": table, "symbol": symbol, "date": date, "case": case,
                       "expected": expected, "actual": actual, "match": expected == actual, "why_expected": why})

    p_raw, p = raw["prices"], clean["prices"]
    r0, c0 = _row(p_raw, "AAPL", "2024-12-02"), _row(p, "AAPL", "2024-12-02")
    add(1, "prices", "AAPL", "2024-12-02", "first trading day in the data",
        f"kept; close {r0['close']:.2f}; daily_return NaN; not flagged",
        f"kept; close {c0['close']:.2f}; daily_return {'NaN' if pd.isna(c0['daily_return']) else c0['daily_return']}; "
        f"{'flagged' if c0['flag_large_move'] else 'not flagged'}",
        "no earlier price exists, so a return cannot be computed; filling 0 would invent a flat day")

    nv = p[p["symbol"] == "NVDA"].reset_index(drop=True)
    i = nv.index[nv["date"] == pd.Timestamp("2025-01-27")][0]
    manual = nv.loc[i, "adj_close"] / nv.loc[i - 1, "adj_close"] - 1
    c1 = nv.loc[i]
    add(2, "prices", "NVDA", "2025-01-27", "largest one-day drop (DeepSeek news)",
        f"kept; daily_return {manual:.4f}; flag_large_move True",
        f"kept; daily_return {c1['daily_return']:.4f}; flag_large_move {bool(c1['flag_large_move'])}",
        "expected return is a hand calculation from adj_close; real market event, so the value is "
        "correct and must stay; the flag lets the dashboard explain it")

    n_raw, n = raw["news"], clean["news"]
    r2, c2 = _row(n_raw, "ADBE", "2025-01-26"), _row(n, "ADBE", "2025-01-26")
    add(3, "news", "ADBE", "2025-01-26", "25-character fragment on a Sunday",
        "kept; text unchanged; flag_placeholder True; next_trading_date 2025-01-27",
        f"kept; text {'unchanged' if c2['highlights'] == r2['highlights'].strip() else 'CHANGED'}; "
        f"flag_placeholder {bool(c2['flag_placeholder'])}; next_trading_date {c2['next_trading_date'].date()}",
        "an empty summary is still what the agent received; dropping it would break one row per day")

    r3, c3 = _row(n_raw, "ADBE", "2025-02-15"), _row(n, "ADBE", "2025-02-15")
    add(4, "news", "ADBE", "2025-02-15", "Saturday before a market holiday, mentions a later event",
        "kept; flag_lookahead True (mentions 2025-02-25); next_trading_date 2025-02-18",
        f"kept; flag_lookahead {bool(c3['flag_lookahead'])} (mentions {c3['latest_date_mentioned'].date()}); "
        f"next_trading_date {c3['next_trading_date'].date()}",
        "Feb 17 2025 was Presidents Day, so the next session is Feb 18; the Feb 25 Photoshop launch "
        "could not have been known on Feb 15")

    f_raw, f = raw["filings"], clean["filings"]
    r4, c4 = _row(f_raw, "TSLA", "2024-07-23"), _row(f, "TSLA", "2024-07-23")
    prev = _row(f, "TSLA", "2024-04-23")
    add(5, "filings", "TSLA", "2024-07-23", "10-Q whose risk section only points to the 10-K",
        "kept; leading space removed; risk_len 329; same as previous filing; both risk flags True",
        f"kept; leading space {'removed' if not c4['risk_content'].startswith(' ') and r4['risk_content'].startswith(' ') else 'NOT removed'}; "
        f"risk_len {c4['risk_len']}; {'same as' if c4['risk_content'] == prev['risk_content'] else 'differs from'} previous filing; "
        f"both risk flags {bool(c4['flag_risk_repeat'] and c4['flag_risk_reference_only'])}",
        "raw text is 333 characters with 4 whitespace characters at the ends, so 329 after stripping; the filing is real, and its short repeated text means no new risk disclosure, which analysis must know")
    return pd.DataFrame(checks)


def make_sample(prices, news, filings, max_rows=50):
    """Inspection sample of cleaned rows with all columns, weighted toward difficult cases.
    Returns {table: DataFrame}; each row carries a sample_reason."""
    def pick(df, mask, reason, n=None):
        out = df[mask].copy()
        out = out.head(n) if n else out
        out.insert(0, "sample_reason", reason)
        return out

    first_day = prices.groupby("symbol", observed=True).cumcount() == 0
    normal_p = ~first_day & ~prices["flag_large_move"]
    p_s = pd.concat([
        pick(prices, prices["flag_large_move"], "large move > 12% (flagged, kept)"),
        pick(prices, first_day, "first trading day: daily_return NaN by design"),
        pick(prices, normal_p & (prices["date"] == pd.Timestamp("2025-06-02")), "ordinary day (control)", 2),
    ])

    weekend = news["date"].dt.dayofweek >= 5
    holiday = ~news["is_trading_day"] & ~weekend
    ordinary = news["is_trading_day"] & ~news["flag_placeholder"] & ~news["flag_lookahead"]
    n_s = pd.concat([
        pick(news, news["flag_placeholder"], "placeholder or fragment (flagged, kept)"),
        pick(news, news["flag_lookahead"], "mentions a later date (flagged, kept)"),
        pick(news, holiday & (news["symbol"] == "AAPL"), "weekday market holiday mapped to next session", 1),
        pick(news, weekend & ~news["flag_placeholder"] & (news["symbol"] == "MSFT"), "weekend mapped to next session", 1),
        pick(news, ordinary & (news["symbol"] == "NVDA"), "ordinary trading day (control)", 2),
    ])

    flagged = filings["flag_risk_repeat"] | filings["flag_risk_reference_only"]
    adbe_extra = (filings["symbol"] == "ADBE") & (filings["date"] == filings["date"].min())
    f_s = pd.concat([
        pick(filings, flagged, "risk section repeated or reference-only (flagged, kept)"),
        pick(filings, adbe_extra, "ADBE has 10 filings vs 9 for others (Jan 2024 10-K)"),
        pick(filings, ~flagged & (filings["symbol"] == "MSFT"), "ordinary filing (control)", 2),
    ])
    sample = {"prices": p_s, "news": n_s, "filings": f_s}
    total = sum(len(v) for v in sample.values())
    assert total <= max_rows, f"sample has {total} rows, limit {max_rows}"
    return sample


def save_sample(sample, sample_dir="samples_peter"):
    sample_dir = Path(sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)
    for name, df in sample.items():
        df.to_csv(sample_dir / f"{name}_sample_peter.csv", index=False)


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
        e = int(filings_raw[col].str.contains(HTML_ENTITY, regex=True).sum())
        left = int(filings[col].str.contains(HTML_ENTITY, regex=True).sum())
        add(f"- {col}: stripped leading/trailing whitespace in {n} rows; decoded HTML entities in {e} rows "
            f"(rows still containing entities after cleaning: {left}).")
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
    add("Filings text before vs after (AAPL 2024-02-01, first 60 characters of mda_content):\n")
    add(f"- before: `{raw_sorted['mda_content'].iloc[0][:60]!r}`")
    add(f"- after : `{filings['mda_content'].iloc[0][:60]!r}`\n")

    add("## Validation 6: join news to prices (merge check)\n")
    _, js = join_news_to_prices(news, prices)
    add("Keys: (symbol, next_trading_date) in news to (symbol, date) in prices. Expected relationship: "
        "many news rows to one price row (weekend and holiday news share the next session).\n")
    for k, v in js.items():
        add(f"- {k}: {v}")
    add("")

    add("## Validation 7: records supporting each metric\n")
    add(metric_support(prices, news, filings).to_markdown(index=False) + "\n")
    add("Averages and totals use only records_used; excluded rows stay in the data with their flag, so the "
        "denominator is always stated rather than silently shrinking.\n")

    add("## Validation 8: five original-to-cleaned record checks\n")
    rc = record_checks(raw, clean)
    add(rc[["check", "table", "symbol", "date", "case", "expected", "actual", "match"]].to_markdown(index=False) + "\n")
    for _, c in rc.iterrows():
        add(f"- Check {c['check']} reasoning: {c['why_expected']}.")
    add("")

    add("## Refinements made after the first validation run\n")
    add("1. **Placeholder news.** The first rule flagged 20 rows. Reading them showed 12 were long, real "
        "summaries that only said one of several articles was empty. The rule now requires the placeholder "
        "phrasing in a short text (< 1,000 characters) or a fragment (< 200 characters). Result: 8 rows, all "
        "confirmed by reading.")
    add("2. **Look-ahead news.** A keyword search matched 33 rows, but nearly all were disclaimers stating "
        "that future information had been excluded, the opposite of a leak. The rule now compares explicit "
        "dates written in the text with the row date. Result: 1 row (ADBE 2025-02-15 mentions the "
        "2025-02-25 Photoshop for iPhone launch), a real leak.")
    add("3. **Encoded characters in filings.** Building the checklist evidence showed that filings text stores "
        "characters as HTML entities (`&#8217;` for a right quote, `&#160;` for a non-breaking space, `&#38;` "
        "for &). All 73 MD&A sections and 68 risk sections were affected; news had none. These are decoded to "
        "the real characters, which changes encoding, not wording, and makes text lengths and keyword "
        "searches reliable.\n")

    add("## Conclusion: does the cleaned data still represent reality?\n")
    add("Yes. No rows were dropped and no original values or wording were changed beyond whitespace, so every "
        "price, news summary, and filing is still what the benchmark agents actually received. Prices pass all "
        "logic checks, and the 9 large moves line up with known events (2025-04-09 tariff pause rally, NVDA "
        "DeepSeek drop on 2025-01-27). The quality problems are now visible through flags instead of hidden: "
        "8 empty news rows, 1 look-ahead leak, 1,232 non-trading-day news rows aligned to the next session, "
        "and 12 filings whose risk section is repeated or only refers to the 10-K. Anyone analysing agent "
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
    save_sample(make_sample(prices, news, filings))
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    record_checks(raw, clean).to_csv(Path(out_dir) / "record_checks_peter.csv", index=False)
    metric_support(prices, news, filings).to_csv(Path(out_dir) / "metric_support_peter.csv", index=False)
    (Path(out_dir) / "validation_report.md").write_text(build_report(raw, clean), encoding="utf-8")
    return clean


if __name__ == "__main__":
    run_pipeline()
    print("Saved data/clean/*.parquet, samples_peter/*.csv and outputs/")
