import { CalculateMetadataFunction, Composition } from "remotion";

import { Explainer, ExplainerProps } from "../../../Explainer";
import {
  calculateStoryMetadata,
  ExplainerStory,
  ExplainerStoryProps,
} from "./ExplainerStory";
import { validateVerticalProps } from "./contracts";

const calculateVerticalMetadata: CalculateMetadataFunction<ExplainerProps> = async ({ props }) => {
  validateVerticalProps(props);
  const lastEnd = Math.max(...props.cuts.map((cut) => cut.out_seconds));
  return { durationInFrames: Math.ceil((lastEnd + 1) * 30) };
};

export const ContentCreatorCompositions: React.FC = () => (
  <>
    <Composition
      id="ExplainerVertical"
      component={Explainer}
      durationInFrames={30 * 20}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        theme: "flat-motion-graphics",
        cuts: [
          {
            id: "content-creator-default",
            type: "hero_title",
            source: "",
            text: "Content Creator",
            in_seconds: 0,
            out_seconds: 2,
          },
        ],
        overlays: [],
        captions: [],
        audio: {},
      }}
      calculateMetadata={calculateVerticalMetadata}
    />
    <Composition
      id="ExplainerStory"
      component={ExplainerStory}
      durationInFrames={60 * 20}
      fps={60}
      width={1080}
      height={1920}
      defaultProps={{
        beats: [
          {
            scene: {
              content: {
                type: "kinetic_text",
                lines: ["CONTENT", "CREATOR"],
                accentWords: "CREATOR",
              },
            },
            inSeconds: 0,
            outSeconds: 2,
          },
        ],
        captions: [],
        accentColor: "#22D3EE",
        presenterName: "Your AI host",
        outroSeconds: 0.8,
      } as ExplainerStoryProps}
      calculateMetadata={calculateStoryMetadata}
    />
  </>
);
