import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { CaptionToken, KaraokeWord, ShortVideoProps, ThemeStyle } from "./types";
import { FadingImage, getPopScale } from "./effects";

const msToFrames = (ms: number, fps: number): number =>
  Math.max(0, Math.round((ms / 1000) * fps));

const resolveTheme = (props: ShortVideoProps): ThemeStyle => {
  const fallback = props.themes.minimalist ?? Object.values(props.themes)[0];
  return props.themes[props.themeName] ?? fallback;
};

const resolveTokenStyle = (
  token: CaptionToken,
  theme: ThemeStyle,
): React.CSSProperties => {
  const color =
    token.style === "highlight" ? theme.highlight_color : theme.primary_text_color;
  return {
    color,
    fontSize: theme.font_size,
    fontFamily: theme.font,
    fontWeight: 700,
    WebkitTextStroke: `${theme.stroke_width}px ${theme.stroke_color}`,
    paintOrder: "stroke fill",
    textAlign: "center",
    lineHeight: 1.2,
    padding: "0 5%",
  };
};

const CaptionWord: React.FC<{
  token: CaptionToken;
  theme: ThemeStyle;
  fontOverride: string | null;
}> = ({ token, theme, fontOverride }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const text = token.text.trim();
  if (!text) return null;

  const style = resolveTokenStyle(token, theme);
  if (fontOverride) style.fontFamily = fontOverride;

  const scale = token.animation === "pop" ? getPopScale(frame, fps) : 1;

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ ...style, transform: `scale(${scale})` }}>{text}</div>
    </AbsoluteFill>
  );
};

/**
 * True karaoke line — full sentence always visible, active word switches to
 * highlight color. frame is relative to the wrapping Sequence (starts at 0),
 * so globalMs = token.start_ms + (frame / fps) * 1000.
 */
const KaraokeLine: React.FC<{
  token: CaptionToken;
  theme: ThemeStyle;
  fontOverride: string | null;
}> = ({ token, theme, fontOverride }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const baseStyle: React.CSSProperties = {
    fontSize: theme.font_size,
    fontFamily: fontOverride ?? theme.font,
    fontWeight: 700,
    textAlign: "center",
    lineHeight: 1.4,
    padding: "0 5%",
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: "0.2em",
  };

  const globalMs = token.start_ms + (frame / fps) * 1000;
  const words: KaraokeWord[] = token.words ?? [];

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={baseStyle}>
        {words.map((w, i) => {
          const isActive = globalMs >= w.start_ms && globalMs < w.end_ms;
          const color = isActive ? theme.highlight_color : theme.primary_text_color;
          return (
            <span
              key={`${w.text}-${i}`}
              style={{
                color,
                WebkitTextStroke: `${theme.stroke_width}px ${theme.stroke_color}`,
                paintOrder: "stroke fill",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const BackgroundImages: React.FC<{
  images: ShortVideoProps["images"];
  fps: number;
}> = ({ images, fps }) => {
  if (images.length === 0) return null;

  return (
    <>
      {images.map((image, index) => {
        const start = msToFrames(image.start_ms, fps);
        const end = msToFrames(image.end_ms, fps);
        const duration = Math.max(1, end - start);
        return (
          <Sequence key={`${image.src}-${index}`} from={start} durationInFrames={duration}>
            <FadingImage src={image.src} />
          </Sequence>
        );
      })}
    </>
  );
};

export const ShortVideo: React.FC<ShortVideoProps> = (props) => {
  const { fps } = useVideoConfig();
  const theme = resolveTheme(props);

  return (
    <AbsoluteFill style={{ backgroundColor: props.backgroundColor }}>
      <BackgroundImages images={props.images} fps={fps} />
      {props.tokens.map((token, index) => {
        if (token.start_ms == null || token.end_ms == null) return null;
        const start = msToFrames(token.start_ms, fps);
        const end = msToFrames(token.end_ms, fps);
        const duration = Math.max(1, end - start);
        return (
          <Sequence
            key={`${token.text}-${index}-${token.start_ms}`}
            from={start}
            durationInFrames={duration}
          >
            {token.words ? (
              <KaraokeLine token={token} theme={theme} fontOverride={props.fontOverride} />
            ) : (
              <CaptionWord token={token} theme={theme} fontOverride={props.fontOverride} />
            )}
          </Sequence>
        );
      })}
      {props.narrationSrc ? <Audio src={staticFile(props.narrationSrc)} /> : null}
      {props.musicSrc ? (
        <Audio src={staticFile(props.musicSrc)} volume={props.musicVolume ?? 0.3} />
      ) : null}
    </AbsoluteFill>
  );
};
