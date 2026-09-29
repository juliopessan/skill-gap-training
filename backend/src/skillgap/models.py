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


class OtherSkill(BaseModel):
    name: str
    level: int
    evidence: str


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
    hours: int
    link: str


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
