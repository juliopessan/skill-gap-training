from skillgap.classifier import build_profile
from skillgap.models import ExtractedProfile, RawSkill


def profile(*skills):
    return ExtractedProfile(candidate="Maria", skills=list(skills))


def test_synonym_maps_to_taxonomy_skill(small_taxonomy):
    skills, others = build_profile(
        profile(RawSkill(name="PySpark", level=2, evidence="usou PySpark")), small_taxonomy)
    assert [(s.id, s.name, s.track, s.level) for s in skills] == [
        ("databricks.spark", "Apache Spark", "databricks", 2)]
    assert others == []


def test_same_skill_written_three_ways_becomes_one_with_max_level(small_taxonomy):
    skills, _ = build_profile(
        profile(
            RawSkill(name="Spark", level=1, evidence="curso de Spark"),
            RawSkill(name="Apache Spark", level=3, evidence="liderou migração Spark"),
            RawSkill(name="pyspark", level=2, evidence="jobs em PySpark"),
        ),
        small_taxonomy,
    )
    assert len(skills) == 1
    assert skills[0].level == 3
    assert skills[0].evidence == "liderou migração Spark"


def test_unknown_skill_goes_to_other_skills(small_taxonomy):
    skills, others = build_profile(
        profile(RawSkill(name="Kubernetes", level=2, evidence="operou clusters")),
        small_taxonomy)
    assert skills == []
    assert [(o.name, o.level) for o in others] == [("Kubernetes", 2)]


def test_other_skills_are_deduplicated_ignoring_case_and_accents(small_taxonomy):
    _, others = build_profile(
        profile(
            RawSkill(name="Gestão Ágil", level=1, evidence="a"),
            RawSkill(name="gestao agil", level=3, evidence="b"),
        ),
        small_taxonomy,
    )
    assert len(others) == 1 and others[0].level == 3
