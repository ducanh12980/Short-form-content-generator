# Job assets — durable script + slide images per CSV id

```
assets/jobs/<id>/
  scenes_draft.json
  images/intro.png … ending.png
```

## Flow

1. Batch reads a job.
2. If this folder is **complete** for the job topic → reuse script + images.
3. Else → LLM script + AI images → **save here** → continue.
4. Always: TTS → Remotion → Publish.

Optional one-shot freeze (same result as a first batch run):

```bash
python scripts/pregenerate_job_assets.py --csv jobs.csv
```

Strict mode (fail if missing): `python batch_runner.py --require-job-assets`.
