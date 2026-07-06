/**
 * effects.tsx — centralized registry of all visual effects for ShortVideo compositions.
 *
 * Default slide combo (CapCut-style):
 *   • Ken Burns ambient center zoom on holds
 *   • Exit: unified zoom out (~2 s ease-in → sharp mirror reveal + blur)
 *   • Enter: fast zoom back in on the next slide
 *
 * Sections:
 *   1. Image transition effects  — ramp zoom blur + mirror
 *   2. Ambient motion            — Ken Burns
 *   3. Caption animation effects — per-word/token animations (pop scale, …)
 */

import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { TimelineImage } from "./types";

// ─────────────────────────────────────────────────────────────────────────────
// 1. RAMP ZOOM TRANSITION (default)
// ─────────────────────────────────────────────────────────────────────────────

/** Slow pull-back duration before the cut (~2 s). */
export const SLOW_ZOOM_OUT_SEC = 2;

/** Tail of the unified zoom-out — sharp acceleration + blur (frames). */
export const SHARP_ZOOM_OUT_FRAMES = 12;

/** Fast zoom back in on incoming slide (frames). */
export const FAST_ZOOM_IN_FRAMES = 15;

/** Scale at end of Ken Burns / start of zoom out. */
export const HOLD_SCALE_END = 1.08;

/** Deepest scale at end of unified zoom out. */
export const SHARP_ZOOM_OUT_END = 0.55;

/** Peak CSS blur at the deepest zoom-out. */
export const ZOOM_BLUR_MAX_PX = 28;

/** Blur stays off until scale drops below this (deeper zoom → more blur). */
export const ZOOM_BLUR_START_SCALE = 0.85;

/** Enable mirror grid this many seconds before zoom-out starts (avoids black flash). */
export const MIRROR_PRELOAD_SEC = 0.1;

export const getMirrorPreloadFrames = (fps: number): number =>
  Math.max(1, Math.round(MIRROR_PRELOAD_SEC * fps));

const easeIn = Easing.in(Easing.cubic);
const easeOut = Easing.out(Easing.cubic);

export type SlideTransitionType = "zoomBlur";
export const DEFAULT_TRANSITION: SlideTransitionType = "zoomBlur";

export const getSlowZoomOutFrames = (fps: number): number =>
  Math.max(1, Math.round(SLOW_ZOOM_OUT_SEC * fps));

/** Total outgoing zoom-out span: slow lead-in + sharp tail past the cut. */
export const getExitZoomOutFrames = (fps: number): number =>
  getSlowZoomOutFrames(fps) + SHARP_ZOOM_OUT_FRAMES;

export const getTransitionDuration = (_type: SlideTransitionType = "zoomBlur"): number =>
  SHARP_ZOOM_OUT_FRAMES + FAST_ZOOM_IN_FRAMES;

export const buildCutTransitionTypes = (
  slides: { src: string }[],
): SlideTransitionType[] => Array(Math.max(0, slides.length - 1)).fill(DEFAULT_TRANSITION);

type TransitionTransform = {
  scale: number;
  translateXPercent: number;
  opacity: number;
  blurPx: number;
  useMirror: boolean;
};

const identityTransition: TransitionTransform = {
  scale: 1,
  translateXPercent: 0,
  opacity: 1,
  blurPx: 0,
  useMirror: false,
};

/** Radial-style blur tied to how far we've zoomed out — not transition progress. */
export const getZoomBlurForScale = (scale: number): number =>
  interpolate(
    scale,
    [SHARP_ZOOM_OUT_END, ZOOM_BLUR_START_SCALE],
    [ZOOM_BLUR_MAX_PX, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

/**
 * Unified zoom out — continuous ease-in from the live Ken Burns scale/position.
 */
export const getUnifiedZoomOutTransform = (
  progress: number,
  startScale: number,
): TransitionTransform => {
  const t = easeIn(interpolate(progress, [0, 1], [0, 1], { extrapolateRight: "clamp" }));
  const scale = interpolate(t, [0, 1], [startScale, SHARP_ZOOM_OUT_END]);
  return {
    scale,
    translateXPercent: 0,
    opacity: 1,
    blurPx: getZoomBlurForScale(scale),
    useMirror: true,
  };
};

/** Fast zoom back in on incoming slide. */
export const getFastZoomInTransform = (progress: number): TransitionTransform => {
  const clamped = Math.max(0, Math.min(1, progress));
  const t = easeOut(interpolate(clamped, [0, 1], [0, 1]));
  const scale = interpolate(t, [0, 1], [SHARP_ZOOM_OUT_END, 1]);
  return {
    scale,
    translateXPercent: 0,
    opacity: 1,
    blurPx: getZoomBlurForScale(scale),
    // Enter zoom only — no mirror grid so captions stay readable over the cut.
    useMirror: false,
  };
};

// ─────────────────────────────────────────────────────────────────────────────
// 2. AMBIENT MOTION (Ken Burns)
// ─────────────────────────────────────────────────────────────────────────────

export const KEN_BURNS_SCALE_END = HOLD_SCALE_END;

export const getKenBurnsScale = (
  localFrame: number,
  durationFrames: number,
): number => {
  const duration = Math.max(1, durationFrames);
  return interpolate(localFrame, [0, duration], [1, KEN_BURNS_SCALE_END], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
};

// ─────────────────────────────────────────────────────────────────────────────
// MIRROR + ZOOM RENDERER
// ─────────────────────────────────────────────────────────────────────────────

const imgBaseStyle: React.CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block",
};

/** 3×3 mirror tile — center cell normal, edges reflected on X, Y, or both. */
const MIRROR_FLIPS: { flipX: boolean; flipY: boolean }[][] = [
  [
    { flipX: true, flipY: true },
    { flipX: false, flipY: true },
    { flipX: true, flipY: true },
  ],
  [
    { flipX: true, flipY: false },
    { flipX: false, flipY: false },
    { flipX: true, flipY: false },
  ],
  [
    { flipX: true, flipY: true },
    { flipX: false, flipY: true },
    { flipX: true, flipY: true },
  ],
];

const MirrorTile: React.FC<{ src: string; flipX: boolean; flipY: boolean }> = ({
  src,
  flipX,
  flipY,
}) => {
  const parts: string[] = [];
  if (flipX) parts.push("scaleX(-1)");
  if (flipY) parts.push("scaleY(-1)");
  return (
    <div style={{ overflow: "hidden", width: "100%", height: "100%" }}>
      <Img
        src={src}
        style={{
          ...imgBaseStyle,
          transform: parts.length > 0 ? parts.join(" ") : undefined,
          transformOrigin: "center center",
        }}
      />
    </div>
  );
};

const MirrorZoomImage: React.FC<{
  src: string;
  scale: number;
  translateXPercent: number;
  blurPx: number;
  useMirror: boolean;
}> = ({ src, scale, translateXPercent, blurPx, useMirror }) => {
  const file = staticFile(src);
  const { width: frameW, height: frameH } = useVideoConfig();
  const filter = blurPx > 0.5 ? `blur(${blurPx}px)` : undefined;

  const layerW = useMirror ? frameW * 3 : frameW;
  const layerH = useMirror ? frameH * 3 : frameH;

  const layerStyle: React.CSSProperties = {
    position: "absolute",
    left: frameW / 2,
    top: frameH / 2,
    width: layerW,
    height: layerH,
    marginLeft: -layerW / 2,
    marginTop: -layerH / 2,
    transform: `scale(${scale}) translate(${translateXPercent}%, 0%)`,
    transformOrigin: "center center",
    filter,
    ...(useMirror
      ? {
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gridTemplateRows: "1fr 1fr 1fr",
        }
      : {}),
  };

  if (!useMirror) {
    return (
      <div style={layerStyle}>
        <Img src={file} style={imgBaseStyle} />
      </div>
    );
  }

  return (
    <div style={layerStyle}>
      {MIRROR_FLIPS.flatMap((row, rowIdx) =>
        row.map((cell, colIdx) => (
          <MirrorTile
            key={`${rowIdx}-${colIdx}`}
            src={file}
            flipX={cell.flipX}
            flipY={cell.flipY}
          />
        )),
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SLIDESHOW BACKGROUND
// ─────────────────────────────────────────────────────────────────────────────

const msToFrames = (ms: number, fps: number): number =>
  Math.max(0, Math.round((ms / 1000) * fps));

type SlideSegment = TimelineImage & {
  index: number;
  startFrame: number;
  endFrame: number;
};

type SlideRenderStyle = {
  opacity: number;
  zIndex: number;
  scale: number;
  translateXPercent: number;
  blurPx: number;
  useMirror: boolean;
};

const computeSlideStyle = (
  frame: number,
  slide: SlideSegment,
  _slides: SlideSegment[],
  fps: number,
): SlideRenderStyle | null => {
  const { index, startFrame, endFrame } = slide;
  const slowFrames = getSlowZoomOutFrames(fps);
  const hasExit = index < _slides.length - 1;
  const hasEnter = index > 0;
  const cutFrame = endFrame;

  const enterFastStart = hasEnter ? startFrame + SHARP_ZOOM_OUT_FRAMES : startFrame;
  const enterFastEnd = hasEnter
    ? startFrame + SHARP_ZOOM_OUT_FRAMES + FAST_ZOOM_IN_FRAMES
    : startFrame + FAST_ZOOM_IN_FRAMES;

  const holdStart = enterFastEnd;
  const exitZoomStart = hasExit ? Math.max(holdStart, cutFrame - slowFrames) : endFrame;
  const exitZoomEnd = hasExit ? cutFrame + SHARP_ZOOM_OUT_FRAMES : endFrame;

  const showStart = hasEnter ? enterFastStart : startFrame;
  const showEnd = hasExit ? exitZoomEnd : endFrame;

  if (frame < showStart || frame >= showEnd) {
    return null;
  }

  let transition = identityTransition;
  let inTransition = false;

  const holdDuration = Math.max(1, exitZoomStart - holdStart);
  const mirrorPreloadFrames = getMirrorPreloadFrames(fps);
  const mirrorActiveFrom = hasExit ? exitZoomStart - mirrorPreloadFrames : endFrame;

  // Opening / incoming — fast zoom back in.
  if (frame < enterFastEnd) {
    const progress =
      (frame - (hasEnter ? enterFastStart : startFrame)) / FAST_ZOOM_IN_FRAMES;
    transition = getFastZoomInTransform(progress);
    inTransition = true;
  }
  // Outgoing — unified zoom out, starting from live Ken Burns scale.
  else if (hasExit && frame >= exitZoomStart && frame < exitZoomEnd) {
    const span = Math.max(1, exitZoomEnd - exitZoomStart);
    const progress = (frame - exitZoomStart) / span;
    const startScale = getKenBurnsScale(
      Math.max(0, exitZoomStart - holdStart),
      holdDuration,
    );
    transition = getUnifiedZoomOutTransform(progress, startScale);
    inTransition = true;
  }
  // Hold — Ken Burns center zoom.
  else if (frame >= holdStart && frame < exitZoomStart) {
    const holdFrame = frame - holdStart;
    transition = {
      ...identityTransition,
      scale: getKenBurnsScale(holdFrame, holdDuration),
    };
  }

  const scale = transition.scale;
  const translateXPercent = transition.translateXPercent;

  const zIndex =
    inTransition && hasEnter && frame >= enterFastStart ? index + 10 : index;

  // Mirror grid only on outgoing zoom-out (not during incoming zoom-in).
  const useMirror =
    transition.useMirror ||
    (hasExit && frame >= mirrorActiveFrom && frame < exitZoomEnd);

  return {
    opacity: transition.opacity,
    zIndex,
    scale,
    translateXPercent,
    blurPx: transition.blurPx,
    useMirror,
  };
};

/**
 * SlideshowBackground — Ken Burns holds + ramp zoom-blur/mirror transitions.
 */
export const SlideshowBackground: React.FC<{
  images: TimelineImage[];
  fps: number;
}> = ({ images, fps }) => {
  const frame = useCurrentFrame();

  if (images.length === 0) return null;

  const slides: SlideSegment[] = images.map((image, index) => ({
    ...image,
    index,
    startFrame: msToFrames(image.start_ms, fps),
    endFrame: msToFrames(image.end_ms, fps),
  }));

  return (
    <>
      {slides.map((slide) => {
        const style = computeSlideStyle(frame, slide, slides, fps);
        if (!style) return null;

        return (
          <AbsoluteFill
            key={`${slide.src}-${slide.index}`}
            style={{
              opacity: style.opacity,
              zIndex: style.zIndex,
              overflow: "hidden",
            }}
          >
            <MirrorZoomImage
              src={slide.src}
              scale={style.scale}
              translateXPercent={style.translateXPercent}
              blurPx={style.blurPx}
              useMirror={style.useMirror}
            />
          </AbsoluteFill>
        );
      })}
    </>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 3. CAPTION ANIMATION EFFECTS
// ─────────────────────────────────────────────────────────────────────────────

export const POP_DURATION_RATIO = 0.12;
export const POP_SCALE_START = 1.15;

export function getPopScale(frame: number, fps: number): number {
  const rampFrames = Math.max(1, Math.round(POP_DURATION_RATIO * fps));
  return interpolate(frame, [0, rampFrames], [POP_SCALE_START, 1], {
    extrapolateRight: "clamp",
  });
}
