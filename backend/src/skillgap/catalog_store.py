"""Catálogo de treinamentos em SQLite (consultável com SQL puro).

Compartilha o arquivo ``data/skillgap.db`` com o ``Store`` de resultados; por isso
usa WAL e timeout. Toda consulta é parametrizada: entrada de usuário nunca é
concatenada ao SQL.
"""
from __future__ import annotations

import csv
import dataclasses
import sqlite3
import threading
from pathlib import Path

from skillgap.recommender import Course, load_catalog
from skillgap.taxonomy import Taxonomy

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    focus TEXT NOT NULL DEFAULT '',
    level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3),
    provider TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'curso',
    hours INTEGER CHECK(hours IS NULL OR hours >= 0),
    link TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0 CHECK(verified IN (0,1))
);
CREATE TABLE IF NOT EXISTS course_skills (
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL,
    PRIMARY KEY(course_id, skill_id)
);
CREATE INDEX IF NOT EXISTS idx_course_skills_skill ON course_skills(skill_id);
CREATE VIEW IF NOT EXISTS v_course_coverage AS
  SELECT c.id, c.platform, c.title, c.level, c.provider, c.kind, c.hours, c.verified, c.link,
         COALESCE(group_concat(cs.skill_id, ';'), '') AS skills
  FROM courses c LEFT JOIN course_skills cs ON cs.course_id = c.id GROUP BY c.id;
"""

_MIGRATIONS = (
    ("exam_codes", "ALTER TABLE courses ADD COLUMN exam_codes TEXT NOT NULL DEFAULT ''"),
    ("synced_at", "ALTER TABLE courses ADD COLUMN synced_at TEXT NOT NULL DEFAULT ''"),
    ("retired", "ALTER TABLE courses ADD COLUMN retired INTEGER NOT NULL DEFAULT 0"),
)

_SELECT = (
    "SELECT c.id, c.platform, c.title, c.focus, c.level, c.provider, c.kind, c.hours, "
    "c.link, c.source, c.verified, "
    "COALESCE((SELECT group_concat(skill_id, ';') FROM course_skills WHERE course_id = c.id), ''), "
    "c.exam_codes, c.synced_at, c.retired "
    "FROM courses c")

CSV_HEADER = ["id", "plataforma", "titulo", "foco", "nivel", "provedor", "tipo",
              "skills_cobertas", "carga_horaria", "link", "fonte", "verificado"]


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_course(row) -> Course:
    skills = tuple(sorted(s for s in row[11].split(";") if s))
    exams = tuple(e for e in row[12].split(";") if e)
    return Course(id=row[0], platform=row[1], title=row[2], focus=row[3], level=row[4],
                  provider=row[5], kind=row[6], hours=row[7], link=row[8], source=row[9],
                  verified=bool(row[10]), skills=skills, exam_codes=exams,
                  synced_at=row[13], retired=bool(row[14]))


def validate_courses(courses: list[Course], taxonomy: Taxonomy) -> None:
    """Todas as skills devem existir na taxonomia e a plataforma ser uma trilha."""
    valid = {s.id for track in taxonomy.tracks for s in taxonomy.skills_in_track(track)}
    problems: list[str] = []
    for c in courses:
        unknown = sorted(s for s in c.skills if s not in valid)
        if unknown:
            problems.append(f"{c.id}: skill(s) inexistente(s) na taxonomia: {', '.join(unknown)}")
        if c.platform and c.platform not in taxonomy.tracks:
            problems.append(f"{c.id}: plataforma '{c.platform}' não é uma trilha da taxonomia")
    if problems:
        raise ValueError("Catálogo inválido:\n  " + "\n  ".join(problems))


class CatalogStore:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA foreign_keys=ON")
            if path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)
            have = {r[1] for r in self._db.execute("PRAGMA table_info(courses)")}
            for column, ddl in _MIGRATIONS:
                if column not in have:
                    self._db.execute(ddl)
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM courses").fetchone()[0]

    @staticmethod
    def _insert(db: sqlite3.Connection, course: Course) -> None:
        db.execute(
            "INSERT INTO courses (id, platform, title, focus, level, provider, kind, hours, "
            "link, source, verified, exam_codes, synced_at, retired) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET platform=excluded.platform, title=excluded.title, "
            "focus=excluded.focus, level=excluded.level, provider=excluded.provider, "
            "kind=excluded.kind, hours=excluded.hours, link=excluded.link, "
            "source=excluded.source, verified=excluded.verified, exam_codes=excluded.exam_codes, "
            "synced_at=excluded.synced_at, retired=excluded.retired",
            (course.id, course.platform, course.title, course.focus, course.level,
             course.provider, course.kind, course.hours, course.link, course.source,
             int(course.verified), ";".join(course.exam_codes), course.synced_at,
             int(course.retired)))
        db.execute("DELETE FROM course_skills WHERE course_id = ?", (course.id,))
        db.executemany("INSERT INTO course_skills (course_id, skill_id) VALUES (?, ?)",
                       [(course.id, s) for s in dict.fromkeys(course.skills)])

    def upsert(self, courses: list[Course]) -> None:
        with self._lock, self._db:
            for course in courses:
                self._insert(self._db, course)

    def replace_all(self, courses: list[Course]) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM courses")
            for course in courses:
                self._insert(self._db, course)

    def all_courses(self) -> list[Course]:
        return self.list_courses()

    def list_courses(self, platform: str | None = None, level: int | None = None,
                     kind: str | None = None, skill: str | None = None,
                     q: str | None = None, limit: int | None = None,
                     include_retired: bool = False) -> list[Course]:
        where: list[str] = []
        params: list[object] = []
        if platform is not None:
            where.append("c.platform = ?")
            params.append(platform)
        if level is not None:
            where.append("c.level = ?")
            params.append(level)
        if kind is not None:
            where.append("c.kind = ?")
            params.append(kind)
        if skill is not None:
            where.append("EXISTS (SELECT 1 FROM course_skills s "
                         "WHERE s.course_id = c.id AND s.skill_id = ?)")
            params.append(skill)
        if q:
            pattern = f"%{_like_escape(q)}%"
            where.append("(c.title LIKE ? ESCAPE '\\' OR c.focus LIKE ? ESCAPE '\\' "
                         "OR c.provider LIKE ? ESCAPE '\\')")
            params.extend([pattern, pattern, pattern])
        if not include_retired:
            where.append("c.retired = 0")
        sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "")
        sql += " ORDER BY c.platform, c.level, c.id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
        return [_to_course(r) for r in rows]

    def get(self, id: str) -> Course | None:
        with self._lock:
            row = self._db.execute(_SELECT + " WHERE c.id = ?", (id,)).fetchone()
        return _to_course(row) if row else None

    def stats(self) -> dict:
        def grouped(column: str) -> dict[str, int]:
            rows = self._db.execute(
                f"SELECT {column}, COUNT(*) FROM courses WHERE retired = 0 "
                f"GROUP BY {column} ORDER BY {column}")
            return {str(k): n for k, n in rows}

        with self._lock:
            total, verified, unknown = self._db.execute(
                "SELECT COUNT(*), COALESCE(SUM(verified), 0), "
                "COALESCE(SUM(hours IS NULL), 0) FROM courses WHERE retired = 0").fetchone()
            return {
                "total": total,
                "by_platform": grouped("platform"),
                "by_level": grouped("level"),
                "by_kind": grouped("kind"),
                "verified": verified,
                "unverified": total - verified,
                "hours_unknown": unknown,
            }

    def sync_learn(self, items: list[Course], synced_at: str,
                   retire_kinds: set[str] | None = None) -> dict[str, int]:
        """Upsert atômico dos itens ``learn:*``; aposenta os que sumiram do catálogo oficial.

        Nunca toca linhas cujo id não começa com ``learn:`` (comparação sensível a caixa).
        ``retire_kinds`` limita a aposentadoria aos tipos informados (None = todos).
        """
        bad = [c.id for c in items if not c.id.startswith("learn:")]
        if bad:
            raise ValueError("sync_learn só aceita ids com prefixo 'learn:': " + ", ".join(bad))
        incoming = {c.id for c in items}
        with self._lock, self._db:
            rows = self._db.execute(
                "SELECT id, retired, kind FROM courses WHERE substr(id, 1, 6) = 'learn:'").fetchall()
            existing = {row[0]: bool(row[1]) for row in rows}
            kind_of = {row[0]: row[2] for row in rows}
            for course in items:
                self._insert(self._db, dataclasses.replace(
                    course, synced_at=synced_at, retired=False))
            gone = [cid for cid in existing if cid not in incoming
                    and (retire_kinds is None or kind_of[cid] in retire_kinds)]
            self._db.executemany("UPDATE courses SET retired = 1 WHERE id = ?",
                                 [(cid,) for cid in gone])
        return {"inserted": len(incoming - existing.keys()),
                "updated": len(incoming & existing.keys()),
                "retired": sum(1 for cid in gone if not existing[cid])}

    def learn_status(self) -> dict:
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, COUNT(*) FROM courses WHERE substr(id, 1, 6) = 'learn:' AND retired = 0 "
                "GROUP BY kind ORDER BY kind").fetchall()
            retired, last = self._db.execute(
                "SELECT COALESCE(SUM(retired), 0), MAX(synced_at) FROM courses "
                "WHERE substr(id, 1, 6) = 'learn:'").fetchone()
        return {"items": sum(n for _, n in rows), "by_kind": {k: n for k, n in rows},
                "retired": retired, "last_sync": last or None}

    def seed_from_csv_if_empty(self, path: str | Path, taxonomy: Taxonomy) -> int:
        if self.count() > 0:
            return 0
        if not Path(path).is_file():
            raise ValueError(f"Arquivo de catálogo não encontrado: {path}")
        courses = load_catalog(path)
        validate_courses(courses, taxonomy)
        self.replace_all(courses)
        return len(courses)

    def export_csv(self, path: str | Path) -> None:
        courses = self.all_courses()
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            for c in courses:
                writer.writerow([
                    c.id, c.platform, c.title, c.focus, c.level, c.provider, c.kind,
                    ";".join(c.skills), "" if c.hours is None else c.hours, c.link,
                    c.source, int(c.verified)])
