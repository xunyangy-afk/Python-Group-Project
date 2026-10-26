Mag7.events = {
  query(rows,symbol,start,end) {
    return rows.filter(r=>r.symbol===symbol&&r.date>=start&&r.date<=end).slice()
      .sort((a,b)=>b.date.localeCompare(a.date)||String(a.id).localeCompare(String(b.id))||a._source_row-b._source_row);
  },
  flags(row) {
    return Object.entries(row).filter(([k,v])=>k.startsWith('flag_')&&v&&k!=='flag_timing_unverified')
      .map(([k])=>k.replace(/^flag_/, '').replaceAll('_',' '));
  }
};
