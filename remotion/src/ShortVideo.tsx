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
import { AmbientOverlay } from "./AmbientOverlay";
import { getPopScale, SlideshowBackground } from "./effects";

const msToFrames = (ms: number, fps: number): number =>
  Math.max(0, Math.round((ms / 1000) * fps));

const resolveTheme = (props: ShortVideoProps): ThemeStyle => {
  const fallback = props.themes.minimalist ?? Object.values(props.themes)[0];
  return props.themes[props.themeName] ?? fallback;
};

/** Portrait-safe caption band — lower half, above platform UI safe area. */
const resolveCaptionContainerStyle = (theme: ThemeStyle): React.CSSProperties => {
  const position = theme.position?.toLowerCase() ?? "lower";
  if (position === "center") {
    return { justifyContent: "center", alignItems: "center" };
  }
  return {
    justifyContent: "flex-end",
    alignItems: "center",
    paddingBottom: "22%",
    paddingLeft: "5%",
    paddingRight: "5%",
  };
};

/** Slight black edge — stroke plus 1px halo for readability on busy slides. */
const captionOutlineStyle = (theme: ThemeStyle): React.CSSProperties => {
  const stroke = theme.stroke_color ?? "#000000";
  const width = theme.stroke_width ?? 2;
  return {
    WebkitTextStroke: `${width}px ${stroke}`,
    paintOrder: "stroke fill",
    textShadow: [
      `1px 0 0 ${stroke}`,
      `-1px 0 0 ${stroke}`,
      `0 1px 0 ${stroke}`,
      `0 -1px 0 ${stroke}`,
    ].join(", "),
  };
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
    ...captionOutlineStyle(theme),
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
    <AbsoluteFill style={resolveCaptionContainerStyle(theme)}>
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
    <AbsoluteFill style={resolveCaptionContainerStyle(theme)}>
      <div
        style={{
          ...baseStyle,
          backgroundColor: "rgba(0, 0, 0, 0.25)",
          borderRadius: 10,
          padding: "10px 16px",
          maxWidth: "92%",
        }}
      >
        {words.map((w, i) => {
          const isActive = globalMs >= w.start_ms && globalMs < w.end_ms;
          const color = isActive ? theme.highlight_color : theme.primary_text_color;
          return (
            <span
              key={`${w.text}-${i}`}
              style={{
                color,
                ...captionOutlineStyle(theme),
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

export const ShortVideo: React.FC<ShortVideoProps> = (props) => {
  const { fps } = useVideoConfig();
  const theme = resolveTheme(props);

  return (
    <AbsoluteFill style={{ backgroundColor: props.backgroundColor }}>
      <SlideshowBackground images={props.images} fps={fps} />
      {props.ambientOverlaySrc ? (
        <AbsoluteFill
          style={{
            zIndex: 50,
            pointerEvents: "none",
            mixBlendMode: (props.ambientBlendMode ?? "screen") as React.CSSProperties["mixBlendMode"],
            opacity: props.ambientOpacity ?? 0.4,
          }}
        >
          <AmbientOverlay
            src={props.ambientOverlaySrc}
            loopDurationMs={props.ambientLoopDurationMs}
            playbackRate={props.ambientPlaybackRate}
          />
        </AbsoluteFill>
      ) : null}
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
            <AbsoluteFill style={{ zIndex: 100 }}>
              {token.words && token.words.length > 0 ? (
                <KaraokeLine token={token} theme={theme} fontOverride={props.fontOverride} />
              ) : (
                <CaptionWord token={token} theme={theme} fontOverride={props.fontOverride} />
              )}
            </AbsoluteFill>
          </Sequence>
        );
      })}
      {props.narrationSrc ? (
        <Audio src={staticFile(props.narrationSrc)} volume={props.narrationVolume ?? 1.2} />
      ) : null}
      {props.musicSrc ? (
        <Audio src={staticFile(props.musicSrc)} volume={props.musicVolume ?? 0.25} />
      ) : null}
    </AbsoluteFill>
  );
};
