from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]
Status = Literal["processing", "done", "error"]


class RawSkill(BaseModel):
    name: str
    level: int = Field(ge=1, le=3)
    evidence: str


class ExtractedProfile(BaseModel):
    candidate: str
    skills: list[RawSkill]


class Skill(BaseModel):
    id: str
    name: str
    track: str
    level: int
    evidence: str
    evidence_verified: bool | None = None  # None = not checked (old records)


class OtherSkill(BaseModel):
    name: str
    level: int
    evidence: str
    evidence_verified: bool | None = None  # None = not checked (old records)


class Gap(BaseModel):
    skill: str
    name: str
    track: str
    expected: int
    current: int
    severity: Severity


class Recommendation(BaseModel):
    course_id: str
    title: str
    covers: list[str]
    hours: int | None = None  # None = carga horária desconhecida
    link: str = ""  # "" = sem link
    provider: str | None = None  # None = não registrado (resultados antigos)
    kind: str | None = None
    verified: bool | None = None
    level: int | None = None  # nível do curso (1-3); None = resultados antigos
    platform: str | None = None


class TrackRating(BaseModel):
    track: str
    name: str
    adherence: float
    adherence_supported: float
    covered: int
    expected: int
    skills_rated: int
    mean_level: float | None = None
    level_label: str | None = None


class Rating(BaseModel):
    adherence: float
    adherence_supported: float
    covered: int
    expected: int
    mean_level: float | None = None
    level_label: str | None = None
    tracks: list[TrackRating] = []


class CandidateResult(BaseModel):
    id: str
    candidate: str = ""
    status: Status = "processing"
    stage: str = "queued"
    error: str | None = None
    error_message: str | None = None
    no_data_tracks: list[str] = []
    skills: list[Skill] = []
    other_skills: list[OtherSkill] = []
    gaps: list[Gap] = []
    recommendations: list[Recommendation] = []
    rating: Rating | None = None  # None = resultados antigos
