Mag7.state = (()=>{
  const data=JSON.parse(document.getElementById('payload').textContent);
  const s={companies:[...data.meta.symbols],start:data.meta.start,end:data.meta.end,priceMode:'normalized_price',volumeMode:'volume',
    sort:'period_return',descending:true,focus:'AAPL',date:data.meta.end,scope:'date',tab:'news',expanded:null,shortlist:[]};
  function announce(message){document.getElementById('notice').textContent=message;}
  function focusDate(){
    if(s.date>=s.start&&s.date<=s.end)return;
    const rows=data.prices.filter(p=>p.symbol===s.focus&&p.date>=s.start&&p.date<=s.end);
    s.date=rows.at(-1)?.date||s.end;
  }
  function range(start,end,snap=false){
    if(snap){
      const observed=data.meta.dates.filter(d=>d>=start&&d<=end);
      if(!observed.length){announce('No observed price dates selected. The previous range is retained.');return false;}
      start=observed[0];end=observed.at(-1);
    }
    if(!/^\d{4}-\d{2}-\d{2}$/.test(start)||!/^\d{4}-\d{2}-\d{2}$/.test(end)||start>end||start<data.meta.min||end>data.meta.end){
      announce('Choose a start on or before the end, within '+data.meta.min+' to '+data.meta.end+'.');return false;
    }
    s.start=start;s.end=end;focusDate();s.expanded=null;announce('Research interval updated: '+start+' to '+end);return true;
  }
  function company(symbol,checked){
    if(!checked&&s.companies.length===1){announce('Keep at least one company selected.');return false;}
    s.companies=data.meta.symbols.filter(x=>x===symbol?checked:s.companies.includes(x));
    if(!s.companies.includes(s.focus)){s.focus=s.companies[0];focusDate();s.expanded=null;}
    return true;
  }
  function focus(symbol,date=null){s.focus=symbol;if(date){s.date=date;s.scope='date';}focusDate();s.expanded=null;}
  function add(metric){
    if(s.shortlist.some(r=>r.symbol===metric.symbol)){announce('This company is already on your shortlist. Remove it to capture a new interval.');return false;}
    if(s.shortlist.length>=2){announce('Shortlist is full. Remove an existing candidate before adding a third.');return false;}
    const {series,...snapshot}=metric;
    s.shortlist.push({...structuredClone(snapshot),data_as_of:data.meta.cutoff,reason:''});
    announce(metric.symbol+' added. Enter a research reason to enable CSV export.');return true;
  }
  const columns=['symbol','range_start','range_end','first_observation_date','last_observation_date','period_return_pct','daily_volatility_pct','average_daily_volume_shares','max_drawdown_pct','n_prices','n_returns','data_as_of','reason'];
  function csv(){
    if(!s.shortlist.length||s.shortlist.some(r=>!r.reason.trim()))throw Error('Enter a reason for every candidate before exporting.');
    const quote=(value,isText=false)=>{
      let v=value===null||value===undefined?'':String(value);
      if(isText&&/^[\s]*[=+@\-\t\r]/.test(v))v="'"+v;
      return '"'+v.replaceAll('"','""')+'"';
    };
    return columns.join(',')+'\r\n'+s.shortlist.map(r=>{
      const pct=k=>r[k]===null?null:r[k]*100;
      const row={...r,period_return_pct:pct('period_return'),daily_volatility_pct:pct('daily_volatility'),average_daily_volume_shares:r.average_volume,max_drawdown_pct:pct('max_drawdown')};
      return columns.map(k=>quote(row[k],['symbol','range_start','range_end','first_observation_date','last_observation_date','data_as_of','reason'].includes(k))).join(',');
    }).join('\r\n')+'\r\n';
  }
  return {data,s,announce,range,company,focus,add,csv,columns};
})();
