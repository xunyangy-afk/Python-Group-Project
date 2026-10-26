"""Read-only dashboard contracts and independent Python reference calculations."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import mean, stdev

import pandas as pd

SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
HASHES = {
    'prices': '84a3c2c4eaab0977f98666cc431faafdf1eb39cbc20deff36579ab430060ae1e',
    'news': '94fc868bb681c810999d861e40e3cfb402473bc77141554003c6f362f027ba0d',
    'filings': 'd56aa0d85cf96dc991f8e74bc06541479bc044c6652995cbfd3f81f582ab2a6c',
}
FIELDS = {
    'prices': ['open', 'high', 'low', 'close', 'adj_close', 'volume',
               'flag_invalid_numeric', 'flag_ohlc', 'flag_zero_volume', 'flag_large_move',
               'flag_gap_gt4_calendar_days'],
    'news': ['highlights', 'flag_empty_text', 'flag_placeholder', 'flag_future_date_mention',
             'flag_apparent_truncation', 'flag_timing_unverified'],
    'filings': ['document_type', 'mda_content', 'risk_content', 'flag_empty_mda_content',
                'flag_empty_risk_content', 'flag_unexpected_form', 'flag_short_risk_text',
                'flag_repeated_previous_risk'],
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_table(df, kind, production=False):
    """Validate schemas without rewriting source values; fixture validation is reusable."""
    required = ['id', 'symbol', 'date', '_source_row', 'flag_repeated_business_key'] + FIELDS[kind]
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f'{kind}: missing required columns: {sorted(missing)}')
    def fail(mask, field, message):
        if mask.any():
            records = df.loc[mask, ['id', '_source_row']].head(3).to_dict('records')
            raise ValueError(f'{kind}.{field}: {message}; records={records}')
    fail(df.id.isna() | df.id.duplicated(keep=False), 'id', 'missing or duplicate table ID')
    fail(~df.id.map(lambda x: isinstance(x, str)), 'id', 'expected string')
    fail(~df.symbol.isin(SYMBOLS), 'symbol', 'unknown or missing ticker')
    if not pd.api.types.is_datetime64_any_dtype(df.date) or getattr(df.date.dt, 'tz', None) is not None:
        raise ValueError(f'{kind}.date: expected timezone-naive date-only datetime values')
    fail(df.date.isna() | df.date.ne(df.date.dt.normalize()), 'date', 'malformed or non-date-only value')
    if not pd.api.types.is_integer_dtype(df._source_row):
        raise ValueError(f'{kind}._source_row: expected integer source positions')
    fail(df._source_row.isna() | df._source_row.lt(0), '_source_row', 'invalid source position')
    for col in required:
        if col.startswith('flag_'):
            if not pd.api.types.is_bool_dtype(df[col]) or df[col].isna().any():
                raise ValueError(f'{kind}.{col}: expected nonmissing booleans')
    for col in (['open', 'high', 'low', 'close', 'adj_close', 'volume'] if kind == 'prices' else []):
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f'{kind}.{col}: expected readable numeric values')
    text_cols = {'news': ['highlights'], 'filings': ['document_type', 'mda_content', 'risk_content']}.get(kind, [])
    for col in text_cols:
        fail(~df[col].map(lambda x: pd.isna(x) or isinstance(x, str)), col, 'expected text or null')
    if kind == 'prices':
        fail(df.duplicated(['symbol', 'date'], keep=False), 'symbol,date', 'conflicting price key')
    if production:
        if set(df.symbol) != set(SYMBOLS):
            raise ValueError(f'{kind}: production snapshot must contain all seven symbols')
        expected_shapes = {'prices': (2324, 16), 'news': (3402, 11), 'filings': (63, 13)}
        if df.shape != expected_shapes[kind]:
            raise ValueError(f'{kind}: unexpected production shape {df.shape}')
        count = {'prices': 332, 'news': 486, 'filings': 9}[kind]
        if not df.groupby('symbol').size().eq(count).all():
            raise ValueError(f'{kind}: unexpected production company coverage')
        expected_ranges = {'prices': ('2024-12-02', '2026-03-31'), 'news': ('2024-12-01', '2026-03-31'),
                           'filings': ('2024-01-26', '2026-02-25')}
        if (df.date.min().strftime('%Y-%m-%d'), df.date.max().strftime('%Y-%m-%d')) != expected_ranges[kind]:
            raise ValueError(f'{kind}: unexpected production coverage')
    return df.sort_values(['symbol', 'date', 'id', '_source_row'], kind='stable')


def load_inputs(root):
    root = Path(root)
    if not (root / 'artifacts/prices_clean.parquet').exists():
        root = root / 'Python-Group-Project'
    tables, hashes = {}, {}
    for kind in HASHES:
        path = root / f'artifacts/{kind}_clean.parquet'
        if not path.exists():
            raise ValueError(f'Missing cleaned dashboard input: {path}. Provide the three formal Parquet files.')
        hashes[kind] = digest(path)
        if hashes[kind] != HASHES[kind]:
            raise ValueError(f'{path}: snapshot SHA256 mismatch; review the snapshot before building')
        tables[kind] = validate_table(pd.read_parquet(path), kind, production=True)
    return root, tables, hashes


def records(df):
    d = df.copy()
    d['date'] = d.date.dt.strftime('%Y-%m-%d')
    return d.astype(object).where(pd.notna(d), None).to_dict(orient='records')


def valid(value, positive=False):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and (value > 0 if positive else value >= 0)


def analyze(prices, symbols, start, end):
    """Full history in; JSON-safe series/metrics out. No source writes or imputation."""
    if start > end:
        raise ValueError('Expected start <= end')
    output = []
    for symbol in symbols:
        history = sorted((p for p in prices if p['symbol'] == symbol), key=lambda p: (p['date'], p.get('id', ''), p.get('_source_row', 0)))
        series = []
        for i, row in enumerate(history):
            if not start <= row['date'] <= end:
                continue
            past = [r.get('volume') for r in history[max(0, i-20):i]]
            volume = row.get('volume')
            relative = volume / mean(past) if len(past) == 20 and all(valid(v) for v in past) and mean(past) > 0 and valid(volume) else None
            price = row.get('adj_close')
            series.append({'date': row['date'], 'adj_close': price if valid(price, True) else None,
                           'volume': volume if valid(volume) else None, 'relative_volume': relative})
        base = series[0]['adj_close'] if series else None
        for i, row in enumerate(series):
            price = row['adj_close']
            prev = series[i-1]['adj_close'] if i else None
            row['normalized_price'] = price / base * 100 if price is not None and base is not None else None
            row['daily_return'] = price / prev - 1 if price is not None and prev is not None else None
        returns = [r['daily_return'] for r in series if r['daily_return'] is not None]
        volumes = [r['volume'] for r in series if r['volume'] is not None]
        endpoint = series[-1]['adj_close'] if series else None
        drawdown = None
        if len(series) >= 2 and all(r['adj_close'] is not None for r in series):
            peak, drawdown = series[0]['adj_close'], 0.0
            for r in series:
                peak = max(peak, r['adj_close'])
                drawdown = max(drawdown, 1 - r['adj_close'] / peak)
        output.append(dict(symbol=symbol, range_start=start, range_end=end,
                           first_observation_date=series[0]['date'] if series else None,
                           last_observation_date=series[-1]['date'] if series else None,
                           n_prices=len(series), n_returns=len(returns),
                           period_return=endpoint/base-1 if len(series) >= 2 and base is not None and endpoint is not None else None,
                           daily_volatility=stdev(returns) if len(returns) >= 2 else None,
                           average_volume=mean(volumes) if volumes else None,
                           max_drawdown=drawdown, series=series))
    return output
