# Executed verification

Command: `python verify_cleaning.py`

PASS: risk tests exited 0. Two fresh Python processes read all three pinned raw tables. All 12 generated files matched byte for byte, including the full formal tables, exclusions and validation reports. Raw SHA256 hashes remained unchanged.

Test log:

```text
test_adbe_exclusion_complete_even_duplicates (test_risks.RiskTests.test_adbe_exclusion_complete_even_duplicates) ... ok
test_event_key_repeat_kept_but_repeated_id_quarantined (test_risks.RiskTests.test_event_key_repeat_kept_but_repeated_id_quarantined) ... ok
test_exact_duplicate_vs_conflicting_price_key (test_risks.RiskTests.test_exact_duplicate_vs_conflicting_price_key) ... ok
test_fractional_and_unparseable_numeric_values_fail (test_risks.RiskTests.test_fractional_and_unparseable_numeric_values_fail) ... ok
test_html_decode_preserves_paragraphs_and_missing (test_risks.RiskTests.test_html_decode_preserves_paragraphs_and_missing) ... ok
test_interval_baseline_volatility_missing_endpoints (test_risks.RiskTests.test_interval_baseline_volatility_missing_endpoints) ... ok
test_invalid_dates_and_null_symbols_never_become_strings (test_risks.RiskTests.test_invalid_dates_and_null_symbols_never_become_strings) ... ok
test_join_aggregates_events_and_preserves_price_values (test_risks.RiskTests.test_join_aggregates_events_and_preserves_price_values) ... ok
test_numeric_anomalies_retained_not_clipped (test_risks.RiskTests.test_numeric_anomalies_retained_not_clipped) ... ok
test_returns_no_fill_and_no_cross_symbol (test_risks.RiskTests.test_returns_no_fill_and_no_cross_symbol) ... ok
test_source_hash_and_output_overlap_protection (test_risks.RiskTests.test_source_hash_and_output_overlap_protection) ... ok

----------------------------------------------------------------------
Ran 11 tests in 0.292s

OK
```
