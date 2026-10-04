"""Clean and verify local Herculean Parquet files without modifying inputs.
Usage: python cleaning.py [--data-dir data] [--output-dir cleaning_outputs]
"""
from pathlib import Path
import argparse

def run_pipeline(data_dir=None, output_dir=None):
    # Check dependencies without installing or downloading anything.
    import importlib.util
    required_packages = ['pandas', 'numpy', 'pyarrow']
    missing = [name for name in required_packages if importlib.util.find_spec(name) is None]
    if missing:
        raise ImportError('Missing packages: ' + ', '.join(missing) + '. Install the project requirements in this Python environment first.')

    # Notebook paths; the standalone script accepts command-line paths.
    from pathlib import Path
    from datetime import datetime, timezone
    import hashlib, json, platform, importlib.metadata
    import pandas as pd
    import numpy as np
    try:
        from IPython.display import display
    except ImportError:
        def display(value):
            print(value.to_string() if hasattr(value, "to_string") else value)

    REPO = 'TheFinAI/Herculean'
    SOURCE_VERSION = 'Local snapshot; identify exact files by SHA256. Upstream revision not assumed.'
    MAG7 = ['AAPL','AMZN','GOOGL','META','MSFT','NVDA','TSLA']
    TABLES = ['prices','news','filings']
    # The notebook uses the current project directory; the script supplies explicit paths.
    PROJECT_DIR = Path.cwd().resolve()
    RAW_DIR = Path(data_dir).resolve() if data_dir is not None else PROJECT_DIR / 'data'
    OUT = Path(output_dir).resolve() if output_dir is not None else PROJECT_DIR / 'cleaning_outputs'
    if RAW_DIR == OUT or RAW_DIR in OUT.parents:
        raise ValueError('Output directory must be outside the original data directory.')
    for table in TABLES:
        if not (RAW_DIR / f'{table}.parquet').is_file():
            raise FileNotFoundError(f'Missing {RAW_DIR / (table + ".parquet")}. Open the notebook from the project root.')
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option('display.max_colwidth', 100)
    pd.set_option('display.max_rows', 30)
    def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def save(df, name):
        df.to_csv(OUT / (name + '.csv'), index=False, encoding='utf-8-sig', lineterminator='\n')
        return df
    print('Output folder:', OUT)

    manifest_path = OUT / 'local_source_manifest.json'
    previous_manifest = json.loads(manifest_path.read_text('utf-8')) if manifest_path.exists() else {}
    manifest, raw = {}, {}
    for table in TABLES:
        path = RAW_DIR / f'{table}.parquet'
        digest = sha(path)
        if table in previous_manifest:
            assert previous_manifest[table]['sha256'] == digest, f'Input snapshot changed: {table}. Preserve prior results and choose a new output directory.'
        raw[table] = pd.read_parquet(path)
        manifest[table] = dict(dataset=REPO, filename=path.name, sha256=digest,
            bytes=path.stat().st_size, rows=len(raw[table]), version=SOURCE_VERSION,
            first_inspected_utc=previous_manifest.get(table, {}).get('first_inspected_utc', datetime.now(timezone.utc).isoformat()))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    display(pd.DataFrame(manifest).T)
    for table, frame in raw.items():
        print(table, frame.shape)
        display(frame.head(2))
        display(pd.DataFrame({'dtype':frame.dtypes.astype(str), 'missing':frame.isna().sum(), 'distinct':frame.nunique(dropna=False)}))

    rules = pd.DataFrame([
     ('scope','Keep MAG7 only','Project scope; ADBE is not bad data','row reconciliation + excluded records'),
     ('types','Parse dates/numbers; retain IDs as strings','Analysis needs comparable types','conversion failures + dtypes'),
     ('text','Trim boundaries; normalize line endings; uppercase codes','Remove formatting variation; preserve prose','text_changes.csv'),
     ('exact_duplicates','Drop repeated identical original rows, retain first','Avoid double counting identical source records','duplicates.csv + excluded_*.csv'),
     ('keys','Quarantine missing symbol/date and conflicting price keys','Cannot safely identify/join these rows','quarantine + logical duplicate counts'),
     ('missing','Keep unknown values missing; no imputation','Avoid fabricating evidence','missing_before_after.csv'),
     ('numeric_domain','Nonpositive price, negative/fractional volume, nonfinite -> missing','Invalid domain for these metrics','suspicious.csv + numeric_changes.csv'),
     ('unusual','Flag OHLC inconsistency, zero volume, large returns, unexpected forms','Unusual does not prove error','suspicious.csv'),
     ('merge','Aggregate events by symbol/date before left join','Prevent many-to-many multiplication','merge_audit.csv'),
     ('return','Adjusted price ratio minus one, no forward fill','Use only valid consecutive observed rows','independent Decimal calculation + counts'),
    ], columns=['rule','action','reason','check'])
    display(rules)
    save(rules, 'cleaning_log')

    PRICE_COLS = ['open','high','low','close','adj_close']
    NUMERIC = PRICE_COLS + ['volume']
    KEYS = {'prices':['symbol','date'], 'news':['symbol','date'],
            'filings':['symbol','date','document_type']}
    required = {'prices':['id','symbol','date',*NUMERIC],
                'news':['id','symbol','date','highlights'],
                'filings':['id','symbol','date','document_type','mda_content','risk_content']}
    for table in TABLES:
        assert set(required[table]) <= set(raw[table]), f'Unexpected schema: {table}'

    def text_expected(value):
        if pd.isna(value): return None
        result = str(value).replace('\r\n','\n').replace('\r','\n').strip()
        return result or None
    def first_row(table, predicate):
        matches = [i for i, row in raw[table].iterrows() if predicate(row)]
        if not matches: raise ValueError(f'No record for planned check: {table}')
        return int(matches[0])
    p_keep = int(raw['prices'].loc[raw['prices'].symbol.astype(str).str.strip().str.upper().isin(MAG7)].sort_values(['symbol','date']).index[0])
    p_drop = first_row('prices', lambda r: str(r.symbol).strip().upper() == 'ADBE')
    n_ids = [i for i,r in raw['news'].iterrows() if str(r.symbol).strip().upper() in MAG7]
    n_change = [i for i in n_ids if text_expected(raw['news'].loc[i,'highlights']) != raw['news'].loc[i,'highlights']]
    n_pick = int((n_change or n_ids)[0])
    f_pick = first_row('filings', lambda r: str(r.symbol).strip().upper() in MAG7)
    plans = [
     dict(table='prices', source_row=p_drop, field='row_presence', original='ADBE', expected='excluded:scope', reason='ADBE outside MAG7'),
     dict(table='prices', source_row=p_keep, field='daily_return', original=str(raw['prices'].loc[p_keep,'adj_close']), expected=None, reason='First observed price for this symbol has no prior denominator; return must be missing'),
     dict(table='prices', source_row=p_keep, field='date', original=str(raw['prices'].loc[p_keep,'date']), expected=str(raw['prices'].loc[p_keep,'date'])[:10], reason='Preserve calendar date'),
     dict(table='news', source_row=n_pick, field='highlights', original=raw['news'].loc[n_pick,'highlights'], expected=text_expected(raw['news'].loc[n_pick,'highlights']), reason='Boundary/newline normalization; preserve internal text'),
     dict(table='filings', source_row=f_pick, field='mda_content', original=raw['filings'].loc[f_pick,'mda_content'], expected=text_expected(raw['filings'].loc[f_pick,'mda_content']), reason='Normalize actual filing text boundaries and line endings without changing internal content'),
    ]
    # Make the five checks distinct source records, including a second retained price row.
    p_second = first_row('prices', lambda r: str(r.symbol).strip().upper() in MAG7 and r.name != p_keep)
    plans[2].update(source_row=p_second, original=str(raw['prices'].loc[p_second,'date']), expected=str(raw['prices'].loc[p_second,'date'])[:10])
    save(pd.DataFrame(plans), 'record_check_plan')
    display(pd.DataFrame(plans))

    def clean_all(source):
        cleaned, excluded, audit = {}, {}, {'types':[], 'text':[], 'duplicates':[],
            'missing':[], 'rows':[], 'numeric_changes':[]}
        for table, original in source.items():
            d = original.copy(deep=True)
            d['_source_row'] = np.arange(len(d))
            reason = pd.Series('', index=d.index, dtype='string')
            exact = original.duplicated(keep='first')
            reason.loc[exact] = 'exact_duplicate'
            for col in original.columns:
                before = d[col].copy()
                if col == 'date':
                    d[col] = pd.to_datetime(before, errors='coerce', utc=True).dt.tz_convert(None).dt.normalize()
                elif table == 'prices' and col in NUMERIC:
                    d[col] = pd.to_numeric(before, errors='coerce').astype('float64')
                else:
                    d[col] = before.astype('string').str.replace('\r\n','\n',regex=False).str.replace('\r','\n',regex=False).str.strip().replace('',pd.NA)
                    if col in ['symbol','document_type']: d[col] = d[col].str.upper()
                    changed = (before.astype('string').fillna('<NULL>') != d[col].fillna('<NULL>'))
                    for idx in d.index[changed]:
                        audit['text'].append(dict(table=table, source_row=int(idx), column=col,
                            before=before.loc[idx], after=d.loc[idx,col]))
                audit['types'].append(dict(table=table,column=col,before=str(before.dtype),after=str(d[col].dtype),
                    conversion_failures=int((before.notna() & d[col].isna()).sum()) if col=='date' or (table=='prices' and col in NUMERIC) else 0))
            invalid_key = d['symbol'].isna() | d['date'].isna()
            reason.loc[(reason=='') & invalid_key] = 'invalid_key'
            reason.loc[(reason=='') & ~d['symbol'].isin(MAG7)] = 'scope'
            active = d.loc[reason=='']
            repeated_id = active['id'].notna() & active['id'].duplicated(keep=False)
            logical = active.duplicated(KEYS[table], keep=False)
            audit['duplicates'].append(dict(table=table, exact_extra_rows=int(exact.sum()),
                raw_repeated_id_rows=int(original['id'].duplicated(keep=False).sum()),
                scoped_repeated_id_rows=int(repeated_id.sum()), scoped_logical_duplicate_rows=int(logical.sum()),
                scoped_logical_duplicate_groups=int(active.loc[logical,KEYS[table]].drop_duplicates().shape[0])))
            if table=='prices': reason.loc[active.index[logical]] = 'conflicting_price_key'
            d['_disposition'] = reason
            excluded[table] = d.loc[reason!=''].copy()
            d = d.loc[reason==''].drop(columns='_disposition').copy()
            if table=='prices':
                d['flag_invalid_numeric'] = False
                for col in NUMERIC:
                    bad = d[col].notna() & (~np.isfinite(d[col]) | ((d[col]<=0) if col in PRICE_COLS else ((d[col]<0) | (d[col]%1!=0))))
                    for idx in d.index[bad]:
                        audit['numeric_changes'].append(dict(table=table, source_row=int(d.loc[idx,'_source_row']),column=col,before=d.loc[idx,col],after=np.nan))
                    d.loc[bad,'flag_invalid_numeric'] = True
                    d.loc[bad,col] = np.nan
                d['flag_ohlc'] = ((d.high < d.low) | (d.high < d.open) | (d.high < d.close) | (d.low > d.open) | (d.low > d.close))
                d['flag_zero_volume'] = d.volume.eq(0)
            d = d.sort_values(['symbol','date','_source_row'],kind='stable').reset_index(drop=True)
            for col in original.columns:
                audit['missing'].append(dict(table=table,column=col,before=int(original[col].isna().sum()),
                    after=int(d[col].isna().sum()),before_rows=len(original),after_rows=len(d)))
            counts = reason[reason!=''].value_counts().to_dict()
            audit['rows'].append(dict(table=table,start=len(original),exact_duplicate=counts.get('exact_duplicate',0),
                invalid_key=counts.get('invalid_key',0),scope=counts.get('scope',0),
                conflicting_price_key=counts.get('conflicting_price_key',0),final=len(d)))
            cleaned[table] = d
        return cleaned, excluded, audit

    cleaned, excluded, audit = clean_all(raw)
    for key, filename in [('types','type_checks'),('text','text_changes'),('duplicates','duplicates'),
                          ('missing','missing_before_after'),('rows','row_reconciliation'),('numeric_changes','numeric_changes')]:
        evidence = pd.DataFrame(audit[key])
        if evidence.empty: evidence = pd.DataFrame(columns=['table','source_row','column','before','after'])
        save(evidence, filename)
        print(filename, 'records:', len(evidence))
        display(evidence.head(30))
    for table in TABLES:
        save(excluded[table], f'excluded_{table}')
        if table!='prices':
            save(cleaned[table].loc[cleaned[table].duplicated(KEYS[table],keep=False)], f'logical_duplicates_{table}')

    prices, news, filings = (cleaned[t] for t in TABLES)
    prices['previous_adj_close'] = prices.groupby('symbol',dropna=False)['adj_close'].shift(1)
    prices['daily_return'] = prices['adj_close'] / prices['previous_adj_close'] - 1
    prices['gap_days'] = prices.groupby('symbol')['date'].diff().dt.days
    prices['flag_large_return'] = prices.daily_return.abs().gt(0.30)
    prices['flag_date_gap'] = prices.gap_days.gt(4)
    today = pd.Timestamp.now(tz='UTC').tz_localize(None).normalize()
    suspicious = []
    for table, d in cleaned.items():
        d['flag_future_date'] = d.date.gt(today)
        if table=='news': d['flag_missing_text'] = d.highlights.isna()
        if table=='filings':
            d['flag_form'] = ~d.document_type.isin(['10-K','10-Q'])
            d['flag_missing_text'] = d[['mda_content','risk_content']].isna().any(axis=1)
        for flag in [c for c in d if c.startswith('flag_')]:
            suspicious.append(dict(table=table,check=flag,count=int(d[flag].sum()),action='keep flagged; invalid numeric cells set missing'))
        display(d.groupby('symbol').agg(rows=('date','size'),first_date=('date','min'),last_date=('date','max')))
        flag_cols = [c for c in d if c.startswith('flag_')]
        save(d.loc[d[flag_cols].any(axis=1)], f'flagged_{table}')
    save(pd.DataFrame(suspicious), 'suspicious')
    display(pd.DataFrame(suspicious))

    news_daily = news.groupby(['symbol','date'],as_index=False).agg(
        news_record_count=('_source_row','size'),news_nonmissing_text=('highlights','count'))
    filings_daily = filings.groupby(['symbol','date'],as_index=False).agg(filing_record_count=('_source_row','size'))
    panel = prices.copy()
    merge_rows = []
    for label, right in [('news',news_daily),('filings',filings_daily)]:
        keys = ['symbol','date']
        coverage = prices[keys].merge(right[keys],on=keys,how='outer',indicator=True,validate='one_to_one')
        save(coverage.loc[coverage['_merge']!='both'], f'unmatched_{label}_keys')
        before = len(panel)
        panel = panel.merge(right,on=keys,how='left',validate='one_to_one',indicator=True)
        merge_rows.append(dict(table=label,keys='symbol,date',relationship='one_to_one after aggregation',
            before=before,after=len(panel),extra_rows=len(panel)-before,
            price_keys_without_event=int(coverage['_merge'].eq('left_only').sum()),
            event_keys_without_price=int(coverage['_merge'].eq('right_only').sum()),
            matched_keys=int(coverage['_merge'].eq('both').sum())))
        panel = panel.drop(columns='_merge')
    for c in ['news_record_count','news_nonmissing_text','filing_record_count']:
        panel[c] = panel[c].fillna(0).astype('int64')
    assert len(panel)==len(prices) and not panel.duplicated(['symbol','date']).any()
    assert np.isclose(panel.volume.sum(min_count=1),prices.volume.sum(min_count=1),equal_nan=True)
    save(pd.DataFrame(merge_rows),'merge_audit')
    display(pd.DataFrame(merge_rows))

    reconciliation = pd.DataFrame(audit['rows'])
    assert (reconciliation.start == reconciliation[['exact_duplicate','invalid_key','scope','conflicting_price_key','final']].sum(axis=1)).all()
    v = pd.to_numeric(raw['prices']['volume'],errors='coerce').replace([np.inf,-np.inf],np.nan)
    volume_parts = []
    for reason, g in excluded['prices'].groupby('_disposition'):
        volume_parts.append(dict(stage=reason, rows=len(g), volume=float(v.iloc[g._source_row].sum())))
    retained_original_volume = float(v.iloc[prices._source_row].sum())
    volume_parts += [dict(stage='retained_before_domain_cleaning',rows=len(prices),volume=retained_original_volume)]
    assert np.isclose(v.sum(),sum(x['volume'] for x in volume_parts))
    volume_parts += [dict(stage='invalid_volume_removed_from_retained',rows=int(sum(x['column']=='volume' for x in audit['numeric_changes'])),volume=retained_original_volume-float(prices.volume.sum())),
                     dict(stage='cleaned',rows=len(prices),volume=float(prices.volume.sum())),
                     dict(stage='merged',rows=len(panel),volume=float(panel.volume.sum()))]
    save(pd.DataFrame(volume_parts),'volume_reconciliation')
    display(reconciliation)
    display(pd.DataFrame(volume_parts))

    from decimal import Decimal
    independent = []
    for symbol, g in prices.groupby('symbol',sort=False):
        prev = None
        for row in g.itertuples():
            current = None if pd.isna(row.adj_close) else Decimal(str(row.adj_close))
            value = np.nan if prev is None or current is None else float(current / prev - Decimal(1))
            independent.append(value)
            prev = current
    np.testing.assert_allclose(prices.daily_return.to_numpy(), independent, rtol=1e-10,atol=1e-12,equal_nan=True)
    # Artificial verification example, not a source-data record.
    toy = pd.Series([100.0,110.0,np.nan,121.0,133.1])
    np.testing.assert_allclose((toy/toy.shift()-1).to_numpy(),[np.nan,.1,np.nan,np.nan,.1],equal_nan=True,atol=1e-12)
    metrics = prices.groupby('symbol').agg(rows=('date','size'),valid_returns=('daily_return','count'),
        mean_return=('daily_return','mean'),valid_volume=('volume','count'),mean_volume=('volume','mean'))
    metrics['volume_sum'] = prices.groupby('symbol').volume.sum(min_count=1)
    metrics['missing_returns'] = metrics.rows - metrics.valid_returns
    save(metrics.reset_index(),'metrics')
    display(metrics)
    comparison = panel.assign(has_filing=panel.filing_record_count.gt(0)).groupby(
        'has_filing',dropna=False).agg(rows=('date','size'),valid_returns=('daily_return','count'),mean_return=('daily_return','mean')).reset_index()
    save(comparison,'descriptive_comparison')
    display(comparison)
    print('Price days with news:', int(panel.news_record_count.gt(0).sum()), 'of', len(panel))
    if panel.news_record_count.gt(0).all():
        print('No no-news comparison group exists. News availability cannot explain between-group return differences here.')
    print('PASS: every return independently checked; missing-value toy example passed.')

    checks=[]
    for plan in plans:
        table, source_row, field = plan['table'],plan['source_row'],plan['field']
        found = cleaned[table].loc[cleaned[table]._source_row.eq(source_row)]
        if field=='row_presence':
            dropped = excluded[table].loc[excluded[table]._source_row.eq(source_row)]
            actual = 'retained' if len(found) else 'excluded:' + str(dropped.iloc[0]['_disposition'])
        elif found.empty: actual = '<ROW EXCLUDED>'
        else:
            value = found.iloc[0][field]
            actual = None if pd.isna(value) else (value.strftime('%Y-%m-%d') if field=='date' else str(value))
        checks.append({**plan,'actual':actual,'pass':actual==plan['expected']})
    record_checks = save(pd.DataFrame(checks),'record_checks')
    display(record_checks)
    assert len(record_checks)==5 and record_checks['pass'].all()

    fresh = {t:pd.read_parquet(RAW_DIR/f'{t}.parquet') for t in TABLES}
    recleaned, reexcluded, reaudit = clean_all(fresh)
    for table in TABLES:
        base_cols = recleaned[table].columns
        pd.testing.assert_frame_equal(recleaned[table],cleaned[table][base_cols])
        pd.testing.assert_frame_equal(reexcluded[table],excluded[table])
        assert sha(RAW_DIR/f'{table}.parquet')==manifest[table]['sha256']
        save(cleaned[table],f'cleaned_{table}')
        cleaned[table].to_parquet(OUT/f'cleaned_{table}.parquet',index=False)
    save(panel,'analysis_panel')
    samples=[]
    for table, quota in [('prices',25),('news',15),('filings',10)]:
        d=cleaned[table]
        priorities={}
        def add(ids, reason):
            for i in ids: priorities.setdefault(int(i),reason)
        add([p['source_row'] for p in plans if p['table']==table and p['field']!='row_presence'],'predeclared record check')
        flags=[c for c in d if c.startswith('flag_')]
        add(d.loc[d[flags].any(axis=1),'_source_row'],'flagged difficult case')
        add(d.loc[d[required[table]].isna().any(axis=1),'_source_row'],'missing field')
        add(d.groupby('symbol',sort=True).head(1)._source_row,'symbol coverage / first observed row')
        add(d._source_row,'stable-order context')
        ids=[i for i in priorities if i in set(d._source_row)][:quota]
        chosen=d.set_index('_source_row').loc[ids].reset_index()
        chosen.insert(0,'table',table)
        chosen.insert(1,'sample_reason',[priorities[i] for i in ids])
        samples.append(chosen)
    sample=pd.concat(samples,ignore_index=True,sort=False)
    assert len(sample)<=50
    save(sample,'cleaned_sample_max50')
    versions={name:importlib.metadata.version(name) for name in ['pandas','numpy','pyarrow']}
    (OUT/'environment.json').write_text(json.dumps({'python':platform.python_version(),'packages':versions,'source_version':SOURCE_VERSION},indent=2),encoding='utf-8')
    # Checklist changes after the second run; exclude it from deterministic data hashes.
    data_files=sorted(p for p in OUT.iterdir() if p.suffix in ['.csv','.parquet'] and p.name!='checklist_14.csv')
    current_hashes={p.name:sha(p) for p in data_files}
    hash_path=OUT/'output_hashes.json'
    had_baseline=hash_path.exists()
    if had_baseline:
        baseline=json.loads(hash_path.read_text('utf-8'))
        assert baseline==current_hashes, 'Output mismatch: investigate code/data/dependency changes; preserve old baseline.'
    else:
        hash_path.write_text(json.dumps(current_hashes,indent=2),encoding='utf-8')
    print('PASS: outputs match previous complete run.' if had_baseline else 'Baseline saved. Restart Kernel and Run All to confirm reproducibility.')
    print('Sample rows:',len(sample))
    display(sample[['table','sample_reason','symbol','date','_source_row']])

    titles=['State the project vision and question','Define one row','Preserve the source','Inspect columns and types',
            'Standardize text','Investigate duplicates','Handle missing data','Check suspicious values','Verify merges',
            'Reconcile changes','Check calculations','Verify individual records','Test reproducibility','Document remaining limitations']
    refs=['Section 1','Section 2; duplicates.csv','local_source_manifest.json; raw file hashes','type_checks.csv',
          'text_changes.csv (zero changes is valid)','duplicates.csv; excluded_*.csv; logical_duplicates_*.csv',
          'missing_before_after.csv','suspicious.csv; flagged_*.csv','merge_audit.csv; unmatched_*_keys.csv',
          'row_reconciliation.csv; volume_reconciliation.csv','metrics.csv; Decimal all-row assertion',
          'record_check_plan.csv; record_checks.csv','output_hashes.json; Restart & Run All comparison','Section 14']
    statuses=['Done']*14
    notes=['']*14
    if not had_baseline:
        statuses[12]='Unresolved'; notes[12]='Baseline only; restart kernel and run all again.'
    dup=pd.DataFrame(audit['duplicates'])
    if dup.scoped_repeated_id_rows.sum() or dup.scoped_logical_duplicate_rows.sum():
        statuses[5]='Unresolved'; notes[5]='See duplicate evidence; conflicts require source confirmation; event counts may be inflated.'
    if sum(x['count'] for x in suspicious):
        statuses[7]='Unresolved'; notes[7]='Flagged records retained; inspect flagged files; may affect returns or event coverage.'
    checklist=pd.DataFrame({'item':range(1,15),'requirement':titles,'status':statuses,'evidence':refs,'explanation':notes})
    save(checklist,'checklist_14')
    display(checklist)
    print('Saved cleaned data and verification evidence to', OUT)
    print('Complete your individual PDF and project README with your name and GitHub branch details.')

if __name__ == '__main__':
    project = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=project / 'data')
    parser.add_argument('--output-dir', type=Path, default=project / 'cleaning_outputs')
    args = parser.parse_args()
    run_pipeline(args.data_dir, args.output_dir)
