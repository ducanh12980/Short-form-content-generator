import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, staticFile, useVideoConfig } from "remotion";

type AmbientOverlayProps = {
  src: string;
  /** Source clip length in milliseconds; defaults to 10s if omitted. */
  loopDurationMs?: number;
  /** Playback speed (1 = normal, 0.5 = half speed). */
  playbackRate?: number;
};

const msToFrames = (ms: number, fps: number): number =>
  Math.max(1, Math.round((ms / 1000) * fps));

export const AmbientOverlay: React.FC<AmbientOverlayProps> = ({
  src,
  loopDurationMs = 10_000,
  playbackRate = 1,
}) => {
  const { fps } = useVideoConfig();
  const rate = playbackRate > 0 ? playbackRate : 1;
  const loopMs = loopDurationMs / rate;
  return (
    <Loop durationInFrames={msToFrames(loopMs, fps)}>
      <AbsoluteFill>
        <OffthreadVideo
          src={staticFile(src)}
          playbackRate={rate}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
          muted
        />
      </AbsoluteFill>
    </Loop>
  );
};
