"""Tests for orchestrator_mvp guardrails (mocked — no live API)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import orchestrator_mvp as orch


def _mock_completion(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_BASE_URL": "http://test"}, clear=False)
def test_require_env_passes_when_vars_set() -> None:
    orch._require_env("OPENAI_API_KEY", "OPENAI_BASE_URL")


def test_require_env_raises_when_missing() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            orch._require_env("OPENAI_API_KEY")


def test_run_script_writer_rejects_empty_topic() -> None:
    client = MagicMock()
    with pytest.raises(ValueError, match="empty"):
        orch.run_script_writer(client, "   ")


@patch.dict(os.environ, {}, clear=True)
def test_run_script_writer_rejects_empty_response() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("  ")
    with pytest.raises(orch.PipelineError, match="empty script"):
        orch.run_script_writer(client, "valid topic")


@patch.dict(os.environ, {}, clear=True)
def test_run_caption_styler_not_called_when_script_writer_empty() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("")
    with pytest.raises(orch.PipelineError, match="empty script"):
        orch.run_script_writer(client, "topic")
    client.chat.completions.create.assert_called_once()


@patch.dict(os.environ, {}, clear=True)
@patch("orchestrator_mvp.time.sleep")
def test_call_with_api_retry_succeeds_on_second_attempt(mock_sleep: MagicMock) -> None:
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        orch.APIError("transient", request=MagicMock(), body=None),
        _mock_completion("Script text"),
    ]

    result = orch.run_script_writer(client, "topic")

    assert result == "Script text"
    assert client.chat.completions.create.call_count == 2
    mock_sleep.assert_called_once_with(orch.API_RETRY_DELAY_SECONDS)


@patch.dict(os.environ, {}, clear=True)
@patch("orchestrator_mvp.time.sleep")
def test_call_with_api_retry_fails_after_two_attempts(mock_sleep: MagicMock) -> None:
    client = MagicMock()
    client.chat.completions.create.side_effect = orch.APIError(
        "still failing",
        request=MagicMock(),
        body=None,
    )

    with pytest.raises(orch.PipelineError, match="after 2 attempt"):
        orch.run_script_writer(client, "topic")

    assert client.chat.completions.create.call_count == 2
    mock_sleep.assert_called_once_with(orch.API_RETRY_DELAY_SECONDS)


@patch.dict(os.environ, {}, clear=True)
def test_call_with_api_retry_fails_fast_on_daily_quota() -> None:
    client = MagicMock()
    client.chat.completions.create.side_effect = orch.APIError(
        "quota",
        request=MagicMock(),
        body={"error": {"message": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}},
    )

    with pytest.raises(orch.PipelineError, match="daily quota exceeded"):
        orch.run_script_writer(client, "topic")

    assert client.chat.completions.create.call_count == 1


def test_parse_caption_styler_response_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        orch.parse_caption_styler_response("not-json")


def test_parse_caption_styler_response_requires_tokens_key() -> None:
    with pytest.raises(ValueError, match='"tokens"'):
        orch.parse_caption_styler_response('{"layout": []}')


def test_validate_tokens_accepts_text_only() -> None:
    tokens = [{"text": "hello"}]
    assert orch.validate_tokens(tokens) == tokens


def test_validate_tokens_rejects_missing_text() -> None:
    with pytest.raises(ValueError, match="'text'"):
        orch.validate_tokens([{"style": "highlight"}])


def test_validate_tokens_accepts_partial_styling() -> None:
    tokens = [{"text": "hello", "style": "highlight"}]
    assert orch.validate_tokens(tokens) == tokens


def test_validate_tokens_accepts_full_tokens() -> None:
    tokens = [
        {"text": "90%", "style": "highlight", "animation": "pop"},
        {"text": "wrong", "style": "primary", "animation": "none"},
    ]
    assert orch.validate_tokens(tokens) == tokens


@patch("orchestrator_mvp.synthesize_speech", return_value=[])
def test_synthesize_narration_rejects_empty_timestamps(mock_synthesize: MagicMock, tmp_path: Path) -> None:
    with pytest.raises(orch.PipelineError, match="no word boundaries"):
        orch.synthesize_narration("hello world", tmp_path / "narration.mp3", "vi-VN-HoaiMyNeural")
    mock_synthesize.assert_called_once()


def test_save_payload_writes_file(tmp_path: Path) -> None:
    payload = {"topic": "test", "tokens": []}
    path = tmp_path / "nested" / "pipeline_payload.json"
    orch.save_payload(payload, path)
    assert path.is_file()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["topic"] == "test"


@patch.dict(os.environ, {"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": "http://x"}, clear=False)
@patch.object(orch, "synthesize_narration")
@patch.object(orch, "_get_client")
def test_run_mvp_pipeline_happy_path(
    mock_get_client: MagicMock,
    mock_synthesize: MagicMock,
    tmp_path: Path,
) -> None:
    client = MagicMock()
    mock_get_client.return_value = client
    mock_synthesize.return_value = [
        {"text": "Hook", "start_ms": 0, "end_ms": 100},
        {"text": "line", "start_ms": 100, "end_ms": 200},
        {"text": "here", "start_ms": 200, "end_ms": 300},
    ]

    script = "Hook line here."
    tokens_payload = {
        "tokens": [
            {"text": "Hook", "style": "highlight", "animation": "pop"},
            {"text": "line", "style": "primary", "animation": "none"},
            {"text": "here.", "style": "primary", "animation": "none"},
        ]
    }
    client.chat.completions.create.side_effect = [
        _mock_completion(script),
        _mock_completion(json.dumps(tokens_payload)),
    ]

    result = orch.run_mvp_pipeline("test topic", output_dir=tmp_path)
    assert len(result["tokens"]) == 3
    assert result["tokens"][0]["start_ms"] == 0
    assert result["tokens"][0]["spoken_text"] == "Hook"
    assert result["tokens"][2]["text"] == "here."
    assert client.chat.completions.create.call_count == 2
    assert (tmp_path / "pipeline_payload.json").is_file()
    assert result["audio"]["word_timestamps"][0]["text"] == "Hook"
    mock_synthesize.assert_called_once()
