export type Severity = "high" | "medium" | "low";

export interface Skill { id: string; name: string; track: string; level: number; evidence: string;
  /** Computed by the backend: quote found in the CV text. null/absent = not checked. */
  evidence_verified?: boolean | null }
export interface OtherSkill { name: string; level: number; evidence: string;
  evidence_verified?: boolean | null }
export interface Gap {
  skill: string; name: string; track: string;
  expected: number; current: number; severity: Severity;
}
export interface Recommendation {
  course_id: string; title: string; covers: string[];
  /** null = the source list gives no course load. */
  hours: number | null;
  /** "" = no link known. */
  link: string;
  /** Older records lack the next three: missing/null means unknown. */
  provider?: string | null;
  kind?: string | null;
  /** false = the course comes from an unverified list (title, level, hours, link not checked). */
  verified?: boolean | null;
  /** 1 Básico, 2 Intermediário, 3 Avançado. Missing/null = unknown. */
  level?: number | null;
  /** A track id. Missing/null = unknown. */
  platform?: string | null;
  exam_codes?: string[] | null;
  source?: string | null;
  synced_at?: string | null;
  /** "rule" = item da Microsoft Learn ligado às skills por regra; "manual" = lista manual. */
  match_origin?: string | null;
}
/** A documentation link found by the Microsoft Learn search: not a course, no level. */
export interface SupplementaryItem { skill: string; title: string; url: string }
/** Computed by rule FROM LEVELS INFERRED BY THE MODEL: never a measurement. */
export interface TrackRating {
  track: string; name: string;
  adherence: number; adherence_supported: number;
  covered: number; expected: number; skills_rated: number;
  mean_level: number | null; level_label: string | null;
}
export interface Rating {
  adherence: number; adherence_supported: number;
  covered: number; expected: number;
  mean_level: number | null; level_label: string | null;
  tracks: TrackRating[];
}
export interface Candidate {
  id: string;
  candidate: string;
  status: "processing" | "done" | "error";
  stage: string;
  error: string | null;
  error_message: string | null;
  no_data_tracks: string[];
  skills: Skill[];
  other_skills: OtherSkill[];
  gaps: Gap[];
  recommendations: Recommendation[];
  /** Absent/null on old records: render nothing. */
  rating?: Rating | null;
  /** Absent/null on old records. */
  supplementary?: SupplementaryItem[] | null;
  learn_status?: string | null;
}
export interface Track { id: string; name: string }
