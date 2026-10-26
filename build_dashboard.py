"""Build a single offline HTML file from validated formal data and local assets."""
import importlib.metadata
import json
import sys
from pathlib import Path

from plotly.offline import get_plotlyjs

from dashboard_analysis import SYMBOLS, digest, load_inputs, records

ROOT = Path(__file__).resolve().parent


def build():
    root, tables, hashes = load_inputs(ROOT)
    prices = records(tables['prices'])
    dates = sorted({r['date'] for r in prices})
    payload = {k: records(v) for k, v in tables.items()}
    payload['meta'] = dict(symbols=SYMBOLS, dates=dates, start=dates[max(0, len(dates)-60)],
                           end=dates[-1], min=dates[0], cutoff=dates[-1], hashes=hashes,
                           source='TheFinAI/Herculean · team-local-sha256-v1')
    # Escaping '<' prevents literal source text closing the JSON script element.
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    assets = ROOT / 'dashboard_assets'
    template = (assets / 'template.html').read_text(encoding='utf-8')
    scripts = '\n'.join((assets / name).read_text(encoding='utf-8') for name in ['metrics.js', 'events.js', 'state.js', 'render.js'])
    html = template.replace('/*STYLES*/', (assets / 'style.css').read_text(encoding='utf-8'))
    html = html.replace('/*PLOTLY*/', get_plotlyjs()).replace('/*PAYLOAD*/', encoded).replace('/*APP*/', scripts)
    path = ROOT / 'dashboard.html'
    path.write_text(html, encoding='utf-8')
    after = {k: digest(root / f'artifacts/{k}_clean.parquet') for k in tables}
    if after != hashes:
        raise RuntimeError('Input bytes changed during the build')
    report = dict(python=sys.version, packages={p: importlib.metadata.version(p) for p in
                  ['pandas', 'numpy', 'pyarrow', 'plotly', 'narwhals', 'packaging', 'python-dateutil', 'six', 'tzdata']},
                  source_hashes_before=hashes, source_hashes_after=after,
                  shapes={k: list(v.shape) for k,v in tables.items()},
                  default_range=[payload['meta']['start'], dates[-1]], html_bytes=path.stat().st_size,
                  html_sha256=digest(path))
    evidence = ROOT / 'dashboard_verification'
    evidence.mkdir(exist_ok=True)
    (evidence / 'build.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(path)
    return payload


if __name__ == '__main__':
    build()
