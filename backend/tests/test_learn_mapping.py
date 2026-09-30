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
