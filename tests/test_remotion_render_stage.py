"""Tests for Remotion render stage (mocked subprocess — no Node/ffmpeg)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.remotion_render_stage import (
    project_to_remotion_props,
    render_project_video,
    render_with_remotion,
)


def _sample_payload(tmp_path: Path) -> Path:
    narration = tmp_path / "narration.mp3"
    narration.write_bytes(b"fake")
    payload = {
        "topic": "test",
        "raw_script": "Hello",
        "tokens": [
            {
                "text": "Hello",
                "style": "highlight",
                "animation": "none",
                "start_ms": 0,
                "end_ms": 500,
            }
        ],
        "audio": {
            "path": str(narration),
            "word_timestamps": [{"text": "Hello", "start_ms": 0, "end_ms": 500}],
        },
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_project_to_remotion_props(tmp_path: Path) -> None:
    project_path = _sample_payload(tmp_path)
    from core.project_schema import load_project

    project = load_project(project_path)
    props, _public_dir = project_to_remotion_props(project)

    assert props["width"] == 1080
    assert props["height"] == 1920
    assert props["themeName"] == "minimalist"
    assert props["tokens"][0]["text"] == "Hello"
    assert props["narrationSrc"] == "narration.mp3"
    assert props["durationMs"] == 500
    assert "minimalist" in props["themes"]


@patch("core.remotion_render_stage._resolve_npx", return_value="npx")
@patch("core.remotion_render_stage.subprocess.run")
@patch("core.remotion_render_stage._ensure_remotion_ready")
def test_render_with_remotion_invokes_cli(
    mock_ready: MagicMock,
    mock_run: MagicMock,
    _mock_npx: MagicMock,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "preview.mp4"
    props = {"width": 1080, "height": 1920, "fps": 30, "durationMs": 1000, "tokens": []}

    def _touch_output(*_args, **_kwargs) -> MagicMock:
        output_path.write_bytes(b"mp4")
        return MagicMock(returncode=0)

    mock_run.side_effect = _touch_output

    result = render_with_remotion(props, output_path)

    assert result == output_path.resolve()
    mock_run.assert_called_once()
    cmd = mock_run.call_args.args[0]
    assert "remotion" in cmd
    assert "ShortVideo" in cmd


@patch("core.remotion_render_stage.render_with_remotion")
@patch("core.remotion_render_stage._ensure_remotion_ready")
def test_render_project_video(
    mock_ready: MagicMock,
    mock_render: MagicMock,
    tmp_path: Path,
) -> None:
    project_path = _sample_payload(tmp_path)
    expected = tmp_path / "caption_preview.mp4"
    mock_render.return_value = expected.resolve()

    result = render_project_video(project_path, expected)

    assert result == expected.resolve()
    mock_render.assert_called_once()
    props = mock_render.call_args.args[0]
    assert props["tokens"][0]["text"] == "Hello"
