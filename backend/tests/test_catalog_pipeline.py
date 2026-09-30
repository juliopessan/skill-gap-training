import pytest

from pdfs import make_text_pdf
from skillgap.bootstrap import build_service
from skillgap.catalog_store import CatalogStore
from skillgap.config import Settings
from skillgap.models import ExtractedProfile, RawSkill
from skillgap.pipeline import Deps, run_pipeline
from skillgap.recommender import Course
from skillgap.taxonomy import load_taxonomy
from support import OPEN_STORES, FakeExtractor

CV1 = make_text_pdf(["Maria Silva", "Experience with Microsoft Fabric OneLake lakehouse projects."])
CV2 = make_text_pdf(["Joao Souza", "Built a different lakehouse on OneLake with pipelines."])


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy("config/taxonomy_fy27.yaml")


@pytest.fixture
def catalog(taxonomy):
    store = CatalogStore(":memory:")
    OPEN_STORES.append(store)
    assert store.seed_from_csv_if_empty("config/catalog_fy27.csv", taxonomy) == 26
    return store


def profile(**levels):
    return ExtractedProfile(candidate="Maria", skills=[
        RawSkill(name=n.replace("_", " "), level=lv, evidence="Experience with Microsoft Fabric")
        for n, lv in levels.items()])


def run(catalog, taxonomy, extracted, cv=CV1):
    deps = Deps(taxonomy, catalog.all_courses, lambda text, hints: extracted)
    return run_pipeline(cv, deps)["recommendations"]


def test_recommendations_come_from_the_sqlite_catalog(catalog, taxonomy):
    recs = run(catalog, taxonomy, profile(Lakehouse=1))
    assert [r.course_id for r in recs] == [
        "dp-600", "fabric-fundamentals", "dp-700", "fabric-data-engineering",
        "fabric-datascience", "fabric-warehouse", "fabric-realtime", "fabric-lakehouse"]
    assert all(r.hours is None and r.link == "" and r.verified is False for r in recs)
    assert {r.kind for r in recs} == {"curso", "certificação"}
    assert all(catalog.get(r.course_id).platform == "fabric" for r in recs)


def test_level_one_courses_are_skipped_when_person_is_already_at_level_two(catalog, taxonomy):
    recs = run(catalog, taxonomy, profile(Fabric=2, Lakehouse=2, Warehouse=2))
    ids = [r.course_id for r in recs]
    assert "fabric-fundamentals" not in ids and "fabric-lakehouse" not in ids
    assert "fabric-data-engineering" in ids
    assert all(catalog.get(i).level >= 2 for i in ids)


def test_editing_the_db_applies_to_the_next_run_without_rebuilding(catalog, taxonomy):
    deps = Deps(taxonomy, catalog.all_courses, lambda text, hints: profile(Lakehouse=2, Fabric=1))
    first = [r.course_id for r in run_pipeline(CV1, deps)["recommendations"]]
    assert "novo-realtime" not in first
    catalog.upsert([Course("novo-realtime", "Novo curso RT", ("fabric.realtime",), 3, 2, "",
                           platform="fabric", provider="Interno")])
    second = run_pipeline(CV2, deps)["recommendations"]
    added = next(r for r in second if r.course_id == "novo-realtime")
    assert added.hours == 2 and added.provider == "Interno"
    catalog.replace_all([])
    assert run_pipeline(CV1, deps)["recommendations"] == []


def test_empty_catalog_yields_no_recommendations_and_no_crash(taxonomy):
    empty = CatalogStore(":memory:")
    OPEN_STORES.append(empty)
    assert run(empty, taxonomy, profile(Lakehouse=1)) == []


def test_deps_still_accepts_a_plain_list(taxonomy):
    course = Course("c", "C", ("fabric.pipelines",), 2, 3, "", platform="fabric")
    deps = Deps(taxonomy, [course], lambda t, h: profile(Lakehouse=2))
    assert [r.course_id for r in run_pipeline(CV1, deps)["recommendations"]] == ["c"]


def test_build_service_seeds_sqlite_catalog_once_and_never_overwrites(tmp_path):
    settings = Settings(db_path=str(tmp_path / "x.db"))
    first = build_service(settings, extract=FakeExtractor())
    OPEN_STORES.extend([first.store, first.catalog])
    assert first.catalog.count() == 26
    assert callable(first.deps.courses) and len(first.deps.courses()) == 26
    first.catalog.upsert([Course("mine", "Meu", ("fabric.ai",), 1, None, "", platform="fabric")])
    first.catalog.close()
    first.store.close()
    OPEN_STORES.clear()

    second = build_service(settings, extract=FakeExtractor())
    OPEN_STORES.extend([second.store, second.catalog])
    assert second.catalog.count() == 27 and second.catalog.get("mine") is not None


def test_invalid_csv_fails_startup_with_clear_error(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("id,titulo,skills_cobertas,nivel\nc1,Um,fabric.nao_existe,1\n", encoding="utf-8")
    settings = Settings(db_path=str(tmp_path / "x.db"), catalog_path=str(bad))
    with pytest.raises(ValueError, match="fabric.nao_existe"):
        build_service(settings, extract=FakeExtractor())
