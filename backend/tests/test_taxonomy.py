import pytest

from skillgap.taxonomy import load_taxonomy, normalize


def test_normalize_strips_accents_case_and_punctuation():
    assert normalize("  Ação: PySpark/Delta-Lake! ") == "acao pyspark delta lake"


def test_match_by_name_is_case_and_accent_insensitive(small_taxonomy):
    assert small_taxonomy.match("lakehouse").id == "fabric.lakehouse"
    assert small_taxonomy.match("APACHE  spark").id == "databricks.spark"


def test_match_by_synonym(small_taxonomy):
    assert small_taxonomy.match("PySpark").id == "databricks.spark"
    assert small_taxonomy.match("data factory").id == "fabric.pipelines"


def test_unknown_skill_returns_none(small_taxonomy):
    assert small_taxonomy.match("Kubernetes") is None


def test_tracks_keep_declaration_order(small_taxonomy):
    assert list(small_taxonomy.tracks) == ["fabric", "foundry", "databricks"]
    assert small_taxonomy.tracks["foundry"] == "Azure AI Foundry"


def test_skills_in_track(small_taxonomy):
    ids = [s.id for s in small_taxonomy.skills_in_track("fabric")]
    assert ids == ["fabric.lakehouse", "fabric.pipelines"]


def test_hint_names_lists_canonical_names(small_taxonomy):
    assert "Lakehouse" in small_taxonomy.hint_names()


def test_invalid_expected_level_is_rejected(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text(
        "tracks:\n  - id: a\n    name: A\n    skills:\n"
        "      - {id: a.x, name: X, expected_level: 5}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected_level"):
        load_taxonomy(path)


def test_ambiguous_label_between_two_skills_is_rejected(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text(
        "tracks:\n  - id: a\n    name: A\n    skills:\n"
        "      - {id: a.x, name: X, synonyms: [Compartilhado], expected_level: 1}\n"
        "      - {id: a.y, name: Y, synonyms: [compartilhado], expected_level: 1}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="ambíguo"):
        load_taxonomy(path)


def test_generic_platform_mentions_map_to_platform_skills():
    taxonomy = load_taxonomy("config/taxonomy_fy27.yaml")
    assert taxonomy.match("Databricks").id == "databricks.platform"
    assert taxonomy.match("Azure AI Studio").id == "foundry.platform"
    assert taxonomy.match("Microsoft Fabric").id == "fabric.platform"
    assert taxonomy.match("Azure OpenAI").id == "foundry.models"
    assert taxonomy.match("Multi-Agent Systems").id == "foundry.agents"


def test_shipped_fy27_taxonomy_is_valid_and_has_three_tracks():
    taxonomy = load_taxonomy("config/taxonomy_fy27.yaml")
    assert list(taxonomy.tracks) == ["foundry", "fabric", "databricks"]
    for track in taxonomy.tracks:
        assert len(taxonomy.skills_in_track(track)) >= 5


def test_empty_synonyms_key_loads_as_no_synonyms(tmp_path):
    path = tmp_path / "tax.yaml"
    path.write_text(
        "tracks:\n  - id: t\n    name: Trilha\n    skills:\n"
        "      - id: t.a\n        name: Alpha\n        expected_level: 2\n        synonyms:\n",
        encoding="utf-8")
    taxonomy = load_taxonomy(path)
    assert taxonomy.match("Alpha").id == "t.a"
