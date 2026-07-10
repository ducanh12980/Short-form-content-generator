# Job assets — durable script + slide images per CSV id

```
assets/jobs/<id>/
  scenes_draft.json
  images/intro.png … ending.png
```

## Flow (chi tiết)

```
CSV → Đọc job → Soát HẾT assets/jobs/<id>/ (script + từng PNG)
  → Đủ hết? reuse
  → Thiếu bất kỳ phần nào?
       liệt kê toàn bộ phần thiếu
       → GPT chỉ tạo phần còn thiếu (giữ phần đã có)
       → Lưu
→ TTS → Remotion → Publish
```

Optional one-shot freeze:

```bash
python scripts/pregenerate_job_assets.py --csv jobs.csv
```

Strict mode (fail if missing): `python batch_runner.py --require-job-assets`.
