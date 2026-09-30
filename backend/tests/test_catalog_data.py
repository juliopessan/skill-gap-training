from collections import Counter

from skillgap.recommender import load_catalog
from skillgap.taxonomy import load_taxonomy

FONTE = "Lista fornecida pelo usuário em 2026-09-29 (títulos, níveis e provedores não verificados)"


def test_shipped_catalog_is_the_honest_unverified_list():
    taxonomy = load_taxonomy("config/taxonomy_fy27.yaml")
    valid = {s.id for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)}
    courses = load_catalog("config/catalog_fy27.csv")
    assert len(courses) == 26
    assert len({c.id for c in courses}) == 26
    for c in courses:
        assert c.skills and set(c.skills) <= valid, c.id
        assert c.platform in taxonomy.tracks, c.id
        assert c.verified is False and c.hours is None and c.link == "", c.id
        assert c.source == FONTE and c.provider, c.id
        assert c.kind in ("curso", "certificação"), c.id
    assert Counter(c.level for c in courses) == {1: 3, 2: 11, 3: 12}
    assert Counter(c.kind for c in courses) == {"curso": 19, "certificação": 7}
    assert Counter(c.platform for c in courses) == {"foundry": 8, "fabric": 8, "databricks": 10}
