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
    exam_codes: list[str] = []  # só quando o catálogo os informa
    source: str | None = None  # ex.: "Microsoft Learn Catalog API"; None = lista manual/antigo
    synced_at: str | None = None  # data ISO da sincronização
    match_origin: str | None = None  # "rule" (regra) | "manual"; None = resultados antigos


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


class Supplementary(BaseModel):
    """Link de documentação achado pela busca da Microsoft Learn. Não é curso e não tem nível."""
    skill: str
    title: str
    url: str


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
    supplementary: list[Supplementary] | None = None  # None = não consultado / resultados antigos
    learn_status: str | None = None  # ok | none | unavailable | disabled; None = antigo
