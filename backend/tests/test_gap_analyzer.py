import pytest

from skillgap.gap_analyzer import analyze_gaps, severity
from skillgap.models import Skill


def skill(id, track, level, name="n"):
    return Skill(id=id, name=name, track=track, level=level, evidence="e")


@pytest.mark.parametrize("current,expected,label", [
    (0, 3, "high"),
    (0, 2, "high"),
    (0, 1, "medium"),
    (1, 3, "high"),
    (1, 2, "low"),
    (2, 3, "low"),
])
def test_severity_table(current, expected, label):
    assert severity(current, expected) == label


def test_only_tracks_with_data_produce_gaps(small_taxonomy):
    gaps, no_data = analyze_gaps([skill("fabric.lakehouse", "fabric", 1)], small_taxonomy)
    assert {g.skill: (g.current, g.expected, g.severity) for g in gaps} == {
        "fabric.pipelines": (0, 2, "high"),
        "fabric.lakehouse": (1, 2, "low"),
    }
    assert no_data == ["foundry", "databricks"]


def test_no_skills_at_all_means_all_tracks_have_no_data(small_taxonomy):
    gaps, no_data = analyze_gaps([], small_taxonomy)
    assert gaps == []
    assert no_data == ["fabric", "foundry", "databricks"]


def test_skill_at_or_above_expected_level_is_not_a_gap(small_taxonomy):
    gaps, _ = analyze_gaps([skill("databricks.spark", "databricks", 3)], small_taxonomy)
    assert gaps == []


def test_gaps_are_sorted_by_severity(small_taxonomy):
    gaps, _ = analyze_gaps([skill("fabric.lakehouse", "fabric", 1)], small_taxonomy)
    assert [g.severity for g in gaps] == ["high", "low"]


def test_gap_carries_display_name_and_track(small_taxonomy):
    gaps, _ = analyze_gaps([skill("fabric.lakehouse", "fabric", 1)], small_taxonomy)
    pipelines = next(g for g in gaps if g.skill == "fabric.pipelines")
    assert pipelines.name == "Data Pipelines" and pipelines.track == "fabric"
