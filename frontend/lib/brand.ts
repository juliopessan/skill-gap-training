/**
 * Single source of truth for the brand glyph: an ink square with three ascending paper bars on a
 * ledger baseline. Consumed by components/icons.tsx, app/icon.svg (guarded by brand.check.mjs) and
 * scripts/make-favicon.py (which regex-parses the literals below: keep the `{ x: N, y: N, width: N,
 * height: N }` shape and the `ink:`/`paper:` hex strings). Colours are ink/paper tokens only.
 */
export interface Rect { x: number; y: number; width: number; height: number }

export const BRAND_SIZE = 28;

export const BRAND_SQUARE: Rect = { x: 0, y: 0, width: 28, height: 28 };

/** Ascending bars, left to right. All share the bottom edge BRAND_BAR_BOTTOM. */
export const BRAND_BARS: readonly Rect[] = [
  { x: 6, y: 15, width: 4, height: 6 },
  { x: 12, y: 11, width: 4, height: 10 },
  { x: 18, y: 7, width: 4, height: 14 },
];

export const BRAND_BASELINE: Rect = { x: 6, y: 22.5, width: 16, height: 1 };

/** y of the line the bars stand on (their common bottom edge). */
export const BRAND_BAR_BOTTOM = 21;

/** Paper/ink tokens copied from app/globals.css (light, and dark where they invert). */
export const BRAND_COLORS = {
  light: { ink: "#11110f", paper: "#f2efe8" },
  dark: { ink: "#f0ede5", paper: "#12120e" },
} as const;

/** Bar heights (in viewBox units) for the 4 tab-icon frames. Step 3 = every bar full height. */
export const FAVICON_HEIGHTS: readonly (readonly [number, number, number])[] = [
  [6, 10, 14],
  [10, 14, 10],
  [14, 10, 6],
  [14, 14, 14],
];
export const FAVICON_STEPS = FAVICON_HEIGHTS.length;
/** The static "busy" frame used when motion is reduced. */
export const FAVICON_BUSY_STATIC_STEP = 3;

const num = (n: number) => String(n);
const rect = (r: Rect, fill: string) =>
  `<rect x="${num(r.x)}" y="${num(r.y)}" width="${num(r.width)}" height="${num(r.height)}" fill="${fill}"/>`;

/** Standalone SVG for one tab-icon frame (explicit colours, no media query). Pure. */
export function faviconFrame(step: number, dark: boolean): string {
  const heights = FAVICON_HEIGHTS[((Math.trunc(step) % FAVICON_STEPS) + FAVICON_STEPS) % FAVICON_STEPS];
  const { ink, paper } = dark ? BRAND_COLORS.dark : BRAND_COLORS.light;
  const bars = BRAND_BARS.map((b, i) =>
    rect({ ...b, y: BRAND_BAR_BOTTOM - heights[i], height: heights[i] }, paper));
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${BRAND_SIZE} ${BRAND_SIZE}">` +
    [rect(BRAND_SQUARE, ink), ...bars, rect(BRAND_BASELINE, paper)].join("") + `</svg>`;
}

/** `data:` URL for a frame; the SVG is percent-encoded so it is safe inside href. */
export function faviconFrameUrl(step: number, dark: boolean): string {
  return `data:image/svg+xml,${encodeURIComponent(faviconFrame(step, dark))}`;
}
