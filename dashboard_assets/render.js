(() => {
  const {data,s,announce}=Mag7.state;
  const colors={AAPL:'#0072B2',MSFT:'#D55E00',GOOGL:'#009E73',AMZN:'#AA4499',NVDA:'#946200',META:'#56B4E9',TSLA:'#444444'};
  const $=id=>document.getElementById(id);
  const pct=(n,signed=false)=>n===null?'N/A':(signed&&n>0?'+':'')+(n*100).toFixed(2)+'%';
  const number=n=>n===null?'N/A':n.toLocaleString('en-US',{maximumFractionDigits:0});
  const label={period_return:'Interval return',daily_volatility:'Daily volatility',average_volume:'Average daily volume',max_drawdown:'Maximum drawdown'};
  const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
  const dot=symbol=>{const el=node('span',undefined,'dot');el.style.background=colors[symbol];return el;};
  let metrics=[],plotBusy=false,plotsReady=false,queued=false;
  const config={responsive:true,displaylogo:false,displayModeBar:false,scrollZoom:false};
  function comparison(){
    const sorted=metrics.slice().sort((a,b)=>{
      const av=a[s.sort],bv=b[s.sort];
      if(av===null||bv===null)return av===bv?a.symbol.localeCompare(b.symbol):av===null?1:-1;
      return (s.descending?bv-av:av-bv)||a.symbol.localeCompare(b.symbol);
    });
    $('comparison').replaceChildren();
    sorted.forEach(m=>{
      const tr=node('tr');tr.dataset.symbol=m.symbol;tr.classList.toggle('focused',m.symbol===s.focus);
      const name=node('td');const focus=node('button',m.symbol);focus.prepend(dot(m.symbol));focus.setAttribute('aria-label','Read '+m.symbol+' evidence');
      focus.onclick=()=>{Mag7.state.focus(m.symbol);render();};name.append(focus);tr.append(name);
      for(const k of ['period_return','daily_volatility','average_volume','max_drawdown']){const cell=node('td',k==='average_volume'?number(m[k]):pct(m[k],k==='period_return'));cell.dataset.metric=k;cell.dataset.value=m[k]??'';tr.append(cell);}
      const count=node('td',String(m.n_prices));
      count.append(node('span',`${m.first_observation_date||'No prices'}${m.last_observation_date?' → '+m.last_observation_date:''}; ${m.n_returns} valid returns`,'detail'));tr.append(count);
      const action=node('td');const add=node('button','Add to shortlist','add');add.setAttribute('aria-label','Add '+m.symbol+' to shortlist');
      if(s.shortlist.some(r=>r.symbol===m.symbol)){add.textContent='Added';add.disabled=true;}
      add.onclick=()=>{Mag7.state.add(m);render();};action.append(add);tr.append(action);
      tr.onclick=e=>{if(!e.target.closest('button')){Mag7.state.focus(m.symbol);render();}};
      $('comparison').append(tr);
    });
    document.querySelectorAll('th[data-key]').forEach(th=>th.setAttribute('aria-sort',th.dataset.key===s.sort?(s.descending?'descending':'ascending'):'none'));
  }
  function evidence(){
    $('eventHeading').textContent=s.focus+' · '+s.date;
    $('focusCompany').value=s.focus;$('focusDate').value=s.date;$('focusDate').min=s.start;$('focusDate').max=s.end;
    document.querySelectorAll('input[name=scope]').forEach(el=>el.checked=el.value===s.scope);
    const start=s.scope==='date'?s.date:s.start,end=s.scope==='date'?s.date:s.end;
    for(const tab of ['news','filings']){
      const button=$(tab+'Tab'),count=Mag7.events.query(data[tab],s.focus,start,end).length;
      button.textContent=(tab==='news'?'News':'Filings')+' ('+count+')';button.setAttribute('aria-selected',String(tab===s.tab));button.tabIndex=tab===s.tab?0:-1;
    }
    $('timingNote').hidden=s.tab!=='news';$('eventList').setAttribute('aria-labelledby',s.tab+'Tab');
    const rows=Mag7.events.query(data[s.tab],s.focus,start,end);
    if(s.expanded!=='__collapsed__'&&!rows.some(r=>r.id===s.expanded))s.expanded=rows[0]?.id??null;
    const list=$('eventList');list.replaceChildren();
    if(!rows.length){list.append(node('div',`No ${s.tab==='news'?'news digest':'filing excerpt'} for this company and ${s.scope==='date'?'date':'interval'}.`,'empty'));return;}
    rows.forEach(r=>{
      const card=node('article',undefined,'event-card');card.dataset.id=r.id;
      const toggle=node('button',`${r.symbol} · ${r.date}${s.tab==='filings'?' · '+r.document_type:''}`,'event-toggle');
      toggle.setAttribute('aria-expanded',String(s.expanded===r.id));
      toggle.append(node('span','ID '+r.id+' · source row '+r._source_row,'event-meta'));
      const flags=node('span',undefined,'flags');Mag7.events.flags(r).forEach(flag=>flags.append(node('span',flag,'flag')));toggle.append(flags);
      const original=s.tab==='news'?r.highlights:r.mda_content;
      const preview=typeof original==='string'?original:'Text unavailable';
      toggle.append(node('span',preview.slice(0,240)+(preview.length>240?'…':''),'event-preview'));
      toggle.onclick=()=>{s.expanded=s.expanded===r.id?'__collapsed__':r.id;s.date=r.date;evidence();};card.append(toggle);
      if(s.expanded===r.id){
        const body=node('div',undefined,'event-body');
        for(const [title,k] of s.tab==='news'?[['News digest','highlights']]:[['MD&A excerpt','mda_content'],['Risk excerpt','risk_content']]){
          body.append(node('h3',title),node('p',r[k]??'Text unavailable'));
        }card.append(body);
      }list.append(card);
    });
  }
  function shortlist(){
    const box=$('shortlist');box.replaceChildren();$('shortCount').textContent=s.shortlist.length+' / 2';
    $('export').disabled=!s.shortlist.length||s.shortlist.some(r=>!r.reason.trim());
    if(!s.shortlist.length){box.append(node('div','No candidates yet. Compare the evidence, then add up to two companies.','empty'));return;}
    for(const item of s.shortlist){
      const card=node('article',undefined,'candidate');card.style.borderLeftColor=colors[item.symbol];
      const top=node('div',undefined,'section-top');const heading=node('h3',item.symbol);heading.prepend(dot(item.symbol));
      const remove=node('button','Remove','remove');remove.setAttribute('aria-label','Remove '+item.symbol);remove.onclick=()=>{s.shortlist=s.shortlist.filter(r=>r!==item);render();};top.append(heading,remove);card.append(top);
      card.append(node('p',`Frozen range: ${item.range_start} → ${item.range_end}`,'note'));
      const info=node('div',undefined,'metrics');
      for(const k of ['period_return','daily_volatility','average_volume','max_drawdown']){const m=node('div');m.append(node('span',label[k]),node('strong',k==='average_volume'?number(item[k]):pct(item[k],k==='period_return')));info.append(m);}
      card.append(info,node('p',`${item.n_prices} observations · ${item.n_returns} returns · actual ${item.first_observation_date||'N/A'} → ${item.last_observation_date||'N/A'} · cutoff ${item.data_as_of}`,'note'));
      const reason=node('label','Why prioritize this company?');const input=node('textarea');input.value=item.reason;input.setAttribute('aria-label',item.symbol+' research reason');
      input.oninput=()=>{item.reason=input.value;$('export').disabled=s.shortlist.some(r=>!r.reason.trim());};reason.append(input);card.append(reason);box.append(card);
    }
  }
  function trace(result,key,dates,overview=false){
    const byDate=new Map(result.series.map(p=>[p.date,p]));
    const sourceKey=key==='normalized_price'||key==='adj_close'?'adj_close':'volume';
    return {type:'scatter',mode:'lines',name:result.symbol,x:dates,y:dates.map(d=>byDate.get(d)?.[key]??null),
      customdata:dates.map(d=>byDate.get(d)?.[sourceKey]??null),connectgaps:false,
      line:{color:colors[result.symbol],width:result.symbol===s.focus&&!overview?2.8:1.5},
      hovertemplate:result.symbol+' · %{x|%Y-%m-%d}<br>'+(key==='volume'?'Volume: %{y:,.0f} shares':key==='relative_volume'?'Relative volume: %{y:.2f}×':'Value: %{y:.2f}')+
        (key==='normalized_price'?'<br>Adjusted close: %{customdata:.2f}':key==='relative_volume'?'<br>Volume: %{customdata:,.0f} shares':'')+'<extra></extra>'};
  }
  function layout(title,height){return {height,autosize:true,paper_bgcolor:'#fff',plot_bgcolor:'#fff',font:{family:'system-ui, sans-serif',size:11,color:'#536171'},
    margin:{l:60,r:14,t:28,b:36},showlegend:false,dragmode:'select',selectdirection:'h',hovermode:'closest',
    xaxis:{type:'date',range:[s.start,s.end],gridcolor:'#edf0f4',zeroline:false,tickformat:'%b %d\n%Y',fixedrange:false},
    yaxis:{title:{text:title,font:{size:11}},gridcolor:'#edf0f4',zeroline:false,fixedrange:true},
    legend:{itemclick:false,itemdoubleclick:false},selectionrevision:s.start+s.end};}
  async function charts(){
    if(plotBusy){queued=true;return;}plotBusy=true;
    try{
      const dates=[...new Set(metrics.flatMap(m=>m.series.map(p=>p.date)))].sort();
      const priceLayout=layout(s.priceMode==='normalized_price'?'Indexed to 100':'Adjusted close (source units)',innerWidth<600?300:340);
      const volumeLayout=layout(s.volumeMode==='volume'?'Volume (shares)':'Relative volume (×)',240);
      if(s.volumeMode==='volume')volumeLayout.yaxis.tickformat='~s';
      else volumeLayout.shapes=[{type:'line',xref:'paper',x0:0,x1:1,y0:1,y1:1,line:{color:'#99a8b5',width:1,dash:'dot'}}];
      if(!dates.length){priceLayout.annotations=[{text:'No price observations in this interval',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}];}
      const overview=Mag7.metrics.analyze(data.prices,s.companies,data.meta.min,data.meta.end);
      const nav=layout('',90);nav.margin={l:60,r:14,t:0,b:55};nav.dragmode='pan';nav.hovermode=false;nav.yaxis={visible:false,fixedrange:true};
      nav.xaxis={type:'date',range:[s.start,s.end],showticklabels:false,showgrid:false,zeroline:false,ticks:'',title:{text:'',font:{size:11}},rangeslider:{visible:true,range:[data.meta.min,data.meta.end],thickness:.85,bgcolor:'#f7f9fb',bordercolor:'#dce3ea',borderwidth:1}};
      await Promise.all([
        Plotly.react('priceChart',metrics.map(m=>trace(m,s.priceMode,dates)),priceLayout,config),
        Plotly.react('volumeChart',metrics.map(m=>trace(m,s.volumeMode,dates)),volumeLayout,config),
        Plotly.react('navigator',overview.map(m=>trace(m,'normalized_price',data.meta.dates,true)),nav,config)
      ]);
      if(!plotsReady){
        for(const id of ['priceChart','volumeChart']){
          $(id).on('plotly_selected',ev=>{if(!plotBusy&&ev?.range?.x)changeFromPlot(ev.range.x);});
          $(id).on('plotly_click',ev=>{const p=ev?.points?.[0];if(p){Mag7.state.focus(p.data.name,String(p.x).slice(0,10));render();}});
          $(id).on('plotly_relayout',ev=>{if(plotBusy)return;const range=ev['xaxis.range']||[ev['xaxis.range[0]'],ev['xaxis.range[1]']];if(range[0]&&range[1])changeFromPlot(range);});
        }
        $('navigator').on('plotly_relayout',ev=>{if(plotBusy)return;const range=ev['xaxis.range']||[ev['xaxis.range[0]'],ev['xaxis.range[1]']];if(range[0]&&range[1])changeFromPlot(range);});
        plotsReady=true;
      }
    }finally{plotBusy=false;if(queued){queued=false;charts();}}
  }
  function changeFromPlot(range){
    // Lexical date filtering respects fractional drag endpoints without timezone conversion.
    const stamp=v=>{const d=String(v).replace('T',' ');return d.length===10?d+' 00:00:00':d;};
    const low=stamp(range[0]),high=stamp(range[1]);
    const dates=data.meta.dates.filter(d=>d+' 00:00:00'>=low&&d+' 00:00:00'<=high);
    if(!dates.length){announce('No observed price dates selected. The previous range is retained.');charts();return;}
    if(Mag7.state.range(dates[0],dates.at(-1)))render();
  }
  function render(){
    metrics=Mag7.metrics.analyze(data.prices,s.companies,s.start,s.end);Mag7.current=metrics;
    $('start').value=s.start;$('end').value=s.end;$('sort').value=s.sort;
    $('rangeLabel').textContent=s.start+' → '+s.end;
    $('focusCompany').replaceChildren(...s.companies.map(symbol=>{const o=node('option',symbol);o.value=symbol;return o;}));
    document.querySelectorAll('#companies input').forEach(el=>el.checked=s.companies.includes(el.value));
    $('legend').replaceChildren(...s.companies.map(symbol=>{const entry=node('span',symbol);entry.prepend(dot(symbol));return entry;}));
    comparison();evidence();shortlist();return charts();
  }
  data.meta.symbols.forEach(symbol=>{
    const label=node('label');const input=node('input');input.type='checkbox';input.value=symbol;input.checked=true;
    input.onchange=()=>{Mag7.state.company(symbol,input.checked);render();};label.append(input,dot(symbol),document.createTextNode(symbol));$('companies').append(label);
  });
  for(const id of ['start','end']){$(id).min=data.meta.min;$(id).max=data.meta.end;}
  $('rangeForm').onsubmit=e=>{e.preventDefault();if(Mag7.state.range($('start').value,$('end').value))render();};
  $('full').onclick=()=>{Mag7.state.range(data.meta.min,data.meta.end);render();};
  for(const id of ['priceMode','volumeMode'])$(id).onchange=()=>{s[id]=$(id).value;render();};
  $('sort').onchange=()=>{s.sort=$('sort').value;s.descending=true;comparison();};
  document.querySelectorAll('[data-sort]').forEach(button=>button.onclick=()=>{const key=button.dataset.sort;s.descending=s.sort===key?!s.descending:true;s.sort=key;$('sort').value=key;comparison();});
  $('focusCompany').onchange=()=>{Mag7.state.focus($('focusCompany').value);render();};
  $('focusDate').onchange=()=>{const d=$('focusDate').value;if(d>=s.start&&d<=s.end){s.date=d;s.scope='date';s.expanded=null;evidence();}else{announce('Focus date must be inside the research interval.');$('focusDate').value=s.date;}};
  document.querySelectorAll('input[name=scope]').forEach(input=>input.onchange=()=>{s.scope=input.value;s.expanded=null;evidence();});
  function tab(key){s.tab=key;s.expanded=null;evidence();}
  document.querySelectorAll('[data-tab]').forEach(button=>{button.onclick=()=>tab(button.dataset.tab);button.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();tab(e.key==='Home'?'news':e.key==='End'?'filings':s.tab==='news'?'filings':'news');$(s.tab+'Tab').focus();}};});
  $('export').onclick=()=>{
    try{const csv=Mag7.state.csv();const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=node('a');a.href=url;a.download='mag7_research_shortlist.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);announce('CSV exported. Your frozen research shortlist is saved.');}catch(e){announce(e.message);}
  };
  $('coverage').append(node('span','Historical data · cutoff '+data.meta.cutoff),node('span',data.prices.length.toLocaleString()+' price observations'),node('span',data.news.length.toLocaleString()+' news digests · '+data.filings.length+' filing excerpts'));
  $('provenance').textContent=JSON.stringify({source:data.meta.source,price_coverage:[data.meta.min,data.meta.end],counts:{prices:data.prices.length,news:data.news.length,filings:data.filings.length},sha256:data.meta.hashes},null,2);
  Mag7.render=render;Mag7.ready=render();
})();
