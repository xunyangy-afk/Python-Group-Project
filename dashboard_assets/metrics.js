'use strict';
window.Mag7 = window.Mag7 || {};
Mag7.metrics = (() => {
  const valid = (v, positive=false) => typeof v === 'number' && Number.isFinite(v) && (positive ? v > 0 : v >= 0);
  const mean = xs => xs.reduce((a,b)=>a+b,0)/xs.length;
  function analyze(prices, symbols, start, end) {
    if(start>end) throw Error('Expected start <= end');
    return symbols.map(symbol => {
      const history=prices.filter(p=>p.symbol===symbol).slice().sort((a,b)=>a.date.localeCompare(b.date)||String(a.id||'').localeCompare(String(b.id||''))||(a._source_row||0)-(b._source_row||0));
      const series=[];
      history.forEach((p,i)=>{
        if(p.date<start||p.date>end) return;
        const past=history.slice(Math.max(0,i-20),i).map(r=>r.volume);
        const relative=past.length===20&&past.every(v=>valid(v))&&mean(past)>0&&valid(p.volume)?p.volume/mean(past):null;
        series.push({date:p.date,adj_close:valid(p.adj_close,true)?p.adj_close:null,volume:valid(p.volume)?p.volume:null,relative_volume:relative});
      });
      const base=series[0]?.adj_close??null;
      series.forEach((p,i)=>{
        const prev=i?series[i-1].adj_close:null;
        p.normalized_price=p.adj_close!==null&&base!==null?p.adj_close/base*100:null;
        p.daily_return=p.adj_close!==null&&prev!==null?p.adj_close/prev-1:null;
      });
      const returns=series.map(p=>p.daily_return).filter(v=>v!==null);
      const volumes=series.map(p=>p.volume).filter(v=>v!==null);
      const last=series.at(-1)?.adj_close??null;
      let drawdown=null;
      if(series.length>=2&&series.every(p=>p.adj_close!==null)){
        let peak=base; drawdown=0;
        for(const p of series){peak=Math.max(peak,p.adj_close);drawdown=Math.max(drawdown,1-p.adj_close/peak);}
      }
      const avg=returns.length?mean(returns):null;
      return {symbol,range_start:start,range_end:end,first_observation_date:series[0]?.date??null,last_observation_date:series.at(-1)?.date??null,
        n_prices:series.length,n_returns:returns.length,period_return:series.length>=2&&base!==null&&last!==null?last/base-1:null,
        daily_volatility:returns.length>=2?Math.sqrt(returns.reduce((sum,r)=>sum+(r-avg)**2,0)/(returns.length-1)):null,
        average_volume:volumes.length?mean(volumes):null,max_drawdown:drawdown,series};
    });
  }
  return {analyze};
})();
