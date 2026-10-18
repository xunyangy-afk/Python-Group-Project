Suggested title: Unify Mag7 cleaning with full datasets, provenance and reproducible validation

Prepare three separate, complete Magnificent Seven tables for junior equity research. This consolidates the actual implementations from Evelyn-Workbook, Jim-Work, Olivia-work, Peter-work, Zack-Work and cleaning-nicole without sequential branch merges. CLEANING_DECISIONS.md records source commits, implementation differences, adopted rules and unconfirmed proposals.

The pipeline preserves local raw inputs with SHA256 provenance, retains ADBE exclusions, distinguishes exact duplicates from conflicting keys, decodes filing HTML while preserving paragraphs, and retains suspicious prices/news with review flags. Raw inputs are local-only and ignored by Git; their manifest remains tracked. Analysis is separate: adjusted-close returns explicitly disable forward fill; normalization and interval metrics accept a date range and leave unestimable volatility missing. Date-only news is not presented as safe for predictive alignment.

Validation executed with `python verify_cleaning.py`:

- 11 risk tests passed; two fresh-process full runs produced 12 byte-identical files and unchanged raw SHA256 hashes.
- Full formal tables: prices 2,324; news 3,402; filings 63. ADBE exclusions: 332 / 486 / 10; no other rows excluded in this snapshot.
- No source-field missingness, exact duplicates, ID conflicts, price-key conflicts, invalid numeric domains or OHLC inconsistencies found. All 13,944 retained price/volume values are exact; volume reconciles.
- 146 filing text cells formatted across the full source (126 retained, 20 in ADBE exclusions); 2,317 calculable adjusted returns verified independently with Decimal; first returns remain missing.
- Both aggregated event joins retained 2,324 price rows and every price field. Unmatched 1,078 news and 28 filing records are retained and audited.
- All complete formal Parquet tables, source metadata and audit evidence are included; raw inputs are obtained separately and checked against the manifest. The largest formal file is about 5.37 MB, so ordinary Git is sufficient.

Team review remains necessary for the proposed 12%/text thresholds, conflict quarantine rules and interval metric conventions. Upstream revision, source date semantics, price adjustment methodology and exchange-calendar completeness are unverified. The upstream fixed-revision request required authentication; individual documentation reports CC BY 4.0, but redistribution terms still require confirmation from a member with source access before public publication. The local snapshot is identified by exact hashes, not an inferred upstream revision.

No Dashboard is included. This PR merges the unified analysis-ready solution into main at the repository owner's request; unresolved methodological and provenance questions remain documented rather than being represented as unanimous team approval.
