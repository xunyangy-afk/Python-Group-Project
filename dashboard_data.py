"""Read-only schema and exact production-snapshot validation."""
from pathlib import Path
import hashlib
import math
import pandas as pd
import numpy as np
from dashboard_analysis import SYMBOLS

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    'prices': ('84a3c2c4eaab0977f98666cc431faafdf1eb39cbc20deff36579ab430060ae1e', (2324, 16), '2024-12-02', '2026-03-31', 332),
    'news': ('94fc868bb681c810999d861e40e3cfb402473bc77141554003c6f362f027ba0d', (3402, 11), '2024-12-01', '2026-03-31', 486),
    'filings': ('d56aa0d85cf96dc991f8e74bc06541479bc044c6652995cbfd3f81f582ab2a6c', (63, 13), '2024-01-26', '2026-02-25', 9),
}
FIELDS = {
    'prices': ['open', 'high', 'low', 'close', 'adj_close', 'volume', 'flag_invalid_numeric', 'flag_ohlc', 'flag_zero_volume', 'flag_large_move', 'flag_gap_gt4_calendar_days'],
    'news': ['highlights', 'flag_empty_text', 'flag_placeholder', 'flag_future_date_mention', 'flag_apparent_truncation', 'flag_timing_unverified'],
    'filings': ['document_type', 'mda_content', 'risk_content', 'flag_empty_mda_content', 'flag_empty_risk_content', 'flag_unexpected_form', 'flag_short_risk_text', 'flag_repeated_previous_risk'],
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(df, table, path, require_all=True):
    required = ['id', 'symbol', 'date', '_source_row', 'flag_repeated_business_key'] + FIELDS[table]
    missing = set(required) - set(df)
    if missing:
        raise ValueError(f'{path}: missing fields {sorted(missing)}')

    def fail(mask, field, message):
        if mask.any():
            records = df.loc[mask, ['id', '_source_row']].head(3).to_dict('records')
            raise ValueError(f'{path}: {field}: {message}; records={records}')

    for field in ['id', 'symbol']:
        fail(df[field].isna() | ~df[field].map(lambda x: isinstance(x, str)), field, 'nonmissing strings required')
    fail(df.id.duplicated(keep=False), 'id', 'duplicate table ID')
    fail(~df.symbol.isin(SYMBOLS), 'symbol', 'unknown ticker')
    if require_all and set(df.symbol) != set(SYMBOLS):
        raise ValueError(f'{path}: symbol: all seven companies required')
    if not pd.api.types.is_datetime64_ns_dtype(df.date.dtype) or getattr(df.date.dtype, 'tz', None) is not None:
        raise ValueError(f'{path}: date: timezone-naive datetime64[ns] required; records={df[["id", "_source_row"]].head(3).to_dict("records")}')
    fail(df.date.isna() | (df.date != df.date.dt.normalize()), 'date', 'missing or not date-only')
    if not pd.api.types.is_integer_dtype(df['_source_row']):
        raise ValueError(f'{path}: _source_row: integer required')
    fail(df['_source_row'].isna() | (df['_source_row'] < 0), '_source_row', 'invalid source position')
    for field in required:
        if field.startswith('flag_') and (not pd.api.types.is_bool_dtype(df[field]) or df[field].isna().any()):
            raise ValueError(f'{path}: {field}: nonmissing boolean required')
    if table == 'prices':
        for field in ['open', 'high', 'low', 'close', 'adj_close', 'volume']:
            if not pd.api.types.is_numeric_dtype(df[field]):
                raise ValueError(f'{path}: {field}: numeric required')
        fail(df.duplicated(['symbol', 'date'], keep=False), 'symbol,date', 'duplicate price key')
    else:
        for field in (['highlights'] if table == 'news' else ['document_type', 'mda_content', 'risk_content']):
            fail(df[field].notna() & ~df[field].map(lambda x: isinstance(x, str)), field, 'text or missing required')


def records(df):
    out = df.sort_values(['symbol', 'date', 'id', '_source_row'], kind='stable').copy()
    out['date'] = out.date.dt.strftime('%Y-%m-%d')
    return [{k: (None if pd.isna(v) or isinstance(v, (float, np.floating)) and not math.isfinite(v)
                 else v.item() if isinstance(v, np.generic) else v) for k, v in row.items()}
            for row in out.to_dict('records')]


def load(directory=None):
    if directory is None:
        candidates = [ROOT / 'artifacts', ROOT / 'Python-Group-Project' / 'artifacts']
        directory = next((p for p in candidates if all((p / f'{n}_clean.parquet').is_file() for n in EXPECTED)), candidates[0])
    directory = Path(directory)
    tables, identity = {}, {}
    for name, (expected_hash, shape, first, last, per_company) in EXPECTED.items():
        path = directory / f'{name}_clean.parquet'
        if not path.is_file():
            raise FileNotFoundError(f'Missing required input: {path}. Supply the approved three cleaned Parquet files; no raw or substitute data will be used.')
        observed = digest(path)
        if observed != expected_hash:
            raise ValueError(f'{path}: SHA256 mismatch. Expected {expected_hash}; observed {observed}. A reviewed snapshot update is required.')
        df = pd.read_parquet(path)
        validate(df, name, path)
        counts = df.groupby('symbol').size().to_dict()
        bounds = [df.date.min().strftime('%Y-%m-%d'), df.date.max().strftime('%Y-%m-%d')]
        if df.shape != shape or bounds != [first, last] or any(v != per_company for v in counts.values()):
            raise ValueError(f'{path}: snapshot shape/coverage/count mismatch: {df.shape}, {bounds}, {counts}')
        tables[name] = records(df)
        identity[name] = dict(sha256=observed, shape=list(df.shape), first_date=bounds[0], last_date=bounds[1], rows_by_symbol=counts)
    dates = sorted({r['date'] for r in tables['prices']})
    metadata = dict(identity=identity, snapshot='team-local-sha256-v1', min_date=dates[0], cutoff=dates[-1], default_start=dates[max(0, len(dates)-60)], dates=dates)
    return tables, metadata
