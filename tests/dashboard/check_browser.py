"""Independent browser environment: standard library + Playwright only."""
import argparse
import csv
import io
import json
import math
from pathlib import Path
import traceback

from playwright.sync_api import sync_playwright


def compare(actual, expected, path='result'):
    if isinstance(expected,dict):
        assert set(actual)==set(expected),(path,'keys')
        for key,value in expected.items():compare(actual[key],value,path+'.'+key)
    elif isinstance(expected,list):
        assert len(actual)==len(expected),(path,'length',len(actual),len(expected))
        for i,(a,e) in enumerate(zip(actual,expected)):compare(a,e,f'{path}[{i}]')
    elif isinstance(expected,(float,int)) and not isinstance(expected,bool):
        assert actual is not None and math.isfinite(actual),(path,actual,expected)
        tolerance=1e-6 if 'volume' in path and 'relative_volume' not in path else 1e-10
        assert abs(actual-expected)<=tolerance,(path,actual,expected)
    else:assert actual==expected,(path,actual,expected)


def run(html,chrome):
    out=html.parent/'dashboard_verification';out.mkdir(exist_ok=True)
    report={'checks':[], 'errors':[], 'external_requests':[]}
    def passed(name):report['checks'].append(name);print('PASS',name)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=str(chrome),headless=True)
        report['browser']=browser.version
        context=browser.new_context(viewport={'width':1440,'height':900},accept_downloads=True)
        context.route('http://**/*',lambda route:(report['external_requests'].append(route.request.url),route.abort())[-1])
        context.route('https://**/*',lambda route:(report['external_requests'].append(route.request.url),route.abort())[-1])
        page=context.new_page();page.on('pageerror',lambda error:report['errors'].append(str(error)))
        try:
            page.goto(html.as_uri(),wait_until='load');page.evaluate('async()=>await Mag7.ready')
            page.wait_for_function("document.querySelector('#priceChart')._fullLayout && document.querySelector('#navigator')._fullLayout")
            passed('file:// opened with external network blocked')
            for case in json.loads((out/'reference.json').read_text(encoding='utf-8')):
                actual=page.evaluate('(c)=>Mag7.metrics.analyze(c.production?Mag7.state.data.prices:c.prices,c.symbols,c.start,c.end)',case)
                compare(actual,case['expected'],case['name'])
            passed('Python/browser parity: all synthetic fixtures and three real intervals, including every series value and null')
            evidence=json.loads((out/'real_data.json').read_text(encoding='utf-8'))
            state=page.evaluate('Mag7.state.s')
            assert [state['start'],state['end']]==evidence['default_range']
            assert state['companies']==['AAPL','MSFT','GOOGL','AMZN','NVDA','META','TSLA']
            assert page.locator('#comparison tr').count()==7
            assert page.evaluate('Mag7.state.data.meta.cutoff')=='2026-03-31'
            assert page.evaluate('Mag7.current.every(m=>m.series[0].normalized_price===100)')
            assert page.evaluate('Mag7.state.data.filings.length')==63
            assert page.evaluate("Mag7.state.data.filings.some(r=>r.date<Mag7.state.data.meta.min)")
            passed('Default seven companies, last 60 observed dates, cutoff and full event payload')
            plotted=page.evaluate("() => {const p=document.getElementById('priceChart').data.find(r=>r.name==='AAPL');const v=document.getElementById('volumeChart').data.find(r=>r.name==='AAPL');return {price:p.customdata.at(-1),volume:v.y.at(-1),day:p.x.at(-1),ret:Mag7.current.find(m=>m.symbol==='AAPL').period_return}}")
            assert plotted['price']==evidence['aapl_last']['adj_close']
            assert plotted['volume']==evidence['aapl_last']['volume']
            assert plotted['day']==evidence['aapl_last']['date']
            assert abs(plotted['ret']-evidence['independent_endpoint_return'])<1e-10
            report['aapl_chart_check']=plotted;passed('Actual AAPL Parquet endpoints, chart values and independently calculated interval return')
            for kind in ['news','filings']:
                original=evidence[kind]
                page.locator('[data-tab='+kind+']').click()
                if kind=='filings':page.locator('input[name=scope][value=interval]').check()
                card=page.locator('.event-card').filter(has=page.locator('.event-meta',has_text='ID '+original['id']+' ·'))
                assert card.count()==1
                assert card.locator('.event-toggle').get_attribute('aria-expanded')=='true'
                texts=card.locator('.event-body p').all_text_contents()
                assert texts==([original['highlights']] if kind=='news' else [original['mda_content'],original['risk_content']])
            passed('Real news and filing IDs/full paragraph text match Parquet exactly')
            # A range drag uses the real Plotly relayout event used by navigator handles.
            for symbol in ['MSFT','GOOGL','AMZN','META','TSLA']:
                page.locator('#companies input[value='+symbol+']').uncheck()
            page.evaluate('async()=>await Mag7.render()')
            # Real mouse drags, as well as the programmatic event parity check below.
            for chart in ['priceChart','volumeChart']:
                target=page.locator('#'+chart+' .nsewdrag');target.scroll_into_view_if_needed()
                bounds=target.bounding_box();before=page.evaluate('Mag7.state.s.start')
                y=bounds['y']+bounds['height']*.5
                page.mouse.move(bounds['x']+bounds['width']*.15,y);page.mouse.down()
                page.mouse.move(bounds['x']+bounds['width']*.85,y,steps=16);page.mouse.up()
                page.wait_for_function('(old)=>Mag7.state.s.start!==old',arg=before)
                page.evaluate('async()=>await Mag7.render()')
            # Drag the actual minimum handle in the full-history navigator.
            handle=page.locator('#navigator .rangeslider-grabber-min');handle.scroll_into_view_if_needed()
            bounds=handle.bounding_box();before=page.evaluate('Mag7.state.s.start')
            page.mouse.move(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2);page.mouse.down()
            page.mouse.move(bounds['x']-35,bounds['y']+bounds['height']/2,steps=12);page.mouse.up()
            page.wait_for_function('(old)=>Mag7.state.s.start!==old',arg=before)
            page.evaluate('async()=>await Mag7.render()')
            assert page.evaluate("()=>{const p=document.getElementById('navigator');return p.querySelector('.rangeslider-container').getBoundingClientRect().bottom<=p.getBoundingClientRect().bottom}")
            passed('Real mouse drags on both charts and navigator handles update the shared interval; navigator is not clipped')
            page.evaluate("async()=>{await Mag7.render();await Plotly.relayout('navigator',{'xaxis.range':['2025-06-01','2025-08-30']});}")
            page.wait_for_function("Mag7.state.s.start==='2025-06-02' && Mag7.state.s.end==='2025-08-29'")
            page.evaluate('async()=>await Mag7.render()')
            drag=page.evaluate('({start:Mag7.state.s.start,end:Mag7.state.s.end,metrics:Mag7.current})')
            page.locator('#start').fill(drag['start']);page.locator('#end').fill(drag['end']);page.get_by_role('button',name='Apply dates').click()
            page.evaluate('async()=>await Mag7.render()');compare(page.evaluate('Mag7.current'),drag['metrics'])
            passed('Navigator range event and date inputs produce identical shared state and metrics')
            baseline=page.evaluate('({current:Mag7.current,date:Mag7.state.s.date,scope:Mag7.state.s.scope,tab:Mag7.state.s.tab})')
            page.locator('#priceMode').select_option('adj_close');page.locator('#volumeMode').select_option('relative_volume')
            page.evaluate('async()=>await Mag7.render()')
            compare(page.evaluate('({current:Mag7.current,date:Mag7.state.s.date,scope:Mag7.state.s.scope,tab:Mag7.state.s.tab})'),baseline)
            assert page.evaluate("document.getElementById('volumeChart').layout.shapes[0].y0")==1
            passed('Display modes preserve metrics/event state; relative-volume chart has 1x line')
            # Point selection routed through Plotly event, with unchanged global interval.
            page.evaluate("document.getElementById('priceChart').emit('plotly_click',{points:[{data:{name:'NVDA'},x:'2025-07-15'}]})")
            assert page.evaluate('Mag7.state.s.focus')=='NVDA'
            assert page.evaluate('Mag7.state.s.date')=='2025-07-15'
            assert page.evaluate('Mag7.state.s.start')==drag['start']
            passed('Plotly point event focuses company/date without changing range')
            page.locator('#start').fill('2025-07-05');page.locator('#end').fill('2025-07-06');page.get_by_role('button',name='Apply dates').click();page.evaluate('async()=>await Mag7.render()')
            assert page.evaluate('Mag7.current.every(m=>m.n_prices===0&&m.period_return===null)')
            page.locator('[data-tab=news]').click();page.locator('input[name=scope][value=interval]').check()
            first=page.locator('.event-card').first
            assert first.count()==1
            weekend_id=first.get_attribute('data-id');first.locator('button').click()
            assert page.evaluate('Mag7.state.s.scope')=='interval'
            assert page.evaluate("['2025-07-05','2025-07-06'].includes(Mag7.state.s.date)")
            report['weekend_event_id']=weekend_id;passed('Weekend-only interval has no fabricated prices and original-date news remains readable')
            # Restore useful interval and test actual UI actions/CSV download.
            page.locator('#start').fill(evidence['default_range'][0]);page.locator('#end').fill(evidence['default_range'][1]);page.get_by_role('button',name='Apply dates').click();page.evaluate('async()=>await Mag7.render()')
            page.get_by_role('button',name='Add AAPL to shortlist',exact=True).click()
            reason='Research, "cash flow"\nsecond line'
            page.get_by_role('textbox',name='AAPL research reason').fill(reason)
            frozen=page.evaluate('structuredClone(Mag7.state.s.shortlist[0])')
            page.get_by_role('button',name='Add NVDA to shortlist',exact=True).click()
            page.get_by_role('textbox',name='NVDA research reason').fill('=HYPERLINK("test")')
            # Make a third company visible, then reject its addition.
            page.locator('#companies input[value=MSFT]').check();page.get_by_role('button',name='Add MSFT to shortlist',exact=True).click()
            assert page.evaluate('Mag7.state.s.shortlist.length')==2
            assert 'full' in page.locator('#notice').inner_text()
            page.locator('#companies input[value=AAPL]').uncheck();page.locator('#full').click();page.evaluate('async()=>await Mag7.render()')
            compare(page.evaluate('Mag7.state.s.shortlist[0]'),frozen)
            with page.expect_download() as info:page.locator('#export').click()
            download=info.value;assert download.suggested_filename=='mag7_research_shortlist.csv'
            download.save_as(out/'tested_shortlist.csv')
            rows=list(csv.DictReader(io.StringIO((out/'tested_shortlist.csv').read_text(encoding='utf-8'))))
            assert rows[0]['reason']==reason
            assert rows[1]['reason'].startswith("'=")
            assert abs(float(rows[0]['period_return_pct'])-frozen['period_return']*100)<1e-10
            assert list(rows[0])==page.evaluate('Mag7.state.columns')
            page.get_by_role('button',name='Remove NVDA',exact=True).click()
            page.get_by_role('button',name='Add NVDA to shortlist',exact=True).click()
            assert page.evaluate('Mag7.state.s.shortlist.length')==2
            passed('Frozen shortlist, third-entry rejection, hidden-company retention, removal/re-addition and real CSV download/round-trip/formula safety')
            # Validation and sort semantics, with deliberately missing metrics.
            current=page.evaluate('({start:Mag7.state.s.start,end:Mag7.state.s.end})')
            assert not page.evaluate("Mag7.state.range('2026-03-31','2025-01-01')")
            assert not page.evaluate("Mag7.state.range('2024-01-01','2026-03-31')")
            compare(page.evaluate('({start:Mag7.state.s.start,end:Mag7.state.s.end})'),current)
            for key in ['period_return','daily_volatility','average_volume','max_drawdown']:
                page.locator('#sort').select_option(key)
                values=page.locator('td[data-metric='+key+']').evaluate_all('(els)=>els.map(e=>e.dataset.value===""?null:Number(e.dataset.value))')
                numeric=[v for v in values if v is not None];assert numeric==sorted(numeric,reverse=True)
                page.locator('button[data-sort='+key+']').click()
                values=page.locator('td[data-metric='+key+']').evaluate_all('(els)=>els.map(e=>e.dataset.value===""?null:Number(e.dataset.value))')
                numeric=[v for v in values if v is not None];assert numeric==sorted(numeric)
            passed('Invalid ranges retained; all metric sorts toggle in UI')
            # Safe literal markup and same-day distinct event records in memory only.
            inert='literal </script><img src=x onerror="window.__unsafe=1">\n\nSecond paragraph'
            page.evaluate('(text)=>{Mag7.state.data.news.push({symbol:"NVDA",date:Mag7.state.s.date,id:"fixture-literal",_source_row:90000,highlights:text});Mag7.state.s.tab="news";Mag7.state.s.scope="date";Mag7.state.s.expanded="fixture-literal";Mag7.render();}',inert)
            assert page.locator('.event-card[data-id="fixture-literal"] .event-body p').inner_text()==inert
            assert page.locator('.event-card[data-id="fixture-literal"] img').count()==0
            assert page.evaluate('window.__unsafe===undefined')
            passed('Literal markup stays inert text and distinct same-day events remain available')
            # Reload removes the synthetic fixture and session shortlist.
            page.reload();page.evaluate('async()=>await Mag7.ready')
            assert page.evaluate('Mag7.state.s.shortlist.length')==0
            page.screenshot(path=str(out/'desktop.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            # Keyboard alternatives: date/mode/sort/tab/focus/shortlist.
            page.locator('#priceMode').focus();page.keyboard.press('ArrowDown');page.keyboard.press('Tab')
            page.locator('#start').focus();page.keyboard.press('Tab')
            page.locator('#sort').focus();page.keyboard.press('ArrowDown')
            page.locator('#newsTab').focus();page.keyboard.press('ArrowRight')
            assert page.locator('#filingsTab').get_attribute('aria-selected')=='true'
            page.get_by_role('button',name='Add AAPL to shortlist',exact=True).focus();page.keyboard.press('Enter')
            page.get_by_role('textbox',name='AAPL research reason').focus();page.keyboard.type('Keyboard research reason')
            assert not page.locator('#export').is_disabled()
            page.get_by_role('button',name='Remove AAPL',exact=True).focus();page.keyboard.press('Enter')
            assert page.evaluate('Mag7.state.s.shortlist.length')==0
            passed('Keyboard mode/date/sort/tab/shortlist alternatives and reload-cleared session')
            page.set_viewport_size({'width':390,'height':844});page.evaluate('async()=>await Mag7.render()');page.wait_for_timeout(500)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),page.evaluate('({scroll:document.documentElement.scrollWidth,width:innerWidth})')
            page.screenshot(path=str(out/'mobile.png'),full_page=True)
            # Expand the longest available excerpts at phone width.
            for kind,text_key in [('news','highlights'),('filings','mda_content')]:
                record=page.evaluate('(args)=>Mag7.state.data[args[0]].filter(r=>r.date>=Mag7.state.data.meta.min).sort((a,b)=>(b[args[1]]||"").length-(a[args[1]]||"").length)[0]',[kind,text_key])
                page.evaluate('(r)=>{Mag7.state.range(Mag7.state.data.meta.min,Mag7.state.data.meta.end);Mag7.state.focus(r.symbol,r.date);Mag7.state.s.tab=r.highlights!==undefined?"news":"filings";Mag7.state.s.expanded=r.id;Mag7.render();}',record)
                assert page.locator('.event-body p').first.text_content()==record[text_key]
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            passed('390px phone layout has no document overflow; longest news/filing text retained and scrollable')
            assert not report['errors'],report['errors']
            assert not report['external_requests'],report['external_requests']
            passed('No browser JavaScript errors or external HTTP(S) requests')
            report['status']='PASS'
        except Exception:
            report['status']='FAIL';report['failure']=traceback.format_exc();page.screenshot(path=str(out/'failure.png'),full_page=True);raise
        finally:
            (out/'browser.json').write_text(json.dumps(report,indent=2),encoding='utf-8');browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--html',type=Path,required=True);parser.add_argument('--chrome',type=Path,required=True)
    args=parser.parse_args();run(args.html.resolve(),args.chrome.resolve())

