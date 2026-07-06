"""One-off spike: POST EverAI TTS, poll until done, inspect response + SRT."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

api_key = (os.environ.get("EVERAI_API_KEY") or "").strip()
if not api_key:
    sys.exit("EVERAI_API_KEY missing or empty")

BASE = "https://www.everai.vn/api/v1/tts"
HEADERS = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}
TEXT = "Chào mừng bạn đến với kênh của chúng tôi. Hôm nay chúng ta sẽ khám phá một bí mật thú vị."
VOICE = "vi_male_lenghia_mb"
OUT_DIR = ROOT / "output" / "everai_spike"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    payload = {
        "input_text": TEXT,
        "voice_code": VOICE,
        "audio_type": "mp3",
        "bitrate": 128,
        "speed_rate": 1.0,
        "pitch_rate": 1.0,
        "generate_srt": True,
        "model_id": "everai-v1.5",
    }

    print("=== POST /tts ===")
    print("voice_code:", VOICE)
    print("text_len:", len(TEXT))
    response = requests.post(BASE, headers=HEADERS, json=payload, timeout=60)
    print("HTTP", response.status_code)
    post_body = response.json()
    (OUT_DIR / "post_response.json").write_text(
        json.dumps(post_body, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("POST status:", post_body.get("status"))

    if post_body.get("status") != 1:
        print("error_code:", post_body.get("error_code"))
        print("error_message:", post_body.get("error_message"))
        sys.exit("POST failed")

    request_id = post_body["result"]["request_id"]
    print("\n=== Polling GET /tts/{request_id} ===")
    poll_url = f"{BASE}/{request_id}"
    final = None
    for attempt in range(1, 61):
        poll_response = requests.get(poll_url, headers=HEADERS, timeout=60)
        body = poll_response.json()
        result = body.get("result") or {}
        status = result.get("status")
        progress = result.get("progress")
        print(f"poll {attempt}: status={status!r} progress={progress!r}")
        if status == "done":
            final = body
            break
        if status in ("failure", "failed", "error"):
            (OUT_DIR / "poll_failed.json").write_text(
                json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            sys.exit("TTS failed")
        time.sleep(2)
    else:
        sys.exit("Timed out polling")

    print("\n=== Final poll response saved ===")
    (OUT_DIR / "poll_final.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    result = final["result"]
    audio_link = result.get("audio_link")
    links = {key: value for key, value in result.items() if isinstance(value, str) and value.startswith("http")}
    print("\n=== URL fields in result ===")
    for key, value in sorted(links.items()):
        preview = value if len(value) <= 100 else value[:100] + "..."
        print(f"  {key}: {preview}")

    if audio_link:
        audio_path = OUT_DIR / "spike.mp3"
        audio_response = requests.get(audio_link, timeout=120)
        audio_path.write_bytes(audio_response.content)
        print(f"\nDownloaded audio: {audio_path} ({len(audio_response.content)} bytes)")

    srt_downloaded = False
    for key in ("srt_link", "subtitle_link", "srt_url"):
        link = result.get(key)
        if not link:
            continue
        srt_response = requests.get(link, timeout=120)
        srt_path = OUT_DIR / "spike.srt"
        srt_path.write_bytes(srt_response.content)
        print(f"\nDownloaded SRT from {key}: {srt_path}")
        print("SRT cue count:", srt_response.text.count("\n\n") + 1)
        (OUT_DIR / "spike.srt").write_text(srt_response.text, encoding="utf-8")
        srt_downloaded = True
        break

    if not srt_downloaded:
        for key, value in result.items():
            if "srt" in key.lower():
                print(f"\nSRT-related field {key}: {value!r}")

    print("\n=== Result key inventory ===")
    for key, value in sorted(result.items()):
        preview = value
        if isinstance(value, str) and len(value) > 100:
            preview = value[:100] + "..."
        print(f"  {key}: ({type(value).__name__}) {preview!r}")


if __name__ == "__main__":
    main()
