import itertools

import pytest

from skillgap.models import Skill
from skillgap.rating import compute_rating, level_label

# Taxonomy (conftest): fabric.lakehouse=2, fabric.pipelines=2, foundry.agents=2,
# foundry.models=1, databricks.spark=3.


def sk(id, level, verified=True):
    track = id.split(".")[0]
    return Skill(id=id, name=id, track=track, level=level, evidence="q", evidence_verified=verified)


def test_no_skills_gives_none(small_taxonomy):
    assert compute_rating([], small_taxonomy) is None


def test_only_tracks_with_data_appear(small_taxonomy):
    r = compute_rating([sk("databricks.spark", 2)], small_taxonomy)
    assert [t.track for t in r.tracks] == ["databricks"]
    # covered = min(2,3) = 2; expected = 3 -> 66.7
    assert (r.covered, r.expected, r.adherence) == (2, 3, 66.7)
    assert r.tracks[0].name == "Databricks" and r.tracks[0].skills_rated == 1


def test_mixed_candidate_exact_numbers(small_taxonomy):
    skills = [sk("fabric.lakehouse", 1), sk("databricks.spark", 3), sk("foundry.models", 1)]
    r = compute_rating(skills, small_taxonomy)
    # fabric:     lakehouse min(1,2)=1 + pipelines 0            -> 1 / 4 = 25.0
    # foundry:    agents 0 + models min(1,1)=1                  -> 1 / 3 = 33.3
    # databricks: spark min(3,3)=3                              -> 3 / 3 = 100.0
    # overall: covered 5 / expected 10 = 50.0
    by = {t.track: t for t in r.tracks}
    assert (by["fabric"].covered, by["fabric"].expected, by["fabric"].adherence) == (1, 4, 25.0)
    assert (by["foundry"].covered, by["foundry"].expected, by["foundry"].adherence) == (1, 3, 33.3)
    assert (by["databricks"].covered, by["databricks"].expected, by["databricks"].adherence) == (3, 3, 100.0)
    assert (r.covered, r.expected, r.adherence) == (5, 10, 50.0)
    # mean levels: fabric 1.0, foundry 1.0, databricks 3.0; overall (1+3+1)/3 = 1.67
    assert by["fabric"].mean_level == 1.0 and by["fabric"].level_label == "Básico"
    assert by["databricks"].mean_level == 3.0 and by["databricks"].level_label == "Avançado"
    assert r.mean_level == 1.67 and r.level_label == "Intermediário"


def test_level_above_expected_is_capped_but_raises_mean(small_taxonomy):
    r = compute_rating([sk("foundry.models", 3)], small_taxonomy)
    # models: min(3,1)=1; agents 0 -> 1 / 3 = 33.3 ; mean stays 3.0
    assert (r.covered, r.expected, r.adherence) == (1, 3, 33.3)
    assert r.mean_level == 3.0 and r.level_label == "Avançado"


def test_expected_reached_everywhere_is_100(small_taxonomy):
    skills = [sk("fabric.lakehouse", 2), sk("fabric.pipelines", 3), sk("foundry.agents", 2),
              sk("foundry.models", 1), sk("databricks.spark", 3)]
    r = compute_rating(skills, small_taxonomy)
    assert r.adherence == 100.0 and r.adherence_supported == 100.0
    assert r.covered == r.expected == 10  # 2+2+2+1+3
    assert all(t.adherence == 100.0 for t in r.tracks)


def test_supported_equals_adherence_when_all_verified(small_taxonomy):
    r = compute_rating([sk("fabric.lakehouse", 1), sk("databricks.spark", 2)], small_taxonomy)
    assert r.adherence_supported == r.adherence
    assert all(t.adherence_supported == t.adherence for t in r.tracks)


def test_unverified_lowers_supported(small_taxonomy):
    skills = [sk("fabric.lakehouse", 2), sk("databricks.spark", 3, verified=False)]
    r = compute_rating(skills, small_taxonomy)
    # adherence: (2+0+3)/7 = 71.4 ; supported: (2+0+0)/7 = 28.6
    assert r.adherence == 71.4 and r.adherence_supported == 28.6
    by = {t.track: t for t in r.tracks}
    assert by["fabric"].adherence_supported == 50.0 and by["databricks"].adherence_supported == 0.0


def test_unchecked_none_counts_as_unsupported(small_taxonomy):
    r = compute_rating([sk("databricks.spark", 3, verified=None)], small_taxonomy)
    assert r.adherence == 100.0 and r.adherence_supported == 0.0


def test_supported_never_exceeds_adherence(small_taxonomy):
    ids = ["fabric.lakehouse", "foundry.agents", "databricks.spark"]
    for levels in itertools.product([1, 2, 3], repeat=3):
        for flags in itertools.product([True, False, None], repeat=3):
            skills = [sk(i, lv, fl) for i, lv, fl in zip(ids, levels, flags)]
            r = compute_rating(skills, small_taxonomy)
            assert r.adherence_supported <= r.adherence
            assert all(t.adherence_supported <= t.adherence for t in r.tracks)


@pytest.mark.parametrize("mean,label", [
    (1.0, "Básico"), (1.49, "Básico"), (1.5, "Intermediário"),
    (2.49, "Intermediário"), (2.5, "Avançado"), (3.0, "Avançado")])
def test_label_boundaries(mean, label):
    assert level_label(mean) == label
    assert level_label(None) is None


def test_label_from_crafted_levels(small_taxonomy):
    # levels 1 and 2 -> mean 1.5 -> Intermediário; 2 and 3 -> 2.5 -> Avançado
    assert compute_rating([sk("fabric.lakehouse", 1), sk("fabric.pipelines", 2)],
                          small_taxonomy).level_label == "Intermediário"
    assert compute_rating([sk("fabric.lakehouse", 2), sk("fabric.pipelines", 3)],
                          small_taxonomy).level_label == "Avançado"


def test_tracks_follow_taxonomy_order_and_expected_sums(small_taxonomy):
    skills = [sk("databricks.spark", 1), sk("foundry.agents", 1), sk("fabric.lakehouse", 1)]
    r = compute_rating(skills, small_taxonomy)
    assert [t.track for t in r.tracks] == ["fabric", "foundry", "databricks"]
    assert r.expected == sum(t.expected for t in r.tracks)
    assert r.covered == sum(t.covered for t in r.tracks)


def test_rounds_to_one_decimal(small_taxonomy):
    # 1/3 -> 33.3 ; 2/3 -> 66.7
    assert compute_rating([sk("databricks.spark", 1)], small_taxonomy).adherence == 33.3
    assert compute_rating([sk("databricks.spark", 2)], small_taxonomy).adherence == 66.7
