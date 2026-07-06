import React from "react";
import { Composition } from "remotion";
import { ShortVideo } from "./ShortVideo";
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  defaultShortVideoProps,
  normalizeCanvasSize,
  type ShortVideoProps,
} from "./types";

const calculateMetadata = async ({ props }: { props: ShortVideoProps }) => {
  const fps = props.fps || 30;
  const durationMs = Math.max(props.durationMs, 1000);
  const { width, height } = normalizeCanvasSize(props.width, props.height);
  return {
    durationInFrames: Math.max(1, Math.ceil((durationMs / 1000) * fps)),
    fps,
    width,
    height,
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ShortVideo"
      component={ShortVideo}
      durationInFrames={90}
      fps={defaultShortVideoProps.fps}
      width={CANVAS_WIDTH}
      height={CANVAS_HEIGHT}
      defaultProps={defaultShortVideoProps}
      calculateMetadata={calculateMetadata}
    />
  );
};
