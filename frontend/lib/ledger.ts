import type { Candidate } from "./types";

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
  hoursTotal: number;
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
    hoursTotal: Math.round(recs.reduce((sum, r) => sum + r.hours, 0) * 10) / 10,
    noDataTracks: [...(c.no_data_tracks ?? [])],
  };
}
