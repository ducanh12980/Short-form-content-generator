"""Master Controller — dual-LLM MVP pipeline (script → styled tokens → TTS → payload)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIError, OpenAI

from core.audio_generator import synthesize_speech

SCRIPT_WRITER_MODEL = "gemini-2.5-flash"
CAPTION_STYLER_MODEL = "gemini-2.5-flash"
DEFAULT_TTS_VOICE = "vi-VN-HoaiMyNeural"

SCRIPT_WRITER_SYSTEM_PROMPT = (
    "You are a viral short-form copywriter for Vietnamese audiences. "
    "Write punchy, high-retention narration scripts in Vietnamese for TikTok, Reels, and YouTube Shorts. "
    "Use a strong hook in the first line, short sentences, and a clear payoff. "
    "Write entirely in Vietnamese — natural spoken Vietnamese, not English. "
    "Output only the spoken script text — no titles, labels, or markdown."
)

CAPTION_STYLER_SYSTEM_PROMPT = """You are a caption styler for short-form video typography.

The narration script is in Vietnamese. Parse it into a raw dictionary object with a root key "tokens".

"tokens" must be a JSON array containing one object for every single individual word in the script, in spoken order.

Each word object must use these exact keys:
- "word": the individual Vietnamese word as spoken (preserve punctuation attached to the word)
- "highlight_color": one of "yellow", "red", "green", or "none"
- "animation_pop": one of "elastic_bounce", "sudden_snap", or "none"

Rules:
- Split on whitespace; every word gets its own object — do not merge phrases.
- Keep Vietnamese diacritics exactly as in the script (e.g. uống, không, được).
- Reserve yellow/red/green highlights for hook words, stats, and emotional peaks.
- Use elastic_bounce or sudden_snap sparingly on the highest-impact words.
- Output valid JSON only with the root shape: {"tokens": [...]}
"""

_env_loaded = False


class PipelineError(RuntimeError):
    """Raised when an LLM or TTS pipeline stage fails."""


def _load_env() -> None:
    """Load key/value pairs from `.env` in the project root into ``os.environ`` (once per process)."""
    global _env_loaded
    if _env_loaded:
        return
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    _env_loaded = True


def _require_env(*names: str) -> None:
    """Raise ``RuntimeError`` if any named environment variable is missing or empty."""
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment variable(s): {joined}. "
            "Copy .env.example to .env and fill in the values."
        )


def _get_client() -> OpenAI:
    """Return an OpenAI-compatible client using ``OPENAI_API_KEY`` and ``OPENAI_BASE_URL`` from the environment."""
    _load_env()
    _require_env("OPENAI_API_KEY", "OPENAI_BASE_URL")
    timeout = float(os.environ.get("OPENAI_TIMEOUT", "60"))
    return OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
        timeout=timeout,
    )


def _model_from_env(env_var: str, default: str) -> str:
    """Read an LLM model id from the environment, falling back to the module default."""
    return os.environ.get(env_var, default)


def _tts_voice_from_env() -> str:
    """Read the edge-tts voice name from ``TTS_VOICE``, defaulting to Vietnamese HoaiMy."""
    return os.environ.get("TTS_VOICE", DEFAULT_TTS_VOICE)


def run_script_writer(client: OpenAI, topic_prompt: str) -> str:
    """Call the script-writer LLM with a video topic; return the spoken narration text in Vietnamese."""
    topic = topic_prompt.strip()
    if not topic:
        raise ValueError("topic_prompt must not be empty.")

    model = _model_from_env("SCRIPT_WRITER_MODEL", SCRIPT_WRITER_MODEL)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SCRIPT_WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": topic},
            ],
        )
    except APIError as exc:
        raise PipelineError(f"Script writer API call failed: {exc}") from exc

    raw_script = (response.choices[0].message.content or "").strip()
    if not raw_script:
        raise PipelineError("Script writer returned an empty script.")

    return raw_script


def run_caption_styler(client: OpenAI, raw_script: str) -> str:
    """Call the caption-styler LLM; return a JSON string with styled per-word tokens."""
    model = _model_from_env("CAPTION_STYLER_MODEL", CAPTION_STYLER_MODEL)
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CAPTION_STYLER_SYSTEM_PROMPT},
                {"role": "user", "content": raw_script},
            ],
        )
    except APIError as exc:
        raise PipelineError(f"Caption styler API call failed: {exc}") from exc

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise PipelineError("Caption styler returned an empty response.")

    return content


def parse_caption_styler_response(content: str) -> list[dict]:
    """Parse the caption styler's JSON string and return the ``tokens`` array as a Python list."""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Caption styler returned invalid JSON: {exc}") from exc

    tokens = parsed.get("tokens") if isinstance(parsed, dict) else None
    if not isinstance(tokens, list):
        raise ValueError('Caption styler JSON must include a "tokens" array.')

    return tokens


def validate_tokens(tokens: list[dict]) -> list[dict]:
    """Ensure each token is a dict with a non-empty ``word`` string; return the list unchanged."""
    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            raise ValueError(f"Token {index} must be an object.")
        word = token.get("word")
        if not isinstance(word, str) or not word.strip():
            raise ValueError(f"Token {index} must include a non-empty 'word'.")

    return tokens


def synthesize_narration(text: str, path: Path, voice: str) -> list[dict[str, Any]]:
    """Generate ``path`` as an MP3 from ``text`` via edge-tts; return per-word millisecond timestamps."""
    word_timestamps = synthesize_speech(text, path, voice=voice)
    if not word_timestamps:
        raise PipelineError("TTS produced no word boundaries.")

    return word_timestamps


def save_payload(payload: dict[str, Any], path: Path) -> None:
    """Write ``payload`` as pretty-printed UTF-8 JSON to ``path``, creating parent folders if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_mvp_pipeline(
    topic_prompt: str,
    *,
    output_dir: str | Path = "output",
) -> dict[str, Any]:
    """Run the full MVP: script writer → caption styler → TTS → ``pipeline_payload.json``; return the payload dict."""
    client = _get_client()
    out = Path(output_dir)
    voice = _tts_voice_from_env()

    raw_script = run_script_writer(client, topic_prompt)

    print("=" * 60)
    print("SCRIPT WRITER — RAW SCRIPT")
    print("=" * 60)
    print(raw_script)
    print()

    caption_styler_content = run_caption_styler(client, raw_script)
    tokens = parse_caption_styler_response(caption_styler_content)
    tokens = validate_tokens(tokens)

    print("=" * 60)
    print("CAPTION STYLER — STRUCTURED TOKEN LIST")
    print("=" * 60)
    print(json.dumps(tokens, indent=2, ensure_ascii=False))
    print()

    narration_path = out / "narration.mp3"
    word_timestamps = synthesize_narration(raw_script, narration_path, voice)

    payload: dict[str, Any] = {
        "topic": topic_prompt.strip(),
        "raw_script": raw_script,
        "tokens": tokens,
        "audio": {
            "path": str(narration_path.resolve()),
            "voice": voice,
            "word_timestamps": word_timestamps,
        },
    }
    payload_path = out / "pipeline_payload.json"
    save_payload(payload, payload_path)

    print("=" * 60)
    print("OUTPUT ARTIFACTS")
    print("=" * 60)
    print(f"Narration: {narration_path.resolve()}")
    print(f"Payload:   {payload_path.resolve()}")

    return payload


def main() -> None:
    """CLI entry point: parse topic and output dir, run the pipeline, exit 1 on failure."""
    _load_env()
    default_output = os.environ.get("OUTPUT_DIR", "output")

    parser = argparse.ArgumentParser(description="Run the short-form video MVP orchestrator.")
    parser.add_argument(
        "topic",
        nargs="?",
        default="90% mọi người đang uống nước sai cách",
        help="Video topic for the script writer",
    )
    parser.add_argument(
        "--output-dir",
        default=default_output,
        help="Directory for narration.mp3 and pipeline_payload.json (default: OUTPUT_DIR or output)",
    )
    args = parser.parse_args()

    try:
        run_mvp_pipeline(args.topic, output_dir=args.output_dir)
    except (PipelineError, ValueError, RuntimeError) as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
