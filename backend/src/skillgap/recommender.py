import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from skillgap.models import Gap, Recommendation

WEIGHT = {"high": 3, "medium": 2, "low": 1}

REQUIRED_COLUMNS = ("id", "titulo", "skills_cobertas", "nivel")

_LEVEL_NAMES = {
    "fundamentals": 1, "basic": 1, "basico": 1,
    "intermediate": 2, "intermediario": 2,
    "advanced": 3, "avancado": 3,
}
_TRUE = {"1", "true", "sim"}
_FALSE = {"0", "false", "nao"}


@dataclass(frozen=True)
class Course:
    id: str
    title: str
    skills: tuple[str, ...]
    level: int
    hours: int | None  # None = carga horária desconhecida (nunca estimada)
    link: str  # "" = sem link
    platform: str = ""
    focus: str = ""
    provider: str = ""
    kind: str = "curso"
    source: str = ""
    verified: bool = False


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip().lower()


def _parse_level(raw: str) -> int | None:
    value = _fold(raw)
    if re.fullmatch(r"[1-3]", value):
        return int(value)
    return _LEVEL_NAMES.get(value)


def load_catalog(path: str | Path) -> list[Course]:
    where = str(path)
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = [c.strip() for c in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in columns]
        if missing:
            raise ValueError(
                f"{where}: coluna obrigatória ausente: {', '.join(missing)}")
        courses: list[Course] = []
        seen: set[str] = set()
        for row in reader:
            line = reader.line_num
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}

            def fail(reason: str) -> ValueError:
                return ValueError(f"{where}: linha {line}: {reason}")

            cid = row["id"]
            if not cid:
                raise fail("id vazio")
            if cid in seen:
                raise fail(f"id duplicado '{cid}'")
            seen.add(cid)
            level = _parse_level(row["nivel"])
            if level is None:
                raise fail(f"nivel inválido '{row['nivel']}' (use 1-3, Fundamentals, "
                           "Intermediate ou Advanced)")
            raw_hours = row.get("carga_horaria", "")
            try:
                hours = int(raw_hours) if raw_hours else None
            except ValueError:
                raise fail(f"carga_horaria não é um inteiro: '{raw_hours}'") from None
            if hours is not None and hours < 0:
                raise fail(f"carga_horaria negativa: {hours}")
            raw_verified = _fold(row.get("verificado", ""))
            if raw_verified in _TRUE:
                verified = True
            elif raw_verified in _FALSE or raw_verified == "":
                verified = False
            else:
                raise fail(f"verificado inválido '{row['verificado']}' (use 0/1, sim/não)")
            skills = tuple(s.strip() for s in re.split(r"[;,]", row["skills_cobertas"]) if s.strip())
            courses.append(Course(
                id=cid, title=row["titulo"], skills=skills, level=level, hours=hours,
                link=row.get("link", ""), platform=row.get("plataforma", ""),
                focus=row.get("foco", ""), provider=row.get("provedor", ""),
                kind=row.get("tipo", "") or "curso", source=row.get("fonte", ""),
                verified=verified))
        return courses


def recommend(gaps: list[Gap], courses: list[Course], limit: int = 10) -> list[Recommendation]:
    by_skill = {g.skill: g for g in gaps}
    scored: list[tuple[int, Course, list[str]]] = []
    for course in courses:
        covered = [
            by_skill[skill] for skill in course.skills
            if skill in by_skill and course.level >= by_skill[skill].current
        ]
        if covered:
            score = sum(WEIGHT[g.severity] for g in covered)
            scored.append((score, course, [g.skill for g in covered]))
    scored.sort(key=lambda item: (-item[0], item[1].hours is None, item[1].hours or 0, item[1].id))
    return [
        Recommendation(course_id=c.id, title=c.title, covers=covers, hours=c.hours, link=c.link,
                       provider=c.provider or None, kind=c.kind or None, verified=c.verified,
                       level=c.level, platform=c.platform or None)
        for _, c, covers in scored[:limit]
    ]
