from skillgap.models import Gap
from skillgap.recommender import Course, load_catalog, recommend


def gap(skill, current, expected, severity):
    return Gap(skill=skill, name=skill, track="t", expected=expected,
               current=current, severity=severity)


def course(id, skills, level=1, hours=8):
    return Course(id=id, title=f"Curso {id}", skills=tuple(skills), level=level,
                  hours=hours, link=f"https://example.com/{id}")


def test_orders_by_weighted_score_and_lists_covered_gaps():
    gaps = [gap("a", 0, 2, "high"), gap("b", 1, 2, "low")]
    courses = [course("c-a", ["a"]), course("c-ab", ["a", "b"])]
    result = recommend(gaps, courses)
    assert [r.course_id for r in result] == ["c-ab", "c-a"]
    assert result[0].covers == ["a", "b"]
    assert result[0].title == "Curso c-ab" and result[0].hours == 8


def test_ties_are_broken_by_fewer_hours_then_id():
    gaps = [gap("a", 0, 2, "high")]
    courses = [course("z", ["a"], hours=10), course("y", ["a"], hours=4), course("x", ["a"], hours=4)]
    assert [r.course_id for r in recommend(gaps, courses)] == ["x", "y", "z"]


def test_course_below_current_level_does_not_cover_that_gap():
    gaps = [gap("a", 2, 3, "low")]
    assert recommend(gaps, [course("basic", ["a"], level=1)]) == []
    assert [r.course_id for r in recommend(gaps, [course("adv", ["a"], level=2)])] == ["adv"]


def test_course_that_covers_no_gap_is_omitted():
    assert recommend([gap("a", 0, 2, "high")], [course("other", ["zzz"])]) == []


def test_no_gaps_means_no_recommendations():
    assert recommend([], [course("c", ["a"])]) == []


def test_limit_is_applied():
    gaps = [gap("a", 0, 2, "high")]
    courses = [course(str(i), ["a"], hours=i + 1) for i in range(5)]
    assert len(recommend(gaps, courses, limit=2)) == 2


def test_load_catalog_parses_csv(tmp_path):
    path = tmp_path / "catalog.csv"
    path.write_text(
        "id,titulo,skills_cobertas,nivel,carga_horaria,link\n"
        'c1,"Fabric, do zero",fabric.lakehouse;fabric.pipelines,1,12,https://example.com/c1\n',
        encoding="utf-8")
    [c] = load_catalog(path)
    assert c == Course("c1", "Fabric, do zero", ("fabric.lakehouse", "fabric.pipelines"),
                       1, 12, "https://example.com/c1")


def test_shipped_catalog_references_only_taxonomy_skills():
    from skillgap.taxonomy import load_taxonomy
    taxonomy = load_taxonomy("config/taxonomy_fy27.yaml")
    valid = {s.id for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)}
    courses = load_catalog("config/catalog.csv")
    assert len(courses) >= 10
    for c in courses:
        assert set(c.skills) <= valid, f"{c.id} referencia skill inexistente"
        assert c.level in (1, 2, 3)


def test_catalog_with_utf8_bom_parses(tmp_path):
    path = tmp_path / "catalog.csv"
    path.write_text("id,titulo,skills_cobertas,nivel,carga_horaria,link\n"
                    "c1,Curso Um,a;b,2,8,https://example.com/c1\n", encoding="utf-8-sig")
    courses = load_catalog(path)
    assert courses[0].id == "c1" and courses[0].skills == ("a", "b")
