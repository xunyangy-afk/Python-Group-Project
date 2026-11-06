"""Pure shared state transitions, original-date evidence retrieval, and CSV export."""
from copy import deepcopy
import csv
import io
from dashboard_analysis import SYMBOLS

METRICS = {'Interval return': 'period_return', 'Daily return volatility': 'daily_volatility',
           'Average daily volume': 'average_daily_volume', 'Maximum drawdown': 'max_drawdown'}
CSV_COLUMNS = ['symbol', 'range_start', 'range_end', 'first_observation_date', 'last_observation_date',
               'period_return_pct', 'daily_volatility_pct', 'average_daily_volume_shares', 'max_drawdown_pct',
               'n_prices', 'n_returns', 'data_as_of', 'reason']


def initial_state(meta):
    return dict(companies=SYMBOLS.copy(), start=meta['default_start'], end=meta['cutoff'],
                focus='AAPL', focus_date=meta['cutoff'], scope='Selected date', shortlist=[])


def set_range(state, start, end, meta, prices, snap=False):
    if start > end or start < meta['min_date'] or end > meta['cutoff']:
        raise ValueError('Choose a start on or before the end, within price coverage. The previous range is retained.')
    if snap:
        dates = [d for d in meta['dates'] if start <= d <= end]
        if not dates:
            raise ValueError('No observed dates were selected. The previous range is retained.')
        start, end = dates[0], dates[-1]
    state['start'], state['end'] = start, end
    reconcile_focus(state, prices)


def reconcile_focus(state, prices):
    if state['focus'] not in state['companies']:
        state['focus'] = next(s for s in SYMBOLS if s in state['companies'])
    if not state['start'] <= state['focus_date'] <= state['end']:
        dates = [r['date'] for r in prices if r['symbol'] == state['focus'] and state['start'] <= r['date'] <= state['end']]
        state['focus_date'] = max(dates) if dates else state['end']


def set_companies(state, companies, prices):
    if not companies:
        raise ValueError('Keep at least one company selected.')
    state['companies'] = [s for s in SYMBOLS if s in companies]
    reconcile_focus(state, prices)


def query_events(rows, symbol, start, end):
    return sorted((r for r in rows if r['symbol'] == symbol and start <= r['date'] <= end),
                  key=lambda r: (-int(r['date'].replace('-', '')), r['id'], r['_source_row']))


def sorted_metrics(results, metric, descending=True):
    return sorted(results, key=lambda r: (r[metric] is None,
                  (-r[metric] if descending else r[metric]) if r[metric] is not None else 0, r['symbol']))


def add_candidate(state, metric, cutoff):
    if any(r['symbol'] == metric['symbol'] for r in state['shortlist']):
        raise ValueError('This company is already saved. Remove and re-add it to capture another interval.')
    if len(state['shortlist']) >= 2:
        raise ValueError('The shortlist is full. Remove an existing entry before adding a third company.')
    snapshot = deepcopy({k: v for k, v in metric.items() if k != 'series'})
    snapshot.update(data_as_of=cutoff, reason='')
    state['shortlist'].append(snapshot)


def spreadsheet_safe(text):
    # Inspect past whitespace/control characters, but preserve the original reason.
    stripped = text.lstrip()
    return "'" + text if text.startswith(('\t', '\r', '\n')) or stripped.startswith(('=', '+', '-', '@')) else text


def export_csv(candidates):
    if not 1 <= len(candidates) <= 2 or any(not r['reason'].strip() for r in candidates):
        raise ValueError('Add one or two companies and a non-whitespace research reason for each before exporting.')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for candidate in candidates:
        row = {k: candidate.get(k) for k in CSV_COLUMNS}
        for target, source in [('period_return_pct', 'period_return'), ('daily_volatility_pct', 'daily_volatility'), ('max_drawdown_pct', 'max_drawdown')]:
            row[target] = candidate[source] * 100 if candidate[source] is not None else None
        row['average_daily_volume_shares'] = candidate['average_daily_volume']
        for field in ['symbol', 'range_start', 'range_end', 'first_observation_date', 'last_observation_date', 'data_as_of', 'reason']:
            if isinstance(row[field], str):
                row[field] = spreadsheet_safe(row[field])
        writer.writerow(row)
    return output.getvalue().encode('utf-8')
