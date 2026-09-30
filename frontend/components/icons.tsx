"use client";

import { motion, useReducedMotion } from "motion/react";
import type { CSSProperties, SVGProps } from "react";
import { BRAND_BARS, BRAND_BASELINE, BRAND_SIZE, BRAND_SQUARE } from "@/lib/brand";

/** Small inline SVG set. Decorative by default (aria-hidden); fills/strokes follow currentColor. */
type IconProps = Omit<SVGProps<SVGSVGElement>, "children"> & { size?: number };

function Svg({ size = 16, viewBox = "0 0 16 16", ...rest }: IconProps & { viewBox?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
      focusable="false"
      {...rest}
    />
  );
}

type BrandMarkProps = IconProps & {
  /** Header only: bars rise on mount (and on each `replayKey` change). Footer leaves this off. */
  animated?: boolean;
  /** Soft wave loop while true (a candidate is processing). */
  busy?: boolean;
  /** Bump to replay the rise once (hover/focus on the brand). */
  replayKey?: number;
};

/** Own brand mark: an ink square with ascending stepped bars (the gap) on a ledger baseline.
 *  Geometry comes from lib/brand.ts. Motion is CSS (see .brand-mark--* in globals.css) and is
 *  dropped for reduced motion both here and by the global prefers-reduced-motion rule. */
export function BrandMark({ size = 28, animated = false, busy = false, replayKey = 0, className, ...rest }: BrandMarkProps) {
  const reduce = useReducedMotion();
  const mode = !animated || reduce ? "" : busy ? " brand-mark--busy" : " brand-mark--rise";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${BRAND_SIZE} ${BRAND_SIZE}`} aria-hidden="true" focusable="false"
      className={`${className ?? ""}${mode}`.trim() || undefined} {...rest}>
      <rect {...BRAND_SQUARE} fill="currentColor" />
      <g key={busy ? "busy" : replayKey} style={{ fill: "var(--paper)" }}>
        {BRAND_BARS.map((b, i) => (
          <rect key={i} className="brand-bar" style={{ "--i": i } as CSSProperties} {...b} />
        ))}
        <rect {...BRAND_BASELINE} />
      </g>
    </svg>
  );
}

export function ArrowDownIcon(props: IconProps) {
  return <Svg {...props}><path d="M8 2v11M3.5 8.5 8 13l4.5-4.5" /></Svg>;
}

export function ArrowUpRightIcon(props: IconProps) {
  return <Svg {...props}><path d="M4 12 12 4M5.5 4H12v6.5" /></Svg>;
}

export function KeyIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="5" cy="11" r="2.75" />
      <path d="M7 9 13.5 2.5M11 5l1.75 1.75" />
    </Svg>
  );
}

export function CloseIcon(props: IconProps) {
  return <Svg {...props}><path d="M3 3l10 10M13 3 3 13" /></Svg>;
}

export function UploadIcon(props: IconProps) {
  return <Svg {...props}><path d="M8 11V2.5M4.5 6 8 2.5 11.5 6M2.5 13.5h11" /></Svg>;
}

const CHECK_PATH = "M3 8.5 6.5 12 13 4.5";

/** Check mark. With `draw`, the stroke is drawn in with pathLength (instant under reduced motion). */
export function CheckIcon({ draw = false, ...props }: IconProps & { draw?: boolean }) {
  const reduce = useReducedMotion();
  return (
    <Svg {...props}>
      {draw ? (
        <motion.path
          d={CHECK_PATH}
          initial={reduce ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.35, ease: "easeOut", delay: 0.1 }}
        />
      ) : (
        <path d={CHECK_PATH} />
      )}
    </Svg>
  );
}
