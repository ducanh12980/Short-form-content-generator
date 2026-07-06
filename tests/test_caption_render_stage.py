"""Tests for caption render stage (delegates to Remotion)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.caption_render_stage import render_caption_preview


def _sample_payload(tmp_path: Path) -> Path:
    narration = tmp_path / "narration.mp3"
    narration.write_bytes(b"fake")
    payload = {
        "topic": "test",
        "raw_script": "Hello",
        "tokens": [{"text": "Hello", "style": "highlight", "animation": "none"}],
        "audio": {
            "path": str(narration),
            "word_timestamps": [{"text": "Hello", "start_ms": 0, "end_ms": 500}],
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@patch("core.caption_render_stage.render_project_video")
def test_render_caption_preview_delegates_to_remotion(
    mock_render: MagicMock,
    tmp_path: Path,
) -> None:
    project_path = _sample_payload(tmp_path)
    output_path = tmp_path / "caption_preview.mp4"
    mock_render.return_value = output_path.resolve()

    result = render_caption_preview(project_path, output_path)

    assert result == output_path.resolve()
    mock_render.assert_called_once_with(
        project_path,
        output_path,
        background_color="#000000",
    )
