"""Caption tokens — shared caption token shape and TTS timestamp enrichment."""

from __future__ import annotations

import re
from typing import Any

VALID_STYLES = frozenset({"primary", "highlight"})
VALID_ANIMATIONS = frozenset({"none", "pop"})
LEGACY_POP_ANIMATIONS = frozenset({"elastic_bounce", "sudden_snap"})
_MATCH_PUNCT = ".,!?;:\"'()[]…"
_ELLIPSIS_PLACEHOLDER = "\uE000"
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def normalize_match_text(text: str) -> str:
    """Normalize display or TTS text for word-boundary alignment.

    Goal: Match caption tokens to edge-tts timestamps when display text keeps punctuation
        (e.g. \"Nam.\") but TTS boundaries omit it (e.g. \"Nam\").
    Params: text — raw word from a caption token or word_timestamps entry.
    Output: Lowercase string with outer whitespace and punctuation stripped.
    """
    cleaned = text.strip().lower()
    return cleaned.strip(_MATCH_PUNCT)


def match_word_timestamp(
    spoken: str,
    word_timestamps: list[dict[str, Any]],
    cursor: int,
    *,
    fallback_by_norm: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, int]:
    """Align one spoken word to TTS boundaries without draining the timestamp cursor.

    Goal: Sequential sync — check only word_timestamps[cursor]; advance cursor on success;
        leave cursor unchanged on failure so later tokens can still match.
    Params: spoken — text used for TTS alignment (spoken_text or display text);
        word_timestamps — edge-tts boundary list; cursor — next expected index;
        fallback_by_norm — optional normalize_match_text → timestamp map.
    Output: (matched {text, start_ms, end_ms} or None, updated cursor).
    """
    norm = normalize_match_text(spoken)
    if not norm:
        return None, cursor

    if cursor < len(word_timestamps):
        candidate = word_timestamps[cursor]
        if normalize_match_text(candidate["text"]) == norm:
            return candidate, cursor + 1

    if fallback_by_norm is not None:
        hit = fallback_by_norm.get(norm)
        if hit is not None:
            try:
                idx = word_timestamps.index(hit)
            except ValueError:
                return hit, cursor
            return hit, max(cursor, idx + 1)

    return None, cursor


def normalize_caption_token(token: dict[str, Any]) -> dict[str, Any]:
    """Ensure one token uses caption_renderer field names (text, style, animation).

    Goal: Accept current or legacy MVP tokens and return the canonical renderer shape.
    Params: token — caption dict (canonical or legacy word/highlight_color/animation_pop).
    Output: Token dict with at least text, style, and animation keys.
    """
    if "text" in token:
        normalized = dict(token)
        normalized.setdefault("style", "primary")
        normalized.setdefault("animation", "none")
        return normalized

    word = str(token.get("word", ""))
    highlight = str(token.get("highlight_color", "none")).lower()
    animation_pop = str(token.get("animation_pop", "none")).lower()

    return {
        **{k: v for k, v in token.items() if k not in ("word", "highlight_color", "animation_pop")},
        "text": word,
        "style": "highlight" if highlight != "none" else "primary",
        "animation": "pop" if animation_pop in LEGACY_POP_ANIMATIONS else "none",
    }


def merge_styled_tokens_with_timestamps(
    styled_tokens: list[dict[str, Any]],
    word_timestamps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join LLM styling with TTS timing by index — TTS is authoritative for spoken text and ms.

    Goal: Avoid text matching on the hot path; caption styler and TTS both derive from raw_script
        in spoken order, so tokens[i] aligns with word_timestamps[i].
    Params: styled_tokens — LLM output (text, style, animation); word_timestamps — edge-tts list.
    Output: Tokens with display text, spoken_text, start_ms, and end_ms on every entry.
    """
    if len(styled_tokens) != len(word_timestamps):
        raise ValueError(
            f"Caption token count ({len(styled_tokens)}) does not match "
            f"TTS word count ({len(word_timestamps)}). "
            "Re-run caption styler or TTS so both lists align."
        )

    merged: list[dict[str, Any]] = []
    for styled, ts in zip(styled_tokens, word_timestamps, strict=True):
        token = normalize_caption_token(styled)
        display_text = str(token.get("text", "")).strip()
        spoken = str(ts["text"]).strip()
        merged.append(
            {
                **{
                    k: v
                    for k, v in token.items()
                    if k not in ("start_ms", "end_ms", "spoken_text")
                },
                "text": display_text or spoken,
                "spoken_text": spoken,
                "start_ms": ts["start_ms"],
                "end_ms": ts["end_ms"],
            }
        )
    return merged


def _enrich_tokens_by_text_match(
    tokens: list[dict[str, Any]],
    word_timestamps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Legacy fallback: align tokens to TTS by spoken text when list lengths differ."""
    enriched: list[dict[str, Any]] = []
    cursor = 0
    fallback_by_norm = {
        normalize_match_text(entry["text"]): entry for entry in word_timestamps
    }

    for raw in tokens:
        token = normalize_caption_token(raw)
        copy = dict(token)
        if "spoken_text" not in copy:
            copy["spoken_text"] = copy.get("text", "")

        if "start_ms" in copy and "end_ms" in copy:
            enriched.append(copy)
            continue

        spoken = str(copy.get("spoken_text", copy.get("text", ""))).strip()
        timing, cursor = match_word_timestamp(
            spoken,
            word_timestamps,
            cursor,
            fallback_by_norm=fallback_by_norm,
        )

        if timing is not None:
            copy["start_ms"] = timing["start_ms"]
            copy["end_ms"] = timing["end_ms"]
            copy["spoken_text"] = timing["text"]

        enriched.append(copy)

    return enriched


def enrich_tokens_with_timestamps(
    tokens: list[dict[str, Any]],
    word_timestamps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach start_ms and end_ms to each token from TTS word boundaries.

    Goal: Sync caption tokens to narration timing for render and legacy payload upgrade.
    Params: tokens — list of caption tokens; word_timestamps — edge-tts boundary list.
    Output: New list of tokens with start_ms/end_ms and spoken_text when possible.
    """
    if not word_timestamps:
        return [normalize_caption_token(raw) for raw in tokens]

    normalized = [normalize_caption_token(raw) for raw in tokens]
    if all("start_ms" in t and "end_ms" in t for t in normalized):
        enriched: list[dict[str, Any]] = []
        for token in normalized:
            copy = dict(token)
            copy.setdefault("spoken_text", copy.get("text", ""))
            enriched.append(copy)
        return enriched

    if len(tokens) == len(word_timestamps):
        return merge_styled_tokens_with_timestamps(tokens, word_timestamps)

    return _enrich_tokens_by_text_match(tokens, word_timestamps)


def split_tts_sentences(tts: str) -> list[str]:
    """Split narration into sentences on . ? ! boundaries.

    Goal: Derive per-sentence caption blocks from scene TTS without splitting ellipses.
    Params: tts — scene narration text.
    Output: Non-empty sentence strings preserving original punctuation.
    """
    text = tts.strip()
    if not text:
        return []

    protected = text.replace("...", _ELLIPSIS_PLACEHOLDER)
    parts = _SENTENCE_SPLIT_RE.split(protected)
    sentences: list[str] = []
    for part in parts:
        restored = part.replace(_ELLIPSIS_PLACEHOLDER, "...").strip()
        if restored:
            sentences.append(restored)
    return sentences


def _scene_word_timestamps(
    word_timestamps: list[dict[str, Any]],
    scene_start_ms: int,
    scene_end_ms: int,
) -> list[dict[str, Any]]:
    """Return word boundaries that overlap a scene window (inclusive of boundary speech)."""
    return [
        entry
        for entry in word_timestamps
        if int(entry["start_ms"]) < scene_end_ms and int(entry["end_ms"]) > scene_start_ms
    ]


def _timing_for_sentence(
    sentence: str,
    scene_words: list[dict[str, Any]],
    cursor: int,
    *,
    scene_start_ms: int,
    scene_end_ms: int,
) -> tuple[int, int, int]:
    """Align one sentence to word timestamps; return (start_ms, end_ms, new_cursor)."""
    fallback_by_norm = {
        normalize_match_text(entry["text"]): entry for entry in scene_words
    }
    matched: list[dict[str, Any]] = []
    for spoken_word in sentence.split():
        timing, cursor = match_word_timestamp(
            spoken_word,
            scene_words,
            cursor,
            fallback_by_norm=fallback_by_norm,
        )
        if timing is not None:
            matched.append(timing)

    if matched:
        return int(matched[0]["start_ms"]), int(matched[-1]["end_ms"]), cursor

    return scene_start_ms, scene_end_ms, cursor


def _words_for_sentence(
    sentence: str,
    scene_words: list[dict[str, Any]],
    cursor: int,
) -> tuple[list[dict[str, Any]], int]:
    """Match each whitespace-split word in a sentence to a TTS timestamp entry.

    Goal: Produce the per-word timing array for a karaoke token.
    Params: sentence — display sentence string; scene_words — TTS words for this scene;
        cursor — sequential search cursor (advance on each match).
    Output: (list of {text, start_ms, end_ms}, updated cursor).
    """
    fallback_by_norm = {normalize_match_text(e["text"]): e for e in scene_words}
    matched: list[dict[str, Any]] = []
    for spoken_word in sentence.split():
        timing, cursor = match_word_timestamp(
            spoken_word,
            scene_words,
            cursor,
            fallback_by_norm=fallback_by_norm,
        )
        if timing is not None:
            matched.append(
                {
                    "text": spoken_word,
                    "start_ms": int(timing["start_ms"]),
                    "end_ms": int(timing["end_ms"]),
                }
            )
    return matched, cursor


def build_karaoke_tokens_from_scenes(
    scenes: list[dict[str, Any]],
    words_by_scene: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build one caption token per TTS sentence with per-word highlight timing.

    Goal: True karaoke display — full sentence visible throughout, current word highlighted
        as it is spoken. No LLM call required; timing is sourced from TTS word boundaries.
    Params: scenes — slideshow scenes with start_ms/end_ms;
        words_by_scene — {scene_id: [{text, start_ms, end_ms}]} pre-grouped at TTS time.
    Output: Sentence-level tokens with start_ms, end_ms, style=primary, animation=none,
        and a words[] array for per-word highlight timing.
    """
    tokens: list[dict[str, Any]] = []
    for scene in scenes:
        start_ms = scene.get("start_ms")
        end_ms = scene.get("end_ms")
        if start_ms is None or end_ms is None:
            continue
        tts = str(scene.get("tts", "")).strip()
        if not tts:
            continue

        scene_start_ms = int(start_ms)
        scene_end_ms = int(end_ms)
        scene_id = int(scene.get("id", 0))
        scene_words = words_by_scene.get(scene_id, [])
        sentences = split_tts_sentences(tts)
        if not sentences:
            continue

        cursor = 0
        for sentence in sentences:
            word_entries, cursor = _words_for_sentence(sentence, scene_words, cursor)
            if word_entries:
                token_start = word_entries[0]["start_ms"]
                token_end = word_entries[-1]["end_ms"]
            else:
                token_start, token_end = scene_start_ms, scene_end_ms
            tokens.append(
                {
                    "text": sentence,
                    "spoken_text": sentence,
                    "style": "primary",
                    "animation": "none",
                    "start_ms": token_start,
                    "end_ms": token_end,
                    "words": word_entries,
                }
            )
    return tokens


def build_sentence_tokens_from_scenes(
    scenes: list[dict[str, Any]],
    word_timestamps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build one caption token per TTS sentence, timed via word boundaries when available."""
    tokens: list[dict[str, Any]] = []
    use_word_timing = bool(word_timestamps)

    for scene in scenes:
        tts = str(scene.get("tts", "")).strip()
        if not tts:
            continue
        start_ms = scene.get("start_ms")
        end_ms = scene.get("end_ms")
        if start_ms is None or end_ms is None:
            continue

        scene_start_ms = int(start_ms)
        scene_end_ms = int(end_ms)

        if not use_word_timing:
            tokens.append(
                {
                    "text": tts,
                    "style": "primary",
                    "animation": "none",
                    "spoken_text": tts,
                    "start_ms": scene_start_ms,
                    "end_ms": scene_end_ms,
                }
            )
            continue

        scene_words = _scene_word_timestamps(
            word_timestamps or [],
            scene_start_ms,
            scene_end_ms,
        )
        sentences = split_tts_sentences(tts)
        if not sentences:
            continue

        cursor = 0
        for sentence in sentences:
            sent_start_ms, sent_end_ms, cursor = _timing_for_sentence(
                sentence,
                scene_words,
                cursor,
                scene_start_ms=scene_start_ms,
                scene_end_ms=scene_end_ms,
            )
            tokens.append(
                {
                    "text": sentence,
                    "style": "primary",
                    "animation": "none",
                    "spoken_text": sentence,
                    "start_ms": sent_start_ms,
                    "end_ms": sent_end_ms,
                }
            )

    return tokens
