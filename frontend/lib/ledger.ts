import type { Candidate, Rating } from "./types";

export interface LedgerFigures {
  mapped: number;
  cited: number;
  checked: boolean;
  /** cited items whose evidence_verified is not a boolean (not checked) */
  unchecked: number;
  verified: number;
  unverifiedNames: string[];
  gapsHigh: number;
  gapsMedium: number;
  gapsLow: number;
  coursesTotal: number;
  /** Sum of the KNOWN course hours only. */
  hoursTotal: number;
  /** Recommendations whose hours are null/unknown. */
  hoursUnknown: number;
  /** Titles of recommended courses with verified === false, in API order. */
  unverifiedCourses: string[];
  noDataTracks: string[];
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Whole hours are padded ("08"); fractional hours keep one decimal ("12.5"). */
export function fmtHours(h: number): string {
  const r = Math.round(h * 10) / 10;
  return Number.isInteger(r) ? pad2(r) : r.toFixed(1);
}

/** Share of `part` in `whole` as a 0-100 percentage; 0 when whole is 0, capped at 100. */
export function barPercent(part: number, whole: number): number {
  return whole > 0 ? Math.min(100, (part / whole) * 100) : 0;
}

/** True when the recommendation carries a usable course load. */
export function hasHours(h: number | null | undefined): h is number {
  return typeof h === "number" && Number.isFinite(h);
}

/** Pure: every figure here is computed from the candidate record, never asserted. */
export function computeLedger(c: Candidate): LedgerFigures {
  const skills = c.skills ?? [];
  const others = c.other_skills ?? [];
  const gaps = c.gaps ?? [];
  const recs = c.recommendations ?? [];
  const all = [...skills, ...others];
  return {
    mapped: skills.length,
    cited: all.length,
    checked: all.some((s) => typeof s.evidence_verified === "boolean"),
    unchecked: all.filter((s) => typeof s.evidence_verified !== "boolean").length,
    verified: all.filter((s) => s.evidence_verified === true).length,
    unverifiedNames: Array.from(new Set(all.filter((s) => s.evidence_verified === false).map((s) => s.name))),
    gapsHigh: gaps.filter((g) => g.severity === "high").length,
    gapsMedium: gaps.filter((g) => g.severity === "medium").length,
    gapsLow: gaps.filter((g) => g.severity === "low").length,
    coursesTotal: recs.length,
    hoursTotal: Math.round(recs.reduce((sum, r) => sum + (hasHours(r.hours) ? r.hours : 0), 0) * 10) / 10,
    hoursUnknown: recs.filter((r) => !hasHours(r.hours)).length,
    unverifiedCourses: recs.filter((r) => r.verified === false).map((r) => r.title),
    noDataTracks: [...(c.no_data_tracks ?? [])],
  };
}

/** pt-BR percentage with a decimal comma and one decimal: 72.5 -> "72,5%". Non-finite -> "—". */
export function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const r = Math.round(value * 10) / 10;
  return `${r.toFixed(1).replace(".", ",")}%`;
}

export interface RatingTrackView {
  track: string;
  name: string;
  /** 0-100, clamped: drives the bar width. */
  percent: number;
  /** "Intermediário · 64%" (label omitted when unknown). */
  text: string;
}
export interface RatingView {
  adherence: number;
  /** Never above `adherence` when displayed: the supported figure is a lower bound. */
  supported: number;
  levelLabel: string | null;
  tracks: RatingTrackView[];
}

const clamp100 = (n: number) => (Number.isFinite(n) ? Math.min(100, Math.max(0, n)) : 0);

/** Pure view-model. null when the record has no rating (old records): nothing is rendered. */
export function ratingView(rating: Rating | null | undefined): RatingView | null {
  if (!rating || typeof rating.adherence !== "number" || !Number.isFinite(rating.adherence)) return null;
  const adherence = clamp100(rating.adherence);
  const supported = Math.min(adherence, clamp100(rating.adherence_supported));
  return {
    adherence,
    supported,
    levelLabel: rating.level_label || null,
    tracks: (rating.tracks ?? []).map((t) => {
      const percent = clamp100(t.adherence);
      const label = t.level_label ? `${t.level_label} · ` : "";
      return { track: t.track, name: t.name || t.track, percent, text: `${label}${Math.round(percent)}%` };
    }),
  };
}
