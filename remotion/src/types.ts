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

export type TimelineImage = {
  /** Path relative to Remotion --public-dir (for staticFile). */
  src: string;
  start_ms: number;
  end_ms: number;
  source?: string;
  media_type?: string;
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
  images: TimelineImage[];
  backgroundColor: string;
  /** Optional background music file relative to Remotion --public-dir. */
  musicSrc?: string;
  /** Volume for background music (0–1). Defaults to 0.3. */
  musicVolume?: number;
};

export const defaultShortVideoProps: ShortVideoProps = {
  width: 1080,
  height: 1920,
  fps: 30,
  durationMs: 3000,
  themeName: "minimalist",
  fontOverride: null,
  themes: {
    minimalist: {
      primary_text_color: "#FFFFFF",
      highlight_color: "#FFFF00",
      font: "Arial, sans-serif",
      font_size: 72,
      stroke_color: "#000000",
      stroke_width: 2,
      position: "center",
    },
  },
  tokens: [],
  narrationSrc: "",
  images: [],
  backgroundColor: "#000000",
};
