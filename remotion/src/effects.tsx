/**
 * effects.tsx — centralized registry of all visual effects for ShortVideo compositions.
 *
 * Per-cut transitions (CapCut-style):
 *   • pullIn — dolly zoom in + blur at impact
 *   • teleportShake — shake → white-out → recovery shake to center
 *   • whipPan — shake → ease-in-out horizontal whip + post-cut shake
 *   • zoomBlur — slow zoom-out + mirror grid + blur
 *
 * Sections:
 *   1. Image transition effects
 *   2. Ambient motion (Ken Burns)
 *   3. Caption animation effects
 *   4. Ambient overlays (see AmbientOverlay.tsx)
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
import type { SlideTransitionType, TimelineImage } from "./types";

// ─────────────────────────────────────────────────────────────────────────────
// 1. TRANSITION TYPES & CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────

export type { SlideTransitionType };

export const DEFAULT_TRANSITION_ROTATION: SlideTransitionType[] = [
  "pullIn",
  "teleportShake",
  "whipPan",
  "zoomBlur",
];

export const DEFAULT_TRANSITION: SlideTransitionType = "pullIn";

/** Slow pull-back duration before zoomBlur cut (~2 s). */
export const SLOW_ZOOM_OUT_SEC = 2;

/** Tail of zoom-out / pull transition past the cut (frames). */
export const SHARP_ZOOM_OUT_FRAMES = 12;

/** Fast zoom back in on incoming slide (frames). */
export const FAST_ZOOM_IN_FRAMES = 15;

/** Scale at end of Ken Burns / start of zoom out. */
export const HOLD_SCALE_END = 1.15;

/** Deepest scale at end of zoom-out (zoomBlur). */
export const SHARP_ZOOM_OUT_END = 0.55;

export const PULL_IN_SCALE_MAX = 1.9;

/** Peak CSS blur at deepest zoom. */
export const ZOOM_BLUR_MAX_PX = 28;

/** Blur stays off until scale drops below this (deeper zoom → more blur). */
export const ZOOM_BLUR_START_SCALE = 0.85;

/** Enable mirror grid this many seconds before zoomBlur zoom-out starts. */
export const MIRROR_PRELOAD_SEC = 0.1;

/** Shared shake phase lengths (frames) — +30% vs original base. */
export const SHAKE_EXIT_FRAMES = 12;
export const FLASH_FRAMES = 6;
export const SHAKE_ENTER_FRAMES = 16;

export const SHAKE_AMPLITUDE_PCT = 3.75;

/** whipPan pan phase lengths (frames). */
export const WHIP_EXIT_FRAMES = 10;
export const WHIP_ENTER_FRAMES = 10;
export const WHIP_DISTANCE_PCT = 110;
export const WHIP_BLUR_MAX_PX = 22;
export const WHIP_SCALE_END = 1.05;
export const SHAKE_CYCLES = 2.5;
export const TELEPORT_ZOOM_PUNCH = 1.08;
export const WHITE_FLASH_MAX = 0.9;

export const getMirrorPreloadFrames = (fps: number): number =>
  Math.max(1, Math.round(MIRROR_PRELOAD_SEC * fps));

const easeIn = Easing.in(Easing.cubic);
const easeOut = Easing.out(Easing.cubic);
const easeInOut = Easing.inOut(Easing.cubic);

const endsAtCut = (type: SlideTransitionType): boolean =>
  type === "teleportShake" || type === "whipPan";

export const resolveSlideTransition = (
  slide: { transition?: SlideTransitionType },
  index: number,
): SlideTransitionType =>
  slide.transition ?? DEFAULT_TRANSITION_ROTATION[index % DEFAULT_TRANSITION_ROTATION.length];

export const getSlowZoomOutFrames = (fps: number): number =>
  Math.max(1, Math.round(SLOW_ZOOM_OUT_SEC * fps));

export const getExitZoomOutFrames = (fps: number): number =>
  getSlowZoomOutFrames(fps) + SHARP_ZOOM_OUT_FRAMES;

export const getTransitionDuration = (type: SlideTransitionType = DEFAULT_TRANSITION): number => {
  if (type === "teleportShake") {
    return SHAKE_EXIT_FRAMES + FLASH_FRAMES + SHAKE_ENTER_FRAMES;
  }
  if (type === "whipPan") {
    return SHAKE_EXIT_FRAMES + WHIP_EXIT_FRAMES + WHIP_ENTER_FRAMES + SHAKE_ENTER_FRAMES;
  }
  return SHARP_ZOOM_OUT_FRAMES + FAST_ZOOM_IN_FRAMES;
};

export const buildCutTransitionTypes = (
  slides: { transition?: SlideTransitionType }[],
): SlideTransitionType[] =>
  slides.slice(0, -1).map((slide, index) => resolveSlideTransition(slide, index));

type TransitionTransform = {
  scale: number;
  translateXPercent: number;
  translateYPercent: number;
  opacity: number;
  blurPx: number;
  useMirror: boolean;
};

const identityTransition: TransitionTransform = {
  scale: 1,
  translateXPercent: 0,
  translateYPercent: 0,
  opacity: 1,
  blurPx: 0,
  useMirror: false,
};

// ─────────────────────────────────────────────────────────────────────────────
// BLUR HELPERS
// ─────────────────────────────────────────────────────────────────────────────

export const getZoomBlurForScale = (scale: number): number =>
  interpolate(
    scale,
    [SHARP_ZOOM_OUT_END, ZOOM_BLUR_START_SCALE],
    [ZOOM_BLUR_MAX_PX, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

const getPullInBlurForScale = (scale: number): number =>
  interpolate(scale, [1, PULL_IN_SCALE_MAX], [0, ZOOM_BLUR_MAX_PX], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

// ─────────────────────────────────────────────────────────────────────────────
// zoomBlur TRANSFORMS
// ─────────────────────────────────────────────────────────────────────────────

export const getUnifiedZoomOutTransform = (
  progress: number,
  startScale: number,
): TransitionTransform => {
  const t = easeIn(interpolate(progress, [0, 1], [0, 1], { extrapolateRight: "clamp" }));
  const scale = interpolate(t, [0, 1], [startScale, SHARP_ZOOM_OUT_END]);
  return {
    scale,
    translateXPercent: 0,
    translateYPercent: 0,
    opacity: 1,
    blurPx: getZoomBlurForScale(scale),
    useMirror: true,
  };
};

export const getFastZoomInTransform = (progress: number): TransitionTransform => {
  const clamped = Math.max(0, Math.min(1, progress));
  const t = easeOut(interpolate(clamped, [0, 1], [0, 1]));
  const scale = interpolate(t, [0, 1], [SHARP_ZOOM_OUT_END, 1]);
  return {
    scale,
    translateXPercent: 0,
    translateYPercent: 0,
    opacity: 1,
    blurPx: getZoomBlurForScale(scale),
    useMirror: true,
  };
};

// ─────────────────────────────────────────────────────────────────────────────
// pullIn TRANSFORMS
// ─────────────────────────────────────────────────────────────────────────────

export const getPullInExitTransform = (
  progress: number,
  startScale: number,
): TransitionTransform => {
  const t = easeIn(Math.max(0, Math.min(1, progress)));
  const scale = interpolate(t, [0, 1], [startScale, PULL_IN_SCALE_MAX]);
  return {
    scale,
    translateXPercent: 0,
    translateYPercent: 0,
    opacity: 1,
    blurPx: getPullInBlurForScale(scale),
    useMirror: false,
  };
};

export const getPullInEnterTransform = (progress: number): TransitionTransform => {
  const t = easeOut(Math.max(0, Math.min(1, progress)));
  const scale = interpolate(t, [0, 1], [PULL_IN_SCALE_MAX, 1]);
  return {
    scale,
    translateXPercent: 0,
    translateYPercent: 0,
    opacity: 1,
    blurPx: getPullInBlurForScale(scale),
    useMirror: false,
  };
};

// ─────────────────────────────────────────────────────────────────────────────
// teleportShake TRANSFORMS
// ─────────────────────────────────────────────────────────────────────────────

export const getShakeOffsetAtExitEnd = (
  amplitude: number = SHAKE_AMPLITUDE_PCT,
): { translateXPercent: number; translateYPercent: number } => {
  const angle = SHAKE_CYCLES * 2 * Math.PI;
  return {
    translateXPercent: amplitude * Math.cos(angle),
    translateYPercent: amplitude * Math.sin(angle),
  };
};

export const getShakeOffset = (
  progress: number,
  amplitude: number,
  phase: "exit" | "enter",
  exitEnd?: { translateXPercent: number; translateYPercent: number },
): { translateXPercent: number; translateYPercent: number } => {
  const p = Math.max(0, Math.min(1, progress));
  if (phase === "exit") {
    const envelope = easeIn(p);
    const angle = p * SHAKE_CYCLES * 2 * Math.PI;
    return {
      translateXPercent: amplitude * envelope * Math.cos(angle),
      translateYPercent: amplitude * envelope * Math.sin(angle),
    };
  }
  const end = exitEnd ?? getShakeOffsetAtExitEnd(amplitude);
  const decay = 1 - easeOut(p);
  const wobble = Math.sin((1 - p) * SHAKE_CYCLES * 2 * Math.PI) * 0.25;
  return {
    translateXPercent: end.translateXPercent * decay * (1 + wobble),
    translateYPercent: end.translateYPercent * decay * (1 + wobble),
  };
};

export const getTeleportShakeExitTransform = (
  progress: number,
  startScale: number,
): TransitionTransform => {
  const p = Math.max(0, Math.min(1, progress));
  const shake = getShakeOffset(p, SHAKE_AMPLITUDE_PCT, "exit");
  const scale = interpolate(easeIn(p), [0, 1], [startScale, TELEPORT_ZOOM_PUNCH]);
  return {
    scale,
    ...shake,
    opacity: 1,
    blurPx: 0,
    useMirror: false,
  };
};

export const getTeleportShakeEnterTransform = (
  progress: number,
  exitEndShake = getShakeOffsetAtExitEnd(),
): TransitionTransform => {
  const p = Math.max(0, Math.min(1, progress));
  const shake = getShakeOffset(p, SHAKE_AMPLITUDE_PCT, "enter", exitEndShake);
  const scale = interpolate(easeOut(p), [0, 1], [TELEPORT_ZOOM_PUNCH, 1]);
  return {
    scale,
    ...shake,
    opacity: 1,
    blurPx: 0,
    useMirror: false,
  };
};

export const getWhiteFlashOpacity = (
  frame: number,
  cutFrame: number,
  flashFrames: number = FLASH_FRAMES,
): number => {
  const half = flashFrames / 2;
  const dist = Math.abs(frame - cutFrame);
  if (dist >= half) return 0;
  return interpolate(dist, [0, half], [WHITE_FLASH_MAX, 0], {
    extrapolateRight: "clamp",
  });
};

// ─────────────────────────────────────────────────────────────────────────────
// whipPan TRANSFORMS
// ─────────────────────────────────────────────────────────────────────────────

export const getWhipDirection = (cutIndex: number): 1 | -1 =>
  cutIndex % 2 === 0 ? 1 : -1;

export const getWhipPanBlurForProgress = (progress: number): number => {
  const p = Math.max(0, Math.min(1, progress));
  return interpolate(Math.sin(p * Math.PI), [0, 1], [0, WHIP_BLUR_MAX_PX], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
};

export const getWhipPanShakeExitTransform = (
  progress: number,
  startScale: number,
): TransitionTransform => {
  const shake = getShakeOffset(progress, SHAKE_AMPLITUDE_PCT, "exit");
  return {
    scale: startScale,
    ...shake,
    opacity: 1,
    blurPx: 0,
    useMirror: false,
  };
};

export const getWhipPanShakeEnterTransform = (
  progress: number,
  exitEndShake = getShakeOffsetAtExitEnd(),
): TransitionTransform => {
  const shake = getShakeOffset(progress, SHAKE_AMPLITUDE_PCT, "enter", exitEndShake);
  return {
    scale: 1,
    ...shake,
    opacity: 1,
    blurPx: 0,
    useMirror: false,
  };
};

export const getWhipPanOutTransform = (
  progress: number,
  startScale: number,
  direction: 1 | -1,
): TransitionTransform => {
  const p = Math.max(0, Math.min(1, progress));
  const t = easeInOut(p);
  const translateX = interpolate(t, [0, 1], [0, -direction * WHIP_DISTANCE_PCT]);
  const scale = interpolate(t, [0, 1], [startScale, WHIP_SCALE_END]);
  return {
    scale,
    translateXPercent: translateX,
    translateYPercent: 0,
    opacity: 1,
    blurPx: getWhipPanBlurForProgress(p),
    useMirror: false,
  };
};

export const getWhipPanInTransform = (
  progress: number,
  direction: 1 | -1,
): TransitionTransform => {
  const p = Math.max(0, Math.min(1, progress));
  const t = easeInOut(p);
  const translateX = interpolate(t, [0, 1], [direction * WHIP_DISTANCE_PCT, 0]);
  const scale = interpolate(t, [0, 1], [WHIP_SCALE_END, 1]);
  return {
    scale,
    translateXPercent: translateX,
    translateYPercent: 0,
    opacity: 1,
    blurPx: getWhipPanBlurForProgress(1 - p),
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
  translateYPercent: number;
  blurPx: number;
  useMirror: boolean;
}> = ({ src, scale, translateXPercent, translateYPercent, blurPx, useMirror }) => {
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
    transform: `scale(${scale}) translate(${translateXPercent}%, ${translateYPercent}%)`,
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
  translateYPercent: number;
  blurPx: number;
  useMirror: boolean;
  whiteFlash: number;
};

const computeWhiteFlashAtFrame = (frame: number, slides: SlideSegment[]): number => {
  let maxFlash = 0;
  for (let i = 0; i < slides.length - 1; i++) {
    const exitType = resolveSlideTransition(slides[i], i);
    if (exitType !== "teleportShake") continue;
    maxFlash = Math.max(maxFlash, getWhiteFlashOpacity(frame, slides[i].endFrame));
  }
  return maxFlash;
};

const computeSlideStyle = (
  frame: number,
  slide: SlideSegment,
  slides: SlideSegment[],
  fps: number,
): SlideRenderStyle | null => {
  const { index, endFrame } = slide;
  const hasExit = index < slides.length - 1;
  const hasEnter = index > 0;
  const cutFrame = endFrame;

  const exitType = hasExit ? resolveSlideTransition(slide, index) : null;
  const enterType = hasEnter ? resolveSlideTransition(slides[index - 1], index - 1) : null;

  const slowFrames = getSlowZoomOutFrames(fps);
  const mirrorPreloadFrames = getMirrorPreloadFrames(fps);
  const exitEndShake = getShakeOffsetAtExitEnd();

  let enterStart = slide.startFrame;
  let enterEnd = slide.startFrame;
  let enterWhipEnd = slide.startFrame;
  let exitStart = cutFrame;
  let exitEnd = cutFrame;
  let exitWhipStart = cutFrame;
  let holdStart = slide.startFrame;
  let holdEnd = cutFrame;

  if (hasEnter && enterType) {
    if (enterType === "teleportShake") {
      enterStart = slide.startFrame;
      enterEnd = slide.startFrame + SHAKE_ENTER_FRAMES;
      holdStart = enterEnd;
    } else if (enterType === "whipPan") {
      enterStart = slide.startFrame;
      enterWhipEnd = slide.startFrame + WHIP_ENTER_FRAMES;
      enterEnd = enterWhipEnd + SHAKE_ENTER_FRAMES;
      holdStart = enterEnd;
    } else {
      enterStart = slide.startFrame + SHARP_ZOOM_OUT_FRAMES;
      enterEnd = slide.startFrame + SHARP_ZOOM_OUT_FRAMES + FAST_ZOOM_IN_FRAMES;
      holdStart = enterEnd;
    }
  }

  if (hasExit && exitType) {
    if (exitType === "teleportShake") {
      exitStart = cutFrame - SHAKE_EXIT_FRAMES;
      exitEnd = cutFrame;
      holdEnd = exitStart;
    } else if (exitType === "whipPan") {
      exitWhipStart = cutFrame - WHIP_EXIT_FRAMES;
      exitStart = exitWhipStart - SHAKE_EXIT_FRAMES;
      exitEnd = cutFrame;
      holdEnd = exitStart;
    } else if (exitType === "zoomBlur") {
      exitStart = Math.max(holdStart, cutFrame - slowFrames);
      exitEnd = cutFrame + SHARP_ZOOM_OUT_FRAMES;
      holdEnd = exitStart;
    } else {
      exitStart = Math.max(holdStart, cutFrame - SHARP_ZOOM_OUT_FRAMES);
      exitEnd = cutFrame + SHARP_ZOOM_OUT_FRAMES;
      holdEnd = exitStart;
    }
  } else if (!hasExit) {
    holdEnd = endFrame;
  }

  const showStart = hasEnter ? enterStart : slide.startFrame;
  let showEnd = hasExit ? exitEnd : endFrame;
  if (hasExit && exitType && endsAtCut(exitType)) {
    showEnd = cutFrame;
  }

  if (frame < showStart || frame >= showEnd) {
    return null;
  }

  let transition = identityTransition;
  let inTransition = false;
  const holdDuration = Math.max(1, holdEnd - holdStart);

  if (hasEnter && enterType && frame < enterEnd) {
    if (enterType === "whipPan" && frame < enterWhipEnd) {
      const progress = (frame - enterStart) / Math.max(1, enterWhipEnd - enterStart);
      const cutIndex = index - 1;
      transition = getWhipPanInTransform(progress, getWhipDirection(cutIndex));
    } else if (enterType === "whipPan") {
      const progress = (frame - enterWhipEnd) / Math.max(1, enterEnd - enterWhipEnd);
      transition = getWhipPanShakeEnterTransform(progress, exitEndShake);
    } else {
      const progress = (frame - enterStart) / Math.max(1, enterEnd - enterStart);
      switch (enterType) {
        case "pullIn":
          transition = getPullInEnterTransform(progress);
          break;
        case "teleportShake":
          transition = getTeleportShakeEnterTransform(progress, exitEndShake);
          break;
        case "zoomBlur":
          transition = getFastZoomInTransform(progress);
          break;
      }
    }
    inTransition = true;
  } else if (hasExit && exitType && frame >= exitStart && frame < exitEnd) {
    if (exitType === "whipPan" && frame < exitWhipStart) {
      const progress = (frame - exitStart) / Math.max(1, exitWhipStart - exitStart);
      const whipStartScale = getKenBurnsScale(
        Math.max(0, exitWhipStart - holdStart),
        holdDuration,
      );
      transition = getWhipPanShakeExitTransform(progress, whipStartScale);
    } else if (exitType === "whipPan") {
      const progress = (frame - exitWhipStart) / Math.max(1, exitEnd - exitWhipStart);
      const whipStartScale = getKenBurnsScale(
        Math.max(0, exitWhipStart - holdStart),
        holdDuration,
      );
      transition = getWhipPanOutTransform(progress, whipStartScale, getWhipDirection(index));
    } else {
      const progress = (frame - exitStart) / Math.max(1, exitEnd - exitStart);
      const startScale = getKenBurnsScale(
        Math.max(0, exitStart - holdStart),
        holdDuration,
      );
      switch (exitType) {
        case "pullIn":
          transition = getPullInExitTransform(progress, startScale);
          break;
        case "teleportShake":
          transition = getTeleportShakeExitTransform(progress, startScale);
          break;
        case "zoomBlur":
          transition = getUnifiedZoomOutTransform(progress, startScale);
          break;
      }
    }
    inTransition = true;
  } else if (frame >= holdStart && frame < holdEnd) {
    const holdFrame = frame - holdStart;
    transition = {
      ...identityTransition,
      scale: getKenBurnsScale(holdFrame, holdDuration),
    };
  }

  const mirrorActiveFrom =
    hasExit && exitType === "zoomBlur" ? exitStart - mirrorPreloadFrames : cutFrame;

  const useMirror =
    transition.useMirror ||
    (hasExit && exitType === "zoomBlur" && frame >= mirrorActiveFrom && frame < exitEnd);

  const zIndex =
    inTransition && hasEnter && frame >= enterStart ? index + 10 : index;

  const whiteFlash =
    exitType === "teleportShake" && frame >= exitStart && frame <= exitEnd + FLASH_FRAMES / 2
      ? getWhiteFlashOpacity(frame, cutFrame)
      : enterType === "teleportShake" && frame >= cutFrame - FLASH_FRAMES / 2 && frame < enterEnd
        ? getWhiteFlashOpacity(frame, cutFrame)
        : 0;

  return {
    opacity: transition.opacity,
    zIndex,
    scale: transition.scale,
    translateXPercent: transition.translateXPercent,
    translateYPercent: transition.translateYPercent,
    blurPx: transition.blurPx,
    useMirror,
    whiteFlash,
  };
};

/**
 * SlideshowBackground — Ken Burns holds + per-cut CapCut-style transitions.
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

  const globalWhiteFlash = computeWhiteFlashAtFrame(frame, slides);

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
              translateYPercent={style.translateYPercent}
              blurPx={style.blurPx}
              useMirror={style.useMirror}
            />
          </AbsoluteFill>
        );
      })}
      {globalWhiteFlash > 0 ? (
        <AbsoluteFill
          style={{
            zIndex: 90,
            backgroundColor: "#ffffff",
            opacity: globalWhiteFlash,
            pointerEvents: "none",
          }}
        />
      ) : null}
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
