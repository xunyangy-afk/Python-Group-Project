import argparse
from .pipeline import ROOT, run

parser = argparse.ArgumentParser(description="Clean the pinned full team snapshot and validate outputs")
parser.add_argument("--raw-dir", type=str, default=str(ROOT / "sources/raw"))
parser.add_argument("--output-dir", type=str, default=str(ROOT / "artifacts"))
args = parser.parse_args()
result = run(args.raw_dir, args.output_dir)
print({name: s["cleaned_rows"] for name, s in result["tables"].items()})
