"""Run with: .venv/bin/python -m unittest discover -s . -p 'test_clean_data.py'."""

import html
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

import clean_data as cleaning


class CleaningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = {name: pd.read_parquet(cleaning.ROOT / "data" / f"{name}.parquet") for name in cleaning.TABLES}

    def test_filing_formatting_preserves_meaning_and_structure(self):
        frame = self.raw["filings"].iloc[:1].copy()
        text = '  Management&#8217;s\n\n  &#8226; Revenue: $1,000 &#38; no decline.&#160;End  '
        frame.loc[frame.index[0], "mda_content"] = text
        cleaned = cleaning.clean_table("filings", frame)
        self.assertEqual(cleaned.mda_content.iloc[0], 'Management’s\n\n  • Revenue: $1,000 & no decline.\u00a0End')
        pd.testing.assert_frame_equal(cleaned, cleaning.clean_table("filings", cleaned), check_exact=True)

    def test_invalid_values_fail_without_mutating_input(self):
        cases = [
            ("duplicate ID", "id", lambda f: f.id.iloc[1]),
            ("unknown symbol", "symbol", lambda f: "UNKNOWN"),
            ("invalid date", "date", lambda f: "2025-02-30"),
            ("negative price", "open", lambda f: -1.0),
            ("range violation", "high", lambda f: f.low.iloc[0] - 1),
            ("infinite price", "close", lambda f: np.inf),
            ("missing price", "close", lambda f: np.nan),
            ("negative volume", "volume", lambda f: -1),
        ]
        for label, column, value in cases:
            with self.subTest(label=label):
                frame = self.raw["prices"].copy()
                frame.loc[0, column] = value(frame)
                before = frame.copy(deep=True)
                with self.assertRaises(ValueError):
                    cleaning.validate("prices", frame)
                pd.testing.assert_frame_equal(frame, before, check_exact=True)
        frame = self.raw["prices"].copy()
        frame["volume"] = frame.volume.astype(float)
        frame.loc[0, "volume"] = 1.5
        with self.assertRaisesRegex(ValueError, "volume must be int64"):
            cleaning.validate("prices", frame)

    def test_duplicate_key_and_blank_narrative_rejected(self):
        frame = self.raw["news"].copy()
        frame.loc[1, "date"] = frame.loc[0, "date"]
        with self.assertRaisesRegex(ValueError, "duplicate company/date"):
            cleaning.validate("news", frame)
        frame = self.raw["news"].copy()
        frame.loc[0, "highlights"] = " \n "
        with self.assertRaisesRegex(ValueError, "blank text"):
            cleaning.validate("news", frame)

    def test_adjusted_close_and_repeated_risk_text_retained(self):
        prices = self.raw["prices"]
        cleaning.validate("prices", prices)
        self.assertEqual(int(((prices.adj_close < prices.low) | (prices.adj_close > prices.high)).sum()), 199)
        cleaned = cleaning.clean_table("filings", self.raw["filings"])
        self.assertEqual(len(cleaned), 73)
        self.assertEqual(int(cleaned.risk_content.duplicated().sum()), 7)
        self.assertTrue(cleaned.id.is_unique)

    def test_exports_reproducible_complete_and_raw_preserved(self):
        source = cleaning.ROOT / "data"
        hashes_before = {p.name: cleaning.sha256(p) for p in source.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "cleaned"
            first = cleaning.run(output)
            hashes_first = {p.name: cleaning.sha256(p) for p in output.iterdir()}
            second = cleaning.run(output)
            self.assertEqual(first, second)
            self.assertEqual(hashes_first, {p.name: cleaning.sha256(p) for p in output.iterdir()})
            self.assertEqual(len(hashes_first), 10)
            for name in cleaning.TABLES:
                exported = pd.read_parquet(output / f"{name}.parquet")
                expected = self.raw[name].copy()
                if name == "filings":
                    for column in ["mda_content", "risk_content"]:
                        expected[column] = expected[column].map(lambda x: html.unescape(x).strip())
                pd.testing.assert_frame_equal(exported, expected, check_exact=True)
            report = json.loads((output / "quality_report.json").read_text())
            self.assertEqual(report["coverage"]["news_without_same_date_price"], 1232)
            self.assertEqual(report["coverage"]["weekend_news"], 1112)
            self.assertEqual(report["coverage"]["filings_before_prices"], 32)
            self.assertEqual(len(report["coverage"]["weekdays_without_prices"]), 15)
            self.assertTrue(all(record["passed"] for record in report["record_checks"]))
            flags = pd.read_csv(output / "review_flags.csv")
            self.assertEqual(set(zip(flags.table, flags.id)), {("news", 543), ("news", 1005), ("news", 2), ("prices", 2412)})
            coverage = pd.read_csv(output / "coverage.csv")
            self.assertEqual(len(coverage), 24)
            self.assertEqual(coverage.groupby("table").rows.sum().to_dict(), {"news": 3888, "prices": 2656, "filings": 73})
        self.assertEqual(hashes_before, {p.name: cleaning.sha256(p) for p in source.iterdir() if p.is_file()})

    def test_raw_directory_cannot_be_output(self):
        with self.assertRaisesRegex(ValueError, "Output must be separate"):
            cleaning.run(cleaning.ROOT / "data")


if __name__ == "__main__":
    unittest.main()
