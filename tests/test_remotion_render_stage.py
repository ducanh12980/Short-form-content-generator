"""Tests for Remotion render stage (mocked subprocess — no Node/ffmpeg)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.remotion_render_stage import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    project_to_remotion_props,
    render_project_video,
    render_with_remotion,
    _normalize_canvas_props,
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


def test_project_to_remotion_props_includes_transition(tmp_path: Path) -> None:
    narration = tmp_path / "narration.mp3"
    narration.write_bytes(b"fake")
    img = tmp_path / "scene.png"
    img.write_bytes(b"png")
    payload = {
        "topic": "test",
        "video": {
            "images": [
                {
                    "path": str(img),
                    "start_ms": 0,
                    "end_ms": 1000,
                    "transition": "pullIn",
                },
                {
                    "path": str(img),
                    "start_ms": 1000,
                    "end_ms": 2000,
                },
            ],
        },
        "audio": {"path": str(narration), "word_timestamps": []},
        "captions": {"theme": "minimalist", "font": None, "tokens": []},
    }
    path = tmp_path / "pipeline_payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    from core.project_schema import load_project

    project = load_project(path)
    props, _ = project_to_remotion_props(project)
    assert len(props["images"]) == 2
    assert props["images"][0]["transition"] == "pullIn"
    assert props["images"][1]["transition"] == "teleportShake"


def test_normalize_canvas_props_swaps_landscape() -> None:
    fixed = _normalize_canvas_props({"width": 1920, "height": 1080, "fps": 30})
    assert fixed["width"] == CANVAS_WIDTH
    assert fixed["height"] == CANVAS_HEIGHT


@patch("core.remotion_render_stage._resolve_npx", return_value="npx")
@patch("core.remotion_render_stage._run_remotion_cli")
@patch("core.remotion_render_stage._ensure_remotion_ready")
def test_render_with_remotion_invokes_cli(
    mock_ready: MagicMock,
    mock_run_cli: MagicMock,
    _mock_npx: MagicMock,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "preview.mp4"
    props = {"width": 1080, "height": 1920, "fps": 30, "durationMs": 1000, "tokens": []}

    def _touch_output(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
        output_path.write_bytes(b"mp4")

    mock_run_cli.side_effect = _touch_output

    result = render_with_remotion(props, output_path)

    assert result == output_path.resolve()
    mock_run_cli.assert_called_once()
    cmd = mock_run_cli.call_args.args[0]
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
    expected = tmp_path / "final.mp4"
    mock_render.return_value = expected.resolve()

    result = render_project_video(project_path, expected)

    assert result == expected.resolve()
    saved = json.loads(project_path.read_text(encoding="utf-8"))
    assert saved["render"]["final_path"] == str(expected.resolve())
    mock_render.assert_called_once()
    props = mock_render.call_args.args[0]
    assert props["tokens"][0]["text"] == "Hello"
