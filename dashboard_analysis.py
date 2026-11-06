"""Read-only reference implementation of BUILD_SPEC section 4."""
import math
import statistics
SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']

def valid(x, price=False):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and (x > 0 if price else x >= 0)

def analyze(rows, symbols, start, end):
    result = []
    for symbol in symbols:
        history = sorted((r for r in rows if r['symbol'] == symbol), key=lambda r: (r['date'], r['id'], r['_source_row']))
        series = []
        selected = [r for r in history if start <= r['date'] <= end]
        base = selected[0]['adj_close'] if selected else None
        for i, row in enumerate(history):
            if not start <= row['date'] <= end:
                continue
            p, v = row['adj_close'], row['volume']
            j = len(series)
            prev = selected[j-1]['adj_close'] if j else None
            window = [x['volume'] for x in history[max(0, i-20):i]]
            mean = sum(window)/20 if len(window) == 20 and all(valid(x) for x in window) else None
            series.append(dict(date=row['date'], adj_close=p if valid(p, True) else None,
                normalized=100*p/base if valid(p, True) and valid(base, True) else None,
                daily_return=p/prev-1 if valid(p, True) and valid(prev, True) else None,
                volume=v if valid(v) else None,
                relative_volume=v/mean if valid(v) and mean is not None and mean > 0 else None))
        returns = [r['daily_return'] for r in series if r['daily_return'] is not None]
        volumes = [r['volume'] for r in series if r['volume'] is not None]
        n = len(series)
        endpoint = series[-1]['adj_close'] if n else None
        drawdown = None
        if n >= 2 and all(r['adj_close'] is not None for r in series):
            peak, drawdown = 0, 0
            for r in series:
                peak = max(peak, r['adj_close'])
                drawdown = max(drawdown, 1-r['adj_close']/peak)
        result.append(dict(symbol=symbol, range_start=start, range_end=end,
            first_observation_date=series[0]['date'] if n else None,
            last_observation_date=series[-1]['date'] if n else None,
            n_prices=n, n_returns=len(returns),
            period_return=endpoint/base-1 if n >= 2 and valid(base, True) and valid(endpoint, True) else None,
            daily_volatility=statistics.stdev(returns) if len(returns) >= 2 else None,
            average_daily_volume=sum(volumes)/len(volumes) if volumes else None,
            max_drawdown=drawdown, series=series))
    return result

