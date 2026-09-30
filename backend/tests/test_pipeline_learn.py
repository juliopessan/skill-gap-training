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
