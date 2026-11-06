"""Magnificent Seven Research Workbench. Run: streamlit run app.py."""
from datetime import date
import html
import pandas as pd
import streamlit as st
from dashboard_analysis import SYMBOLS, analyze
from dashboard_data import load
from dashboard_charts import COLORS, figure
from dashboard_state import (METRICS, initial_state, set_range, set_companies, reconcile_focus,
                             query_events, sorted_metrics, add_candidate, export_csv)

st.set_page_config(page_title='Magnificent Seven Research Workbench', page_icon='📊', layout='wide')
st.markdown('''<style>
.stApp {background:#F5F7FA;color:#18252D;font-family:system-ui,sans-serif}
.block-container {max-width:1440px;padding:2rem 24px 3rem}
h1 {font-size:30px!important;letter-spacing:-.8px} h2,h3 {font-size:18px!important}
[data-testid="stVerticalBlockBorderWrapper"] {background:white;border-radius:10px}
.st-key-filter_panel,.st-key-comparison_panel,.st-key-chart_panel,.st-key-evidence_panel,.st-key-shortlist_panel {background:white;border-radius:10px}
[data-testid="stCaptionContainer"] {color:#536171;font-size:12px}
.source-text {white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.65;user-select:text}
button:focus-visible,input:focus-visible {outline:3px solid #245A81!important;outline-offset:2px}
@media(max-width:900px){[data-testid="stHorizontalBlock"]:has(.workspace-marker){flex-direction:column}}
@media(max-width:600px){.block-container{padding:1.2rem 14px} h1{font-size:26px!important}}
</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner='Validating historical snapshot…')
def cached_load():
    return load()


try:
    tables, meta = cached_load()
except (ValueError, FileNotFoundError, OSError) as error:
    st.error(str(error))
    st.stop()

prices = tables['prices']
if 'research' not in st.session_state:
    st.session_state.research = initial_state(meta)
state = st.session_state.research


def sync_range_controls():
    st.session_state.start_input = date.fromisoformat(state['start'])
    st.session_state.end_input = date.fromisoformat(state['end'])
    st.session_state.navigator = (date.fromisoformat(state['start']), date.fromisoformat(state['end']))
    st.session_state.focus_date_input = date.fromisoformat(state['focus_date'])


def change_range(start, end, snap=False):
    try:
        set_range(state, str(start), str(end), meta, prices, snap=snap)
        sync_range_controls()
        st.session_state.notice = None
    except ValueError as error:
        st.session_state.notice = str(error)


def companies_changed(symbol):
    companies = [s for s in SYMBOLS if st.session_state[f'company_{s}']]
    try:
        set_companies(state, companies, prices)
        st.session_state.focus_company = state['focus']
        st.session_state.focus_date_input = date.fromisoformat(state['focus_date'])
        st.session_state.notice = None
    except ValueError as error:
        st.session_state[f'company_{symbol}'] = True
        st.session_state.notice = str(error)


def focus_company(symbol=None):
    state['focus'] = symbol or st.session_state.focus_company
    reconcile_focus(state, prices)
    st.session_state.focus_company = state['focus']
    st.session_state.focus_date_input = date.fromisoformat(state['focus_date'])


def chart_selected(key):
    selection = st.session_state[key]['selection']
    boxes = selection.get('box', [])
    if boxes:
        bounds = boxes[-1].get('x', [])
        if len(bounds) == 2:
            # Plotly selection dates are date-axis strings; keep their original calendar date.
            low, high = sorted(pd.Timestamp(x) for x in bounds)
            enclosed = [d for d in meta['dates'] if low <= pd.Timestamp(d) <= high]
            if enclosed:
                change_range(enclosed[0], enclosed[-1], snap=True)
            else:
                st.session_state.notice = 'No observed dates were selected. The previous range is retained.'
    elif selection.get('points'):
        point = selection['points'][-1]
        symbol, day = point['customdata'][:2]
        state.update(focus=symbol, focus_date=day, scope='Selected date')
        st.session_state.focus_company = symbol
        st.session_state.focus_date_input = date.fromisoformat(day)
        st.session_state.event_scope = 'Selected date'


def add_to_shortlist(symbol, metrics):
    try:
        add_candidate(state, next(r for r in metrics if r['symbol'] == symbol), meta['cutoff'])
        st.session_state.notice = f'{symbol} saved with a frozen research snapshot.'
    except ValueError as error:
        st.session_state.notice = str(error)


def source_text(text):
    st.markdown(f'<div class="source-text">{html.escape(text or "No excerpt supplied")}</div>', unsafe_allow_html=True)


def choose_event(key, records):
    selected = next(r for r in records if r['id'] == st.session_state[key])
    state['focus_date'] = selected['date']
    st.session_state.focus_date_input = date.fromisoformat(selected['date'])


def event_reader(kind):
    first, last = (state['focus_date'], state['focus_date']) if state['scope'] == 'Selected date' else (state['start'], state['end'])
    matches = query_events(tables[kind], state['focus'], first, last)
    noun = 'news digest' if kind == 'news' else 'filing excerpt'
    if kind == 'news':
        st.caption('News publication timing is unverified. Digests are not individual article counts or established causes of price movements.')
    st.caption(f'{len(matches)} matching {noun} records')
    if not matches:
        scope = 'date' if state['scope'] == 'Selected date' else 'interval'
        st.info(f'No {noun} for this company and {scope}')
        return
    context = f"event_{kind}_{state['focus']}_{state['scope']}_{first}_{last}"
    by_id = {r['id']: r for r in matches}
    selected_id = st.selectbox(f'Open {noun}', list(by_id), key=context,
                              format_func=lambda rid: f"{by_id[rid]['date']} · ID {rid}" + (f" · {by_id[rid]['document_type']}" if kind == 'filings' else ''),
                              on_change=choose_event, args=(context, matches))
    record = by_id[selected_id]
    st.caption(f"{record['symbol']} · {record['date']} · ID {record['id']} · Source row {record['_source_row']}")
    flags = [k.removeprefix('flag_').replace('_', ' ').capitalize() for k, v in record.items() if k.startswith('flag_') and v and k != 'flag_timing_unverified']
    st.caption('Review cues: ' + (', '.join(flags) if flags else 'No additional active flags'))
    text = record.get('highlights') if kind == 'news' else record.get('mda_content')
    st.caption('Preview')
    source_text((text or '')[:240] + ('…' if text and len(text) > 240 else ''))
    with st.container(height=420, border=True):
        if kind == 'news':
            source_text(record['highlights'])
        else:
            st.markdown(f"**{record['document_type']} · MD&A excerpt**")
            source_text(record['mda_content'])
            st.markdown('**Risk excerpt**')
            source_text(record['risk_content'])


st.title('Magnificent Seven Research Workbench')
st.write('Compare historical price performance, trading activity, and company disclosures to choose one or two stocks for deeper research.')
st.caption(f"HISTORICAL SNAPSHOT · Price cutoff {meta['cutoff']} · TheFinAI/Herculean · {meta['snapshot']}")

if 'start_input' not in st.session_state:
    sync_range_controls()
for symbol in SYMBOLS:
    st.session_state.setdefault(f'company_{symbol}', True)
st.session_state.setdefault('focus_company', state['focus'])

with st.container(border=True, key='filter_panel'):
    st.subheader('Research interval')
    for col, symbol in zip(st.columns(7), SYMBOLS):
        col.checkbox(symbol, key=f'company_{symbol}', on_change=companies_changed, args=(symbol,))
    with st.form('date_range'):
        a, b, c = st.columns([2, 2, 1])
        a.date_input('Start date', key='start_input')
        b.date_input('End date', key='end_input')
        c.form_submit_button('Apply range', on_click=lambda: change_range(st.session_state.start_input, st.session_state.end_input), width='stretch')
    a, b, c, d = st.columns([2, 2, 2, 1])
    a.radio('Price display', ['Indexed to 100', 'Source units'], horizontal=True, key='price_mode')
    b.radio('Volume display', ['Shares', 'Relative volume'], horizontal=True, key='volume_mode')
    c.selectbox('Sort metric', list(METRICS), key='sort_metric', on_change=lambda: st.session_state.update(sort_direction='Descending'))
    d.selectbox('Sort direction', ['Descending', 'Ascending'], key='sort_direction')

if st.session_state.get('notice'):
    st.info(st.session_state.notice)
st.caption(f"Selected historical period: {state['start']} through {state['end']} (inclusive)")
results = analyze(prices, state['companies'], state['start'], state['end'])
ordered = sorted_metrics(results, METRICS[st.session_state.sort_metric], st.session_state.sort_direction == 'Descending')

with st.container(border=True, key='comparison_panel'):
    st.subheader('Company comparison')
    st.caption('Select a row to focus its evidence. Sort with the controls above; values are unrounded for sorting. Volatility is daily and unannualized.')
    table = pd.DataFrame([dict(Company=r['symbol'], **{
        'Interval return': r['period_return'] * 100 if r['period_return'] is not None else None,
        'Daily volatility': r['daily_volatility'] * 100 if r['daily_volatility'] is not None else None,
        'Average daily volume': r['average_daily_volume'],
        'Maximum drawdown': r['max_drawdown'] * 100 if r['max_drawdown'] is not None else None,
        'Observations': r['n_prices'], 'Research action': 'Add using controls below',
    }) for r in ordered])
    styled = table.style.format({'Interval return': '{:+.2f}%', 'Daily volatility': '{:.2f}%',
                                'Average daily volume': '{:,.0f}', 'Maximum drawdown': '{:.2f}%'}, na_rep='N/A')
    styled = styled.map(lambda s: f'color:{COLORS[s]};font-weight:600', subset=['Company'])
    table_key = 'comparison_' + '_'.join(r['symbol'] for r in ordered)

    def table_selected():
        rows = st.session_state[table_key]['selection']['rows']
        if rows:
            focus_company(ordered[rows[0]]['symbol'])

    st.dataframe(styled, hide_index=True, width='stretch', height=284,
                 key=table_key, on_select=table_selected, selection_mode='single-row',
                 column_config={'Company': st.column_config.TextColumn(pinned=True)})
    a, b = st.columns([3, 1])
    candidate = a.selectbox('Company to add', state['companies'], key='candidate')
    b.button('Add to shortlist', on_click=add_to_shortlist, args=(candidate, results), width='stretch')
    with st.expander('Observation coverage and valid return counts'):
        st.dataframe(pd.DataFrame([{k: r[k] for k in ['symbol', 'range_start', 'range_end', 'first_observation_date', 'last_observation_date', 'n_prices', 'n_returns']} for r in ordered]), hide_index=True, width='stretch')

left, right = st.columns([2, 1], gap='large')
with left:
    st.markdown('<span class="workspace-marker"></span>', unsafe_allow_html=True)
    with st.container(border=True, key='chart_panel'):
        st.subheader('Price performance & trading activity')
        st.caption('Drag a horizontal box to apply a shared research interval; select a point to read its evidence. Company checkboxes control both charts.')
        if not any(r['n_prices'] for r in results):
            st.info('No observed prices in this interval. Matching event records remain available.')
        price_field = 'normalized' if st.session_state.price_mode == 'Indexed to 100' else 'adj_close'
        price_title = 'Indexed to 100' if price_field == 'normalized' else 'Adjusted close (source units)'
        revision = f"{state['start']}_{state['end']}_{','.join(state['companies'])}_{state['focus']}"
        for field, title, height, name in [(price_field, price_title, 340, 'price'),
                ('volume' if st.session_state.volume_mode == 'Shares' else 'relative_volume', 'Volume (shares)' if st.session_state.volume_mode == 'Shares' else 'Relative volume (×)', 240, 'volume')]:
            key = f'{name}_{revision}_{field}'
            chart = figure(results, field, title, state['start'], state['end'], state['focus'], height)
            st.plotly_chart(chart, key=key, on_select=lambda k=key: chart_selected(k), selection_mode=['points', 'box'], width='stretch', config={'displayModeBar': False})
        st.caption('Relative volume uses exactly the preceding 20 observed volumes, excludes today, and retains full-history lookback. Unavailable values are gaps.')
        st.markdown('**Full-history overview · base 100 at each company’s first full-history observation**')
        overview = analyze(prices, state['companies'], meta['min_date'], meta['cutoff'])
        key = f'overview_{revision}'
        overview_fig = figure(overview, 'normalized', 'Overview context', meta['min_date'], meta['cutoff'], state['focus'], 100, overview=True)
        overview_fig.add_vrect(x0=state['start'], x1=state['end'], fillcolor='#245A81', opacity=.12, line_width=0)
        st.plotly_chart(overview_fig, key=key, on_select=lambda k=key: chart_selected(k), selection_mode='box', width='stretch', config={'displayModeBar': False})
        st.slider('Shared date navigator', min_value=date.fromisoformat(meta['min_date']), max_value=date.fromisoformat(meta['cutoff']), key='navigator', format='YYYY-MM-DD', on_change=lambda: change_range(*st.session_state.navigator, snap=True))
        st.button('Full history', on_click=change_range, args=(meta['min_date'], meta['cutoff']))

with right:
    st.markdown('<span class="workspace-marker"></span>', unsafe_allow_html=True)
    with st.container(border=True, key='evidence_panel'):
        st.subheader('Event evidence')
        st.selectbox('Focus company', state['companies'], key='focus_company', on_change=focus_company)
        st.date_input('Focus date', min_value=date.fromisoformat(state['start']), max_value=date.fromisoformat(state['end']), key='focus_date_input', on_change=lambda: state.update(focus_date=str(st.session_state.focus_date_input)))
        st.radio('Event scope', ['Selected date', 'Selected interval'], horizontal=True, key='event_scope', on_change=lambda: state.update(scope=st.session_state.event_scope))
        st.caption(f"{state['focus']} · Focused date {state['focus_date']}")
        news_tab, filing_tab = st.tabs(['News', 'Filings'])
        with news_tab:
            event_reader('news')
        with filing_tab:
            event_reader('filings')

with st.container(border=True, key='shortlist_panel'):
    st.subheader('Research shortlist')
    st.caption('Choose up to two research candidates. Snapshots stay frozen when filters change. Browser reload or a new session clears the shortlist; export CSV to save it.')
    if not state['shortlist']:
        st.info('No research candidates saved. Add a company from the comparison controls, then write a reason.')
    for snapshot in state['shortlist']:
        symbol = snapshot['symbol']
        st.markdown(f"**{symbol} · {snapshot['range_start']} through {snapshot['range_end']}**")
        def percent(value):
            return 'N/A' if value is None else f'{value:.2%}'
        st.caption(f"Frozen snapshot · Return {percent(snapshot['period_return'])} · Daily volatility {percent(snapshot['daily_volatility'])} · Maximum drawdown {percent(snapshot['max_drawdown'])} · Average volume {'N/A' if snapshot['average_daily_volume'] is None else format(snapshot['average_daily_volume'], ',.0f')} shares · {snapshot['n_prices']} observations / {snapshot['n_returns']} valid returns · Actual {snapshot['first_observation_date']}–{snapshot['last_observation_date']} · Cutoff {snapshot['data_as_of']}")
        reason_key = f'reason_{symbol}'
        st.session_state.setdefault(reason_key, snapshot['reason'])
        st.text_area(f'Research reason for {symbol}', key=reason_key, on_change=lambda r=snapshot, k=reason_key: r.update(reason=st.session_state[k]))
        def remove_candidate(s=symbol):
            state['shortlist'] = [r for r in state['shortlist'] if r['symbol'] != s]
            st.session_state.pop(f'reason_{s}', None)
        st.button(f'Remove {symbol}', on_click=remove_candidate, key=f'remove_{symbol}')
    can_export = bool(state['shortlist']) and all(r['reason'].strip() for r in state['shortlist'])
    st.download_button('Export research shortlist CSV', data=export_csv(state['shortlist']) if can_export else b'',
                       file_name='mag7_research_shortlist.csv', mime='text/csv', disabled=not can_export,
                       on_click=lambda: st.session_state.update(notice='CSV download prepared. Save the file to preserve your shortlist.'))
    if not can_export:
        st.caption('Export requires one or two candidates and a non-whitespace reason for each.')

with st.expander('Source coverage, metric definitions & data-quality limitations'):
    for kind, identity in meta['identity'].items():
        st.write(f"{kind.capitalize()}: {identity['shape'][0]:,} records · {identity['first_date']} through {identity['last_date']}")
        flags = {field: sum(bool(r[field]) for r in tables[kind]) for field in tables[kind][0] if field.startswith('flag_')}
        st.caption('Existing review flags: ' + ', '.join(f"{k.removeprefix('flag_').replace('_', ' ')}: {v:,}" for k, v in flags.items()))
    st.write('Source: team-cleaned TheFinAI/Herculean, team-local-sha256-v1. Upstream revision and price-adjustment methodology remain unconfirmed. Adjusted-close changes are not verified total shareholder returns; source units have no supplied currency field.')
    st.write('Interval return uses actual first/last interval rows. Daily volatility is the sample standard deviation of adjacent valid observed-session returns (ddof=1), without annualization. Maximum drawdown is the largest within-interval adjusted-close peak-to-trough decline; any invalid price makes it unavailable. Average volume includes valid zeros. Missing values are never replaced by zero.')
    st.write('News is supplied digest text, not article counts; publication timing is unverified. Filing text contains MD&A and risk excerpts, not complete documents. Heuristic flags are review cues and do not prove errors. Events retain their original calendar dates, including weekends, and do not establish causation. Calendar gaps are not independently verified exchange holidays. Earlier filings remain loaded but outside the price-bounded research range.')
st.caption('Historical research and prioritization only. The shortlist records analyst-written reasons; it is not an investment recommendation.')
