export type Severity = "high" | "medium" | "low";

export interface Skill { id: string; name: string; track: string; level: number; evidence: string }
export interface OtherSkill { name: string; level: number; evidence: string }
export interface Gap {
  skill: string; name: string; track: string;
  expected: number; current: number; severity: Severity;
}
export interface Recommendation {
  course_id: string; title: string; covers: string[]; hours: number; link: string;
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
}
export interface Track { id: string; name: string }
