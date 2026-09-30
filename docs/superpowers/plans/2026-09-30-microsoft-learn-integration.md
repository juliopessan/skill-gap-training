# Integração Microsoft Learn (catálogo + MCP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recomendar cursos e certificações reais da Microsoft Learn, por nível, sincronizando o Learn Catalog API para o SQLite e usando o MCP da Learn como busca complementar para gaps sem item no catálogo.

**Architecture:** `learn_catalog.py` baixa e normaliza o catálogo oficial; `learn_mapping.py` liga cada item às skills da taxonomia por regras YAML; `CatalogStore.sync_learn` grava só linhas `learn:*` (atômico, aposenta o que sumiu); o recomendador ganha desempate por verificado e campos de proveniência; `learn_mcp.py` (cliente JSON-RPC + cache SQLite) devolve links de documentação para gaps sem item, e o pipeline e a interface mostram tudo com a origem.

**Tech Stack:** Python 3.14 (`backend/.venv`), FastAPI, SQLite, pydantic, PyYAML, `urllib` (sem dependência nova), pytest; Next.js 15 / TypeScript (`frontend/`).

**Spec:** `docs/superpowers/specs/2026-09-30-microsoft-learn-integration-design.md`

## Global Constraints

- Idioma de textos de interface, mensagens e docs: português com acentuação completa. Identificadores em inglês.
- **Nenhum teste usa a rede.** Catálogo e MCP entram por função/transporte injetável. `backend/tests/conftest.py` define `SKILLGAP_LEARN_MCP=0` (autouse).
- **Nunca dar `git push`** nem alterar `main`/`origin`. Só commits locais na branch atual; o controlador publica.
- Nunca escrever chave de API, telefone ou caminho `/Users/...` em arquivo do repositório.
- Todo SQL é parametrizado. Linhas manuais do catálogo (`id` sem prefixo `learn:`) nunca são alteradas pela sincronização.
- Horas e níveis vêm da Microsoft ou ficam `None`/ausentes: **nunca estimados**.
- Verde e terracota do Ledger continuam reservados (citação localizada/não localizada). Nada novo usa essas cores.
- Não rodar `npm run build` enquanto `npm run dev` roda (`.next` compartilhado). Verificação de frontend: `npm run typecheck` e `npm run check:*`.
- Trailer de commit: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Comandos de backend rodam em `backend/` com `.venv/bin/python -m pytest`.

## Review Focus

1. Catálogo com itens incompletos (sem nível, sem URL, `products`/`levels` nulos, resumo com HTML): descartar com motivo, nunca quebrar (Task 2).
2. Resposta 200 vazia ou sem itens mapeados não pode aposentar o catálogo Learn inteiro (Task 4).
3. Banco já existente (sem as colunas novas) precisa abrir; item aposentado nunca é recomendado nem listado (Task 1, 5).
4. MCP fora do ar, lento, malformado ou devolvendo URL de outro domínio: o CV termina igual, com `learn_status="unavailable"`, e nenhum link fora de `learn.microsoft.com` chega à interface (Tasks 6, 7, 9).
5. Ids com `:` e `.` (`learn:learn.fabric.x`) nas rotas `/catalog/{id}` (Task 8).

Rulings (registrados aqui, refletidos na spec na Task 10):
- `match_origin` é derivado do prefixo do id (`learn:` → `rule`, senão `manual`), sem coluna nova em `course_skills`.
- O link do catálogo perde a query inteira (o único parâmetro é `WT.mc_id`).
- O MCP devolve `{skill, title, url}`; sem `excerpt`, porque o texto dos resultados é markdown de metadados da página, não prosa.
- `Settings.learn_mcp` tem padrão `False` na dataclass e `load_settings()` liga por padrão (`SKILLGAP_LEARN_MCP` ≠ `0`), para que testes que constroem `Settings(...)` nunca toquem a rede.
- O texto "horas não informadas" da interface fica como está.

---

### Task 1: Campos de proveniência no `Course` e sincronização no `CatalogStore`

**Files:**
- Modify: `backend/src/skillgap/recommender.py` (dataclass `Course`)
- Modify: `backend/src/skillgap/catalog_store.py`
- Create: `backend/tests/test_catalog_learn_store.py`
- Modify: `backend/tests/conftest.py` (autouse `SKILLGAP_LEARN_MCP=0`)

**Interfaces:**
- Produces: `Course.exam_codes: tuple[str, ...] = ()`, `Course.synced_at: str = ""`, `Course.retired: bool = False`, `Course.match_origin` (property: `"rule"` se `id` começa com `learn:`, senão `"manual"`); `CatalogStore.sync_learn(items: list[Course], synced_at: str) -> dict[str, int]` (chaves `inserted`, `updated`, `retired`); `CatalogStore.learn_status() -> dict` (`items`, `by_kind`, `retired`, `last_sync`); `list_courses(..., include_retired: bool = False)`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_catalog_learn_store.py`

```python
import sqlite3

import pytest

from skillgap.catalog_store import CatalogStore
from skillgap.recommender import Course


def learn(uid, skills=("fabric.lakehouse",), level=2, **kw):
    return Course(id=f"learn:{uid}", title=f"T {uid}", skills=tuple(skills), level=level, hours=3,
                  link=f"https://learn.microsoft.com/{uid}", platform="fabric", kind="trilha",
                  provider="Microsoft Learn", source="Microsoft Learn Catalog API",
                  verified=True, **kw)


def manual(id="m1"):
    return Course(id=id, title="Manual", skills=("fabric.lakehouse",), level=1, hours=None,
                  link="", platform="fabric")


def test_match_origin_is_derived_from_id_prefix():
    assert learn("a").match_origin == "rule"
    assert manual().match_origin == "manual"


def test_sync_inserts_then_updates_and_reports_counts():
    s = CatalogStore(":memory:")
    assert s.sync_learn([learn("a"), learn("b")], "2026-09-30") == {"inserted": 2, "updated": 0, "retired": 0}
    assert s.sync_learn([learn("a", level=3), learn("b")], "2026-10-01") == {"inserted": 0, "updated": 2, "retired": 0}
    a = s.get("learn:a")
    assert a.level == 3 and a.synced_at == "2026-10-01" and a.verified is True


def test_sync_retires_missing_items_and_hides_them_but_keeps_the_row():
    s = CatalogStore(":memory:")
    s.sync_learn([learn("a"), learn("b")], "2026-09-30")
    assert s.sync_learn([learn("a")], "2026-10-01") == {"inserted": 0, "updated": 1, "retired": 1}
    assert [c.id for c in s.list_courses()] == ["learn:a"]
    assert [c.id for c in s.all_courses()] == ["learn:a"]
    assert [c.id for c in s.list_courses(include_retired=True)] == ["learn:a", "learn:b"]
    assert s.get("learn:b").retired is True
    s.sync_learn([learn("a"), learn("b")], "2026-10-02")  # voltou ao catálogo
    assert s.get("learn:b").retired is False


def test_sync_never_touches_manual_rows():
    s = CatalogStore(":memory:")
    s.upsert([manual("m1")])
    s.sync_learn([learn("a")], "2026-09-30")
    s.sync_learn([], "2026-10-01")
    assert s.get("m1").retired is False
    assert s.get("learn:a").retired is True
    assert [c.id for c in s.list_courses()] == ["m1"]


def test_sync_rejects_non_learn_ids_without_writing():
    s = CatalogStore(":memory:")
    with pytest.raises(ValueError, match="learn:"):
        s.sync_learn([learn("a"), manual("m1")], "2026-09-30")
    assert s.count() == 0


def test_sync_is_atomic_when_a_row_is_invalid():
    s = CatalogStore(":memory:")
    with pytest.raises(sqlite3.IntegrityError):
        s.sync_learn([learn("a"), learn("bad", level=9)], "2026-09-30")
    assert s.count() == 0


def test_exam_codes_round_trip():
    s = CatalogStore(":memory:")
    s.sync_learn([learn("cert", exam_codes=("AI-500", "AZ-204"))], "2026-09-30")
    assert s.get("learn:cert").exam_codes == ("AI-500", "AZ-204")
    assert s.get("learn:cert").synced_at == "2026-09-30"


def test_learn_status():
    s = CatalogStore(":memory:")
    assert s.learn_status() == {"items": 0, "by_kind": {}, "retired": 0, "last_sync": None}
    s.upsert([manual()])
    s.sync_learn([learn("a"), learn("b", kind="curso")], "2026-09-30")
    s.sync_learn([learn("a")], "2026-10-01")
    st = s.learn_status()
    assert st["items"] == 1 and st["by_kind"] == {"trilha": 1} and st["retired"] == 1
    assert st["last_sync"] == "2026-10-01"


def test_stats_ignore_retired_rows():
    s = CatalogStore(":memory:")
    s.sync_learn([learn("a"), learn("b")], "2026-09-30")
    s.sync_learn([learn("a")], "2026-10-01")
    assert s.stats()["total"] == 1


def test_old_database_without_new_columns_is_migrated(tmp_path):
    path = str(tmp_path / "old.db")
    db = sqlite3.connect(path)
    db.executescript(
        "CREATE TABLE courses (id TEXT PRIMARY KEY, platform TEXT NOT NULL, title TEXT NOT NULL,"
        " focus TEXT NOT NULL DEFAULT '', level INTEGER NOT NULL, provider TEXT NOT NULL DEFAULT '',"
        " kind TEXT NOT NULL DEFAULT 'curso', hours INTEGER, link TEXT NOT NULL DEFAULT '',"
        " source TEXT NOT NULL DEFAULT '', verified INTEGER NOT NULL DEFAULT 0);"
        "CREATE TABLE course_skills (course_id TEXT NOT NULL, skill_id TEXT NOT NULL,"
        " PRIMARY KEY(course_id, skill_id));"
        "INSERT INTO courses (id, platform, title, level) VALUES ('old1', 'fabric', 'Antigo', 1);"
        "INSERT INTO course_skills VALUES ('old1', 'fabric.lakehouse');")
    db.commit()
    db.close()
    s = CatalogStore(path)
    old = s.get("old1")
    assert old.retired is False and old.exam_codes == () and old.synced_at == ""
    s.sync_learn([learn("a")], "2026-09-30")  # e as colunas novas funcionam
    assert s.get("learn:a").synced_at == "2026-09-30"
```

- [ ] **Step 2: Add the autouse env fixture** — append to `backend/tests/conftest.py`

```python
@pytest.fixture(autouse=True)
def _no_learn_mcp(monkeypatch):
    """Nenhum teste toca a rede: o MCP da Learn fica desligado."""
    monkeypatch.setenv("SKILLGAP_LEARN_MCP", "0")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_catalog_learn_store.py -q`
Expected: FAIL (`Course` sem `exam_codes`, `CatalogStore` sem `sync_learn`).

- [ ] **Step 4: Implement `Course` fields** — `backend/src/skillgap/recommender.py`, dentro de `class Course`, depois de `verified: bool = False`:

```python
    exam_codes: tuple[str, ...] = ()
    synced_at: str = ""  # "" = linha manual ou nunca sincronizada
    retired: bool = False  # True = sumiu do catálogo oficial; nunca é recomendada

    @property
    def match_origin(self) -> str:
        return "rule" if self.id.startswith("learn:") else "manual"
```

- [ ] **Step 5: Implement the store changes** — `backend/src/skillgap/catalog_store.py`

Depois de `SCHEMA`, adicionar:

```python
_MIGRATIONS = (
    ("exam_codes", "ALTER TABLE courses ADD COLUMN exam_codes TEXT NOT NULL DEFAULT ''"),
    ("synced_at", "ALTER TABLE courses ADD COLUMN synced_at TEXT NOT NULL DEFAULT ''"),
    ("retired", "ALTER TABLE courses ADD COLUMN retired INTEGER NOT NULL DEFAULT 0"),
)
```

Trocar `_SELECT` por (novas colunas depois das skills, índices 12-14):

```python
_SELECT = (
    "SELECT c.id, c.platform, c.title, c.focus, c.level, c.provider, c.kind, c.hours, "
    "c.link, c.source, c.verified, "
    "COALESCE((SELECT group_concat(skill_id, ';') FROM course_skills WHERE course_id = c.id), ''), "
    "c.exam_codes, c.synced_at, c.retired "
    "FROM courses c")
```

`_to_course` passa a preencher os novos campos:

```python
def _to_course(row) -> Course:
    skills = tuple(sorted(s for s in row[11].split(";") if s))
    exams = tuple(e for e in row[12].split(";") if e)
    return Course(id=row[0], platform=row[1], title=row[2], focus=row[3], level=row[4],
                  provider=row[5], kind=row[6], hours=row[7], link=row[8], source=row[9],
                  verified=bool(row[10]), skills=skills, exam_codes=exams,
                  synced_at=row[13], retired=bool(row[14]))
```

No `__init__`, logo depois de `self._db.executescript(SCHEMA)`:

```python
            have = {r[1] for r in self._db.execute("PRAGMA table_info(courses)")}
            for column, ddl in _MIGRATIONS:
                if column not in have:
                    self._db.execute(ddl)
```

`_insert` passa a gravar as colunas novas (substituir o método inteiro):

```python
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
```

`list_courses`: adicionar parâmetro `include_retired: bool = False` (depois de `limit`) e, antes de montar o SQL:

```python
        if not include_retired:
            where.append("c.retired = 0")
```

Novos métodos (antes de `seed_from_csv_if_empty`):

```python
    def sync_learn(self, items: list[Course], synced_at: str) -> dict[str, int]:
        """Upsert atômico dos itens ``learn:*``; aposenta os que sumiram do catálogo oficial.

        Nunca toca linhas cujo id não começa com ``learn:``.
        """
        bad = [c.id for c in items if not c.id.startswith("learn:")]
        if bad:
            raise ValueError("sync_learn só aceita ids com prefixo 'learn:': " + ", ".join(bad))
        incoming = {c.id for c in items}
        with self._lock, self._db:
            existing = {row[0]: bool(row[1]) for row in self._db.execute(
                "SELECT id, retired FROM courses WHERE id LIKE 'learn:%'")}
            for course in items:
                self._insert(self._db, dataclasses.replace(
                    course, synced_at=synced_at, retired=False))
            gone = [cid for cid in existing if cid not in incoming]
            self._db.executemany("UPDATE courses SET retired = 1 WHERE id = ?",
                                 [(cid,) for cid in gone])
        return {"inserted": len(incoming - existing.keys()),
                "updated": len(incoming & existing.keys()),
                "retired": sum(1 for cid in gone if not existing[cid])}

    def learn_status(self) -> dict:
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, COUNT(*) FROM courses WHERE id LIKE 'learn:%' AND retired = 0 "
                "GROUP BY kind ORDER BY kind").fetchall()
            retired, last = self._db.execute(
                "SELECT COALESCE(SUM(retired), 0), MAX(synced_at) FROM courses "
                "WHERE id LIKE 'learn:%'").fetchone()
        return {"items": sum(n for _, n in rows), "by_kind": {k: n for k, n in rows},
                "retired": retired, "last_sync": last or None}
```

Adicionar `import dataclasses` no topo. Em `stats()`, restringir as três consultas a linhas ativas: nas consultas de `grouped` trocar `FROM courses GROUP BY` por `FROM courses WHERE retired = 0 GROUP BY`, e a de totais por `... FROM courses WHERE retired = 0`.

- [ ] **Step 6: Run the tests** (novos e existentes de catálogo)

Run: `cd backend && .venv/bin/python -m pytest tests/test_catalog_learn_store.py tests/test_catalog_store.py tests/test_recommender.py tests/test_cli_catalog.py -q`
Expected: PASS. Se algum teste antigo comparar `stats()` ou `CourseOut` por igualdade exata, ajustar só as chaves esperadas.

- [ ] **Step 7: Commit**

```bash
git add backend/src/skillgap/recommender.py backend/src/skillgap/catalog_store.py backend/tests/test_catalog_learn_store.py backend/tests/conftest.py
git commit -m "feat(catalog): campos de proveniência e sync_learn atômico no SQLite

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `learn_catalog.py` — download e normalização do Catalog API

**Files:**
- Create: `backend/src/skillgap/learn_catalog.py`
- Create: `backend/tests/learn_fixtures.py`
- Create: `backend/tests/test_learn_catalog.py`

**Interfaces:**
- Produces: `LearnItem` (dataclass frozen: `uid, kind, title, summary, level, levels, hours, url, products, exam_codes`), `normalize_catalog(payload: dict) -> tuple[list[LearnItem], list[tuple[str, str, str]]]` (itens; descartes `(uid, título, motivo)`), `fetch_catalog(locale: str = "en-us", opener=urllib.request.urlopen, timeout: float = 90) -> dict` (levanta `ValueError` em qualquer falha), `clean_url(url) -> str`, `SOURCE = "Microsoft Learn Catalog API"`.

- [ ] **Step 1: Fixtures compartilhadas** — `backend/tests/learn_fixtures.py`

```python
"""Payload reduzido do Learn Catalog API e regras de mapeamento para a taxonomia pequena dos testes."""


def catalog_payload():
    return {
        "learningPaths": [
            {"uid": "learn.fabric.lakehouse", "title": "Implement a Lakehouse with Microsoft Fabric",
             "summary": "<p>Build a <b>lakehouse</b> with OneLake and Delta tables.</p>",
             "levels": ["intermediate"], "products": ["fabric"], "duration_in_minutes": 421,
             "url": "https://learn.microsoft.com/en-us/training/paths/implement-lakehouse/?WT.mc_id=api_CatalogApi"},
            {"uid": "learn.foundry.agents", "title": "Develop AI agents on Azure",
             "summary": "Build agentic solutions with Foundry Agent Service.",
             "levels": ["intermediate", "advanced"], "products": ["foundry-agent-service"],
             "duration_in_minutes": 240,
             "url": "https://learn.microsoft.com/en-us/training/paths/develop-ai-agents/"},
            {"uid": "learn.dbx.spark", "title": "Use Apache Spark in Azure Databricks",
             "summary": "Process data with PySpark.", "levels": ["beginner"],
             "products": ["azure-databricks"], "duration_in_minutes": 0,
             "url": "https://learn.microsoft.com/en-us/training/paths/spark-databricks/"},
            {"uid": "learn.excel", "title": "Excel basics", "summary": "Spreadsheets",
             "levels": ["beginner"], "products": ["office-excel"], "duration_in_minutes": 60,
             "url": "https://learn.microsoft.com/en-us/training/paths/excel/"},
            {"uid": "learn.nolevel", "title": "Fabric mystery", "summary": "lakehouse",
             "levels": [], "products": ["fabric"], "url": "https://learn.microsoft.com/x"},
            {"uid": "learn.nourl", "title": "Fabric lakehouse without url", "summary": "lakehouse",
             "levels": ["beginner"], "products": ["fabric"]},
            {"uid": "learn.nulls", "title": "Broken entry", "summary": None, "levels": None,
             "products": None, "url": None},
        ],
        "courses": [
            {"uid": "course.dp-600t00", "title": "Implementing analytics solutions using Microsoft Fabric",
             "summary": "warehouse and lakehouse", "levels": ["intermediate"], "products": ["fabric"],
             "duration_in_hours": 24, "url": "https://learn.microsoft.com/en-us/training/courses/dp-600t00/"},
        ],
        "certifications": [
            {"uid": "certification.fabric-data-engineer-associate",
             "title": "Microsoft Certified: Fabric Data Engineer Associate",
             "subtitle": "<p>Design and deploy data engineering solutions.</p>",
             "levels": ["intermediate"], "exams": [],
             "url": "https://learn.microsoft.com/en-us/credentials/certifications/fabric-data-engineer-associate/?WT.mc_id=api_CatalogApi"},
            {"uid": "certification.multi-agent-ai-solutions-expert",
             "title": "Microsoft Certified: Multi-Agent AI Solutions Expert",
             "subtitle": "Build multi-agent AI solutions.", "levels": ["advanced"],
             "exams": ["exam.ai-500"],
             "url": "https://learn.microsoft.com/en-us/credentials/certifications/multi-agent-ai-solutions-expert/"},
        ],
        "exams": [
            {"uid": "exam.ai-500", "title": "Designing and Implementing Multi-Agent AI Solutions",
             "subtitle": "Multi-agent", "levels": ["advanced"], "products": ["microsoft-foundry"],
             "url": "https://learn.microsoft.com/en-us/credentials/exams/ai-500/"},
        ],
    }


MAPPING_YAML = """
version: 1
tracks:
  fabric: {products: [fabric]}
  foundry: {products: [microsoft-foundry, foundry-agent-service]}
  databricks: {products: [azure-databricks]}
skills:
  fabric.lakehouse: {keywords: [lakehouse, onelake], strong: ["fabric data engineer"]}
  fabric.pipelines: {keywords: [pipeline, pipelines]}
  foundry.agents: {keywords: [agent, agents, agentic, multi agent], strong: ["multi agent ai solutions"]}
  foundry.models: {keywords: [deploy, deployment]}
  databricks.spark: {keywords: [spark, pyspark]}
"""
```

- [ ] **Step 2: Failing tests** — `backend/tests/test_learn_catalog.py`

```python
import json

import pytest

from skillgap.learn_catalog import clean_url, fetch_catalog, normalize_catalog
from learn_fixtures import catalog_payload


def by_uid(items):
    return {i.uid: i for i in items}


def test_normalize_levels_hours_urls_and_kinds():
    items, dropped = normalize_catalog(catalog_payload())
    m = by_uid(items)
    lake = m["learn.fabric.lakehouse"]
    assert (lake.kind, lake.level, lake.hours) == ("trilha", 2, 8)  # 421 min -> 8 h (teto)
    assert lake.url == "https://learn.microsoft.com/en-us/training/paths/implement-lakehouse/"
    assert "<" not in lake.summary and "lakehouse" in lake.summary
    agents = m["learn.foundry.agents"]
    assert agents.level == 2 and agents.levels == ("intermediate", "advanced")  # vale o menor
    assert m["learn.dbx.spark"].level == 1 and m["learn.dbx.spark"].hours is None  # 0 min = desconhecido
    assert m["course.dp-600t00"].kind == "curso" and m["course.dp-600t00"].hours == 24
    assert m["exam.ai-500"].kind == "exame" and m["exam.ai-500"].level == 3


def test_certification_keeps_exam_codes_only_when_the_catalog_gives_them():
    m = by_uid(normalize_catalog(catalog_payload())[0])
    assert m["certification.fabric-data-engineer-associate"].exam_codes == ()
    assert m["certification.multi-agent-ai-solutions-expert"].exam_codes == ("AI-500",)
    assert m["certification.multi-agent-ai-solutions-expert"].kind == "certificação"


def test_exam_entries_may_be_dicts():
    payload = {"certifications": [{"uid": "c", "title": "C", "levels": ["beginner"],
                                   "exams": [{"uid": "exam.az-900"}], "url": "https://learn.microsoft.com/c"}]}
    [item], _ = normalize_catalog(payload)
    assert item.exam_codes == ("AZ-900",)


def test_incomplete_items_are_dropped_with_a_reason_and_never_crash():
    items, dropped = normalize_catalog(catalog_payload())
    reasons = {uid: why for uid, _, why in dropped}
    assert "learn.nolevel" not in by_uid(items) and "nível" in reasons["learn.nolevel"]
    assert "learn.nourl" not in by_uid(items) and "link" in reasons["learn.nourl"]
    assert "learn.nulls" not in by_uid(items) and "learn.nulls" in reasons


def test_payload_with_missing_lists_or_garbage_is_tolerated():
    assert normalize_catalog({}) == ([], [])
    assert normalize_catalog({"courses": "x", "exams": [None, 3, {}]})[0] == []


@pytest.mark.parametrize("raw,expected", [
    ("https://learn.microsoft.com/en-us/x/?WT.mc_id=api#frag", "https://learn.microsoft.com/en-us/x/"),
    ("http://learn.microsoft.com/x", ""),
    ("https://evil.example.com/x", ""),
    ("https://learn.microsoft.com.evil.com/x", ""),
    ("https://user:pw@learn.microsoft.com/x", ""),
    ("javascript:alert(1)", ""),
    ("", ""),
    (None, ""),
])
def test_clean_url(raw, expected):
    assert clean_url(raw) == expected


class FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_builds_the_url_and_parses_json():
    seen = {}

    def opener(url, timeout):
        seen["url"] = url
        return FakeResponse(json.dumps({"courses": []}).encode())

    assert fetch_catalog("pt-br", opener=opener) == {"courses": []}
    assert "locale=pt-br" in seen["url"] and "type=courses,learningPaths,certifications,exams" in seen["url"]


def test_fetch_rejects_a_malformed_locale_before_any_request():
    def opener(url, timeout):
        raise AssertionError("não deveria chamar a rede")

    with pytest.raises(ValueError, match="locale"):
        fetch_catalog("../../etc", opener=opener)


def test_fetch_turns_network_and_json_failures_into_value_error():
    def down(url, timeout):
        raise OSError("sem rede")

    with pytest.raises(ValueError, match="Microsoft Learn"):
        fetch_catalog(opener=down)
    with pytest.raises(ValueError, match="inválida"):
        fetch_catalog(opener=lambda u, timeout: FakeResponse(b"<html>"))
    with pytest.raises(ValueError, match="inválida"):
        fetch_catalog(opener=lambda u, timeout: FakeResponse(b"[1, 2]"))
```

Run: `cd backend && .venv/bin/python -m pytest tests/test_learn_catalog.py -q` → FAIL (módulo inexistente). (Os testes importam helpers como `from support import ...`, sem prefixo `tests.`; `learn_fixtures.py` segue o mesmo padrão.)

- [ ] **Step 3: Implement** — `backend/src/skillgap/learn_catalog.py`

```python
"""Download e normalização do Learn Catalog API (fonte oficial de nível, duração e link).

Só código: nenhuma chamada de modelo. O vínculo item → skill vem de ``learn_mapping``.
"""
from __future__ import annotations

import json
import math
import re
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

CATALOG_URL = "https://learn.microsoft.com/api/catalog/"
TYPES = "courses,learningPaths,certifications,exams"
SOURCE = "Microsoft Learn Catalog API"
MAX_BYTES = 64 * 1024 * 1024
ALLOWED_HOST = "learn.microsoft.com"

_LEVEL = {"beginner": 1, "intermediate": 2, "advanced": 3}
_KINDS = {"learningPaths": "trilha", "courses": "curso",
          "certifications": "certificação", "exams": "exame"}


@dataclass(frozen=True)
class LearnItem:
    uid: str
    kind: str
    title: str
    summary: str
    level: int
    levels: tuple[str, ...]
    hours: int | None
    url: str
    products: tuple[str, ...]
    exam_codes: tuple[str, ...]


def clean_url(url: object) -> str:
    """Só https em learn.microsoft.com; remove query (rastreio ``WT.mc_id``) e fragmento."""
    if not isinstance(url, str):
        return ""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return ""
    if (parts.scheme != "https" or parts.hostname != ALLOWED_HOST
            or parts.username or parts.password or port not in (None, 443)):
        return ""
    return urlunsplit(("https", ALLOWED_HOST, parts.path, "", ""))


def _text(value: object) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value).split()) if isinstance(value, str) else ""


def _hours(raw: dict) -> int | None:
    for key, per_hour in (("duration_in_minutes", 60), ("duration_in_hours", 1)):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return math.ceil(value / per_hour)
    return None


def _exam_codes(raw: dict) -> tuple[str, ...]:
    codes: list[str] = []
    for entry in raw.get("exams") or []:
        uid = entry.get("uid") if isinstance(entry, dict) else entry
        if isinstance(uid, str) and "." in uid:
            codes.append(uid.split(".", 1)[1].upper())
    return tuple(codes)


def normalize_catalog(payload: dict) -> tuple[list[LearnItem], list[tuple[str, str, str]]]:
    items: list[LearnItem] = []
    dropped: list[tuple[str, str, str]] = []
    for key, kind in _KINDS.items():
        rows = payload.get(key) if isinstance(payload, dict) else None
        for raw in rows if isinstance(rows, list) else []:
            if not isinstance(raw, dict):
                continue
            uid = raw.get("uid")
            title = _text(raw.get("title"))
            if not isinstance(uid, str) or not uid or not title:
                if isinstance(uid, str) and uid:
                    dropped.append((uid, title, "sem título"))
                continue
            levels = tuple(v for v in (raw.get("levels") or []) if v in _LEVEL)
            if not levels:
                dropped.append((uid, title, "sem nível informado pela Microsoft"))
                continue
            url = clean_url(raw.get("url"))
            if not url:
                dropped.append((uid, title, "sem link válido em learn.microsoft.com"))
                continue
            products = tuple(p for p in (raw.get("products") or []) if isinstance(p, str))
            items.append(LearnItem(
                uid=uid, kind=kind, title=title,
                summary=_text(raw.get("summary") or raw.get("subtitle")),
                level=min(_LEVEL[v] for v in levels), levels=levels, hours=_hours(raw),
                url=url, products=products, exam_codes=_exam_codes(raw)))
    return items, dropped


def fetch_catalog(locale: str = "en-us", opener=urllib.request.urlopen,
                  timeout: float = 90) -> dict:
    if not re.fullmatch(r"[a-z]{2}-[a-z]{2}", locale or ""):
        raise ValueError(f"locale inválido: '{locale}' (use algo como en-us ou pt-br)")
    url = f"{CATALOG_URL}?type={TYPES}&locale={locale}"
    try:
        with opener(url, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"Não foi possível baixar o catálogo da Microsoft Learn: {exc}") from exc
    if len(raw) > MAX_BYTES:
        raise ValueError("Resposta do catálogo da Microsoft Learn grande demais")
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError("Resposta inválida do catálogo da Microsoft Learn (não é JSON)") from exc
    if not isinstance(data, dict):
        raise ValueError("Resposta inválida do catálogo da Microsoft Learn (formato inesperado)")
    return data
```

- [ ] **Step 4: Run** `cd backend && .venv/bin/python -m pytest tests/test_learn_catalog.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/skillgap/learn_catalog.py backend/tests/learn_fixtures.py backend/tests/test_learn_catalog.py
git commit -m "feat(learn): normalização e download do Learn Catalog API

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `learn_mapping.py` e `config/learn_mapping.yaml`

**Files:**
- Create: `backend/src/skillgap/learn_mapping.py`
- Create: `backend/config/learn_mapping.yaml`
- Create: `backend/tests/test_learn_mapping.py`

**Interfaces:**
- Consumes: `LearnItem`, `SOURCE` (Task 2); `Course` (Task 1); `Taxonomy`, `normalize` de `skillgap.taxonomy`.
- Produces: `load_mapping(path, taxonomy) -> Mapping`; `match_item(item, mapping) -> tuple[str, tuple[str, ...]] | None` (trilha, skills); `to_courses(items, mapping, taxonomy, dropped_before=()) -> tuple[list[Course], MappingReport]`; `render_report(report, taxonomy) -> str`. `MappingReport` tem `total`, `matched: dict[skill, list[titles]]`, `dropped: list[(uid, title, reason)]`, `uncovered: list[skill_id]`.

- [ ] **Step 1: Failing tests** — `backend/tests/test_learn_mapping.py`

```python
import pytest

from skillgap.learn_catalog import normalize_catalog
from skillgap.learn_mapping import load_mapping, match_item, render_report, to_courses
from skillgap.taxonomy import load_taxonomy
from learn_fixtures import MAPPING_YAML, catalog_payload


@pytest.fixture
def mapping(tmp_path, small_taxonomy):
    path = tmp_path / "m.yaml"
    path.write_text(MAPPING_YAML, encoding="utf-8")
    return load_mapping(path, small_taxonomy)


def build(mapping, taxonomy):
    items, dropped = normalize_catalog(catalog_payload())
    return to_courses(items, mapping, taxonomy, dropped)


def test_items_are_mapped_by_product_and_keyword(mapping, small_taxonomy):
    courses, _ = build(mapping, small_taxonomy)
    m = {c.id: c for c in courses}
    lake = m["learn:learn.fabric.lakehouse"]
    assert lake.platform == "fabric" and lake.skills == ("fabric.lakehouse",)
    assert lake.verified is True and lake.provider == "Microsoft Learn"
    assert lake.source == "Microsoft Learn Catalog API" and lake.kind == "trilha"
    assert m["learn:learn.foundry.agents"].skills == ("foundry.agents",)
    assert m["learn:learn.dbx.spark"].skills == ("databricks.spark",) and m["learn:learn.dbx.spark"].hours is None
    assert m["learn:course.dp-600t00"].skills == ("fabric.lakehouse",)


def test_certifications_match_by_title_even_without_products_or_exams(mapping, small_taxonomy):
    m = {c.id: c for c in build(mapping, small_taxonomy)[0]}
    cert = m["learn:certification.fabric-data-engineer-associate"]
    assert cert.kind == "certificação" and cert.skills == ("fabric.lakehouse",) and cert.exam_codes == ()
    expert = m["learn:certification.multi-agent-ai-solutions-expert"]
    assert expert.skills == ("foundry.agents",) and expert.exam_codes == ("AI-500",) and expert.level == 3
    assert m["learn:exam.ai-500"].kind == "exame"


def test_item_outside_the_tracks_is_dropped_with_a_reason(mapping, small_taxonomy):
    courses, report = build(mapping, small_taxonomy)
    assert "learn:learn.excel" not in {c.id for c in courses}
    reasons = {uid: why for uid, _, why in report.dropped}
    assert reasons["learn.excel"] == "sem skill casada"
    assert reasons["learn.nolevel"] and reasons["learn.nourl"]  # descartes do normalize entram no relatório
    assert len(courses) == 7


def test_keyword_needs_a_word_boundary_and_a_product_of_the_track(mapping, small_taxonomy):
    from skillgap.learn_catalog import LearnItem

    def item(title, products, summary=""):
        return LearnItem("u", "curso", title, summary, 1, ("beginner",), 1,
                         "https://learn.microsoft.com/x", tuple(products), ())

    assert match_item(item("Sparkle basics", ["azure-databricks"]), mapping) is None
    assert match_item(item("Spark basics", ["fabric"]), mapping) is None  # produto de outra trilha
    assert match_item(item("Spark basics", ["azure-databricks"]), mapping) == ("databricks", ("databricks.spark",))
    assert match_item(item("Cañón Pipeline", ["fabric"]), mapping) == ("fabric", ("fabric.pipelines",))


def test_report_lists_skills_without_any_item(mapping, small_taxonomy):
    _, report = build(mapping, small_taxonomy)
    assert sorted(report.uncovered) == ["fabric.pipelines", "foundry.models"]
    text = render_report(report, small_taxonomy)
    assert "Skills sem nenhum item" in text and "Pipelines" in text.replace("Data Pipelines", "Pipelines")
    assert "sem skill casada" in text


def test_invalid_mapping_reports_every_problem(tmp_path, small_taxonomy):
    path = tmp_path / "bad.yaml"
    path.write_text("tracks:\n  nope: {products: [x]}\nskills:\n  ghost.skill: {keywords: [a]}\n"
                    "  fabric.lakehouse: {}\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        load_mapping(path, small_taxonomy)
    msg = str(exc.value)
    assert "nope" in msg and "ghost.skill" in msg and "fabric.lakehouse" in msg


def test_yaml_syntax_error_becomes_value_error(tmp_path, small_taxonomy):
    path = tmp_path / "bad.yaml"
    path.write_text("tracks: [unclosed", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML"):
        load_mapping(path, small_taxonomy)


def test_shipped_mapping_is_valid_and_has_a_rule_for_every_taxonomy_skill():
    taxonomy = load_taxonomy("config/taxonomy_fy27.yaml")
    mapping = load_mapping("config/learn_mapping.yaml", taxonomy)
    ruled = {r.skill for r in mapping.rules}
    every = {s.id for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)}
    assert ruled == every
```

Run → FAIL.

- [ ] **Step 2: Implement** — `backend/src/skillgap/learn_mapping.py`

```python
"""Regras item → skill da taxonomia para itens da Microsoft Learn (código, sem modelo).

Uma skill casa com um item quando (produto da trilha E palavra-chave em título/resumo) OU
(frase forte no título, sem exigir produto — o caso das certificações, que não têm produto).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from skillgap.learn_catalog import SOURCE, LearnItem
from skillgap.recommender import Course
from skillgap.taxonomy import Taxonomy, normalize


@dataclass(frozen=True)
class SkillRule:
    skill: str
    track: str
    keywords: tuple[str, ...]
    strong: tuple[str, ...]


@dataclass(frozen=True)
class Mapping:
    track_products: dict[str, frozenset[str]]
    rules: tuple[SkillRule, ...]


@dataclass
class MappingReport:
    total: int = 0
    matched: dict[str, list[str]] = field(default_factory=dict)
    dropped: list[tuple[str, str, str]] = field(default_factory=list)
    uncovered: list[str] = field(default_factory=list)


def load_mapping(path: str | Path, taxonomy: Taxonomy) -> Mapping:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: YAML inválido: {exc}") from exc
    valid = {s.id: s.track for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)}
    problems: list[str] = []
    track_products: dict[str, frozenset[str]] = {}
    for tid, cfg in (data.get("tracks") or {}).items():
        if tid not in taxonomy.tracks:
            problems.append(f"trilha '{tid}' não existe na taxonomia")
        track_products[tid] = frozenset((cfg or {}).get("products") or [])
    rules: list[SkillRule] = []
    for sid, cfg in (data.get("skills") or {}).items():
        cfg = cfg or {}
        if sid not in valid:
            problems.append(f"skill '{sid}' não existe na taxonomia")
            continue
        track = valid[sid]
        if track not in track_products:
            problems.append(f"skill '{sid}': a trilha '{track}' não está em 'tracks'")
        keywords = tuple(cfg.get("keywords") or [])
        strong = tuple(cfg.get("strong") or [])
        if not keywords and not strong:
            problems.append(f"skill '{sid}': defina 'keywords' ou 'strong'")
        rules.append(SkillRule(sid, track, keywords, strong))
    if problems:
        raise ValueError(f"{path}: mapeamento inválido:\n  " + "\n  ".join(problems))
    return Mapping(track_products, tuple(rules))


def _contains(haystack: str, phrase: str) -> bool:
    return bool(phrase) and f" {phrase} " in f" {haystack} "


def match_item(item: LearnItem, mapping: Mapping) -> tuple[str, tuple[str, ...]] | None:
    title = normalize(item.title)
    body = normalize(f"{item.title} {item.summary}")
    products = set(item.products)
    hits: dict[str, list[str]] = {}
    for rule in mapping.rules:
        in_track = bool(mapping.track_products.get(rule.track, frozenset()) & products)
        by_keyword = in_track and any(_contains(body, normalize(k)) for k in rule.keywords)
        by_strong = any(_contains(title, normalize(k)) for k in rule.strong)
        if by_keyword or by_strong:
            hits.setdefault(rule.track, []).append(rule.skill)
    if not hits:
        return None
    order = list(mapping.track_products)
    track = max(hits, key=lambda t: (len(hits[t]), -order.index(t) if t in order else 0))
    return track, tuple(hits[track])


def to_courses(items: list[LearnItem], mapping: Mapping, taxonomy: Taxonomy,
               dropped_before=()) -> tuple[list[Course], MappingReport]:
    report = MappingReport(total=len(items) + len(dropped_before), dropped=list(dropped_before))
    courses: list[Course] = []
    for item in items:
        hit = match_item(item, mapping)
        if hit is None:
            report.dropped.append((item.uid, item.title, "sem skill casada"))
            continue
        track, skills = hit
        for skill in skills:
            report.matched.setdefault(skill, []).append(item.title)
        courses.append(Course(
            id=f"learn:{item.uid}", title=item.title, skills=skills, level=item.level,
            hours=item.hours, link=item.url, platform=track, focus=item.summary[:200],
            provider="Microsoft Learn", kind=item.kind, source=SOURCE, verified=True,
            exam_codes=item.exam_codes))
    every = [s.id for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)]
    report.uncovered = [sid for sid in every if sid not in report.matched]
    return courses, report


def render_report(report: MappingReport, taxonomy: Taxonomy) -> str:
    names = {s.id: s.name for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)}
    kept = sum(len(v) for v in report.matched.values())
    lines = [
        "# Relatório de mapeamento Microsoft Learn",
        "",
        f"Itens lidos: {report.total} · vínculos item→skill: {kept} · descartados: {len(report.dropped)}",
        "",
        "## Itens por skill",
    ]
    for skill, titles in sorted(report.matched.items()):
        lines.append(f"- {skill} ({names.get(skill, skill)}): {len(titles)}")
    lines += ["", "## Skills sem nenhum item"]
    lines += [f"- {s} ({names.get(s, s)})" for s in report.uncovered] or ["- nenhuma"]
    lines += ["", "## Descartados"]
    by_reason: dict[str, int] = {}
    for _, _, why in report.dropped:
        by_reason[why] = by_reason.get(why, 0) + 1
    lines += [f"- {why}: {n}" for why, n in sorted(by_reason.items())] or ["- nenhum"]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 3: Write `backend/config/learn_mapping.yaml`** (ponto de partida; o relatório existe para afinar)

```yaml
# Regras item da Microsoft Learn -> skill da taxonomia. Aplicadas por código (sem modelo).
# Uma skill casa quando: (produto da trilha E uma keyword em título/resumo) OU (frase 'strong' no título).
# Frases são comparadas sem acento/caixa/pontuação e com fronteira de palavra ("multi-agent" = "multi agent").
# Edite livremente e rode:  python -m skillgap.cli catalog sync-learn --report relatorio.md
version: 1
tracks:
  foundry:
    products: [microsoft-foundry, foundry-agent-service, foundry-tools, azure-openai]
  fabric:
    products: [fabric]
  databricks:
    products: [azure-databricks]
skills:
  foundry.platform:
    keywords: [get started, fundamentals, introduction, overview, portal]
  foundry.models:
    keywords: [model catalog, deploy, deployment, azure openai, foundation model, language model, fine tune, fine tuning]
    strong: [azure ai engineer, azure ai cloud developer, azure ai apps and agents]
  foundry.agents:
    keywords: [agent, agents, agentic, multi agent, semantic kernel, autogen, agent framework]
    strong: [multi agent ai solutions, ai agent builder, azure ai apps and agents]
  foundry.rag:
    keywords: [rag, retrieval augmented, ai search, vector search, embeddings, grounding, knowledge base]
    strong: [azure ai engineer, azure ai apps and agents]
  foundry.prompt:
    keywords: [prompt, prompts, prompt flow, prompt engineering]
    strong: [azure ai engineer]
  foundry.safety:
    keywords: [content safety, responsible ai, responsible, safety, red teaming, guardrails, content filters]
  foundry.genaiops:
    keywords: [genaiops, llmops, evaluate, evaluation, evaluations, monitoring, tracing, observability, generative ai operations]
  fabric.platform:
    keywords: [get started, fundamentals, introduction, overview, workspace, administer, fabric capacity, governance]
    strong: [fabric data engineer, fabric analytics engineer]
  fabric.lakehouse:
    keywords: [lakehouse, onelake, delta lake, delta tables, medallion]
    strong: [fabric data engineer]
  fabric.pipelines:
    keywords: [data factory, pipeline, pipelines, dataflow, dataflows, data pipelines, ingest, copy data, orchestration]
    strong: [fabric data engineer]
  fabric.warehouse:
    keywords: [warehouse, data warehouse, t sql, sql analytics endpoint, dimensional]
    strong: [fabric data engineer, fabric analytics engineer]
  fabric.realtime:
    keywords: [real time, real time intelligence, eventstream, eventstreams, eventhouse, event house, kql, kusto, activator]
  fabric.powerbi:
    keywords: [power bi, semantic model, semantic models, direct lake, dax, data visualization, dashboards, reports]
    strong: [fabric analytics engineer]
  fabric.ai:
    keywords: [data science, machine learning, copilot, data agent, ai skill, ai skills, mlflow]
  databricks.platform:
    keywords: [get started, fundamentals, introduction, workspace, cluster, clusters, compute]
    strong: [databricks data engineer]
  databricks.spark:
    keywords: [spark, pyspark, spark sql, dataframes, data frames]
    strong: [databricks data engineer]
  databricks.delta:
    keywords: [delta lake, delta tables, delta live tables, lakeflow, declarative pipelines, medallion, lakehouse]
    strong: [databricks data engineer]
  databricks.unity:
    keywords: [unity catalog, governance, data governance, lineage]
    strong: [databricks data engineer]
  databricks.workflows:
    keywords: [workflows, jobs, lakeflow jobs, orchestration, orchestrate, ci cd, asset bundles, deployment]
    strong: [databricks data engineer]
  databricks.mlflow:
    keywords: [mlflow, machine learning, model serving, feature store, mlops]
  databricks.genai:
    keywords: [generative ai, genai, llm, llms, vector search, rag, agent bricks, mosaic ai, ai agents]
```

- [ ] **Step 4: Run** `cd backend && .venv/bin/python -m pytest tests/test_learn_mapping.py tests/test_learn_catalog.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/skillgap/learn_mapping.py backend/config/learn_mapping.yaml backend/tests/test_learn_mapping.py
git commit -m "feat(learn): regras item→skill e relatório de mapeamento

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Settings e comando `catalog sync-learn`

**Files:**
- Modify: `backend/src/skillgap/config.py`
- Modify: `backend/src/skillgap/cli.py`
- Create: `backend/tests/test_cli_learn.py`
- Modify: `backend/tests/test_config.py` (só se comparar `Settings` campo a campo)

**Interfaces:**
- Consumes: `fetch_catalog`, `normalize_catalog` (T2); `load_mapping`, `to_courses`, `render_report` (T3); `CatalogStore.sync_learn` (T1).
- Produces: `Settings.learn_mapping_path = "config/learn_mapping.yaml"`, `Settings.learn_locale = "en-us"`, `Settings.learn_mcp: bool = False` (dataclass) e `load_settings()` lendo `SKILLGAP_LEARN_MAPPING`, `SKILLGAP_LEARN_LOCALE`, `SKILLGAP_LEARN_MCP` (`"0"` desliga; qualquer outro valor liga; ausente liga); `main(argv, service=None, settings=None, learn_fetch=None)`; subcomando `catalog sync-learn [--locale L] [--report ARQ]`.

- [ ] **Step 1: Failing tests** — `backend/tests/test_cli_learn.py`

```python
import pytest

from skillgap.cli import main
from skillgap.config import Settings, load_settings
from skillgap.catalog_store import CatalogStore
from learn_fixtures import catalog_payload

TAXONOMY = "config/taxonomy_fy27.yaml"
SHIPPED = "config/catalog_fy27.csv"


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "s.db"), taxonomy_path=TAXONOMY, catalog_path=SHIPPED,
                    learn_mapping_path="config/learn_mapping.yaml")


def payload_for_real_taxonomy():
    p = catalog_payload()
    p["learningPaths"][0]["products"] = ["fabric"]  # já é fabric: casa fabric.lakehouse
    return p


def run(settings, payload, *extra):
    return main(["catalog", "sync-learn", *extra], settings=settings, learn_fetch=lambda locale: payload)


def test_sync_seeds_manual_catalog_first_then_adds_learn_items(settings, capsys):
    assert run(settings, payload_for_real_taxonomy()) == 0
    out = capsys.readouterr().out
    assert "Sincronização concluída" in out and "inserido(s)" in out
    store = CatalogStore(settings.db_path)
    ids = {c.id for c in store.list_courses()}
    assert "foundry-rag" in ids  # os 26 manuais continuam
    assert any(i.startswith("learn:") for i in ids)
    assert store.learn_status()["last_sync"]


def test_second_sync_is_idempotent_and_retires_what_left(settings, capsys):
    p = payload_for_real_taxonomy()
    assert run(settings, p) == 0
    capsys.readouterr()
    p["learningPaths"].pop(0)
    assert run(settings, p) == 0
    assert "1 aposentado(s)" in capsys.readouterr().out
    store = CatalogStore(settings.db_path)
    assert "learn:learn.fabric.lakehouse" not in {c.id for c in store.list_courses()}
    assert store.get("learn:learn.fabric.lakehouse").retired is True


def test_empty_result_does_not_retire_the_existing_learn_catalog(settings, capsys):
    assert run(settings, payload_for_real_taxonomy()) == 0
    before = CatalogStore(settings.db_path).learn_status()["items"]
    capsys.readouterr()
    assert run(settings, {}) == 1
    assert "nada foi alterado" in capsys.readouterr().out
    assert CatalogStore(settings.db_path).learn_status()["items"] == before


def test_fetch_failure_exits_1_and_changes_nothing(settings, capsys):
    def boom(locale):
        raise ValueError("Não foi possível baixar o catálogo da Microsoft Learn: sem rede")

    assert main(["catalog", "sync-learn"], settings=settings, learn_fetch=boom) == 1
    assert "ERRO" in capsys.readouterr().out
    assert CatalogStore(settings.db_path).learn_status()["items"] == 0


def test_report_goes_to_a_file_when_requested(settings, tmp_path, capsys):
    report = tmp_path / "r.md"
    assert run(settings, payload_for_real_taxonomy(), "--report", str(report)) == 0
    text = report.read_text(encoding="utf-8")
    assert "Skills sem nenhum item" in text
    assert "Skills sem nenhum item" not in capsys.readouterr().out


def test_locale_flag_is_passed_to_the_fetcher(settings):
    seen = []
    main(["catalog", "sync-learn", "--locale", "pt-br"], settings=settings,
         learn_fetch=lambda locale: seen.append(locale) or payload_for_real_taxonomy())
    assert seen == ["pt-br"]


def test_settings_from_env(monkeypatch):
    monkeypatch.delenv("SKILLGAP_LEARN_MCP", raising=False)
    assert load_settings().learn_mcp is True and Settings().learn_mcp is False
    monkeypatch.setenv("SKILLGAP_LEARN_MCP", "0")
    assert load_settings().learn_mcp is False
    monkeypatch.setenv("SKILLGAP_LEARN_LOCALE", "pt-br")
    monkeypatch.setenv("SKILLGAP_LEARN_MAPPING", "x.yaml")
    s = load_settings()
    assert (s.learn_locale, s.learn_mapping_path) == ("pt-br", "x.yaml")
```

Run → FAIL.

- [ ] **Step 2: Settings** — `backend/src/skillgap/config.py`: adicionar à dataclass

```python
    learn_mapping_path: str = "config/learn_mapping.yaml"
    learn_locale: str = "en-us"
    learn_mcp: bool = False  # a dataclass não liga a rede sozinha; load_settings() liga
```

e em `load_settings()` (dentro do `Settings(...)`):

```python
        learn_mapping_path=os.environ.get("SKILLGAP_LEARN_MAPPING", defaults.learn_mapping_path),
        learn_locale=os.environ.get("SKILLGAP_LEARN_LOCALE", defaults.learn_locale),
        learn_mcp=os.environ.get("SKILLGAP_LEARN_MCP", "1").strip() != "0",
```

- [ ] **Step 3: CLI** — `backend/src/skillgap/cli.py`

Imports novos: `from datetime import date`, `from skillgap.learn_catalog import fetch_catalog, normalize_catalog`, `from skillgap.learn_mapping import load_mapping, render_report, to_courses`.

Em `_parser()`, depois do parser `exp`:

```python
    sync = csub.add_parser("sync-learn", help="Sincroniza o catálogo oficial da Microsoft Learn")
    sync.add_argument("--locale", help="Idioma do catálogo (padrão: SKILLGAP_LEARN_LOCALE ou en-us)")
    sync.add_argument("--report", help="Grava o relatório de mapeamento neste arquivo (.md)")
```

Assinatura: `def _catalog_main(args, settings: Settings, learn_fetch=None) -> int:` e `main(..., settings=None, learn_fetch=None)` repassando `_catalog_main(args, settings or load_settings(), learn_fetch)`.

No `_catalog_main`, dentro do `try`, após a linha `store.seed_from_csv_if_empty(...)` (o seed precisa vir ANTES, para o catálogo manual não ser perdido) e antes de `if cmd == "list":`, inserir um ramo (converter o `if cmd == "list"` seguinte em `elif` se necessário):

```python
        if cmd == "sync-learn":
            fetch = learn_fetch or fetch_catalog
            payload = fetch(args.locale or settings.learn_locale)
            items, dropped = normalize_catalog(payload)
            mapping = load_mapping(settings.learn_mapping_path, taxonomy)
            courses, report = to_courses(items, mapping, taxonomy, dropped)
            if not courses:
                raise ValueError("A sincronização não trouxe nenhum item mapeado; "
                                 "nada foi alterado no catálogo.")
            validate_courses(courses, taxonomy)
            counts = store.sync_learn(courses, date.today().isoformat())
            print(f"Sincronização concluída: {counts['inserted']} inserido(s), "
                  f"{counts['updated']} atualizado(s), {counts['retired']} aposentado(s). "
                  f"Descartados: {len(report.dropped)}.")
            text = render_report(report, taxonomy)
            if args.report:
                Path(args.report).write_text(text, encoding="utf-8")
                print(f"Relatório gravado em {args.report}")
            else:
                print(text)
            return 0
```

- [ ] **Step 4: Run** `cd backend && .venv/bin/python -m pytest tests/test_cli_learn.py tests/test_cli_catalog.py tests/test_cli.py tests/test_config.py -q` → PASS (ajustar `test_config` só se comparar a dataclass inteira).

- [ ] **Step 5: Commit**

```bash
git add backend/src/skillgap/config.py backend/src/skillgap/cli.py backend/tests/test_cli_learn.py backend/tests/test_config.py
git commit -m "feat(cli): catalog sync-learn com relatório e proteção contra sync vazio

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Recomendador e modelos (`Recommendation`, desempate, gaps sem item)

**Files:**
- Modify: `backend/src/skillgap/models.py`
- Modify: `backend/src/skillgap/recommender.py`
- Modify: `backend/tests/test_recommender.py`

**Interfaces:**
- Produces: `Recommendation.exam_codes: list[str] = []`, `.source: str | None = None`, `.synced_at: str | None = None`, `.match_origin: str | None = None`; `uncovered_gaps(gaps: list[Gap], courses: list[Course]) -> list[str]` (skills em gap sem nenhum curso que as cubra no nível, ordenadas por severidade desc, estável); `recommend()` desempata por verificado antes de horas.

- [ ] **Step 1: Failing tests** — acrescentar a `backend/tests/test_recommender.py`

```python
from skillgap.recommender import uncovered_gaps


def test_verified_items_win_ties_before_hours():
    gaps = [gap("a", 0, 2, "high")]
    manual = Course("m", "Manual", ("a",), 1, 2, "", verified=False)
    official = Course("learn:o", "Oficial", ("a",), 1, 30, "https://learn.microsoft.com/o", verified=True)
    assert [r.course_id for r in recommend(gaps, [manual, official])] == ["learn:o", "m"]


def test_recommendation_carries_provenance_for_learn_items():
    gaps = [gap("a", 0, 2, "high")]
    c = Course("learn:o", "Cert", ("a",), 2, None, "https://learn.microsoft.com/o", provider="Microsoft Learn",
               kind="certificação", source="Microsoft Learn Catalog API", verified=True,
               exam_codes=("AI-500",), synced_at="2026-09-30")
    [r] = recommend(gaps, [c])
    assert (r.exam_codes, r.source, r.synced_at, r.match_origin) == (
        ["AI-500"], "Microsoft Learn Catalog API", "2026-09-30", "rule")
    [m] = recommend(gaps, [course("x", ["a"])])
    assert m.exam_codes == [] and m.source is None and m.synced_at is None and m.match_origin == "manual"


def test_uncovered_gaps_lists_skills_no_course_can_teach_by_severity():
    gaps = [gap("low1", 0, 2, "low"), gap("hi", 0, 2, "high"), gap("ok", 0, 2, "medium"),
            gap("tooadv", 2, 3, "high")]
    courses = [course("c", ["ok"]), course("basic", ["tooadv"], level=1)]  # 'basic' não ensina quem já está no nível 2
    assert uncovered_gaps(gaps, courses) == ["hi", "tooadv", "low1"]


def test_uncovered_gaps_ignores_courses_when_none_are_given():
    assert uncovered_gaps([gap("a", 0, 2, "high")], []) == ["a"]
    assert uncovered_gaps([], [course("c", ["a"])]) == []
```

Run → FAIL.

- [ ] **Step 2: Models** — `models.py`, dentro de `Recommendation`, ao final:

```python
    exam_codes: list[str] = []  # só quando o catálogo os informa
    source: str | None = None  # ex.: "Microsoft Learn Catalog API"; None = lista manual/antigo
    synced_at: str | None = None  # data ISO da sincronização
    match_origin: str | None = None  # "rule" (regra) | "manual"; None = resultados antigos
```

- [ ] **Step 3: Recommender** — em `recommend()` trocar a chave de ordenação e o construtor:

```python
    scored.sort(key=lambda item: (-item[0], not item[1].verified, item[1].hours is None,
                                  item[1].hours or 0, item[1].id))
    return [
        Recommendation(course_id=c.id, title=c.title, covers=covers, hours=c.hours, link=c.link,
                       provider=c.provider or None, kind=c.kind or None, verified=c.verified,
                       level=c.level, platform=c.platform or None,
                       exam_codes=list(c.exam_codes), source=c.source or None,
                       synced_at=c.synced_at or None, match_origin=c.match_origin)
        for _, c, covers in scored[:limit]
    ]
```

e a nova função (ao final do arquivo):

```python
def uncovered_gaps(gaps: list[Gap], courses: list[Course]) -> list[str]:
    """Skills em gap que nenhum curso do catálogo cobre no nível certo (mais graves primeiro)."""
    ordered = sorted(gaps, key=lambda g: -WEIGHT[g.severity])
    return [g.skill for g in ordered
            if not any(g.skill in c.skills and c.level >= g.current for c in courses)]
```

- [ ] **Step 4: Run** `cd backend && .venv/bin/python -m pytest tests/test_recommender.py tests/test_models.py tests/test_catalog_pipeline.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/skillgap/models.py backend/src/skillgap/recommender.py backend/tests/test_recommender.py
git commit -m "feat(recommender): proveniência Learn, desempate por verificado e gaps sem item

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `learn_mcp.py` — cliente MCP, cache e Supplementer

**Files:**
- Modify: `backend/src/skillgap/models.py` (modelo `Supplementary`)
- Create: `backend/src/skillgap/learn_mcp.py`
- Create: `backend/tests/test_learn_mcp.py`

**Interfaces:**
- Produces: `Supplementary(skill: str, title: str, url: str)` em `models.py`; `DocHit(title, url)`; `McpError`; `http_transport(body, session_id, *, url=MCP_URL, timeout=8.0, opener=urlopen) -> (dict | None, str | None)`; `LearnMcpClient(transport=http_transport).search(query, limit=3) -> list[DocHit]`; `McpCache(path, ttl=604800, clock=time.time)` com `.get(query) -> list[DocHit] | None`, `.put(query, hits)`, `.close()`; `Supplementer(client, cache, taxonomy, enabled=True)` chamável: `(skill_ids: list[str]) -> tuple[list[Supplementary], str]` com status em `{"ok", "none", "unavailable", "disabled"}`; `learn_url(url) -> str`.

- [ ] **Step 1: Failing tests** — `backend/tests/test_learn_mcp.py`

```python
import json

import pytest

from skillgap.learn_mcp import (DocHit, LearnMcpClient, McpCache, McpError, Supplementer,
                                http_transport, learn_url)


def sse(obj):
    return "event: message\ndata: " + json.dumps(obj) + "\n\n"


def search_result(rows):
    return {"jsonrpc": "2.0", "id": 2, "result": {"content": [
        {"type": "text", "text": json.dumps({"results": rows})}]}}


class FakeTransport:
    """Simula o servidor: initialize devolve sessão; tools/call devolve ``rows``."""

    def __init__(self, rows=None, fail=False):
        self.rows, self.fail, self.calls = rows or [], fail, []

    def __call__(self, body, session_id):
        self.calls.append((body, session_id))
        if self.fail:
            raise McpError("MCP indisponível: timeout")
        method = body.get("method")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": body["id"], "result": {"serverInfo": {"name": "x"}}}, "sess-1"
        if method == "notifications/initialized":
            return None, session_id
        return search_result(self.rows), session_id


ROWS = [
    {"title": "Implement a Lakehouse", "content": "# md", "contentUrl": "https://learn.microsoft.com/en-us/training/paths/a/"},
    {"title": "Dup", "content": "", "contentUrl": "https://learn.microsoft.com/en-us/training/paths/a/"},
    {"title": "Evil", "content": "", "contentUrl": "https://evil.example.com/x"},
    {"title": "", "content": "", "contentUrl": "https://learn.microsoft.com/no-title"},
    {"title": "Second", "content": "", "contentUrl": "https://learn.microsoft.com/en-us/training/paths/b/?x=1#f"},
    "garbage",
]


def test_handshake_then_search_filters_domain_dupes_and_limits():
    t = FakeTransport(ROWS)
    hits = LearnMcpClient(t).search("fabric lakehouse", limit=5)
    assert hits == [DocHit("Implement a Lakehouse", "https://learn.microsoft.com/en-us/training/paths/a/"),
                    DocHit("Second", "https://learn.microsoft.com/en-us/training/paths/b/?x=1")]
    methods = [c[0].get("method") for c in t.calls]
    assert methods == ["initialize", "notifications/initialized", "tools/call"]
    assert t.calls[2][1] == "sess-1"  # o id de sessão volta nas chamadas seguintes
    assert t.calls[2][0]["params"] == {"name": "microsoft_docs_search", "arguments": {"query": "fabric lakehouse"}}


def test_session_is_opened_once_and_limit_applies():
    t = FakeTransport(ROWS)
    c = LearnMcpClient(t)
    assert len(c.search("a", limit=1)) == 1
    c.search("b")
    assert [x[0].get("method") for x in t.calls].count("initialize") == 1


def test_transport_failure_raises_and_next_search_reopens_the_session():
    t = FakeTransport(ROWS)
    c = LearnMcpClient(t)
    c.search("a")
    t.fail = True
    with pytest.raises(McpError):
        c.search("b")
    t.fail = False
    c.search("c")
    assert [x[0].get("method") for x in t.calls].count("initialize") == 2


@pytest.mark.parametrize("bad", [{"jsonrpc": "2.0", "id": 2, "result": {"content": []}},
                                 {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "not json"}]}}])
def test_malformed_results(bad):
    class T(FakeTransport):
        def __call__(self, body, sid):
            if body.get("method") == "tools/call":
                return bad, sid
            return super().__call__(body, sid)

    c = LearnMcpClient(T())
    try:
        assert c.search("x") == []
    except McpError:
        pass  # texto que não é JSON deve virar McpError, nunca outra exceção


def test_learn_url():
    assert learn_url("https://learn.microsoft.com/a/b?view=x#frag") == "https://learn.microsoft.com/a/b?view=x"
    for bad in ("http://learn.microsoft.com/a", "https://learn.microsoft.com.evil.com/a", "ftp://x", None, 5, ""):
        assert learn_url(bad) == ""


class FakeResp:
    def __init__(self, body, sid=None):
        self._b, self.headers = body, ({"Mcp-Session-Id": sid} if sid else {})

    def read(self, n=-1):
        return self._b if n < 0 else self._b[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_transport_parses_sse_and_plain_json_and_session_header():
    body, sid = http_transport({"a": 1}, None, opener=lambda r, timeout: FakeResp(sse({"result": {}}).encode(), "s9"))
    assert body == {"result": {}} and sid == "s9"
    body, sid = http_transport({"a": 1}, "keep", opener=lambda r, timeout: FakeResp(b'{"result": {"x": 1}}'))
    assert body == {"result": {"x": 1}} and sid == "keep"
    assert http_transport({"a": 1}, None, opener=lambda r, timeout: FakeResp(b""))[0] is None


def test_http_transport_errors_become_mcp_error():
    def down(r, timeout):
        raise OSError("boom")

    with pytest.raises(McpError):
        http_transport({}, None, opener=down)
    with pytest.raises(McpError):
        http_transport({}, None, opener=lambda r, timeout: FakeResp(b"<html>"))
    with pytest.raises(McpError, match="grande demais"):
        http_transport({}, None, opener=lambda r, timeout: FakeResp(b"x" * (2 * 1024 * 1024 + 5)))


def test_cache_hit_expiry_and_corrupt_row(tmp_path):
    now = [1000.0]
    cache = McpCache(str(tmp_path / "c.db"), ttl=10, clock=lambda: now[0])
    assert cache.get("q") is None
    cache.put("q", [DocHit("T", "https://learn.microsoft.com/t")])
    assert cache.get("q") == [DocHit("T", "https://learn.microsoft.com/t")]
    now[0] = 1011.0
    assert cache.get("q") is None
    cache._db.execute("INSERT OR REPLACE INTO mcp_cache VALUES ('bad', ?, 'not json')", (now[0],))
    assert cache.get("bad") is None


def make(tmp_path, taxonomy, transport, enabled=True):
    return Supplementer(LearnMcpClient(transport), McpCache(str(tmp_path / "c.db")), taxonomy, enabled)


def test_supplementer_queries_only_taxonomy_names_and_caches(tmp_path, small_taxonomy):
    t = FakeTransport(ROWS)
    sup = make(tmp_path, small_taxonomy, t)
    found, status = sup(["fabric.lakehouse"])
    assert status == "ok" and [s.skill for s in found] == ["fabric.lakehouse"] * 2
    assert found[0].url.startswith("https://learn.microsoft.com/")
    query = [c[0] for c in t.calls if c[0].get("method") == "tools/call"][0]["params"]["arguments"]["query"]
    assert query == "Lakehouse Microsoft Fabric training"  # nome da skill + nome da trilha, nada mais
    n = len(t.calls)
    sup(["fabric.lakehouse"])
    assert len(t.calls) == n  # segunda vez vem do cache


def test_supplementer_statuses(tmp_path, small_taxonomy):
    assert make(tmp_path, small_taxonomy, FakeTransport(ROWS), enabled=False)(["fabric.lakehouse"]) == ([], "disabled")
    assert make(tmp_path, small_taxonomy, FakeTransport(ROWS))([]) == ([], "none")
    assert make(tmp_path, small_taxonomy, FakeTransport([]))(["fabric.lakehouse"]) == ([], "none")
    assert make(tmp_path, small_taxonomy, FakeTransport(ROWS, fail=True))(["fabric.lakehouse"]) == ([], "unavailable")
    assert make(tmp_path, small_taxonomy, FakeTransport(ROWS))(["not.a.skill"]) == ([], "none")


def test_supplementer_stops_after_the_first_network_failure_and_caps_skills(tmp_path, small_taxonomy):
    t = FakeTransport(ROWS, fail=True)
    make(tmp_path, small_taxonomy, t)(["fabric.lakehouse", "fabric.pipelines", "foundry.agents"])
    assert len(t.calls) == 1  # não insiste em cada skill quando a rede caiu
    t2 = FakeTransport(ROWS)
    skills = ["fabric.lakehouse", "fabric.pipelines", "foundry.agents", "foundry.models", "databricks.spark"]
    make(tmp_path, small_taxonomy, t2)(skills)
    assert sum(1 for c in t2.calls if c[0].get("method") == "tools/call") <= 4
```

Run → FAIL.

- [ ] **Step 2: Model** — `models.py` (antes de `CandidateResult`):

```python
class Supplementary(BaseModel):
    """Link de documentação achado pela busca da Microsoft Learn. Não é curso e não tem nível."""
    skill: str
    title: str
    url: str
```

- [ ] **Step 3: Implement** — `backend/src/skillgap/learn_mcp.py`

```python
"""Busca complementar via MCP da Microsoft Learn (documentação, sem nível).

Só o nome de skills da taxonomia sai daqui; nunca texto do CV. Qualquer falha vira status
``unavailable``, nunca erro para o usuário.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from skillgap.models import Supplementary
from skillgap.taxonomy import Taxonomy

MCP_URL = "https://learn.microsoft.com/api/mcp"
PROTOCOL = "2025-03-26"
ALLOWED_HOST = "learn.microsoft.com"
MAX_BYTES = 2 * 1024 * 1024
MAX_SKILLS = 4
HITS_PER_SKILL = 3
CACHE_TTL = 7 * 24 * 3600

Transport = Callable[[dict, "str | None"], "tuple[dict | None, str | None]"]


class McpError(Exception):
    pass


@dataclass(frozen=True)
class DocHit:
    title: str
    url: str


def learn_url(url: object) -> str:
    """https em learn.microsoft.com; mantém a query (``?view=``), remove o fragmento."""
    if not isinstance(url, str):
        return ""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return ""
    if (parts.scheme != "https" or parts.hostname != ALLOWED_HOST
            or parts.username or parts.password or port not in (None, 443)):
        return ""
    return urlunsplit(("https", ALLOWED_HOST, parts.path, parts.query, ""))


def _parse(raw: str) -> dict | None:
    if not raw.strip():
        return None
    match = re.search(r"^data: (.*)$", raw, re.M)
    try:
        value = json.loads(match.group(1) if match else raw)
    except ValueError as exc:
        raise McpError("resposta do MCP não é JSON") from exc
    return value if isinstance(value, dict) else None


def http_transport(body: dict, session_id: str | None, *, url: str = MCP_URL,
                   timeout: float = 8.0, opener=urllib.request.urlopen):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(url, json.dumps(body).encode("utf-8"), headers, method="POST")
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
            new_id = response.headers.get("Mcp-Session-Id") or session_id
    except OSError as exc:
        raise McpError(f"MCP indisponível: {exc}") from exc
    if len(raw) > MAX_BYTES:
        raise McpError("resposta do MCP grande demais")
    return _parse(raw.decode("utf-8", "replace")), new_id


class LearnMcpClient:
    def __init__(self, transport: Transport = http_transport):
        self._transport = transport
        self._session: str | None = None
        self._ready = False
        self._next_id = 0
        self._lock = threading.Lock()

    def _rpc(self, method: str, params: dict) -> dict:
        self._next_id += 1
        reply, session = self._transport(
            {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}, self._session)
        if session:
            self._session = session
        if not reply or not isinstance(reply.get("result"), dict):
            raise McpError(f"MCP sem resultado para {method}")
        return reply["result"]

    def _open(self) -> None:
        if self._ready:
            return
        self._rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                 "clientInfo": {"name": "skillgap", "version": "1"}})
        self._transport({"jsonrpc": "2.0", "method": "notifications/initialized"}, self._session)
        self._ready = True

    def search(self, query: str, limit: int = HITS_PER_SKILL) -> list[DocHit]:
        with self._lock:
            try:
                self._open()
                result = self._rpc("tools/call", {"name": "microsoft_docs_search",
                                                  "arguments": {"query": query}})
            except McpError:
                self._ready = False  # a sessão pode ter expirado: reabre na próxima
                self._session = None
                raise
        text = next((c.get("text") for c in result.get("content") or []
                     if isinstance(c, dict) and c.get("type") == "text"), None)
        if not text:
            return []
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise McpError("resultado do MCP não é JSON") from exc
        rows = payload.get("results") if isinstance(payload, dict) else None
        hits: list[DocHit] = []
        seen: set[str] = set()
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            url = learn_url(row.get("contentUrl"))
            title = " ".join(str(row.get("title") or "").split())
            if not url or not title or url in seen:
                continue
            seen.add(url)
            hits.append(DocHit(title[:200], url))
            if len(hits) >= limit:
                break
        return hits


class McpCache:
    def __init__(self, path: str, ttl: float = CACHE_TTL, clock: Callable[[], float] = time.time):
        self._ttl, self._clock = ttl, clock
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        with self._lock:
            if path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("CREATE TABLE IF NOT EXISTS mcp_cache ("
                             "query TEXT PRIMARY KEY, fetched_at REAL NOT NULL, json TEXT NOT NULL)")
            self._db.commit()

    def get(self, query: str) -> list[DocHit] | None:
        with self._lock:
            row = self._db.execute("SELECT fetched_at, json FROM mcp_cache WHERE query = ?",
                                   (query,)).fetchone()
        if not row or self._clock() - row[0] > self._ttl:
            return None
        try:
            return [DocHit(**h) for h in json.loads(row[1])]
        except (ValueError, TypeError):
            return None

    def put(self, query: str, hits: list[DocHit]) -> None:
        payload = json.dumps([{"title": h.title, "url": h.url} for h in hits])
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO mcp_cache (query, fetched_at, json) VALUES (?, ?, ?)",
                             (query, self._clock(), payload))

    def close(self) -> None:
        with self._lock:
            self._db.close()


class Supplementer:
    def __init__(self, client: LearnMcpClient, cache: McpCache, taxonomy: Taxonomy,
                 enabled: bool = True):
        self._client, self._cache, self._taxonomy, self.enabled = client, cache, taxonomy, enabled

    def __call__(self, skill_ids: list[str]) -> tuple[list[Supplementary], str]:
        if not self.enabled:
            return [], "disabled"
        if not skill_ids:
            return [], "none"
        found: list[Supplementary] = []
        failed = False
        for sid in skill_ids[:MAX_SKILLS]:
            skill = self._taxonomy.match(sid)
            if skill is None:
                continue
            query = f"{skill.name} {self._taxonomy.tracks[skill.track]} training"
            hits = self._cache.get(query)
            if hits is None:
                try:
                    hits = self._client.search(query)
                except Exception:  # rede/protocolo: não insiste nas demais skills
                    failed = True
                    break
                self._cache.put(query, hits)
            found.extend(Supplementary(skill=sid, title=h.title, url=h.url) for h in hits)
        if found:
            return found, "ok"
        return [], "unavailable" if failed else "none"
```


- [ ] **Step 4: Run** `cd backend && .venv/bin/python -m pytest tests/test_learn_mcp.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/skillgap/models.py backend/src/skillgap/learn_mcp.py backend/tests/test_learn_mcp.py
git commit -m "feat(learn): cliente MCP, cache e Supplementer com degradação silenciosa

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Pipeline, serviço, bootstrap e `CandidateResult`

**Files:**
- Modify: `backend/src/skillgap/models.py`
- Modify: `backend/src/skillgap/pipeline.py`
- Modify: `backend/src/skillgap/bootstrap.py`
- Create: `backend/tests/test_pipeline_learn.py`

**Interfaces:**
- Consumes: `uncovered_gaps` (T5); `Supplementary`, `Supplementer` (T6); `Settings.learn_mcp` (T4).
- Produces: `CandidateResult.supplementary: list[Supplementary] | None = None` e `.learn_status: str | None = None`; `Deps.supplement: Callable[[list[str]], tuple[list[Supplementary], str]] | None = None`; `run_pipeline` devolve também `supplementary` e `learn_status`.

- [ ] **Step 1: Failing tests** — `backend/tests/test_pipeline_learn.py`

```python
import pytest

from pdfs import make_text_pdf
from skillgap.catalog_store import CatalogStore
from skillgap.models import CandidateResult, ExtractedProfile, RawSkill, Supplementary
from skillgap.pipeline import Deps, run_pipeline
from skillgap.recommender import Course
from skillgap.taxonomy import load_taxonomy
from support import OPEN_STORES

CV = make_text_pdf(["Maria Silva", "Experience with Microsoft Fabric OneLake lakehouse projects."])


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy("config/taxonomy_fy27.yaml")


@pytest.fixture
def fabric_ids(taxonomy):
    return {s.id for s in taxonomy.skills_in_track("fabric")}


def extracted():
    return ExtractedProfile(candidate="Maria", skills=[
        RawSkill(name="Lakehouse", level=1, evidence="Experience with Microsoft Fabric")])


def catalog_with(courses):
    store = CatalogStore(":memory:")
    OPEN_STORES.append(store)
    store.upsert(courses)
    return store


LAKEHOUSE_ONLY = Course("lh", "Lakehouse", ("fabric.lakehouse",), 2, 3, "", platform="fabric")


def test_gaps_without_any_catalog_item_trigger_the_supplement_with_only_skill_ids(taxonomy, fabric_ids):
    calls = []

    def supplement(skill_ids):
        calls.append(list(skill_ids))
        return [Supplementary(skill=skill_ids[0], title="Doc", url="https://learn.microsoft.com/d")], "ok"

    deps = Deps(taxonomy, catalog_with([LAKEHOUSE_ONLY]).all_courses, lambda t, h: extracted(), supplement)
    fields = run_pipeline(CV, deps)
    assert len(calls) == 1 and calls[0]
    assert set(calls[0]) <= fabric_ids and "fabric.lakehouse" not in calls[0]  # só ids da taxonomia
    assert all(isinstance(x, str) and x in fabric_ids for x in calls[0])  # nunca texto do CV
    assert fields["learn_status"] == "ok" and fields["supplementary"][0].title == "Doc"
    assert [r.course_id for r in fields["recommendations"]] == ["lh"]


def test_when_the_catalog_covers_every_gap_the_supplement_gets_an_empty_list(taxonomy, fabric_ids):
    calls = []

    def supplement(skill_ids):
        calls.append(list(skill_ids))
        return [], "none"

    everything = Course("all", "Tudo", tuple(sorted(fabric_ids)), 3, 10, "", platform="fabric")
    deps = Deps(taxonomy, catalog_with([everything]).all_courses, lambda t, h: extracted(), supplement)
    fields = run_pipeline(CV, deps)
    assert calls == [[]] and fields["learn_status"] == "none" and fields["supplementary"] == []


def test_supplement_failure_never_breaks_the_pipeline(taxonomy):
    def boom(skill_ids):
        raise RuntimeError("rede caiu")

    courses = catalog_with([LAKEHOUSE_ONLY]).all_courses
    plain = run_pipeline(CV, Deps(taxonomy, courses, lambda t, h: extracted()))
    broken = run_pipeline(CV, Deps(taxonomy, courses, lambda t, h: extracted(), boom))
    assert broken["recommendations"] == plain["recommendations"]
    assert broken["learn_status"] == "unavailable" and broken["supplementary"] == []


def test_without_a_supplement_the_new_fields_stay_null(taxonomy):
    fields = run_pipeline(CV, Deps(taxonomy, catalog_with([LAKEHOUSE_ONLY]).all_courses, lambda t, h: extracted()))
    assert fields["supplementary"] is None and fields["learn_status"] is None


def test_old_records_load_and_new_fields_round_trip():
    old = CandidateResult(id="x")
    assert old.supplementary is None and old.learn_status is None
    new = CandidateResult(id="y", learn_status="ok", supplementary=[
        Supplementary(skill="a", title="t", url="https://learn.microsoft.com/t")])
    assert CandidateResult.model_validate_json(new.model_dump_json()) == new
```

Run: `cd backend && .venv/bin/python -m pytest tests/test_pipeline_learn.py -q` → FAIL.

- [ ] **Step 2: Models** — `CandidateResult`, ao final:

```python
    supplementary: list[Supplementary] | None = None  # None = não consultado / resultados antigos
    learn_status: str | None = None  # ok | none | unavailable | disabled; None = antigo
```

- [ ] **Step 3: Pipeline** — `pipeline.py`: importar `Supplementary` de `skillgap.models` e `uncovered_gaps` de `skillgap.recommender`; em `Deps` acrescentar, depois de `extract`:

```python
    supplement: Callable[[list[str]], tuple[list[Supplementary], str]] | None = None
```

Em `run_pipeline`, depois de `recommendations = recommend(gaps, courses)`:

```python
    supplementary: list[Supplementary] | None = None
    learn_status: str | None = None
    if deps.supplement is not None:
        # Só nomes de skills da taxonomia saem daqui; nunca texto do CV.
        try:
            supplementary, learn_status = deps.supplement(uncovered_gaps(gaps, courses))
        except Exception:
            supplementary, learn_status = [], "unavailable"
```

e no dicionário retornado: `"supplementary": supplementary, "learn_status": learn_status,`.

- [ ] **Step 4: Bootstrap** — `bootstrap.py`: importar `LearnMcpClient, McpCache, Supplementer` de `skillgap.learn_mcp`. Assinatura `build_service(settings, extract=None, keystore=None, supplement=None)`. Antes de criar `Deps`:

```python
    if supplement is None and settings.learn_mcp:
        supplement = Supplementer(LearnMcpClient(), McpCache(settings.db_path), taxonomy)
```

e passar `Deps(taxonomy, catalog.all_courses, extract, supplement)`.

- [ ] **Step 5: Run** `cd backend && .venv/bin/python -m pytest -q` → PASS (suíte inteira; corrigir só testes antigos que comparem o dict retornado por `run_pipeline` chave a chave, acrescentando as duas chaves novas).

- [ ] **Step 6: Commit**

```bash
git add backend/src/skillgap/models.py backend/src/skillgap/pipeline.py backend/src/skillgap/bootstrap.py backend/tests/test_pipeline_learn.py
git commit -m "feat(pipeline): leitura complementar via MCP para gaps sem item no catálogo

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: API — `CourseOut`, `/catalog/status` e ids com `:`/`.`

**Files:**
- Modify: `backend/src/skillgap/api.py`
- Modify: `backend/tests/test_api_catalog.py`

**Interfaces:**
- Produces: `CourseOut` ganha `exam_codes: list[str]`, `synced_at: str`, `retired: bool`, `match_origin: str`; `GET /catalog/status` → `CatalogStore.learn_status()` (registrado **antes** de `/catalog/{course_id}`).

- [ ] **Step 1: Failing tests** — acrescentar a `backend/tests/test_api_catalog.py` (reusa `COURSES`, `TestClient`, `create_app` e `make_service` já importados no arquivo)

```python
LEARN = Course("learn:learn.fabric.x", "Fabric X", ("fabric.lakehouse",), 2, 3,
               "https://learn.microsoft.com/x", platform="fabric", kind="certificação",
               provider="Microsoft Learn", source="Microsoft Learn Catalog API", verified=True,
               exam_codes=("DP-700",))


@pytest.fixture
def learn_client(small_taxonomy):
    service, _ = make_service(small_taxonomy)
    service.catalog.replace_all(COURSES)
    service.catalog.sync_learn([LEARN], "2026-09-30")
    return TestClient(create_app(service), base_url="http://localhost"), service.catalog


def test_status_route_reports_learn_items(learn_client):
    client, _ = learn_client
    body = client.get("/catalog/status").json()
    assert body == {"items": 1, "by_kind": {"certificação": 1}, "retired": 0, "last_sync": "2026-09-30"}


def test_ids_with_colon_and_dots_resolve_and_carry_provenance(learn_client):
    client, _ = learn_client
    r = client.get("/catalog/learn:learn.fabric.x")
    assert r.status_code == 200
    j = r.json()
    assert j["match_origin"] == "rule" and j["exam_codes"] == ["DP-700"]
    assert j["synced_at"] == "2026-09-30" and j["retired"] is False and j["verified"] is True


def test_retired_items_leave_the_list_but_can_still_be_fetched(learn_client):
    client, catalog = learn_client
    catalog.sync_learn([], "2026-10-01")
    assert "learn:learn.fabric.x" not in ids(client.get("/catalog"))
    j = client.get("/catalog/learn:learn.fabric.x").json()
    assert j["retired"] is True
    assert client.get("/catalog/status").json()["retired"] == 1


def test_manual_course_reports_manual_origin(client):
    j = client.get("/catalog/f1").json()
    assert j["match_origin"] == "manual" and j["exam_codes"] == [] and j["synced_at"] == "" and j["retired"] is False
```

Também atualizar o dict esperado de `f1` em `test_list_all_with_course_shape`: acrescentar `"exam_codes": [], "synced_at": "", "retired": False, "match_origin": "manual"`.

Run: `cd backend && .venv/bin/python -m pytest tests/test_api_catalog.py -q` → FAIL.

- [ ] **Step 2: Implement** — `CourseOut` e `course_out`:

```python
class CourseOut(BaseModel):
    ...  # campos existentes
    exam_codes: list[str]
    synced_at: str
    retired: bool
    match_origin: str
```

`course_out` passa `exam_codes=list(c.exam_codes), synced_at=c.synced_at, retired=c.retired, match_origin=c.match_origin`. Em `_add_catalog_routes`, entre `catalog_stats` e `get_course`:

```python
    @app.get("/catalog/status")
    def catalog_status():
        return catalog.learn_status()
```

- [ ] **Step 3: Run** `cd backend && .venv/bin/python -m pytest tests/test_api_catalog.py tests/test_api.py tests/test_api_guard.py tests/test_cli_catalog.py -q` → PASS (ajustar comparações exatas de `CourseOut` nos testes antigos, se houver).

- [ ] **Step 4: Commit**

```bash
git add backend/src/skillgap/api.py backend/tests/test_api_catalog.py
git commit -m "feat(api): proveniência Learn em CourseOut e GET /catalog/status

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Frontend — tipos, helpers, cartão do item e "Leitura complementar"

**Files:**
- Modify: `frontend/lib/types.ts`
- Create: `frontend/lib/learn.ts`
- Create: `frontend/lib/learn.check.mjs`
- Modify: `frontend/package.json` (script `check:learn`)
- Modify: `frontend/components/TrainingPlan.tsx`
- Create: `frontend/components/SupplementaryLinks.tsx`
- Modify: `frontend/components/CandidateCard.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/components/Footer.tsx`

**Interfaces:**
- Consumes: campos novos da API (T5, T7).
- Produces: `lib/learn.ts` exporta `kindLabel`, `certificationsLast`, `linkLabel`, `learnSourceLine`, `isLearnUrl`. Sem imports de outros módulos do projeto (o check compila só este arquivo).

- [ ] **Step 1: `frontend/lib/learn.ts`**

```ts
// Pure helpers for Microsoft Learn items. No project imports: the check compiles this file alone.

interface KindLike { kind?: string | null }
interface SourceLike { match_origin?: string | null; synced_at?: string | null }

const KIND_LABEL: Record<string, string> = {
  course: "curso", curso: "curso", trilha: "trilha",
  certification: "certificação", certificacao: "certificação", "certificação": "certificação",
  exam: "exame", exame: "exame",
};

export function kindLabel(kind: string | null | undefined): string {
  if (!kind) return "";
  return KIND_LABEL[kind.toLowerCase()] ?? kind;
}

const isMilestone = (kind: string | null | undefined) => {
  const k = kindLabel(kind);
  return k === "certificação" || k === "exame";
};

/** Stable partition: courses/trilhas first, certifications/exams last (groupByLevel then keeps this order inside each stage). */
export function certificationsLast<T extends KindLike>(items: readonly T[]): T[] {
  return [...items.filter((i) => !isMilestone(i.kind)), ...items.filter((i) => isMilestone(i.kind))];
}

export function linkLabel(kind: string | null | undefined): string {
  switch (kindLabel(kind)) {
    case "certificação": return "Abrir certificação →";
    case "exame": return "Abrir exame →";
    case "trilha": return "Abrir trilha →";
    default: return "Abrir curso →";
  }
}

function formatSynced(value: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

/** "" for manual/old records. The skill link is a code rule, never shown as "verified". */
export function learnSourceLine(r: SourceLike): string {
  if (r.match_origin !== "rule") return "";
  const date = formatSynced(r.synced_at);
  return `Microsoft Learn${date ? ` · sincronizado em ${date}` : ""} · skills casadas por regra`;
}

export function isLearnUrl(value: unknown): boolean {
  if (typeof value !== "string") return false;
  try {
    const u = new URL(value);
    return u.protocol === "https:" && u.hostname === "learn.microsoft.com" && !u.username && !u.password;
  } catch {
    return false;
  }
}
```

- [ ] **Step 2: Check script** — `frontend/lib/learn.check.mjs`, seguindo o cabeçalho de `lib/schedule.check.mjs` (compila `learn.ts` com `tsc` para um tmp e importa). Afirmar:

```js
assert.equal(kindLabel("certification"), "certificação"); assert.equal(kindLabel("Trilha"), "trilha");
assert.equal(kindLabel("exame"), "exame"); assert.equal(kindLabel(null), ""); assert.equal(kindLabel("outro"), "outro");
assert.deepEqual(certificationsLast([{id:1,kind:"certificação"},{id:2,kind:"curso"},{id:3,kind:"exame"},{id:4}]).map(x=>x.id), [2,4,1,3]);
assert.deepEqual(certificationsLast([]), []);
assert.equal(linkLabel("certificação"), "Abrir certificação →"); assert.equal(linkLabel("exame"), "Abrir exame →");
assert.equal(linkLabel("trilha"), "Abrir trilha →"); assert.equal(linkLabel(undefined), "Abrir curso →");
assert.equal(learnSourceLine({match_origin:"rule", synced_at:"2026-09-30"}), "Microsoft Learn · sincronizado em 30/09/2026 · skills casadas por regra");
assert.equal(learnSourceLine({match_origin:"rule"}), "Microsoft Learn · skills casadas por regra");
assert.equal(learnSourceLine({match_origin:"manual", synced_at:"2026-09-30"}), ""); assert.equal(learnSourceLine({}), "");
for (const ok of ["https://learn.microsoft.com/a"]) assert.equal(isLearnUrl(ok), true);
for (const bad of ["http://learn.microsoft.com/a","https://learn.microsoft.com.evil.com/a","https://evil.com","https://u:p@learn.microsoft.com/a","javascript:1","",null,5]) assert.equal(isLearnUrl(bad), false);
```

e imprimir `ok (...)` por bloco como os outros checks. Adicionar ao `package.json`: `"check:learn": "node lib/learn.check.mjs"`. Run: `cd frontend && npm run check:learn` → PASS.

- [ ] **Step 3: Tipos** — `lib/types.ts`: em `Recommendation` acrescentar (opcionais, `null`/ausente = registro antigo)

```ts
  exam_codes?: string[] | null;
  source?: string | null;
  synced_at?: string | null;
  /** "rule" = item da Microsoft Learn ligado às skills por regra; "manual" = lista manual. */
  match_origin?: string | null;
```

e criar/exportar `export interface SupplementaryItem { skill: string; title: string; url: string }`; em `CandidateResult` acrescentar `supplementary?: SupplementaryItem[] | null; learn_status?: string | null;`.

- [ ] **Step 4: `TrainingPlan.tsx`** — substituir o mapa `KIND` por `kindLabel`; importar `{ certificationsLast, kindLabel, learnSourceLine, linkLabel } from "@/lib/learn"`; trocar

```tsx
const stages = useMemo(() => groupByLevel(recommendations), [recommendations]);
```

por

```tsx
const ordered = useMemo(() => certificationsLast(recommendations), [recommendations]);
const stages = useMemo(() => groupByLevel(ordered), [ordered]);
```

Na linha de meta: `{r.kind && <>{kindLabel(r.kind)} · </>}` e, antes de `cobre:`, `{r.exam_codes && r.exam_codes.length > 0 && <>exame {r.exam_codes.join(", ")} · </>}`. Depois do bloco `course-meta`, `{learnSourceLine(r) && <div className="course-source">{learnSourceLine(r)}</div>}`. O texto do link vira `{linkLabel(r.kind)}`. Manter "horas não informadas".

- [ ] **Step 5: `SupplementaryLinks.tsx`**

```tsx
import { isLearnUrl } from "@/lib/learn";
import type { SupplementaryItem } from "@/lib/types";

interface Props {
  items?: SupplementaryItem[] | null;
  status?: string | null;
  skillName: (id: string) => string;
}

/** Documentation links from the Microsoft Learn search. Not courses, no level. Only learn.microsoft.com links render. */
export default function SupplementaryLinks({ items, status, skillName }: Props) {
  const safe = (items ?? []).filter((i) => isLearnUrl(i.url));
  if (safe.length === 0) {
    return status === "unavailable"
      ? <p className="plan-caption">Busca complementar da Microsoft Learn indisponível agora. As recomendações acima não dependem dela.</p>
      : null;
  }
  return (
    <section className="supp" aria-label="Leitura complementar">
      <h4 className="stage-title">Leitura complementar</h4>
      <p className="plan-caption">
        Encontrado pela busca da Microsoft Learn para gaps sem item no catálogo. Não é curso e não tem nível.
      </p>
      <ul className="supp-list">
        {safe.map((i) => (
          <li key={i.url}>
            <a className="course-link" href={i.url} target="_blank" rel="noopener noreferrer">{i.title} →</a>
            <span className="course-meta"> · {skillName(i.skill)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 6: `CandidateCard.tsx`** — logo depois do `<TrainingPlan ... />` (linha ~185), dentro do mesmo ramo em que ele aparece, acrescentar `<SupplementaryLinks items={candidate.supplementary} status={candidate.learn_status} skillName={skillName} />` (importar o componente). Se `recommendations.length === 0` mas há `supplementary`, o bloco deve continuar aparecendo: renderizar `SupplementaryLinks` fora do ternário de "sem recomendações".

- [ ] **Step 7: CSS** — `globals.css`: `.course-source` (fonte mono pequena, cor de tinta secundária já usada em `.course-meta`, sem verde/terracota), `.supp` (margem superior como `.stage`), `.supp-list` (lista sem marcador, itens com espaçamento igual ao de `.courses`). Seguir as variáveis existentes; sem sombras.

- [ ] **Step 8: Footer** — em `Footer.tsx` localizar a nota de catálogo não verificado e trocar por: itens da Microsoft Learn vêm do catálogo oficial (nível, duração e link são da Microsoft; o vínculo com as skills é regra); a lista manual continua não verificada. Manter o tamanho/tom do texto atual.

- [ ] **Step 9: Verify** — `cd frontend && npm run typecheck && npm run check:learn && npm run check:schedule && npm run check:ledger && npm run check:pipeline && npm run check:brand` → todos PASS. Não rodar `npm run build`.

- [ ] **Step 10: Commit**

```bash
git add frontend
git commit -m "feat(ui): itens da Microsoft Learn por nível, certificações/exames e leitura complementar

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Smoke ao vivo, documentação e verificação final

**Files:**
- Create: `backend/scripts/learn_smoke.py`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-09-30-microsoft-learn-integration-design.md`
- Modify: `backend/config/learn_mapping.yaml` (só se o smoke mostrar skills sem item que uma regra razoável resolva)

- [ ] **Step 1: Script de smoke ao vivo** (fora do CI; usa banco temporário e a rede)

```python
"""Teste ao vivo: sincroniza o catálogo real num banco temporário e faz uma busca no MCP.

Uso (a partir de backend/):  .venv/bin/python scripts/learn_smoke.py
Não grava nada no banco do app.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillgap.catalog_store import CatalogStore, validate_courses  # noqa: E402
from skillgap.learn_catalog import fetch_catalog, normalize_catalog  # noqa: E402
from skillgap.learn_mapping import load_mapping, render_report, to_courses  # noqa: E402
from skillgap.learn_mcp import LearnMcpClient  # noqa: E402
from skillgap.taxonomy import load_taxonomy  # noqa: E402


def main() -> int:
    taxonomy = load_taxonomy("config/taxonomy_fy27.yaml")
    items, dropped = normalize_catalog(fetch_catalog("en-us"))
    courses, report = to_courses(items, load_mapping("config/learn_mapping.yaml", taxonomy), taxonomy, dropped)
    validate_courses(courses, taxonomy)
    with tempfile.TemporaryDirectory() as tmp:
        store = CatalogStore(f"{tmp}/smoke.db")
        print(store.sync_learn(courses, "smoke"))
        print(store.learn_status())
        store.close()
    print(render_report(report, taxonomy))
    hits = LearnMcpClient().search("Microsoft Fabric lakehouse training")
    print("MCP:", [(h.title, h.url) for h in hits])
    return 0 if courses and hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Rodar o smoke e afinar as regras**

Run: `cd backend && .venv/bin/python scripts/learn_smoke.py`
Expected: exit 0; `learn_status` com itens > 0 e certificações; MCP com pelo menos 1 resultado. Ler "Skills sem nenhum item". Para cada skill sem item, procurar no catálogo real um título/resumo que devesse casar e ajustar **só** `learn_mapping.yaml` (nunca código). Repetir até sobrarem apenas skills para as quais a Microsoft realmente não tem item, e registrar quais no relatório final da task. Anexar ao relatório os números (itens por tipo e por nível, skills sem item).

- [ ] **Step 3: Suíte completa**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/python -W error -m pytest -q`
Expected: PASS nas duas (a contagem sobe em relação aos 416 testes anteriores).

- [ ] **Step 4: README** — acrescentar, na seção do catálogo SQLite, o parágrafo "Microsoft Learn": o que é sincronizado (`python -m skillgap.cli catalog sync-learn [--locale pt-br] [--report r.md]`), que o nível/duração/link são da Microsoft e o vínculo com as skills é regra (`config/learn_mapping.yaml`), que certificações são casadas por título porque o catálogo devolve `exams` vazio na maioria, o MCP como busca complementar (só nomes de skills saem; `SKILLGAP_LEARN_MCP=0` desliga), variáveis `SKILLGAP_LEARN_MAPPING`, `SKILLGAP_LEARN_LOCALE`, `SKILLGAP_LEARN_MCP`, e o comando do smoke. Em "Limitações" acrescentar: catálogo pt-br menor que en-us; qualidade do mapeamento depende das regras; links do MCP são leitura, não treinamento. Em "Verificado/Não verificado": o que o smoke ao vivo confirmou e o que continua sem verificação (mapeamento em escala). Atualizar a contagem de testes.

- [ ] **Step 5: Spec** — na spec, registrar os rulings do topo deste plano (id-prefixo para `match_origin`, query inteira removida do link, sem `excerpt`, `learn_mcp` padrão `False` na dataclass).

- [ ] **Step 6: Varredura e commit**

```bash
# varredura de dados pessoais e segredos (telefone, nome, caminho local, chaves sk-ant-...) na árvore inteira:
git grep -nIE "$SKILLGAP_PII_REGEX" -- . ; test $? -eq 1 && echo "limpo"
git add backend/scripts/learn_smoke.py backend/config/learn_mapping.yaml README.md docs
git commit -m "docs+chore(learn): smoke ao vivo, README e rulings da spec

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: a varredura imprime `limpo`.
