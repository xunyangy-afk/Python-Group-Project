"""Plotly renderers consume analysis results; they never calculate financial metrics."""
import plotly.graph_objects as go

COLORS = dict(AAPL='#0072B2', MSFT='#D55E00', GOOGL='#009E73', AMZN='#AA4499',
              NVDA='#946200', META='#56B4E9', TSLA='#444444')


def figure(results, field, title, start, end, focus, height=340, overview=False):
    dates = sorted({p['date'] for r in results for p in r['series']})
    fig = go.Figure()
    for result in results:
        by_date = {p['date']: p for p in result['series']}
        original = 'volume' if field in ('volume', 'relative_volume') else 'adj_close'
        custom = [[result['symbol'], d, by_date.get(d, {}).get(original)] for d in dates]
        suffix = '×' if field == 'relative_volume' else ''
        number_format = ',.0f' if field == 'volume' else '.2f'
        original_format = ',.0f' if original == 'volume' else '.2f'
        fig.add_trace(go.Scatter(
            x=dates, y=[by_date.get(d, {}).get(field) for d in dates],
            name=result['symbol'], mode='lines', connectgaps=False, customdata=custom,
            line=dict(color=COLORS[result['symbol']], width=3 if result['symbol'] == focus else 1.7),
            hovertemplate=f"%{{customdata[0]}} · %{{x}}<br>{title}: %{{y:{number_format}}}{suffix}<br>Original {original}: %{{customdata[2]:{original_format}}}<extra></extra>",
        ))
    fig.update_layout(
        height=height, margin=dict(l=12, r=12, t=15, b=10),
        paper_bgcolor='white', plot_bgcolor='white', font=dict(family='Arial, sans-serif', color='#18252D', size=12),
        dragmode='select', selectdirection='h', hovermode='closest',
        legend=dict(orientation='h', y=1.18, itemclick=False, itemdoubleclick=False),
        showlegend=not overview,
        xaxis=dict(type='date', range=[start, end], fixedrange=True, tickformat='%b %Y', gridcolor='#EEF1F5'),
        yaxis=dict(title=None if overview else title, fixedrange=True, gridcolor='#EEF1F5', tickformat='~s' if field == 'volume' else None),
    )
    if field == 'relative_volume':
        fig.add_hline(y=1, line_dash='dash', line_color='#536171', annotation_text='1× preceding-20 baseline')
    return fig
