import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd
from dashboard_analysis import SYMBOLS, analyze, load_inputs, records, validate_table
from team_cleaning.analysis import interval_metrics


def fixture(values, volumes=None):
    dates = pd.date_range('2025-01-01', periods=len(values)).strftime('%Y-%m-%d')
    return [dict(symbol='AAPL', id=str(i), _source_row=i, date=date, adj_close=value,
                 volume=volumes[i] if volumes is not None else 100) for i, (date, value) in enumerate(zip(dates, values))]


def cases():
    basic = fixture([100, 120, 90])
    result = []
    def case(name, rows, start=None, end=None):
        start = start or rows[0]['date']; end = end or rows[-1]['date']
        result.append(dict(name=name, prices=rows, symbols=['AAPL'], start=start, end=end,
                           expected=analyze(rows, ['AAPL'], start, end)))
    case('three prices', basic)
    case('last two', basic, basic[1]['date'])
    case('invalid baseline', fixture([None, 120, 90]))
    case('interior gap', fixture([100, None, 110]))
    case('single price', fixture([100]))
    case('no observations', basic, '2025-01-04', '2025-01-05')
    case('nonpositive endpoints', fixture([0,120,-1]))
    for name, vols in [('relative two', [100]*20+[200]), ('zero today', [100]*20+[0]),
                       ('zero baseline', [0]*20+[200]), ('invalid previous', [None]+[100]*19+[200]),
                       ('insufficient lookback', [100]*19+[200]), ('invalid current', [100]*20+[-2])]:
        rows=fixture([100]*len(vols),vols);case(name, rows)
        case(name+' filtered', rows, rows[-1]['date'])
    case('nondecreasing', fixture([100,100,110]))
    return result


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tables, cls.hashes = load_inputs(ROOT)
        cls.prices = records(cls.tables['prices'])

    def test_arithmetic_independent_known_answers(self):
        m=analyze(fixture([100,120,90]),['AAPL'],'2025-01-01','2025-01-03')[0]
        self.assertAlmostEqual(m['period_return'],-.1)
        self.assertAlmostEqual(m['max_drawdown'],.25)
        self.assertAlmostEqual(m['daily_volatility'],.3181980515339464)
        self.assertEqual([p['normalized_price'] for p in m['series']],[100,120,90])
        self.assertAlmostEqual(m['series'][1]['daily_return'],.2)
        self.assertEqual(m['series'][2]['daily_return'],-.25)

    def test_missingness_endpoints_and_single_row_adapter(self):
        for row in cases():
            json.dumps(row,allow_nan=False)
        gap=cases()[3]['expected'][0]
        self.assertEqual(gap['n_returns'],0)
        self.assertAlmostEqual(gap['period_return'],.1)
        self.assertIsNone(gap['max_drawdown'])
        invalid=cases()[2]['expected'][0]
        self.assertTrue(all(p['normalized_price'] is None for p in invalid['series']))
        single=cases()[4]['expected'][0]
        for key in ['period_return','max_drawdown','daily_volatility']:self.assertIsNone(single[key])
        # Explicitly preserve the original API's one-row convention.
        df=self.tables['prices'].iloc[:1]
        _, original=interval_metrics(df,df.date.min(),df.date.max())
        self.assertEqual(original.period_return.iloc[0],0)

    def test_relative_volume_full_history_and_zero(self):
        for vols, expected in [([100]*20+[200],2),([100]*20+[0],0),([0]*20+[200],None),
                               ([None]+[100]*19+[200],None),([100]*19+[200],None)]:
            rows=fixture([100]*len(vols),vols)
            whole=analyze(rows,['AAPL'],rows[0]['date'],rows[-1]['date'])[0]
            filtered=analyze(rows,['AAPL'],rows[-1]['date'],rows[-1]['date'])[0]
            self.assertEqual(whole['series'][-1]['relative_volume'],expected)
            self.assertEqual(filtered['series'][0]['relative_volume'],expected)

    def test_production_overlaps_existing_api(self):
        for start,end in [('2024-12-02','2025-01-15'),('2025-06-01','2025-08-30'),('2026-01-06','2026-03-31')]:
            _, old=interval_metrics(self.tables['prices'],start,end)
            expected=old.set_index('symbol')
            for m in analyze(self.prices,SYMBOLS,start,end):
                for key in ['period_return','daily_volatility','average_volume']:
                    self.assertAlmostEqual(m[key],expected.loc[m['symbol'],key],delta=1e-6 if key=='average_volume' else 1e-10)

    def test_schema_and_key_rejections(self):
        table=self.tables['prices']
        for label,mutate in [
            ('missing column',lambda d:d.drop(columns='adj_close')),
            ('duplicate id',lambda d:pd.concat([d,d.iloc[:1]])),
            ('unknown symbol',lambda d:d.assign(symbol='ADBE')),
            ('bad date type',lambda d:d.assign(date='broken')),
            ('timestamp',lambda d:d.assign(date=d.date+pd.Timedelta(hours=1))),
            ('bad numeric',lambda d:d.assign(volume='bad'))]:
            with self.subTest(label=label),self.assertRaises(ValueError):validate_table(mutate(table.copy()),'prices')
        extra=table.iloc[:1].copy();extra['id']='different-id'
        with self.assertRaisesRegex(ValueError,'price key'):validate_table(pd.concat([table,extra]),'prices')

    def test_multiple_events_and_literal_text_preserved(self):
        news=self.tables['news'].iloc[:1].copy();extra=news.copy();extra['id']='new-id'
        combined=pd.concat([news,extra]);validate_table(combined,'news')
        combined=combined.copy();combined['highlights']='line 1\n\n</script><script>alert(1)</script>& "quoted"'
        self.assertEqual(records(combined)[0]['highlights'],combined.highlights.iloc[0])

    def test_generate_reference_evidence(self):
        dates=sorted({p['date'] for p in self.prices});start=dates[-60];end=dates[-1]
        reference=cases()
        for name,a,b in [('real early',dates[0],dates[35]),('real middle','2025-06-01','2025-08-30'),('real default',start,end)]:
            reference.append(dict(name=name,production=True,symbols=SYMBOLS,start=a,end=b,expected=analyze(self.prices,SYMBOLS,a,b)))
        aapl=[p for p in self.prices if p['symbol']=='AAPL' and start<=p['date']<=end]
        actual=dict(default_range=[start,end],aapl_first=aapl[0],aapl_last=aapl[-1],
                    independent_endpoint_return=aapl[-1]['adj_close']/aapl[0]['adj_close']-1)
        for kind in ['news','filings']:
            rows=records(self.tables[kind]);rows=[p for p in rows if p['symbol']=='AAPL' and start<=p['date']<=end]
            actual[kind]=sorted(rows,key=lambda r:(r['date'],r['id']),reverse=True)[0]
        out=ROOT/'dashboard_verification';out.mkdir(exist_ok=True)
        (out/'reference.json').write_text(json.dumps(reference,allow_nan=False),encoding='utf-8')
        (out/'real_data.json').write_text(json.dumps(actual,indent=2,allow_nan=False),encoding='utf-8')


if __name__=='__main__':unittest.main()
