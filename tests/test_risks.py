import html
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from team_cleaning.analysis import adjusted_returns, interval_metrics
from team_cleaning.pipeline import ROOT, clean_table, join_audit, run, sha256


def prices(values=(100., 110., 121.)):
    return pd.DataFrame(dict(id=list(range(1, len(values) + 1)), symbol=["AAPL"] * len(values),
                             date=pd.date_range("2025-01-01", periods=len(values)).date,
                             open=values, high=values, low=values, close=values,
                             adj_close=values, volume=[10] * len(values)))


class RiskTests(unittest.TestCase):
    def test_exact_duplicate_vs_conflicting_price_key(self):
        p = prices()
        duplicate = p.iloc[[0]]
        conflict = p.iloc[[1]].assign(id=99, close=115.)
        raw = pd.concat([p, duplicate, conflict], ignore_index=True)
        before = raw.copy(deep=True)
        clean, excluded, stats, _ = clean_table("prices", raw)
        self.assertEqual(stats["exact_duplicate_extra_rows"], 1)
        self.assertEqual(set(clean.id), {"1", "3"})
        self.assertEqual(excluded._reason.value_counts().to_dict(), {
            "conflicting_price_key_quarantine_all": 2, "exact_duplicate_keep_first_source_row": 1})
        pd.testing.assert_frame_equal(raw, before)

    def test_event_key_repeat_kept_but_repeated_id_quarantined(self):
        n = pd.DataFrame(dict(id=[1, 2, 3, 3], symbol=["AAPL"] * 4,
                              date=["2025-01-01"] * 4, highlights=["one", "two", "three", "four"]))
        clean, excluded, _, _ = clean_table("news", n)
        self.assertEqual(set(clean.id), {"1", "2"})
        self.assertTrue(clean.flag_repeated_business_key.all())
        self.assertEqual(set(excluded._reason), {"conflicting_id_quarantine_all"})

    def test_invalid_dates_and_null_symbols_never_become_strings(self):
        n = pd.DataFrame(dict(id=[1, 2, 3, 4, 5], symbol=[None, " aapl ", "AAPL", "AAPL", "UNKNOWN"],
                              date=["2025-01-01", "2025-02-30", "2025-01-01T23:00:00-08:00", "2025-01-01", "2025-01-01"],
                              highlights=[None] * 5))
        clean, excluded, _, _ = clean_table("news", n)
        self.assertEqual(list(clean.id), ["4"])
        self.assertEqual(len(excluded), 4)
        self.assertTrue(pd.isna(clean.highlights.iloc[0]))

    def test_html_decode_preserves_paragraphs_and_missing(self):
        text = '  Management&#8217;s\n\n  Revenue: $1,000 &#38; more.&#160;End  '
        raw = pd.DataFrame(dict(id=[1, 2], symbol=["AAPL"] * 2,
                                date=["2025-01-01", "2025-01-02"], document_type=["10-Q"] * 2,
                                mda_content=[text, None], risk_content=[text, text]))
        clean, _, _, changes = clean_table("filings", raw)
        self.assertEqual(clean.mda_content.iloc[0], html.unescape(text).strip())
        self.assertIn("\n\n  Revenue", clean.mda_content.iloc[0])
        self.assertTrue(pd.isna(clean.mda_content.iloc[1]))
        self.assertEqual(len(changes), 3)

    def test_returns_no_fill_and_no_cross_symbol(self):
        p = prices((100., np.nan, 121., 130.)).assign(symbol=["AAPL"] * 3 + ["MSFT"])
        r = adjusted_returns(p)
        self.assertTrue(r.isna().all())
        p = prices((100., 110.)).assign(adj_close=[100., 120.])
        self.assertAlmostEqual(adjusted_returns(p).iloc[1], .2)
        with self.assertRaisesRegex(ValueError, "Sort prices"):
            adjusted_returns(p.iloc[::-1])

    def test_interval_baseline_volatility_missing_endpoints(self):
        p = prices((100., 110., 121.))
        p.date = pd.to_datetime(p.date)
        series, metrics = interval_metrics(p, "2025-01-02", "2025-01-03")
        self.assertEqual(list(series.normalized_price.round(8)), [100., 110.])
        self.assertAlmostEqual(metrics.period_return.iloc[0], .1)
        self.assertTrue(pd.isna(metrics.daily_volatility.iloc[0]))
        p.loc[0, "adj_close"] = np.nan
        series, metrics = interval_metrics(p, "2025-01-01", "2025-01-03")
        self.assertTrue(series.normalized_price.isna().all())
        self.assertTrue(pd.isna(metrics.period_return.iloc[0]))
        self.assertEqual(len(interval_metrics(p, "2026-01-01", "2026-01-02")[0]), 0)
        p.loc[0, "adj_close"] = 100.
        p.loc[1, "adj_close"] = np.inf
        series, _ = interval_metrics(p, "2025-01-01", "2025-01-03")
        self.assertTrue(pd.isna(series.normalized_price.iloc[1]))

    def test_numeric_anomalies_retained_not_clipped(self):
        raw = prices((100., 200., -1.))
        raw.loc[0, "adj_close"] = 90.  # Adjusted close may be outside unadjusted OHLC.
        raw.loc[1, "volume"] = 0
        clean, excluded, _, _ = clean_table("prices", raw)
        self.assertEqual(len(clean), 3)
        self.assertTrue(excluded.empty)
        self.assertEqual(clean.adj_close.iloc[0], 90.)
        self.assertFalse(clean.flag_ohlc.iloc[0])
        self.assertEqual(clean.close.iloc[2], -1.)
        self.assertTrue(clean.flag_invalid_numeric.iloc[2])
        self.assertTrue(clean.flag_large_move.iloc[1])
        self.assertTrue(pd.isna(adjusted_returns(clean).iloc[2]))

    def test_fractional_and_unparseable_numeric_values_fail(self):
        for col, value in [("volume", 1.5), ("close", "oops")]:
            raw = prices()
            raw[col] = raw[col].astype(object)
            raw.loc[0, col] = value
            with self.assertRaises(ValueError):
                clean_table("prices", raw)

    def test_join_aggregates_events_and_preserves_price_values(self):
        p, _, _, _ = clean_table("prices", prices())
        n = pd.DataFrame(dict(id=[1, 2, 3], symbol=["AAPL"] * 3,
                              date=pd.to_datetime(["2025-01-01", "2025-01-01", "2024-12-31"]), _source_row=[0, 1, 2]))
        audit, unmatched = join_audit(dict(prices=p, news=n, filings=n))
        self.assertEqual(audit["news"]["price_rows_after"], 3)
        self.assertEqual(len(unmatched["news"]), 1)
        with self.assertRaises(ValueError):
            join_audit(dict(prices=pd.concat([p, p]), news=n, filings=n))

    def test_adbe_exclusion_complete_even_duplicates(self):
        raw = prices().assign(symbol="ADBE")
        raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
        clean, excluded, stats, _ = clean_table("prices", raw)
        self.assertTrue(clean.empty)
        self.assertEqual(len(excluded), 4)
        self.assertEqual(stats["dispositions"], {"scope_ADBE": 4})
        self.assertEqual(stats["exact_duplicate_extra_rows"], 1)

    def test_source_hash_and_output_overlap_protection(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            run(ROOT / "sources/raw", ROOT / "sources")
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / "prices.parquet").write_bytes(b"wrong snapshot")
            digest = sha256(p / "prices.parquet")
            with self.assertRaisesRegex(ValueError, "snapshot mismatch"):
                run(p, p.parent / "unused-output")
            self.assertEqual(sha256(p / "prices.parquet"), digest)


if __name__ == "__main__":
    unittest.main()
