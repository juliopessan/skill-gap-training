import sqlite3
import threading

import pytest

from skillgap.catalog_store import CatalogStore, validate_courses
from skillgap.models import CandidateResult
from skillgap.recommender import Course, load_catalog
from skillgap.store import Store


def mk(id, platform="fabric", level=1, skills=("fabric.lakehouse",), hours=None, **kw):
    return Course(id, kw.pop("title", f"Curso {id}"), tuple(skills), level, hours,
                  kw.pop("link", ""), platform=platform, **kw)


@pytest.fixture
def catalog():
    store = CatalogStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def filled(catalog):
    catalog.upsert([
        mk("f1", "fabric", 1, ("fabric.platform", "fabric.lakehouse"), None, provider="Microsoft Learn",
           focus="OneLake e Lakehouse"),
        mk("f2", "fabric", 2, ("fabric.pipelines",), 10, kind="certificação", verified=True),
        mk("d1", "databricks", 3, ("databricks.spark",), None, title="Spark 100% real_deal",
           provider="Databricks"),
        mk("g1", "foundry", 2, ("foundry.rag", "foundry.prompt"), 4, title="RAG com Foundry"),
    ])
    return catalog


def test_empty_catalog(catalog):
    assert catalog.count() == 0 and catalog.all_courses() == [] and catalog.get("x") is None
    assert catalog.stats()["total"] == 0


def test_upsert_get_roundtrip_and_replaces_skills(catalog):
    c = mk("a", skills=("z.b", "z.a"), hours=7, link="https://l", focus="F", provider="P",
           kind="certificação", source="S", verified=True)
    catalog.upsert([c])
    got = catalog.get("a")
    assert got == Course("a", "Curso a", ("z.a", "z.b"), 1, 7, "https://l", "fabric", "F", "P",
                         "certificação", "S", True)
    catalog.upsert([mk("a", skills=("z.c",), title="Novo", hours=None)])
    got = catalog.get("a")
    assert got.skills == ("z.c",) and got.title == "Novo" and got.hours is None
    assert catalog.count() == 1


def test_upsert_is_one_transaction(catalog):
    catalog.upsert([mk("a")])
    with pytest.raises(sqlite3.IntegrityError):
        catalog.upsert([mk("b"), mk("c", level=9)])
    assert catalog.count() == 1 and catalog.get("b") is None


def test_replace_all_swaps_everything_in_one_transaction(filled):
    filled.replace_all([mk("only", skills=("x.y",))])
    assert [c.id for c in filled.all_courses()] == ["only"]
    with pytest.raises(sqlite3.IntegrityError):
        filled.replace_all([mk("k"), mk("k2", hours=-1)])
    assert [c.id for c in filled.all_courses()] == ["only"]


def test_all_courses_ordered_by_platform_level_id(filled):
    assert [c.id for c in filled.all_courses()] == ["d1", "f1", "f2", "g1"]


@pytest.mark.parametrize("kwargs, expected", [
    ({"platform": "fabric"}, ["f1", "f2"]),
    ({"level": 2}, ["f2", "g1"]),
    ({"kind": "certificação"}, ["f2"]),
    ({"skill": "fabric.lakehouse"}, ["f1"]),
    ({"q": "LAKEHOUSE"}, ["f1"]),
    ({"q": "databricks"}, ["d1"]),
    ({"platform": "fabric", "level": 2}, ["f2"]),
    ({"platform": "fabric", "level": 3}, []),
    ({"limit": 2}, ["d1", "f1"]),
    ({}, ["d1", "f1", "f2", "g1"]),
])
def test_list_filters(filled, kwargs, expected):
    assert [c.id for c in filled.list_courses(**kwargs)] == expected


def test_q_treats_percent_and_underscore_literally(filled):
    assert [c.id for c in filled.list_courses(q="100%")] == ["d1"]
    assert [c.id for c in filled.list_courses(q="d_a")] == []
    assert [c.id for c in filled.list_courses(q="real_deal")] == ["d1"]
    assert filled.list_courses(q="%") == filled.list_courses(q="100%")
    assert filled.list_courses(q="\\") == []


@pytest.mark.parametrize("evil", ["'; DROP TABLE courses;--", "x' OR '1'='1", "\") OR 1=1 --"])
def test_injection_strings_are_inert(filled, evil):
    for kwargs in ({"q": evil}, {"platform": evil}, {"kind": evil}, {"skill": evil}):
        assert filled.list_courses(**kwargs) == []
    assert filled.count() == 4


def test_stats(filled):
    s = filled.stats()
    assert s == {
        "total": 4,
        "by_platform": {"databricks": 1, "fabric": 2, "foundry": 1},
        "by_level": {"1": 1, "2": 2, "3": 1},
        "by_kind": {"certificação": 1, "curso": 3},
        "verified": 1, "unverified": 3, "hours_unknown": 2,
    }


def test_view_v_course_coverage(tmp_path):
    path = str(tmp_path / "c.db")
    store = CatalogStore(path)
    store.upsert([mk("v1", skills=("b.b", "a.a"), hours=None, verified=True), mk("v2", skills=())])
    raw = sqlite3.connect(path)
    rows = {r[0]: r for r in raw.execute(
        "SELECT id, platform, title, level, provider, kind, hours, verified, link, skills "
        "FROM v_course_coverage")}
    raw.close()
    store.close()
    assert set(rows["v1"][9].split(";")) == {"a.a", "b.b"} and rows["v1"][6] is None
    assert rows["v1"][7] == 1
    assert rows["v2"][9] == ""


def test_foreign_key_cascade_and_check_constraints(tmp_path):
    path = str(tmp_path / "c.db")
    store = CatalogStore(path)
    store.upsert([mk("a", skills=("s.1", "s.2"))])
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA foreign_keys=ON")
    raw.execute("DELETE FROM courses WHERE id='a'")
    assert raw.execute("SELECT COUNT(*) FROM course_skills").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("INSERT INTO courses(id, platform, title, level) VALUES('x','p','t',9)")
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("INSERT INTO courses(id, platform, title, level, hours) VALUES('x','p','t',1,-3)")
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("INSERT INTO course_skills(course_id, skill_id) VALUES('nope','s')")
    raw.close()
    store.close()


CSV = ("id,plataforma,titulo,foco,nivel,provedor,tipo,skills_cobertas,carga_horaria,link,fonte,verificado\n"
       "a,fabric,A,,1,P,curso,fabric.lakehouse,,,S,0\n"
       "b,foundry,B,,2,P,certificação,foundry.agents;foundry.models,5,https://b,S,1\n")


def test_seed_only_when_empty_and_never_overwrites_edits(tmp_path, small_taxonomy):
    csv_path = tmp_path / "c.csv"
    csv_path.write_text(CSV, encoding="utf-8")
    store = CatalogStore(":memory:")
    assert store.seed_from_csv_if_empty(csv_path, small_taxonomy) == 2
    store.upsert([mk("a", title="Editado", skills=("fabric.pipelines",))])
    assert store.seed_from_csv_if_empty(csv_path, small_taxonomy) == 0
    assert store.get("a").title == "Editado"
    store.close()


def test_seed_rejects_invalid_csv_with_clear_message(tmp_path, small_taxonomy):
    csv_path = tmp_path / "c.csv"
    csv_path.write_text(CSV.replace("fabric.lakehouse", "fabric.inexistente"), encoding="utf-8")
    store = CatalogStore(":memory:")
    with pytest.raises(ValueError, match="fabric.inexistente"):
        store.seed_from_csv_if_empty(csv_path, small_taxonomy)
    assert store.count() == 0
    store.close()


def test_seed_missing_file_is_clear_error(tmp_path, small_taxonomy):
    store = CatalogStore(":memory:")
    with pytest.raises(ValueError, match="não encontrado"):
        store.seed_from_csv_if_empty(tmp_path / "nao-existe.csv", small_taxonomy)
    store.close()


def test_validate_courses_lists_all_offenders(small_taxonomy):
    bad = [mk("ok", "fabric", skills=("fabric.lakehouse",)),
           mk("b1", "fabric", skills=("nada.a", "fabric.pipelines")),
           mk("b2", "inexistente", skills=("nada.b",)),
           mk("b3", "", skills=("fabric.lakehouse",))]
    with pytest.raises(ValueError) as exc:
        validate_courses(bad, small_taxonomy)
    msg = str(exc.value)
    for needle in ("b1", "nada.a", "b2", "nada.b", "inexistente"):
        assert needle in msg
    validate_courses([bad[0], bad[3]], small_taxonomy)


def test_export_csv_roundtrips_through_load_catalog(filled, tmp_path):
    out = tmp_path / "out.csv"
    filled.export_csv(out)
    assert load_catalog(out) == filled.all_courses()


def test_export_csv_roundtrip_with_commas_and_quotes(catalog, tmp_path):
    catalog.upsert([mk("q", title='Com "aspas", vírgula', focus="a, b", hours=3, link="https://x")])
    out = tmp_path / "out.csv"
    catalog.export_csv(out)
    assert load_catalog(out) == catalog.all_courses()


def test_creates_parent_dir_and_uses_wal(tmp_path):
    path = tmp_path / "sub" / "dir" / "c.db"
    store = CatalogStore(str(path))
    store.upsert([mk("a")])
    store.close()
    raw = sqlite3.connect(path)
    assert raw.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    raw.close()


def test_coexists_with_results_store_on_one_file(tmp_path):
    path = str(tmp_path / "skillgap.db")
    results, catalog = Store(path), CatalogStore(path)
    errors = []

    def write_results():
        try:
            for i in range(40):
                results.save(CandidateResult(id=f"r{i}", status="done"), f"sha{i}")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    def write_catalog():
        try:
            for i in range(40):
                catalog.upsert([mk(f"c{i}")])
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=write_results), threading.Thread(target=write_catalog)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(results.list()) == 40 and catalog.count() == 40
    results.close()
    catalog.close()


def test_concurrent_reads_from_many_threads(filled):
    out = []
    threads = [threading.Thread(target=lambda: out.append(len(filled.list_courses()))) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert out == [4] * 8
