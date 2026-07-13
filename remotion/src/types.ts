export type KaraokeWord = {
  text: string;
  start_ms: number;
  end_ms: number;
};

export type CaptionToken = {
  text: string;
  style: "primary" | "highlight";
  animation: "none" | "pop";
  start_ms: number;
  end_ms: number;
  /** Present in karaoke sentence mode — drives per-word highlight inside the sentence. */
  words?: KaraokeWord[];
};

export type ThemeStyle = {
  primary_text_color: string;
  highlight_color: string;
  font: string;
  font_size: number;
  stroke_color: string;
  stroke_width: number;
  position: string;
};

export type ThemeStyles = Record<string, ThemeStyle>;

/** Outgoing transition at the cut to the next slide. */
export type SlideTransitionType = "pullIn" | "teleportShake" | "whipPan" | "zoomBlur";

export type TimelineImage = {
  /** Path relative to Remotion --public-dir (for staticFile). */
  src: string;
  start_ms: number;
  end_ms: number;
  source?: string;
  media_type?: string;
  /** Outgoing transition to the next slide (cut after this image). */
  transition?: SlideTransitionType;
};

/** TikTok / Reels / Shorts — always portrait 9:16 (width < height). */
export const CANVAS_WIDTH = 1080;
export const CANVAS_HEIGHT = 1920;

/** Normalize props so landscape dimensions cannot slip through. */
export const normalizeCanvasSize = (
  width?: number,
  height?: number,
): { width: number; height: number } => {
  const w = width ?? CANVAS_WIDTH;
  const h = height ?? CANVAS_HEIGHT;
  if (w > h) {
    return { width: h, height: w };
  }
  return { width: w, height: h };
};

export type ShortVideoProps = {
  width: number;
  height: number;
  fps: number;
  durationMs: number;
  themeName: string;
  fontOverride: string | null;
  themes: ThemeStyles;
  tokens: CaptionToken[];
  /** Narration file relative to Remotion --public-dir (for staticFile). */
  narrationSrc: string;
  /** Volume for narration (1.0 = unchanged). Defaults to 1.2. */
  narrationVolume?: number;
  images: TimelineImage[];
  backgroundColor: string;
  /** Optional background music file relative to Remotion --public-dir. */
  musicSrc?: string;
  /** Volume for background music (0–1). Defaults to 0.35. */
  musicVolume?: number;
  /** Ambient overlay video relative to Remotion --public-dir. */
  ambientOverlaySrc?: string | null;
  ambientOpacity?: number;
  ambientBlendMode?: string;
  /** Loop length for ambient overlay in milliseconds. */
  ambientLoopDurationMs?: number;
  /** Ambient overlay playback speed (1 = normal). */
  ambientPlaybackRate?: number;
};

export const defaultShortVideoProps: ShortVideoProps = {
  width: CANVAS_WIDTH,
  height: CANVAS_HEIGHT,
  fps: 30,
  durationMs: 3000,
  themeName: "minimalist",
  fontOverride: null,
  themes: {
    minimalist: {
      primary_text_color: "#FFFFFF",
      highlight_color: "#FFFF00",
      font: "Arial, sans-serif",
      font_size: 52,
      stroke_color: "#000000",
      stroke_width: 2,
      position: "lower",
    },
  },
  tokens: [],
  narrationSrc: "",
  images: [],
  backgroundColor: "#000000",
};
