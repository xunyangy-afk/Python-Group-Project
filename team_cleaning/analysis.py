"""Optional, date-range-dependent analysis; never writes cleaning outputs."""
import numpy as np
import pandas as pd


def adjusted_returns(prices):
    """Returns across consecutive observed rows, with no implicit forward fill."""
    if prices.duplicated(["symbol", "date"]).any():
        raise ValueError("Conflicting price keys")
    if not all(g.date.is_monotonic_increasing for _, g in prices.groupby("symbol")):
        raise ValueError("Sort prices by symbol and date before calculating returns")
    values = pd.to_numeric(prices.adj_close, errors="raise")
    values = values.where(np.isfinite(values) & values.gt(0))
    return values.groupby(prices.symbol).pct_change(fill_method=None)


def interval_metrics(prices, start, end):
    """Inclusive interval, normalized to first observed value (base 100).

    Returns within the interval only; no return crossing its left boundary.
    Missing endpoints remain missing. Sample daily volatility uses ddof=1;
    one or zero returns cannot estimate volatility. No annualization assumed.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError("Expected a valid start <= end")
    p = prices.loc[prices.date.between(start, end)].copy()
    p = p.sort_values(["symbol", "date"]).reset_index(drop=True)
    if p.duplicated(["symbol", "date"]).any():
        raise ValueError("Conflicting price keys")
    p["daily_return"] = adjusted_returns(p)
    # transform('first') would silently skip a missing first observation.
    base = p.groupby("symbol").adj_close.transform(lambda s: s.iloc[0])
    valid_base = base.where(np.isfinite(base) & base.gt(0))
    p["normalized_price"] = p.adj_close.where(np.isfinite(p.adj_close) & p.adj_close.gt(0)) / valid_base * 100
    rows = []
    for symbol, g in p.groupby("symbol", sort=True):
        first, last = g.adj_close.iloc[0], g.adj_close.iloc[-1]
        valid = pd.notna(first) and pd.notna(last) and np.isfinite(first) and np.isfinite(last) and first > 0 and last > 0
        rows.append(dict(symbol=symbol, start=g.date.iloc[0], end=g.date.iloc[-1],
                         n_prices=len(g), n_returns=int(g.daily_return.count()),
                         period_return=last / first - 1 if valid else np.nan,
                         daily_volatility=g.daily_return.std(ddof=1),
                         average_volume=g.volume.where(np.isfinite(g.volume) & g.volume.ge(0)).mean()))
    return p, pd.DataFrame(rows, columns=["symbol", "start", "end", "n_prices", "n_returns",
                                         "period_return", "daily_volatility", "average_volume"])
