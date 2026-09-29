import csv
from dataclasses import dataclass
from pathlib import Path

from skillgap.models import Gap, Recommendation

WEIGHT = {"high": 3, "medium": 2, "low": 1}


@dataclass(frozen=True)
class Course:
    id: str
    title: str
    skills: tuple[str, ...]
    level: int
    hours: int
    link: str


def load_catalog(path: str | Path) -> list[Course]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [
            Course(
                id=row["id"].strip(),
                title=row["titulo"].strip(),
                skills=tuple(s.strip() for s in row["skills_cobertas"].split(";") if s.strip()),
                level=int(row["nivel"]),
                hours=int(row["carga_horaria"]),
                link=row["link"].strip(),
            )
            for row in csv.DictReader(handle)
        ]


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
    scored.sort(key=lambda item: (-item[0], item[1].hours, item[1].id))
    return [
        Recommendation(course_id=c.id, title=c.title, covers=covers, hours=c.hours, link=c.link)
        for _, c, covers in scored[:limit]
    ]
