"""Independent audit check: reads formal data, never imports dashboard code.

Run from any directory with the project's dashboard Python environment.
This script checks source arithmetic, not the live browser's behavior.
"""
import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent


def main():
    price_path = ROOT / 'artifacts/prices_clean.parquet'
    news_path = ROOT / 'artifacts/news_clean.parquet'
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [price_path, news_path]}
    prices = pd.read_parquet(price_path)
    news = pd.read_parquet(news_path)
    results = []
    with localcontext() as context:
        context.prec = 40
        # Small case whose result is known without using any application implementation.
        small_case = Decimal('90') / Decimal('100') - 1
        assert small_case == Decimal('-0.1')
        for symbol, displayed in [('AAPL', '-4.13'), ('NVDA', '-4.42')]:
            rows = prices.loc[prices.symbol.eq(symbol) & prices.date.between('2026-03-02', '2026-03-31')].sort_values('date')
            assert len(rows) >= 2
            first, last = rows.iloc[0], rows.iloc[-1]
            first_price, last_price = Decimal(str(first.adj_close)), Decimal(str(last.adj_close))
            assert first_price > 0 and last_price > 0
            value = last_price / first_price - 1
            percentage = value * 100
            rounded = percentage.quantize(Decimal('0.01'))
            assert rounded == Decimal(displayed), (symbol, rounded, displayed)
            results.append(dict(symbol=symbol, first_date=str(first.date.date()), last_date=str(last.date.date()),
                                first_id=str(first.id), last_id=str(last.id), n_prices=len(rows),
                                first_adj_close=str(first_price), last_adj_close=str(last_price),
                                return_fraction=str(value), return_pct=str(percentage),
                                expected_ui_pct=str(rounded), observed_screenshot_pct=displayed,
                                agrees_at_display_precision=True))
        # Expected source evidence boundaries; this is not a claim of enumerating the UI.
        events = news.loc[news.symbol.eq('AAPL') & news.date.between('2026-03-02', '2026-03-31')].sort_values(['date', 'id', '_source_row'])
        event_result = dict(count=len(events), first_date=str(events.date.min().date()),
                            last_date=str(events.date.max().date()), first_id=str(events.iloc[0].id),
                            last_id=str(events.iloc[-1].id))
        single = prices.loc[prices.symbol.isin(['AAPL', 'NVDA']) & prices.date.between('2026-03-01', '2026-03-02')].sort_values(['symbol', 'date'])
        single_rows = [dict(symbol=r.symbol, date=str(r.date.date()), id=str(r.id),
                            adj_close=str(r.adj_close), volume=int(r.volume)) for r in single.itertuples()]
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [price_path, news_path]}
    assert before == after, 'Source bytes changed'
    report = dict(app_commit='e630f6823fd12bc11cf0525fab7dc9be59ff5eae',
                  method='Independent pandas row selection + Decimal endpoint ratio; no dashboard imports',
                  source_hashes=before, source_bytes_unchanged=True,
                  small_case=dict(prices=[100, 120, 90], expected_return_pct='-10',
                                  calculated_return_pct=str(small_case * 100)),
                  interval_results=results, expected_aapl_news=event_result,
                  single_observation_source_rows=single_rows,
                  scope_note='UI values are transcribed from student screenshots; this script independently checks source values, not browser execution.')
    (OUTPUT / 'independent-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
