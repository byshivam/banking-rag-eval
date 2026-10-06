# Reports

- `latest.md` / `latest.json` — the most recent run (not committed; CI uploads them as an artifact and to the job summary).
- `baseline.json` — the approved reference run. Every new run is compared against it, and a drop larger than the regression tolerance blocks the release.

Create or refresh the baseline after reviewing a run you are happy with:

```bash
PYTHONPATH=src:. python -m evals.run_eval --update-baseline
```
