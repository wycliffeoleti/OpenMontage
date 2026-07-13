export interface ResponsiveSceneLayout {
  isPortrait: boolean;
  contentWidth: string;
  heroTitleFontSize: number;
  heroSubtitleFontSize: number;
  calloutFontSize: number;
  calloutTitleFontSize: number;
  scenePadding: number;
  terminalFontSize: number;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export function getResponsiveSceneLayout(
  width: number,
  height: number,
): ResponsiveSceneLayout {
  const isPortrait = height > width;
  return {
    isPortrait,
    contentWidth: isPortrait ? "84%" : "72%",
    heroTitleFontSize: Math.round(clamp(width * 0.075, 54, 96)),
    heroSubtitleFontSize: Math.round(clamp(width * 0.028, 24, 40)),
    calloutFontSize: Math.round(clamp(width / 30, 28, 42)),
    calloutTitleFontSize: Math.round(clamp(width / 25, 34, 50)),
    scenePadding: Math.round(clamp(width * 0.05, 40, 80)),
    terminalFontSize: Math.round(clamp(width / 36, 22, 32)),
  };
}
