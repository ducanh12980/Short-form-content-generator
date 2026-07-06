/**
 * effects.tsx — centralized registry of all visual effects for ShortVideo compositions.
 *
 * Both the full orchestrator pipeline and the simple stitch demo render through
 * ShortVideo.tsx, which imports everything from here. Add new effects in the
 * appropriate section below, export them, and consume in ShortVideo.tsx.
 *
 * Sections:
 *   1. Image transition effects  — slide-change animations (FadingImage, …)
 *   2. Caption animation effects — per-word/token animations (pop scale, …)
 */

import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";

// ─────────────────────────────────────────────────────────────────────────────
// 1. IMAGE TRANSITION EFFECTS
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Duration of the fade-in ramp at the start of each slide, in frames.
 * At 30 fps this is 200 ms — long enough to feel smooth, short enough not to
 * eat into reading time.
 */
export const SLIDE_FADE_IN_FRAMES = 6;

/**
 * FadingImage — renders a full-bleed image that fades in from transparent over
 * SLIDE_FADE_IN_FRAMES frames, then holds at full opacity for the rest of its
 * Sequence duration.
 *
 * Usage: wrap in a <Sequence from={start} durationInFrames={duration}>.
 * The frame counter resets to 0 at the start of each Sequence, so the fade
 * always fires on entry regardless of absolute timeline position.
 */
export const FadingImage: React.FC<{ src: string }> = ({ src }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, SLIDE_FADE_IN_FRAMES], [0, 1], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ opacity }}>
      <Img
        src={staticFile(src)}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 2. CAPTION ANIMATION EFFECTS
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Fraction of the current fps used as the pop animation ramp duration.
 * e.g. at 30 fps → Math.round(0.12 * 30) = 4 frames (≈ 133 ms).
 */
export const POP_DURATION_RATIO = 0.12;

/**
 * Starting scale for the "pop" entrance animation.
 * The word renders at this size on frame 0 and eases down to 1× by the end
 * of the ramp, giving a quick elastic-in feel.
 */
export const POP_SCALE_START = 1.15;

/**
 * getPopScale — returns the CSS transform scale for a caption token on the
 * given frame when the "pop" animation is active.
 *
 * @param frame  - current frame relative to the token's Sequence (starts at 0)
 * @param fps    - composition frame rate
 * @returns      - scale multiplier (1.0 after the ramp completes)
 */
export function getPopScale(frame: number, fps: number): number {
  const rampFrames = Math.max(1, Math.round(POP_DURATION_RATIO * fps));
  return interpolate(frame, [0, rampFrames], [POP_SCALE_START, 1], {
    extrapolateRight: "clamp",
  });
}
