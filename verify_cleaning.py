"""One command: risk tests, two fresh-process full runs, exact hash comparison."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from team_cleaning.pipeline import ROOT, TABLES, sha256, write_json


def main():
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                           cwd=ROOT, capture_output=True, text=True)
    sys.stdout.write(tests.stdout)
    sys.stderr.write(tests.stderr)
    if tests.returncode:
        raise SystemExit(tests.returncode)
    raw = ROOT / "sources/raw"
    initial = {name: sha256(raw / f"{name}.parquet") for name in TABLES}
    with tempfile.TemporaryDirectory(prefix="team-reproduce-") as temp:
        out = Path(temp)
        for folder in (ROOT / "artifacts", out):
            subprocess.run([sys.executable, "-m", "team_cleaning", "--output-dir", str(folder)], cwd=ROOT, check=True)
        expected = {p.name: sha256(p) for p in out.iterdir()}
        actual = {name: sha256(ROOT / "artifacts" / name) for name in expected}
        if actual != expected:
            raise ValueError("Fresh-process outputs differ")
    final = {name: sha256(raw / f"{name}.parquet") for name in TABLES}
    if final != initial:
        raise ValueError("Source files changed")
    report = dict(status="PASS", command="python verify_cleaning.py", risk_tests_exit_code=tests.returncode,
                  test_output=tests.stdout + tests.stderr, fresh_process_runs=2,
                  compared_files=len(expected), identical_output_sha256=expected, raw_sha256_unchanged=final)
    write_json(ROOT / "artifacts/verification.json", report)
    (ROOT / "artifacts/verification.md").write_text(
        "# Executed verification\n\nCommand: `python verify_cleaning.py`\n\n"
        f"PASS: risk tests exited 0. Two fresh Python processes read all three pinned raw tables. "
        f"All {len(expected)} generated files matched byte for byte, including the full formal tables, exclusions and validation reports. "
        "Raw SHA256 hashes remained unchanged.\n\nTest log:\n\n```text\n" + tests.stdout + tests.stderr + "```\n",
        encoding="utf-8", newline="\n")
    print(f"PASS: tests, source preservation, two full runs, {len(expected)} identical output files")


if __name__ == "__main__":
    main()
