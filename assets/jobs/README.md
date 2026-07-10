# Job assets — durable script + slide images per CSV id

```
assets/jobs/<id>/
  scenes_draft.json
  images/intro.png … ending.png
```

## Flow (chi tiết)

```
CSV → Đọc job → assets/jobs/<id> tồn tại?
  Có  → Đọc scenes_draft.json + images/*.png
        → Đủ? reuse
        → Script OK, thiếu ảnh? giữ ảnh có sẵn + GPT chỉ tạo PNG còn thiếu → Lưu
        → Script hỏng? GPT script + GPT chỉ tạo PNG còn thiếu → Lưu
  Không → GPT script → GPT ảnh → Lưu
→ TTS → Remotion → Publish
```

Optional one-shot freeze:

```bash
python scripts/pregenerate_job_assets.py --csv jobs.csv
```

Strict mode (fail if missing): `python batch_runner.py --require-job-assets`.
