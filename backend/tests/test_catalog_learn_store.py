import sqlite3

import pytest

from skillgap.catalog_store import CatalogStore
from skillgap.recommender import Course
from support import OPEN_STORES


def open_store(path=":memory:"):
    store = CatalogStore(path)
    OPEN_STORES.append(store)
    return store


def learn(uid, skills=("fabric.lakehouse",), level=2, **kw):
    kw.setdefault("kind", "trilha")
    return Course(id=f"learn:{uid}", title=f"T {uid}", skills=tuple(skills), level=level, hours=3,
                  link=f"https://learn.microsoft.com/{uid}", platform="fabric",
                  provider="Microsoft Learn", source="Microsoft Learn Catalog API",
                  verified=True, **kw)


def manual(id="m1"):
    return Course(id=id, title="Manual", skills=("fabric.lakehouse",), level=1, hours=None,
                  link="", platform="fabric")


def test_match_origin_is_derived_from_id_prefix():
    assert learn("a").match_origin == "rule"
    assert manual().match_origin == "manual"


def test_sync_inserts_then_updates_and_reports_counts():
    s = open_store()
    assert s.sync_learn([learn("a"), learn("b")], "2026-09-30") == {"inserted": 2, "updated": 0, "retired": 0}
    assert s.sync_learn([learn("a", level=3), learn("b")], "2026-10-01") == {"inserted": 0, "updated": 2, "retired": 0}
    a = s.get("learn:a")
    assert a.level == 3 and a.synced_at == "2026-10-01" and a.verified is True


def test_sync_retires_missing_items_and_hides_them_but_keeps_the_row():
    s = open_store()
    s.sync_learn([learn("a"), learn("b")], "2026-09-30")
    assert s.sync_learn([learn("a")], "2026-10-01") == {"inserted": 0, "updated": 1, "retired": 1}
    assert [c.id for c in s.list_courses()] == ["learn:a"]
    assert [c.id for c in s.all_courses()] == ["learn:a"]
    assert [c.id for c in s.list_courses(include_retired=True)] == ["learn:a", "learn:b"]
    assert s.get("learn:b").retired is True
    s.sync_learn([learn("a"), learn("b")], "2026-10-02")  # voltou ao catálogo
    assert s.get("learn:b").retired is False


def test_sync_never_touches_manual_rows():
    s = open_store()
    s.upsert([manual("m1")])
    s.sync_learn([learn("a")], "2026-09-30")
    s.sync_learn([], "2026-10-01")
    assert s.get("m1").retired is False
    assert s.get("learn:a").retired is True
    assert [c.id for c in s.list_courses()] == ["m1"]


def test_sync_rejects_non_learn_ids_without_writing():
    s = open_store()
    with pytest.raises(ValueError, match="learn:"):
        s.sync_learn([learn("a"), manual("m1")], "2026-09-30")
    assert s.count() == 0


def test_sync_is_atomic_when_a_row_is_invalid():
    s = open_store()
    with pytest.raises(sqlite3.IntegrityError):
        s.sync_learn([learn("a"), learn("bad", level=9)], "2026-09-30")
    assert s.count() == 0


def test_exam_codes_round_trip():
    s = open_store()
    s.sync_learn([learn("cert", exam_codes=("AI-500", "AZ-204"))], "2026-09-30")
    assert s.get("learn:cert").exam_codes == ("AI-500", "AZ-204")
    assert s.get("learn:cert").synced_at == "2026-09-30"


def test_learn_status():
    s = open_store()
    assert s.learn_status() == {"items": 0, "by_kind": {}, "retired": 0, "last_sync": None}
    s.upsert([manual()])
    s.sync_learn([learn("a"), learn("b", kind="curso")], "2026-09-30")
    s.sync_learn([learn("a")], "2026-10-01")
    st = s.learn_status()
    assert st["items"] == 1 and st["by_kind"] == {"trilha": 1} and st["retired"] == 1
    assert st["last_sync"] == "2026-10-01"


def test_stats_ignore_retired_rows():
    s = open_store()
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
    s = open_store(path)
    old = s.get("old1")
    assert old.retired is False and old.exam_codes == () and old.synced_at == ""
    s.sync_learn([learn("a")], "2026-09-30")  # e as colunas novas funcionam
    assert s.get("learn:a").synced_at == "2026-09-30"


def test_sync_prefix_match_is_case_sensitive_so_manual_rows_survive():
    s = open_store()
    s.upsert([manual("Learn:foo"), manual("LEARN:x")])
    s.sync_learn([learn("a")], "2026-09-30")
    s.sync_learn([], "2026-10-01")
    assert s.get("Learn:foo").retired is False and s.get("LEARN:x").retired is False
    assert s.learn_status()["items"] == 0 and s.learn_status()["retired"] == 1


def test_manual_csv_cannot_claim_the_learn_prefix(tmp_path):
    from skillgap.recommender import load_catalog
    path = tmp_path / "c.csv"
    path.write_text("id,titulo,skills_cobertas,nivel\nlearn:sneaky,Falso,fabric.lakehouse,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="learn:"):
        load_catalog(path)


def test_sync_retires_only_the_requested_kinds():
    s = open_store()
    s.sync_learn([learn("a"), learn("c", kind="curso")], "2026-09-30")
    s.sync_learn([learn("a")], "2026-10-01", retire_kinds={"trilha"})
    assert s.get("learn:c").retired is False
    s.sync_learn([learn("a")], "2026-10-02")  # sem restrição: comportamento anterior
    assert s.get("learn:c").retired is True
