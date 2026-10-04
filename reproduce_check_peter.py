"""
Reproducibility check (checklist item 13).

Copies the original data and clean_peter.py into a new temporary folder, runs the pipeline
there in a fresh Python process, and compares every output with the submitted version.
Run: python3 reproduce_check_peter.py
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW_FILES = ["prices.parquet", "news.parquet", "filings.parquet"]
OUTPUTS = (
    [f"data/clean/{t}_clean.parquet" for t in ["prices", "news", "filings"]]
    + [f"samples_peter/{t}_sample_peter.csv" for t in ["prices", "news", "filings"]]
    + ["outputs/validation_report.md", "outputs/record_checks_peter.csv", "outputs/metric_support_peter.csv"]
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def same(a, b):
    """Parquet compared by content (file bytes can differ by writer metadata); others byte for byte."""
    if a.suffix == ".parquet":
        return pd.read_parquet(a).equals(pd.read_parquet(b))
    return a.read_bytes() == b.read_bytes()


def main():
    raw_before = {f: sha256(HERE / "data/raw" / f) for f in RAW_FILES}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "data/raw").mkdir(parents=True)
        for f in RAW_FILES:
            shutil.copy2(HERE / "data/raw" / f, tmp / "data/raw" / f)
        shutil.copy2(HERE / "clean_peter.py", tmp / "clean_peter.py")
        cmd = [sys.executable, "clean_peter.py"]
        run = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
        if run.returncode != 0:
            sys.exit(f"Pipeline failed in fresh session:\n{run.stderr}")
        rows = [{"output": o, "matches_submitted": same(HERE / o, tmp / o)} for o in OUTPUTS]
    raw_after = {f: sha256(HERE / "data/raw" / f) for f in RAW_FILES}

    result = pd.DataFrame(rows)
    lines = [
        "# Reproducibility check (Peter-work)\n",
        f"Run on {date.today()} with Python {sys.version.split()[0]}, pandas {pd.__version__}.\n",
        "Procedure: copy `data/raw/*.parquet` and `clean_peter.py` into an empty temporary folder, run "
        "`python3 clean_peter.py` there in a new Python process, compare every output with the submitted "
        "file (parquet by content, other files byte for byte).\n",
        result.to_markdown(index=False) + "\n",
        f"All outputs match: **{bool(result['matches_submitted'].all())}**\n",
        "Raw files unchanged by the run (SHA-256, first 16 characters):\n",
        "\n".join(f"- {f}: {raw_before[f]} ({'unchanged' if raw_before[f] == raw_after[f] else 'CHANGED'})"
                  for f in RAW_FILES),
    ]
    (HERE / "outputs/reproducibility_peter.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(result.to_string(index=False))
    print("All outputs match:", bool(result["matches_submitted"].all()))


if __name__ == "__main__":
    main()
