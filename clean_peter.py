"""
Data cleaning for the TheFinAI/Herculean dataset (Peter-work).
Implements the rules and decisions in plan.md.

Vision: a junior equity research analyst decides which of seven mega-cap technology stocks
to prioritize for this week's deep-dive research.
Question: how does company news relate to subsequent price changes and trading volume?

Each step is a function that takes DataFrames in and returns DataFrames out,
so it can be checked on its own in check_cleaning_peter.ipynb.

Input : data/raw/{prices,news,filings}.parquet   (download from Hugging Face)
Output: data/clean/{prices,news,filings}_clean.parquet
        samples_peter/{prices,news,filings}_sample_peter.csv
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

SCOPE_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]  # D7: team vision scope
LARGE_MOVE = 0.12           # D5: flag only, never drop
VOLUME_WINDOW = 20          # D10: trailing sessions for the volume baseline
SHORT_TEXT = 200            # D1: news shorter than this is a fragment
PLACEHOLDER_MAX_LEN = 1000  # D1: placeholder phrasing only counts in short texts (refinement 1)
RISK_REFERENCE_ONLY = 1000  # D4: 10-Q risk section that only points to the 10-K
WEEKEND_GAP_DAYS = 3        # D9: a date this close before the first session still maps to it

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


# ------------------------------------------------------------------ loading and scope
def load_raw(raw_dir=RAW):
    """Read the three raw parquet files. Returns (prices_raw, news_raw, filings_raw)."""
    raw_dir = Path(raw_dir)
    return (
        pd.read_parquet(raw_dir / "prices.parquet"),
        pd.read_parquet(raw_dir / "news.parquet"),
        pd.read_parquet(raw_dir / "filings.parquet"),
    )


def apply_scope(df, symbols=SCOPE_SYMBOLS):
    """D7: keep only the companies in the project vision. Returns (in_scope, excluded);
    the excluded rows are returned, not discarded, so they can be counted and reported."""
    keep = df["symbol"].str.strip().str.upper().isin(symbols)
    return df[keep].copy(), df[~keep].copy()


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


def decode_text(text):
    """Refinement 3 (D8): turn HTML entities into the characters they stand for
    (&#8217; to a right quote, &#38; to &) and non-breaking spaces into normal spaces,
    then strip. Wording is not changed."""
    text = html.unescape(text)
    return text.replace(" ", " ").replace(" ", " ").strip()


def map_to_session(dates, trading_days, strictly_after=False):
    """D9: map each date to a trading session in the calendar.
    strictly_after=False: same day if it is a session, otherwise the next one.
    strictly_after=True : the first session after the date (the 'subsequent' session).
    Returns NaT when the session is outside the data: after the last session, or when the
    date is more than WEEKEND_GAP_DAYS before the first session (its real next session
    is missing from the data)."""
    dates = pd.Series(pd.to_datetime(dates)).reset_index(drop=True)
    days = pd.Series(sorted(trading_days)).reset_index(drop=True)
    pos = days.searchsorted(dates, side="right" if strictly_after else "left")
    out = pd.Series([days.iloc[i] if i < len(days) else pd.NaT for i in pos], dtype="datetime64[ns]")
    too_early = dates < days.iloc[0] - pd.Timedelta(days=WEEKEND_GAP_DAYS)
    out[too_early] = pd.NaT
    return out


# ------------------------------------------------------------------ prices
def clean_prices(prices_raw):
    """Clean prices. Adds daily_return (from adj_close, D6), flag_large_move (D5) and
    volume_ratio_20d: volume divided by the average of the previous 20 sessions (D10)."""
    prices = clean_common(prices_raw)
    g = prices.groupby("symbol", observed=True)
    prices["daily_return"] = g["adj_close"].pct_change()
    prices["flag_large_move"] = prices["daily_return"].abs() > LARGE_MOVE
    baseline = g["volume"].transform(
        lambda v: v.shift(1).rolling(VOLUME_WINDOW, min_periods=VOLUME_WINDOW).mean())
    prices["volume_ratio_20d"] = prices["volume"] / baseline
    return prices


def trading_calendar(prices):
    """Sorted Series of unique trading dates taken from the cleaned prices table."""
    return pd.Series(sorted(prices["date"].unique()), name="trading_date")


# ------------------------------------------------------------------ news
def clean_news(news_raw, trading_days):
    """Clean news. Wording is never edited (D3). Adds text_len, flag_placeholder (D1),
    latest_date_mentioned, flag_lookahead (D3), is_trading_day, next_trading_date (D2)
    and reaction_date, the first session after the news date (D9)."""
    news = clean_common(news_raw)
    news["highlights"] = news["highlights"].str.strip()
    news["text_len"] = news["highlights"].str.len()

    # Refinement 1: placeholder phrasing only counts in short texts.
    phrase_hit = news["highlights"].str.contains(PLACEHOLDER_PATTERN, case=False, regex=True)
    news["flag_placeholder"] = (
        (phrase_hit & (news["text_len"] < PLACEHOLDER_MAX_LEN))
        | (news["text_len"] < SHORT_TEXT)
    )

    # Refinement 2: compare explicit dates in the text with the row date.
    news["latest_date_mentioned"] = news["highlights"].map(latest_date_mentioned)
    news["flag_lookahead"] = news["latest_date_mentioned"] > news["date"]

    news["is_trading_day"] = news["date"].isin(trading_days)
    news["next_trading_date"] = map_to_session(news["date"], trading_days, strictly_after=False).values
    news["reaction_date"] = map_to_session(news["date"], trading_days, strictly_after=True).values
    return news


# ------------------------------------------------------------------ filings
def clean_filings(filings_raw, trading_days):
    """Clean filings. Decodes HTML entities and strips whitespace in text only (D8).
    Adds mda_len, risk_len, flag_risk_repeat, flag_risk_reference_only (D4),
    in_price_window and reaction_date (D9)."""
    filings = clean_common(filings_raw)
    for col in ["mda_content", "risk_content"]:
        filings[col] = filings[col].map(decode_text)
    filings["document_type"] = filings["document_type"].str.strip().astype("category")
    filings["mda_len"] = filings["mda_content"].str.len()
    filings["risk_len"] = filings["risk_content"].str.len()
    prev_risk = filings.groupby("symbol", observed=True)["risk_content"].shift()
    filings["flag_risk_repeat"] = filings["risk_content"] == prev_risk
    filings["flag_risk_reference_only"] = filings["risk_len"] < RISK_REFERENCE_ONLY
    filings["reaction_date"] = map_to_session(filings["date"], trading_days, strictly_after=True).values
    filings["in_price_window"] = filings["reaction_date"].notna()
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


def reconcile_rows(raw_tables, excluded_tables, clean_tables):
    """Row accounting per table: start = excluded by scope + final. Also total volume for prices."""
    rows = []
    for name in raw_tables:
        rows.append({"table": name, "start_rows": len(raw_tables[name]),
                     "excluded_out_of_scope": len(excluded_tables[name]),
                     "other_rows_removed": len(raw_tables[name]) - len(excluded_tables[name]) - len(clean_tables[name]),
                     "final_rows": len(clean_tables[name])})
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
        filings.groupby("symbol", observed=True)["in_price_window"]
            .apply(lambda s: int((~s).sum())).rename("filings_before_price_window"),
    ], axis=1).astype(int)
    flags.loc["TOTAL"] = flags.sum()
    return flags


def join_news_to_prices(news, prices):
    """Attach the subsequent session's return and volume ratio to each news row:
    news (symbol, reaction_date) to prices (symbol, date), many news rows to one price row.
    Returns (joined DataFrame, dict of row counts for the merge check)."""
    right = prices[["symbol", "date", "daily_return", "volume", "volume_ratio_20d"]].rename(columns={
        "date": "reaction_date", "daily_return": "next_return",
        "volume": "next_volume", "volume_ratio_20d": "next_volume_ratio"})
    joined = news.merge(right, on=["symbol", "reaction_date"], how="left",
                        validate="many_to_one", indicator=True)
    no_session = news["reaction_date"].isna()
    stats = {
        "news_rows_before": len(news),
        "rows_after_join": len(joined),
        "news_without_next_session": int(no_session.sum()),
        "unmatched_with_a_session": int(((joined["_merge"] != "both") & ~no_session.values).sum()),
        "max_news_rows_per_price_row": int(news.groupby(["symbol", "reaction_date"], observed=True).size().max()),
    }
    return joined.drop(columns="_merge"), stats


def metric_support(prices, news, filings):
    """How many records support each planned metric, and why the rest are excluded."""
    joined, _ = join_news_to_prices(news, prices)
    usable_news = ~joined["flag_placeholder"] & ~joined["flag_lookahead"]
    rows = [
        ("daily return and volatility per stock", "prices", len(prices),
         int(prices["daily_return"].notna().sum()), "first session of each stock has no prior price"),
        ("volume ratio vs previous 20 sessions", "prices", len(prices),
         int(prices["volume_ratio_20d"].notna().sum()), "first 20 sessions of each stock have no full baseline"),
        ("next-session return after news", "news", len(news),
         int((usable_news & joined["next_return"].notna()).sum()),
         "placeholder or look-ahead news; no next session in the data (last day); or the next session "
         "is the first in the data, which has no return"),
        ("next-session volume ratio after news", "news", len(news),
         int((usable_news & joined["next_volume_ratio"].notna()).sum()),
         "placeholder or look-ahead news, no next session, or next session inside the first 20 sessions"),
        ("price and volume reaction after a filing", "filings", len(filings),
         int(filings["in_price_window"].sum()), "filed before the price data starts (2024-12-02)"),
    ]
    out = pd.DataFrame(rows, columns=["metric", "table", "records_total", "records_used", "excluded_because"])
    out["records_excluded"] = out["records_total"] - out["records_used"]
    out["missing_group_keys"] = [int(t[["symbol", "date"]].isna().any(axis=1).sum())
                                 for t in [prices, prices, news, news, filings]]
    return out[["metric", "table", "records_total", "records_used", "records_excluded",
                "excluded_because", "missing_group_keys"]]


def _row(df, symbol, date):
    hit = df[(df["symbol"].astype(str).str.strip() == symbol) & (pd.to_datetime(df["date"]) == pd.Timestamp(date))]
    assert len(hit) <= 1, (symbol, date, len(hit))
    return hit.iloc[0] if len(hit) else None


def _d(x):
    return "NaT" if pd.isna(x) else str(pd.Timestamp(x).date())


def record_checks(raw, clean):
    """Original-to-cleaned record checks, chosen as difficult cases.
    raw holds the full raw tables, clean the cleaned in-scope tables.
    Returns one row per check with expected and actual results."""
    checks = []

    def add(n, table, symbol, date, case, expected, actual, why):
        checks.append({"check": n, "table": table, "symbol": symbol, "date": date, "case": case,
                       "expected": expected, "actual": actual, "match": expected == actual, "why_expected": why})

    p_raw, p = raw["prices"], clean["prices"]
    r0, c0 = _row(p_raw, "AAPL", "2024-12-02"), _row(p, "AAPL", "2024-12-02")
    add(1, "prices", "AAPL", "2024-12-02", "first session in the data",
        f"kept; close {r0['close']:.2f}; daily_return NaN; volume_ratio_20d NaN",
        f"kept; close {c0['close']:.2f}; daily_return {'NaN' if pd.isna(c0['daily_return']) else c0['daily_return']}; "
        f"volume_ratio_20d {'NaN' if pd.isna(c0['volume_ratio_20d']) else c0['volume_ratio_20d']}",
        "no earlier price or volume exists; filling 0 or 1 would invent a quiet day")

    nv_raw = p_raw[p_raw["symbol"] == "NVDA"].assign(date=lambda d: pd.to_datetime(d["date"])).sort_values("date").reset_index(drop=True)
    i = nv_raw.index[nv_raw["date"] == pd.Timestamp("2025-01-27")][0]
    manual_ret = nv_raw.loc[i, "adj_close"] / nv_raw.loc[i - 1, "adj_close"] - 1
    manual_vr = nv_raw.loc[i, "volume"] / nv_raw.loc[i - VOLUME_WINDOW:i - 1, "volume"].mean()
    c1 = _row(p, "NVDA", "2025-01-27")
    add(2, "prices", "NVDA", "2025-01-27", "largest one-day drop (DeepSeek news)",
        f"kept; daily_return {manual_ret:.4f}; volume_ratio_20d {manual_vr:.2f}; flag_large_move True",
        f"kept; daily_return {c1['daily_return']:.4f}; volume_ratio_20d {c1['volume_ratio_20d']:.2f}; "
        f"flag_large_move {bool(c1['flag_large_move'])}",
        "expected values are hand calculations from the raw adj_close and the previous 20 volumes; "
        "a real market event, so the row stays and the flag explains it")

    n_raw, n = raw["news"], clean["news"]
    r2, c2 = _row(n_raw, "GOOGL", "2024-12-29"), _row(n, "GOOGL", "2024-12-29")
    add(3, "news", "GOOGL", "2024-12-29", "placeholder summary on a Sunday",
        "kept; text unchanged; flag_placeholder True; next_trading_date 2024-12-30; reaction_date 2024-12-30",
        f"kept; text {'unchanged' if c2['highlights'] == r2['highlights'].strip() else 'CHANGED'}; "
        f"flag_placeholder {bool(c2['flag_placeholder'])}; next_trading_date {_d(c2['next_trading_date'])}; "
        f"reaction_date {_d(c2['reaction_date'])}",
        "an empty summary is still what was published that day; it stays for one row per day but is "
        "excluded from news-reaction metrics by its flag")

    c3 = _row(n, "AAPL", "2025-02-14")
    add(4, "news", "AAPL", "2025-02-14", "Friday before a weekend and a market holiday",
        "kept; is_trading_day True; next_trading_date 2025-02-14; reaction_date 2025-02-18",
        f"kept; is_trading_day {bool(c3['is_trading_day'])}; next_trading_date {_d(c3['next_trading_date'])}; "
        f"reaction_date {_d(c3['reaction_date'])}",
        "Friday news can only move the next session; Feb 15-16 is a weekend and Feb 17 2025 was "
        "Presidents Day, so the subsequent session is Tuesday Feb 18")

    f_raw, f = raw["filings"], clean["filings"]
    r4, c4 = _row(f_raw, "TSLA", "2024-07-23"), _row(f, "TSLA", "2024-07-23")
    prev = _row(f, "TSLA", "2024-04-23")
    add(5, "filings", "TSLA", "2024-07-23", "10-Q before the price window, risk section only points to the 10-K",
        "kept; risk_len 329; same as previous filing; both risk flags True; in_price_window False",
        f"kept; risk_len {c4['risk_len']}; {'same as' if c4['risk_content'] == prev['risk_content'] else 'differs from'} "
        f"previous filing; both risk flags {bool(c4['flag_risk_repeat'] and c4['flag_risk_reference_only'])}; "
        f"in_price_window {bool(c4['in_price_window'])}",
        "raw text is 333 characters with 4 whitespace characters at the ends; the filing is real but has no "
        "new risk text, and July 2024 is before the price data starts, so it cannot support a reaction metric")

    in_clean = _row(n, "ADBE", "2025-02-15") is not None
    in_raw = _row(n_raw, "ADBE", "2025-02-15") is not None
    add(6, "news", "ADBE", "2025-02-15", "company outside the vision scope",
        "present in raw; absent from cleaned; counted in excluded_out_of_scope",
        f"{'present' if in_raw else 'absent'} in raw; {'present' if in_clean else 'absent'} from cleaned; "
        f"counted in excluded_out_of_scope",
        "ADBE is not one of the seven stocks the analyst chooses between (D7); its rows are removed "
        "and counted, not silently lost")
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
    first_full_ratio = prices["volume_ratio_20d"].notna() & prices.groupby("symbol", observed=True)[
        "volume_ratio_20d"].transform(lambda s: s.notna().cumsum() == 1)
    ordinary_p = ~first_day & ~prices["flag_large_move"] & (prices["date"] == pd.Timestamp("2025-06-02"))
    p_s = pd.concat([
        pick(prices, prices["flag_large_move"], "large move > 12% (flagged, kept)"),
        pick(prices, first_day, "first session: daily_return and volume ratio NaN by design"),
        pick(prices, first_full_ratio & (prices["symbol"] == "AAPL"), "first session with a full 20-day volume baseline", 1),
        pick(prices, ordinary_p, "ordinary day (control)", 2),
    ])

    weekend = news["date"].dt.dayofweek >= 5
    holiday = ~news["is_trading_day"] & ~weekend
    ordinary = news["is_trading_day"] & ~news["flag_placeholder"] & ~news["flag_lookahead"]
    n_s = pd.concat([
        pick(news, news["flag_placeholder"], "placeholder or fragment (flagged, kept)"),
        pick(news, news["flag_lookahead"], "mentions a later date (flagged, kept)"),
        pick(news, (news["symbol"] == "AAPL") & (news["date"] == pd.Timestamp("2025-02-14")),
             "Friday before weekend and holiday: reaction_date skips to Tuesday"),
        pick(news, holiday & (news["symbol"] == "AAPL"), "weekday market holiday", 1),
        pick(news, weekend & ~news["flag_placeholder"] & (news["symbol"] == "MSFT"), "weekend news", 1),
        pick(news, news["reaction_date"].isna() & (news["symbol"] == "NVDA"), "last day: no next session in the data"),
        pick(news, ordinary & (news["symbol"] == "NVDA"), "ordinary trading day (control)", 2),
    ])

    flagged = filings["flag_risk_repeat"] | filings["flag_risk_reference_only"]
    f_s = pd.concat([
        pick(filings, flagged, "risk section repeated or reference-only (flagged, kept)"),
        pick(filings, ~flagged & ~filings["in_price_window"] & (filings["symbol"] == "META"),
             "filed before price data starts", 1),
        pick(filings, ~flagged & filings["in_price_window"] & (filings["symbol"] == "MSFT"),
             "ordinary filing inside the price window (control)", 2),
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


def build_report(raw, excluded, clean):
    """Markdown validation report. raw, excluded and clean are {name: df} dicts."""
    prices, news, filings = clean["prices"], clean["news"], clean["filings"]
    filings_raw = raw["filings"]
    r = []
    add = r.append

    add("# Validation Report (Peter-work)\n")
    add("Generated by `clean_peter.py`. Rules and decisions come from `plan.md`. "
        "Each function is checked in `check_cleaning_peter.ipynb`.\n")
    add("**Vision:** a junior equity research analyst decides which of seven mega-cap technology stocks "
        f"({', '.join(SCOPE_SYMBOLS)}) to prioritize for this week's deep-dive research. "
        "**Question:** how does company news relate to subsequent price changes and trading volume?\n")

    add("## Step 0: scope (D7)")
    for name in raw:
        add(f"- {name}: {len(raw[name])} raw rows, {len(excluded[name])} excluded "
            f"(symbols {sorted(excluded[name]['symbol'].unique().tolist())}), {len(clean[name])} kept.")
    add(f"- Excluded ADBE price volume: {int(excluded['prices']['volume'].sum()):,} shares.\n")

    add("## Step 1: prices")
    add("- Converted date to datetime64, symbol to category; no rows dropped after scope.")
    add(f"- daily_return from adj_close (D6); NaN by design on the first session of each stock: "
        f"{int(prices['daily_return'].isna().sum())} rows.")
    add(f"- volume_ratio_20d = volume / mean of the previous {VOLUME_WINDOW} sessions (D10); NaN by design for the "
        f"first {VOLUME_WINDOW} sessions of each stock: {int(prices['volume_ratio_20d'].isna().sum())} rows.")
    add(f"- flag_large_move (|return| > {LARGE_MOVE:.0%}, D5): {int(prices['flag_large_move'].sum())} rows, kept.\n")

    add("## Step 2: news")
    phrase_hit = int(news["highlights"].str.contains(PLACEHOLDER_PATTERN, case=False, regex=True).sum())
    add("- Stripped whitespace only; wording untouched (D3).")
    add(f"- Placeholder phrasing found in {phrase_hit} rows; only short ones count (refinement 1).")
    add(f"- flag_placeholder (D1): {int(news['flag_placeholder'].sum())} rows, kept.")
    add(f"- flag_lookahead (D3): {int(news['flag_lookahead'].sum())} row(s) mention an explicit later date "
        "(the one leak found in the full data was an ADBE row, now out of scope).")
    add(f"- Non-trading-day rows (D2): {int((~news['is_trading_day']).sum())}, kept; next_trading_date set for all.")
    add(f"- reaction_date = first session after the news date (D9): missing for "
        f"{int(news['reaction_date'].isna().sum())} rows (news on the last session, no later price in the data).\n")

    add("## Step 3: filings")
    for col in ["mda_content", "risk_content"]:
        src = raw["filings"].loc[raw["filings"]["symbol"].isin(SCOPE_SYMBOLS), col]
        n = int((src != src.str.strip()).sum())
        e = int(src.str.contains(HTML_ENTITY, regex=True).sum())
        left = int(filings[col].str.contains(HTML_ENTITY, regex=True).sum())
        add(f"- {col}: stripped leading/trailing whitespace in {n} rows; decoded HTML entities in {e} rows "
            f"(rows still containing entities after cleaning: {left}).")
    bad_types = set(filings["document_type"].unique()) - {"10-K", "10-Q"}
    add(f"- document_type values outside {{10-K, 10-Q}}: {sorted(bad_types) or 'none'}.")
    add(f"- flag_risk_repeat (D4): {int(filings['flag_risk_repeat'].sum())} rows, kept.")
    add(f"- flag_risk_reference_only (D4): {int(filings['flag_risk_reference_only'].sum())} rows, kept.")
    add(f"- in_price_window (D9): {int(filings['in_price_window'].sum())} filings have a next session in the "
        f"price data; {int((~filings['in_price_window']).sum())} were filed before it starts.\n")

    add("## Validation 1: rows, missing values, duplicates (raw -> cleaned)\n")
    add("| Table | Rows | Missing | Dup id | Dup symbol+date | Symbols |")
    add("|---|---|---|---|---|---|")
    comp = compare_profiles(raw, clean)
    for name, c in comp.iterrows():
        add(f"| {name} | {c.rows_before} -> {c.rows_after} | {c.missing_before} -> {c.missing_after} | "
            f"{c.dup_id_before} -> {c.dup_id_after} | {c.dup_symbol_date_before} -> {c.dup_symbol_date_after} | "
            f"{c.symbols_before} -> {c.symbols_after} |")
    add("")
    add(reconcile_rows(raw, excluded, clean).to_markdown() + "\n")
    miss = {name: df.isna().sum() for name, df in clean.items()}
    add("New missing values, all in derived columns and expected: "
        + "; ".join(f"{name}.{col} {int(v)}" for name, s in miss.items() for col, v in s.items() if v > 0)
        + ". No original column has missing values before or after cleaning.\n")

    add("## Validation 2: categorical columns\n")
    add(f"- symbol: {', '.join(prices['symbol'].cat.categories)}")
    for name, df in clean.items():
        add(f"- rows per symbol, {name}: {df['symbol'].value_counts().sort_index().to_dict()}")
    add(f"- document_type: {filings['document_type'].value_counts().to_dict()}\n")

    add("## Validation 3: numeric ranges\n")
    num = prices[["open", "high", "low", "close", "adj_close", "volume", "daily_return", "volume_ratio_20d"]].describe().T
    add(num[["min", "50%", "max"]].round(4).to_markdown() + "\n")
    add(f"- OHLC logic violations: {ohlc_violations(prices)}")
    add(f"- news text_len min / median / max: {news['text_len'].min()} / {int(news['text_len'].median())} / {news['text_len'].max()}")
    add(f"- filings risk_len min / median / max: {filings['risk_len'].min()} / {int(filings['risk_len'].median())} / {filings['risk_len'].max()}\n")

    add("## Validation 4: flag counts by symbol\n")
    add(flag_summary(prices, news, filings).to_markdown() + "\n")

    add("## Validation 5: example rows\n")
    add("Large moves (kept, flagged):\n")
    add(prices.loc[prices["flag_large_move"], ["symbol", "date", "close", "daily_return", "volume_ratio_20d"]]
        .assign(date=lambda d: d["date"].dt.date, daily_return=lambda d: d["daily_return"].round(4),
                volume_ratio_20d=lambda d: d["volume_ratio_20d"].round(2))
        .to_markdown(index=False) + "\n")
    add("Placeholder news (all, text truncated):\n")
    add(news.loc[news["flag_placeholder"], ["symbol", "date", "text_len", "highlights"]]
        .assign(date=lambda d: d["date"].dt.date,
                highlights=lambda d: d["highlights"].str.replace("\n", " ").str[:90] + "...")
        .to_markdown(index=False) + "\n")
    add("News mapped to sessions (examples):\n")
    ex = news[(news["symbol"] == "AAPL") & news["date"].between("2025-02-13", "2025-02-18")]
    add(ex[["symbol", "date", "is_trading_day", "next_trading_date", "reaction_date"]]
        .assign(date=lambda d: d["date"].dt.date, next_trading_date=lambda d: d["next_trading_date"].dt.date,
                reaction_date=lambda d: d["reaction_date"].dt.date)
        .to_markdown(index=False) + "\n")
    raw_sorted = filings_raw.sort_values(["symbol", "date"]).reset_index(drop=True)
    add("Filings text before vs after (AAPL 2024-02-01, first 60 characters of mda_content):\n")
    add(f"- before: `{raw_sorted['mda_content'].iloc[0][:60]!r}`")
    add(f"- after : `{filings['mda_content'].iloc[0][:60]!r}`\n")

    add("## Validation 6: join news to the subsequent price session (merge check)\n")
    _, js = join_news_to_prices(news, prices)
    add("Keys: news (symbol, reaction_date) to prices (symbol, date). Expected relationship: many news rows to "
        "one price row (Friday, weekend and holiday news share the next session). News on the last session "
        "has no next session in the data and is expected to stay unmatched.\n")
    for k, v in js.items():
        add(f"- {k}: {v}")
    add("")

    add("## Validation 7: records supporting each metric\n")
    add(metric_support(prices, news, filings).to_markdown(index=False) + "\n")
    add("Averages use records_used as the denominator; excluded rows stay in the data with a flag or a NaN, "
        "so the denominator is always stated rather than silently shrinking.\n")

    add("## Validation 8: original-to-cleaned record checks\n")
    rc = record_checks(raw, clean)
    add(rc[["check", "table", "symbol", "date", "case", "expected", "actual", "match"]].to_markdown(index=False) + "\n")
    for _, c in rc.iterrows():
        add(f"- Check {c['check']} reasoning: {c['why_expected']}.")
    add("")

    add("## Refinements made after the first validation run\n")
    add("Refinements 1 and 2 were found on the full 8-company data, before the team fixed the scope.\n")
    add("1. **Placeholder news.** The first rule flagged 20 rows. Reading them showed 12 were long, real "
        "summaries that only said one of several articles was empty. The rule now requires the placeholder "
        "phrasing in a short text (< 1,000 characters) or a fragment (< 200 characters). Result: 8 rows on "
        f"the full data, all confirmed by reading; {int(news['flag_placeholder'].sum())} in scope.")
    add("2. **Look-ahead news.** A keyword search matched 33 rows, but nearly all were disclaimers stating "
        "that future information had been excluded, the opposite of a leak. The rule now compares explicit "
        "dates written in the text with the row date. Result: 1 row on the full data (ADBE 2025-02-15 "
        f"mentions the 2025-02-25 Photoshop launch); {int(news['flag_lookahead'].sum())} in scope.")
    add("3. **Encoded characters in filings.** Filings text stored characters as HTML entities (`&#8217;` "
        "for a right quote, `&#160;` for a non-breaking space, `&#38;` for &). They are decoded to the real "
        "characters, which changes encoding, not wording.")
    add("4. **Scope and timing after the vision was fixed.** The team chose seven stocks and a question "
        "about news and subsequent price and volume changes, so ADBE rows are excluded (D7), each news row "
        "and filing gets the first session after its date (D9), and prices get a 20-session volume "
        "baseline (D10).\n")

    add("## Conclusion: does the cleaned data still represent reality?\n")
    add(f"Yes, for the seven stocks in scope. Apart from the {sum(len(v) for v in excluded.values())} ADBE rows "
        "removed by the scope decision, no rows were dropped and no values or wording were changed beyond "
        "whitespace and character encoding. Prices pass all logic checks, and the "
        f"{int(prices['flag_large_move'].sum())} large moves line up with known events (2025-04-09 tariff pause "
        "rally, NVDA DeepSeek drop on 2025-01-27). Every news row now points to the session that follows it, "
        "so the question about subsequent price and volume changes can be answered without look-ahead. "
        f"Quality problems are visible through flags: {int(news['flag_placeholder'].sum())} empty news rows, "
        f"{int((~news['is_trading_day']).sum())} non-trading-day news rows mapped to the next session, "
        f"{int((filings['flag_risk_repeat'] | filings['flag_risk_reference_only']).sum())} filings with no new "
        f"risk text, and {int((~filings['in_price_window']).sum())} filings that predate the price data.")
    return "\n".join(r) + "\n"


# ------------------------------------------------------------------ pipeline
def run_pipeline(raw_dir=RAW, clean_dir=CLEAN, out_dir=OUT):
    """Full run: load, scope, clean, save, write report. Returns the cleaned tables as a dict."""
    prices_raw, news_raw, filings_raw = load_raw(raw_dir)
    raw = {"prices": prices_raw, "news": news_raw, "filings": filings_raw}
    scoped = {name: apply_scope(df) for name, df in raw.items()}
    excluded = {name: s[1] for name, s in scoped.items()}

    prices = clean_prices(scoped["prices"][0])
    days = trading_calendar(prices)
    news = clean_news(scoped["news"][0], days)
    filings = clean_filings(scoped["filings"][0], days)
    clean = {"prices": prices, "news": news, "filings": filings}

    save_clean(prices, news, filings, clean_dir)
    save_sample(make_sample(prices, news, filings))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    record_checks(raw, clean).to_csv(out_dir / "record_checks_peter.csv", index=False)
    metric_support(prices, news, filings).to_csv(out_dir / "metric_support_peter.csv", index=False)
    (out_dir / "validation_report.md").write_text(build_report(raw, excluded, clean), encoding="utf-8")
    return clean


if __name__ == "__main__":
    run_pipeline()
    print("Saved data/clean/*.parquet, samples_peter/*.csv and outputs/")
