import React from "react";
import { Composition } from "remotion";
import { ShortVideo } from "./ShortVideo";
import { defaultShortVideoProps, type ShortVideoProps } from "./types";

const calculateMetadata = async ({ props }: { props: ShortVideoProps }) => {
  const fps = props.fps || 30;
  const durationMs = Math.max(props.durationMs, 1000);
  return {
    durationInFrames: Math.max(1, Math.ceil((durationMs / 1000) * fps)),
    fps,
    width: props.width,
    height: props.height,
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ShortVideo"
      component={ShortVideo}
      durationInFrames={90}
      fps={defaultShortVideoProps.fps}
      width={defaultShortVideoProps.width}
      height={defaultShortVideoProps.height}
      defaultProps={defaultShortVideoProps}
      calculateMetadata={calculateMetadata}
    />
  );
};
