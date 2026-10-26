# Zack's Module 9 audit evidence

Audited app version: `e630f6823fd12bc11cf0525fab7dc9be59ff5eae`.

- Screenshots and their file manifest were removed from the project folder at the student's request. The root `my-audit.md` preserves the manual observations, inputs, actual values and full reproducible calculation without attachment dependencies.
- `verify_number.py`: AI-assisted, independently implemented source-row arithmetic. It imports pandas and Python Decimal, not dashboard functions or browser metrics.
- `independent-check.json`: executed numeric/source-boundary check, including full precision values and source hashes.

Run from the project root:

```powershell
.venv-dashboard\Scripts\python.exe audit_evidence/zack/verify_number.py
```

The check reads the team's formal price/news Parquet files. It does not execute the browser or enumerate the UI's news list. Screenshot values are explicit transcriptions for comparison, not newly scraped UI observations. The script generates only its JSON output and verifies unchanged input hashes.

See the root `my-audit.md` for the actual observations, distinctions between source/UI evidence, limits and AI disclosure. `change-requests.md` uses the course template and contains the open single-observation display request. No fix was made to the audited app.
