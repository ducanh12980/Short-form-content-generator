"""Batch runner — process pending rows from a CSV job queue through the video pipeline."""

from __future__ import annotations

import csv
import os
import tempfile
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    from zoneinfo import ZoneInfo

    VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:  # ZoneInfoNotFoundError / missing tzdata on Windows
    VN_TZ = timezone(timedelta(hours=7), name="UTC+7")

VALID_STATUSES = frozenset({"pending", "running", "done", "failed"})
VALID_MODES = frozenset({"slideshow", "mvp"})
VALID_IMAGE_PROVIDERS = frozenset({"chatgpt", "pollinations", "mock"})
VALID_SELECT_MODES = frozenset({"pending", "due-today", "failed"})

REQUIRED_COLUMNS = ("id", "topic", "status")
JOB_COLUMNS = (
    "id",
    "topic",
    "status",
    "mode",
    "image_provider",
    "output_path",
    "error",
    "created_at",
    "completed_at",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _today_vn(*, now: datetime | None = None) -> date:
    """Calendar date in Asia/Ho_Chi_Minh."""
    current = now if now is not None else datetime.now(VN_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(VN_TZ).date()


def job_created_date_vn(created_at: str) -> date | None:
    """Parse job created_at ISO timestamp to a Vietnam calendar date, or None if empty/invalid."""
    raw = (created_at or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(VN_TZ).date()


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = {col: (row.get(col) or "").strip() for col in JOB_COLUMNS}
    if not normalized["mode"]:
        normalized["mode"] = "slideshow"
    return normalized


def init_jobs_csv(path: str | Path, *, examples: bool = True) -> Path:
    """Create a new jobs CSV with headers and optional example pending rows."""
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    if examples:
        now = _utc_now_iso()
        rows = [
            {
                "id": "1",
                "topic": "90% mọi người đang uống nước sai cách",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": now,
                "completed_at": "",
            },
            {
                "id": "2",
                "topic": "3 thói quen buổi sáng giúp tỉnh táo cả ngày",
                "status": "pending",
                "mode": "slideshow",
                "image_provider": "mock",
                "output_path": "",
                "error": "",
                "created_at": now,
                "completed_at": "",
            },
        ]

    save_jobs(csv_path, rows)
    return csv_path


def load_jobs(path: str | Path) -> list[dict[str, str]]:
    """Load job rows from CSV. Missing optional columns are filled with empty strings."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Jobs CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"Jobs CSV missing required columns: {', '.join(missing)}")

        rows: list[dict[str, str]] = []
        for raw in reader:
            row = _normalize_row({k: v or "" for k, v in raw.items()})
            if not row["id"] and not row["topic"]:
                continue
            rows.append(row)
        return rows


def save_jobs(path: str | Path, rows: list[dict[str, str]]) -> None:
    """Atomically write job rows to CSV."""
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        dir=csv_path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=JOB_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_normalize_row(row))
        temp_path = Path(handle.name)

    temp_path.replace(csv_path)


def reset_stale_running(rows: list[dict[str, str]]) -> int:
    """Reset rows stuck in running (e.g. after a crash) back to pending."""
    count = 0
    for row in rows:
        if row.get("status") == "running":
            row["status"] = "pending"
            row["error"] = ""
            count += 1
    return count


def collect_slideshow_image_paths(payload: dict[str, Any]) -> list[Path]:
    """Return slide image paths in playback order for stitch."""
    slides = payload.get("slides")
    if isinstance(slides, list) and slides:
        paths: list[Path] = []
        for slide in sorted(slides, key=lambda s: int(s.get("id", 0))):
            if not isinstance(slide, dict):
                continue
            image = slide.get("image")
            if isinstance(image, dict) and image.get("path"):
                paths.append(Path(str(image["path"])))
        if paths:
            return paths

    scenes = payload.get("scenes", [])
    if isinstance(scenes, list) and scenes:
        paths: list[Path] = []
        for scene in sorted(scenes, key=lambda s: int(s.get("id", 0))):
            if not isinstance(scene, dict):
                continue
            image = scene.get("image")
            if isinstance(image, dict) and image.get("path"):
                paths.append(Path(str(image["path"])))
        if paths:
            return paths

    video_images = payload.get("video", {}).get("images", [])
    if isinstance(video_images, list):
        ordered = sorted(
            (img for img in video_images if isinstance(img, dict) and img.get("path")),
            key=lambda img: int(img.get("start_ms", 0)),
        )
        paths = [Path(str(img["path"])) for img in ordered]
        if paths:
            return paths

    raise ValueError("No slide images found in pipeline payload.")


def is_quota_exhausted_error(exc: BaseException) -> bool:
    """True when the failure is an LLM/API daily quota (retrying other jobs won't help)."""
    text = str(exc).lower()
    markers = (
        "quota exceeded",
        "daily quota",
        "resource_exhausted",
        "exceeded your current quota",
        "generate_content_free_tier",
    )
    return any(marker in text for marker in markers)


def execute_job(
    row: dict[str, str],
    *,
    output_dir: str | Path | None = None,
    caption_mode: str | None = None,
    require_job_assets: bool = False,
) -> Path:
    """Run one job row through generation and render. Returns path to final MP4.

    Slideshow jobs pass ``job_assets_id``. When ``assets/jobs/<id>/`` is complete,
    script + images are reused; otherwise LLM/image APIs run and results are
    persisted there. Set ``require_job_assets=True`` to fail if the library is missing.

    Always clears the run folder first so leftover ``scenes_draft.json`` / images
    from a previous CSV row cannot be reused under a different job id.
    """
    from core.run_output import reset_run_dir, resolve_final_output_dir

    job_id = row["id"].strip()
    topic = row["topic"].strip()
    if not job_id:
        raise ValueError("Job row must include non-empty id.")
    if not topic:
        raise ValueError(f"Job {job_id} must include non-empty topic.")

    mode = (row.get("mode") or "slideshow").strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"Job {job_id}: mode must be one of {sorted(VALID_MODES)}.")

    image_provider = (row.get("image_provider") or "").strip().lower() or None
    if image_provider and image_provider not in VALID_IMAGE_PROVIDERS:
        raise ValueError(
            f"Job {job_id}: image_provider must be one of {sorted(VALID_IMAGE_PROVIDERS)}."
        )

    resolved_caption_mode = (
        caption_mode
        or (row.get("caption_mode") or "").strip()
        or os.environ.get("CAPTION_MODE", "none").strip()
        or "none"
    )

    target = output_dir if output_dir is not None and str(output_dir).strip() else resolve_final_output_dir()
    job_dir = reset_run_dir(target)

    if mode == "slideshow":
        from orchestrator_mvp import run_slideshow_with_render

        _, final = run_slideshow_with_render(
            topic,
            output_dir=job_dir,
            caption_mode=resolved_caption_mode,
            image_provider=image_provider,
            publish=False,
            job_assets_id=job_id,
            require_job_assets=require_job_assets,
        )
        return final

    from orchestrator_mvp import run_mvp_with_render

    _, final = run_mvp_with_render(topic, output_dir=job_dir, publish=False)
    return final


@contextmanager
def batch_lock(lock_path: str | Path) -> Iterator[None]:
    """Exclusive lock for batch runs. Raises BatchLockError if another run holds it."""
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise BatchLockError(f"Another batch run is active (lock: {path})") from exc

    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        path.unlink(missing_ok=True)


class BatchLockError(RuntimeError):
    """Raised when a concurrent batch run holds the lock."""


class BatchRunnerError(RuntimeError):
    """Raised when batch processing fails."""


def select_jobs(
    rows: list[dict[str, str]],
    *,
    select: str = "pending",
    today: date | None = None,
) -> list[dict[str, str]]:
    """Filter job rows by select mode. Returns references into ``rows`` (same dict objects)."""
    mode = (select or "pending").strip().lower()
    if mode not in VALID_SELECT_MODES:
        raise ValueError(f"select must be one of {sorted(VALID_SELECT_MODES)}.")

    if mode == "pending":
        return [row for row in rows if row.get("status") == "pending"]

    if mode == "failed":
        return [row for row in rows if row.get("status") == "failed"]

    # due-today: pending jobs whose created_at calendar date (VN) is today
    target = today if today is not None else _today_vn()
    matched: list[dict[str, str]] = []
    for row in rows:
        if row.get("status") != "pending":
            continue
        created = job_created_date_vn(row.get("created_at", ""))
        if created is not None and created == target:
            matched.append(row)
    return matched


def select_pending_from_today(
    rows: list[dict[str, str]],
    *,
    today: date | None = None,
) -> list[dict[str, str]]:
    """Pending jobs with created_at date >= today (Asia/Ho_Chi_Minh).

    Used by asset pregenerate so each cron can fill images for today and
    future schedule days, while skipping past-due pending rows.
    """
    target = today if today is not None else _today_vn()
    matched: list[dict[str, str]] = []
    for row in rows:
        if row.get("status") != "pending":
            continue
        created = job_created_date_vn(row.get("created_at", ""))
        if created is not None and created >= target:
            matched.append(row)
    return matched


def _resolve_job_limit(max_jobs: int | None) -> int | None:
    """Return slice size, or None for unlimited (max_jobs is None or <= 0)."""
    if max_jobs is None or max_jobs <= 0:
        return None
    return max_jobs


def process_pending_jobs(
    csv_path: str | Path,
    *,
    max_jobs: int | None = 1,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
    lock_path: str | Path | None = None,
    select: str = "pending",
    publish: bool = False,
    today: date | None = None,
    require_job_assets: bool = False,
) -> list[dict[str, str]]:
    """Process selected job rows. Returns summary dicts for each attempted row.

    ``select``:
      - ``pending`` — all pending rows (legacy default)
      - ``due-today`` — pending rows with created_at date == today (Asia/Ho_Chi_Minh)
      - ``failed`` — all failed rows (retry)

    ``max_jobs``: positive int limits how many; ``None`` or ``0`` means all matched.
    ``publish``: after each successful render, publish that MP4 via publish_runner.
    ``require_job_assets``: if True, slideshow jobs fail when ``assets/jobs/<id>/``
    is incomplete; default False generates and persists missing assets.
    """
    path = Path(csv_path)
    lock = Path(lock_path) if lock_path else path.with_suffix(path.suffix + ".lock")
    results: list[dict[str, str]] = []
    limit = _resolve_job_limit(max_jobs)

    with batch_lock(lock):
        rows = load_jobs(path)
        reset_stale_running(rows)

        selected = select_jobs(rows, select=select, today=today)
        if not selected:
            save_jobs(path, rows)
            return results

        to_run = selected if limit is None else selected[:limit]

        for row in to_run:
            job_id = row["id"]
            if dry_run:
                results.append({"id": job_id, "status": "dry_run", "topic": row["topic"]})
                continue

            if not row.get("created_at"):
                row["created_at"] = _utc_now_iso()
            row["status"] = "running"
            row["error"] = ""
            row["output_path"] = ""
            row["completed_at"] = ""
            save_jobs(path, rows)

            try:
                output = execute_job(
                    row,
                    output_dir=output_dir,
                    require_job_assets=require_job_assets,
                )
                row["status"] = "done"
                row["output_path"] = str(output.resolve())
                row["error"] = ""
                row["completed_at"] = _utc_now_iso()
                save_jobs(path, rows)

                if publish:
                    from core.publish_runner import publish_video

                    payload_path = output.resolve().parent / "pipeline_payload.json"
                    ok = publish_video(
                        output,
                        jobs_csv=path,
                        payload_path=payload_path if payload_path.is_file() else None,
                    )
                    if not ok:
                        results.append(
                            {
                                "id": job_id,
                                "status": "done",
                                "output_path": row["output_path"],
                                "publish": "failed",
                            }
                        )
                    else:
                        results.append(
                            {
                                "id": job_id,
                                "status": "done",
                                "output_path": row["output_path"],
                                "publish": "ok",
                            }
                        )
                else:
                    results.append(
                        {"id": job_id, "status": "done", "output_path": row["output_path"]}
                    )
            except Exception as exc:
                row["status"] = "failed"
                row["error"] = str(exc)
                row["completed_at"] = _utc_now_iso()
                results.append({"id": job_id, "status": "failed", "error": row["error"]})
                save_jobs(path, rows)
                # Free-tier Gemini quota is shared — continuing only fails every later row.
                if is_quota_exhausted_error(exc):
                    remaining = sum(
                        1
                        for later in to_run
                        if later["id"] not in {item["id"] for item in results}
                    )
                    if remaining:
                        print(
                            f"[batch] stopping early after job {job_id}: API quota exhausted "
                            f"({remaining} remaining job(s) left pending — retry later).",
                            flush=True,
                        )
                    break

    return results
