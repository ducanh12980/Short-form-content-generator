"""Audio Mixer — voice + ambient music with ducking during speech."""

from __future__ import annotations

from pathlib import Path

from moviepy import AudioFileClip, CompositeAudioClip


def compose_master_audio(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path,
    *,
    music_volume: float = 0.18,
    ducking_factor: float = 0.35,
) -> Path:
    """Overlay ambient music under narration with reduced music level during speech."""
    voice = AudioFileClip(str(voice_path))
    music = AudioFileClip(str(music_path))

    if music.duration < voice.duration:
        loops = int(voice.duration // music.duration) + 1
        music = CompositeAudioClip([music.with_start(i * music.duration) for i in range(loops)])
    music = music.subclipped(0, voice.duration)

    bed = music.with_volume_scaled(music_volume * ducking_factor)
    master = CompositeAudioClip([bed, voice])

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    master.write_audiofile(str(out), fps=44100, logger=None)
    voice.close()
    music.close()
    master.close()
    return out
