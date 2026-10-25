"""Conservative cleaning, provenance and validation. No dashboard calculations."""
import hashlib
import html
import json
import platform
import re
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow

from .analysis import adjusted_returns

ROOT = Path(__file__).resolve().parents[1]
TABLES = ("prices", "news", "filings")
MAG7 = ("AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA")
NUMERIC = ("open", "high", "low", "close", "adj_close", "volume")
REQUIRED = {
    "prices": ["id", "symbol", "date", *NUMERIC],
    "news": ["id", "symbol", "date", "highlights"],
    "filings": ["id", "symbol", "date", "document_type", "mda_content", "risk_content"],
}
KEYS = {"prices": ["symbol", "date"], "news": ["symbol", "date"],
        "filings": ["symbol", "date", "document_type"]}
PLACEHOLDER = (r"no substantive|cannot be (?:identified|constructed)|no basis to summarize"
               r"|I can.t provide|could not be retrieved|no (?:actual )?[A-Z]{3,5}[- ]related"
               r"|no [A-Z]{3,5} (?:content|coverage|news)|data-availability limitation"
               r"|does not contain any actual")
MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December"
          "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def latest_mentioned(value):
    if pd.isna(value):
        return pd.NaT
    candidates = re.findall(r"\b20\d\d-\d\d-\d\d\b", value)
    candidates += [f"{m} {d} {y}" for m, d, y in re.findall(
        r"\b(" + MONTHS + r")\.? (\d{1,2}),? (20\d\d)\b", value)]
    dates = [pd.to_datetime(v, errors="coerce") for v in candidates]
    return max((d for d in dates if pd.notna(d)), default=pd.NaT)


def clean_table(name, original):
    """Return clean rows, disjoint excluded rows and measured audit.

    Exact means identical across ALL original fields, before normalization.
    Nonidentical repeated IDs are quarantined in every table. Conflicting
    price business keys are quarantined as a group; event business-key repeats
    are retained and flagged (several filings/news can occur on one date).
    Invalid numeric domains are retained, flagged, and excluded by analysis.
    """
    require(set(REQUIRED[name]) <= set(original), f"{name}: required columns missing")
    require(not any(c.startswith(("_source", "flag_")) for c in original), "Expected raw input")
    d = original.copy(deep=True).reset_index(drop=True)
    d["_source_row"] = np.arange(len(d), dtype="int64")
    reasons = pd.Series("", index=d.index, dtype="string")
    exact = original.reset_index(drop=True).duplicated(keep="first")
    conversions, changes = [], []
    for col in REQUIRED[name]:
        before = d[col].copy()
        if col == "date":
            # Date-only source contract: reject timestamps, timezone shifts and truncation.
            text = before.astype("string")
            legal = text.str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)
            d[col] = pd.to_datetime(text.where(legal), format="%Y-%m-%d", errors="coerce").astype("datetime64[ns]")
        elif col in NUMERIC and name == "prices":
            d[col] = pd.to_numeric(before, errors="coerce")
            if col == "volume":
                fractional = d[col].notna() & (d[col] % 1 != 0)
                require(not fractional.any(), "Fractional volume: investigate source before exporting")
                require(not (d[col].notna() & ~np.isfinite(d[col])).any(), "Nonfinite volume")
                d[col] = d[col].astype("Int64")
            else:
                d[col] = d[col].astype("float64")
        else:
            require(before.dropna().map(lambda v: isinstance(v, (str, int, np.integer)) if col == "id" else isinstance(v, str)).all(),
                    f"{name}.{col}: unexpected value type")
            d[col] = before.astype("string")
            if col != "id":
                if name == "filings" and col in ("mda_content", "risk_content"):
                    d[col] = d[col].map(lambda v: v if pd.isna(v) else html.unescape(v)).astype("string")
                d[col] = d[col].str.strip()
            if col in ("symbol", "document_type"):
                d[col] = d[col].str.upper()
            mask = before.astype("string").fillna("<NULL>").ne(d[col].fillna("<NULL>"))
            for idx in d.index[mask]:
                # Full before/after values are recoverable from source row and formal output.
                changes.append(dict(table=name, source_row=int(idx), column=col,
                                    before_sha256=hashlib.sha256(str(before.loc[idx]).encode()).hexdigest(),
                                    after_sha256=hashlib.sha256(str(d.loc[idx, col]).encode()).hexdigest(),
                                    rule="html_decode_outer_trim" if name == "filings" and col.endswith("content") else "label_or_outer_trim"))
        failures = before.notna() & d[col].isna()
        conversions.append(dict(column=col, before_dtype=str(before.dtype), after_dtype=str(d[col].dtype),
                                conversion_failures=int(failures.sum())))
        if name == "prices" and col in NUMERIC:
            require(not failures.any(), f"{name}.{col}: numeric conversion failure; source untouched")

    # Scope precedence ensures EVERY ADBE row is kept in the exclusion register,
    # even if it is also an exact duplicate. Other issue counts remain independent.
    reasons.loc[d.symbol.eq("ADBE").fillna(False)] = "scope_ADBE"
    reasons.loc[reasons.eq("") & exact] = "exact_duplicate_keep_first_source_row"
    invalid = d.date.isna() | d.symbol.isna() | d.id.isna() | d.id.eq("")
    invalid |= ~d.symbol.isin([*MAG7, "ADBE"])
    if name == "filings":
        invalid |= d.document_type.isna() | d.document_type.eq("")
    reasons.loc[reasons.eq("") & invalid] = "invalid_key_or_unknown_symbol"
    active = d.loc[reasons.eq("")]
    id_conflict = active.id.duplicated(keep=False)
    reasons.loc[active.index[id_conflict]] = "conflicting_id_quarantine_all"
    active = d.loc[reasons.eq("")]
    business_conflict = active.duplicated(KEYS[name], keep=False)
    if name == "prices":
        reasons.loc[active.index[business_conflict]] = "conflicting_price_key_quarantine_all"
    d["flag_repeated_business_key"] = d.duplicated(KEYS[name], keep=False)
    excluded = d.loc[reasons.ne("")].copy()
    excluded["_reason"] = reasons.loc[excluded.index]
    excluded = excluded.reset_index(drop=True)
    d = d.loc[reasons.eq("")].sort_values(["symbol", "date", "id", "_source_row"], kind="stable").reset_index(drop=True)
    if name == "prices":
        d["flag_invalid_numeric"] = (~np.isfinite(d[list(NUMERIC)]).all(axis=1)
                                      | d[list(NUMERIC[:-1])].le(0).any(axis=1) | d.volume.lt(0)
                                      | d[list(NUMERIC)].isna().any(axis=1))
        d["flag_ohlc"] = (d.high.lt(d.low) | d.open.lt(d.low) | d.open.gt(d.high)
                           | d.close.lt(d.low) | d.close.gt(d.high))
        d["flag_zero_volume"] = d.volume.eq(0).fillna(False)
        # Temporary return is used only for a review flag, never persisted as a metric.
        d["flag_large_move"] = adjusted_returns(d).abs().gt(0.12).fillna(False)
        d["flag_gap_gt4_calendar_days"] = d.groupby("symbol").date.diff().dt.days.gt(4)
    elif name == "news":
        text = d.highlights
        d["flag_empty_text"] = (text.isna() | text.eq("")).fillna(True)
        d["flag_placeholder"] = (text.str.len().lt(200) | (text.str.len().lt(1000)
                                      & text.str.contains(PLACEHOLDER, flags=re.I, regex=True, na=False))).fillna(False)
        latest = text.map(latest_mentioned)
        d["flag_future_date_mention"] = latest.gt(d.date)
        # Selected findings are tied to content, not hardcoded IDs in other snapshots.
        d["flag_apparent_truncation"] = text.str.endswith(('"', '“', '‘'), na=False)
        d["flag_timing_unverified"] = True
    else:
        for col in ("mda_content", "risk_content"):
            d[f"flag_empty_{col}"] = (d[col].isna() | d[col].eq("")).fillna(True)
        d["flag_unexpected_form"] = ~d.document_type.isin(["10-K", "10-Q"])
        d["flag_short_risk_text"] = d.risk_content.str.len().lt(1000).fillna(False)
        d["flag_repeated_previous_risk"] = d.risk_content.eq(d.groupby("symbol").risk_content.shift()).fillna(False)
    require(d.id.is_unique and d[KEYS[name]].notna().all().all(), f"{name}: primary-key validation")
    if name == "prices":
        require(not d.duplicated(KEYS[name]).any(), "Price keys must be unique")
    require(len(d) + len(excluded) == len(original), f"{name}: row accounting")
    stats = dict(raw_rows=len(original), cleaned_rows=len(d), excluded_rows=len(excluded),
                 exact_duplicate_extra_rows=int(exact.sum()),
                 raw_repeated_id_rows=int(original.id.duplicated(keep=False).sum()),
                 conflicting_id_rows=int(id_conflict.sum()),
                 repeated_business_key_rows=int(business_conflict.sum()),
                 dispositions={str(k): int(v) for k, v in reasons[reasons.ne("")].value_counts().items()},
                 missing_before={c: int(v) for c, v in original.isna().sum().items()},
                 missing_after={c: int(v) for c, v in d.isna().sum().items()},
                 conversions=conversions,
                 flags={c: int(d[c].sum()) for c in d if c.startswith("flag_")})
    return d, excluded, stats, changes


def join_audit(tables):
    """Same-calendar-date descriptive joins ONLY; events aggregate before joining."""
    prices = tables["prices"]
    require(not prices.duplicated(["symbol", "date"]).any(), "Duplicate price keys")
    panel = prices.copy()
    report, unmatched = {}, {}
    for name in ("news", "filings"):
        events = tables[name]
        counts = events.groupby(["symbol", "date"], as_index=False).size().rename(columns={"size": f"{name}_count"})
        for key in ("symbol", "date"):
            counts[key] = counts[key].astype(prices[key].dtype)
        panel = panel.merge(counts, on=["symbol", "date"], how="left", validate="one_to_one", sort=False)
        require(len(panel) == len(prices), "Join multiplied price rows")
        pd.testing.assert_frame_equal(panel[list(prices)], prices, check_exact=True)
        keys = prices[["symbol", "date"]]
        left = events.merge(keys, on=["symbol", "date"], how="left", validate="many_to_one", indicator=True)
        unmatched[name] = left.loc[left._merge.eq("left_only"), ["id", "symbol", "date", "_source_row"]]
        report[name] = dict(event_rows=len(events), aggregated_keys=len(counts),
                            unmatched_event_rows=len(unmatched[name]),
                            price_rows_without_event=int(panel[f"{name}_count"].isna().sum()),
                            price_rows_before=len(prices), price_rows_after=len(panel))
    return report, unmatched


def run(raw_dir=ROOT / "sources/raw", output_dir=ROOT / "artifacts"):
    raw_dir, output_dir = Path(raw_dir).resolve(), Path(output_dir).resolve()
    require(not output_dir.is_relative_to(raw_dir) and not raw_dir.is_relative_to(output_dir),
            "Raw and output directories must not overlap")
    source = json.loads((ROOT / "sources/manifest.json").read_text(encoding="utf-8"))
    manifest_hash = sha256(ROOT / "sources/manifest.json")
    raw, clean, excluded, stats, changes, hashes = {}, {}, {}, {}, [], {}
    for name in TABLES:
        path = raw_dir / f"{name}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing local raw input: {path}. Raw data is not stored in Git. "
                                    "Obtain the complete snapshot matching sources/manifest.json and place it in --raw-dir.")
        hashes[name] = sha256(path)
        require(hashes[name] == source["tables"][name]["sha256"], f"{name}: source snapshot mismatch")
        raw[name] = pd.read_parquet(path)
        clean[name], excluded[name], stats[name], delta = clean_table(name, raw[name])
        changes += delta
        # Check each retained numeric value against its exact original source row.
        retained = raw[name].iloc[clean[name]._source_row].reset_index(drop=True)
        if name == "prices":
            for col in NUMERIC:
                pd.testing.assert_series_equal(clean[name][col], retained[col], check_dtype=False, check_exact=True)
        for col in REQUIRED[name]:
            if col in ("date", "symbol", "document_type", "id") or (name == "prices" and col in NUMERIC):
                continue
            expected = retained[col].astype("string")
            if name == "filings":
                expected = expected.map(lambda v: v if pd.isna(v) else html.unescape(v)).astype("string")
            pd.testing.assert_series_equal(clean[name][col], expected.str.strip(), check_exact=True)
    joins, unmatched = join_audit(clean)
    volume = dict(raw=int(raw["prices"].volume.sum()), cleaned=int(clean["prices"].volume.sum()),
                  excluded=int(excluded["prices"].volume.sum()))
    require(volume["raw"] == volume["cleaned"] + volume["excluded"], "Volume reconciliation")
    coverage = pd.concat([d.groupby("symbol").agg(rows=("id", "size"), first_date=("date", "min"),
                          last_date=("date", "max")).reset_index().assign(table=name)
                          for name, d in clean.items()], ignore_index=True)
    ranges = {c: dict(min=float(clean["prices"][c].min()), max=float(clean["prices"][c].max())) for c in NUMERIC}
    days = pd.DatetimeIndex(clean["prices"].date.unique()).sort_values()
    weekday_gaps = pd.bdate_range(days.min(), days.max()).difference(days).strftime("%Y-%m-%d").tolist()
    returns = adjusted_returns(clean["prices"])
    checked_returns = 0
    for _, group in clean["prices"].groupby("symbol"):
        previous = None
        for idx, value in group.adj_close.items():
            valid = pd.notna(value) and np.isfinite(value) and value > 0
            if previous is None or not valid:
                require(pd.isna(returns.loc[idx]), "Return must be missing without two valid endpoints")
            else:
                expected = float(Decimal(str(value)) / Decimal(str(previous)) - 1)
                require(np.isclose(returns.loc[idx], expected, rtol=1e-12, atol=1e-12), "Decimal return mismatch")
                checked_returns += 1
            previous = value if valid else None
    # All validations above happen before publishing any files.
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".team-stage-", dir=output_dir.parent) as temp:
        stage = Path(temp)
        for name in TABLES:
            for label, d in ((f"{name}_clean", clean[name]), (f"excluded_{name}", excluded[name])):
                path = stage / f"{label}.parquet"
                d.to_parquet(path, index=False, compression="zstd")
                pd.testing.assert_frame_equal(d, pd.read_parquet(path), check_exact=True)
        coverage.to_csv(stage / "coverage.csv", index=False, lineterminator="\n")
        pd.DataFrame(changes, columns=["table", "source_row", "column", "before_sha256", "after_sha256", "rule"]).to_csv(
            stage / "text_changes.csv", index=False, lineterminator="\n")
        for name, d in unmatched.items():
            d.to_csv(stage / f"unmatched_{name}.csv", index=False, lineterminator="\n")
        report = dict(tables=stats, source=source, source_sha256=hashes, source_manifest_sha256=manifest_hash,
                      joins=joins, volume=volume, independently_checked_returns=checked_returns,
                      missing_returns=int(returns.isna().sum()),
                      numeric_ranges=ranges, weekdays_without_observed_prices=weekday_gaps,
                      filings_before_first_price=int((clean["filings"].date < days.min()).sum()),
                      preserved_price_numeric_cells=len(clean["prices"]) * len(NUMERIC),
                      text_changed_cells=len(changes),
                      retained_text_changed_cells=sum(change["source_row"] in set(clean[change["table"]]._source_row)
                                                      for change in changes),
                      environment=dict(python=platform.python_version(), pandas=pd.__version__,
                                       numpy=np.__version__, pyarrow=pyarrow.__version__),
                      executed_checks=["pinned source SHA256", "primary keys", "row reconciliation", "volume reconciliation",
                                       "all retained price numeric values exact", "all retained narrative cells vs rule",
                                       "join cardinality and all price fields unchanged", "Parquet exact round trips",
                                       "all computable adjusted returns vs independent Decimal ratios",
                                       "raw SHA256 unchanged after run"],
                      not_verified=["upstream revision of local snapshot", "exchange calendar completeness",
                                    "news factual correctness/publication timestamps", "price adjustment methodology",
                                    "dataset redistribution license independently confirmed"])
        for name in TABLES:
            require(sha256(raw_dir / f"{name}.parquet") == hashes[name], "Raw bytes changed")
        require(sha256(ROOT / "sources/manifest.json") == manifest_hash, "Source manifest changed during run")
        report["output_sha256"] = {p.name: sha256(p) for p in sorted(stage.iterdir())}
        write_json(stage / "validation_report.json", report)
        lines = ["# Actual full-snapshot cleaning validation", "", "Generated by `python -m team_cleaning`; no historical branch checks are counted as new passes.", "",
                 "| Table | Raw | Excluded ADBE | Other excluded | Clean |", "|---|---:|---:|---:|---:|"]
        for name, s in stats.items():
            adbe = s["dispositions"].get("scope_ADBE", 0)
            lines.append(f"| {name} | {s['raw_rows']} | {adbe} | {s['excluded_rows'] - adbe} | {s['cleaned_rows']} |")
        lines += ["", f"Preserved {report['preserved_price_numeric_cells']} retained price/volume cells exactly. Volume: {volume}.",
                  f"Text cells changed: {len(changes)} across the whole source, including exclusions; "
                  f"{report['retained_text_changed_cells']} in the formal retained tables. All source hashes unchanged; all Parquet round trips exact.",
                  "", "Join audit (calendar date only; no availability or causality claim):", "", "```json", json.dumps(joins, indent=2), "```", "",
                  "Missing counts, conversions, duplicates, flags, ranges and coverage are in validation_report.json / coverage.csv.",
                  "Weekdays without observed prices are diagnostic only, not an exchange-calendar failure.", "",
                  "Not verified: " + "; ".join(report["not_verified"]) + ".", "",
                  "Two fresh-process reruns and risk tests are recorded separately in verification.json / verification.md."]
        (stage / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in stage.iterdir():
            require(not (output_dir / path.name).is_symlink(), "Symlink output refused")
        for path in stage.iterdir():
            # Copy into the destination directory so published files inherit its
            # access rules, rather than the private staging directory's ACL.
            published = output_dir / f".{path.name}.publishing"
            require(not published.exists() and not published.is_symlink(), "Stale publishing file: inspect before retry")
            with published.open("xb") as dest, path.open("rb") as src:
                shutil.copyfileobj(src, dest)
            published.replace(output_dir / path.name)
    return report
