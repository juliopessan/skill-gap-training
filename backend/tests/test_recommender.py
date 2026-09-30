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
    courses = load_catalog("config/catalog_fy27.csv")
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


# ---- Course estendido, horas desconhecidas e loader tolerante ----

import pytest


def test_course_positional_fields_and_new_defaults():
    c = Course("c1", "T", ("a",), 1, None, "")
    assert c.hours is None
    assert (c.platform, c.focus, c.provider, c.kind, c.source, c.verified) == (
        "", "", "", "curso", "", False)


def test_unknown_hours_sort_last_on_ties_and_recommendation_carries_fields():
    gaps = [gap("a", 0, 2, "high")]
    courses = [
        Course("n", "Sem horas", ("a",), 1, None, "", provider="P", kind="certificação", verified=True),
        Course("k", "Com horas", ("a",), 1, 30, "", verified=True),
    ]
    result = recommend(gaps, courses)
    assert [r.course_id for r in result] == ["k", "n"]
    assert result[1].hours is None and result[1].link == ""
    assert (result[1].provider, result[1].kind, result[1].verified) == ("P", "certificação", True)


def write(tmp_path, text, name="c.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_legacy_six_column_csv_still_loads(tmp_path):
    path = write(tmp_path, "id,titulo,skills_cobertas,nivel,carga_horaria,link\n"
                           "c1,Um,a;b,2,8,https://x/c1\n")
    [c] = load_catalog(path)
    assert c.hours == 8 and c.link == "https://x/c1" and c.kind == "curso" and c.verified is False


def test_new_columns_blanks_and_nivel_names(tmp_path):
    header = ("id,plataforma,titulo,foco,nivel,provedor,tipo,skills_cobertas,"
              "carga_horaria,link,fonte,verificado\n")
    rows = (
        'a,fabric,"Titulo, com virgula",Foco,Fundamentals,Prov,curso,x.y;x.z,,,Fonte A,0\n'
        "b,fabric,B,,INTERMEDIÁRIO,,certificação,x.y,10,https://l,,sim\n"
        "c,fabric,C,,avançado,,curso,\"x.y, x.z\",5,,,TRUE\n"
        "d,fabric,D,,basic,,curso,x.y,,,,não\n"
        "e,fabric,E,,Intermediate,,curso,x.y,,,,false\n"
        "f,fabric,F,,Advanced,,curso,x.y,,,,1\n"
    )
    cs = {c.id: c for c in load_catalog(write(tmp_path, header + rows))}
    assert cs["a"].title == "Titulo, com virgula" and cs["a"].level == 1
    assert cs["a"].hours is None and cs["a"].link == "" and cs["a"].source == "Fonte A"
    assert cs["a"].verified is False and cs["a"].skills == ("x.y", "x.z")
    assert cs["b"].level == 2 and cs["b"].kind == "certificação" and cs["b"].verified is True
    assert cs["c"].level == 3 and cs["c"].skills == ("x.y", "x.z") and cs["c"].verified is True
    assert cs["d"].level == 1 and cs["e"].level == 2 and cs["f"].level == 3
    assert cs["d"].verified is False and cs["f"].verified is True


@pytest.mark.parametrize("text, needle", [
    ("id,titulo,nivel\nc1,Um,1\n", "skills_cobertas"),
    ("id,titulo,skills_cobertas,nivel\nc1,Um,a,9\n", "nivel"),
    ("id,titulo,skills_cobertas,nivel\nc1,Um,a,1\nc1,Dois,a,1\n", "duplicado"),
    ("id,titulo,skills_cobertas,nivel,carga_horaria\nc1,Um,a,1,oito\n", "carga_horaria"),
    ("id,titulo,skills_cobertas,nivel,verificado\nc1,Um,a,1,talvez\n", "verificado"),
])
def test_bad_rows_raise_portuguese_error_with_line(tmp_path, text, needle):
    path = write(tmp_path, text)
    with pytest.raises(ValueError) as exc:
        load_catalog(path)
    message = str(exc.value)
    assert needle in message and "c.csv" in message


def test_bad_row_message_names_line_number(tmp_path):
    path = write(tmp_path, "id,titulo,skills_cobertas,nivel\nc1,Um,a,1\nc2,Dois,a,9\n")
    with pytest.raises(ValueError, match="linha 3"):
        load_catalog(path)


def test_recommendation_carries_level_and_platform():
    c = Course("p", "Curso p", ("a",), 2, 4, "", platform="Microsoft Learn")
    [r] = recommend([gap("a", 0, 2, "high")], [c])
    assert r.level == 2 and r.platform == "Microsoft Learn"


def test_empty_platform_becomes_none():
    [r] = recommend([gap("a", 0, 2, "high")], [course("q", ["a"], level=3)])
    assert r.platform is None and r.level == 3


from skillgap.recommender import uncovered_gaps


def test_verified_items_win_ties_before_hours():
    gaps = [gap("a", 0, 2, "high")]
    manual = Course("m", "Manual", ("a",), 1, 2, "", verified=False)
    official = Course("learn:o", "Oficial", ("a",), 1, 30, "https://learn.microsoft.com/o", verified=True)
    assert [r.course_id for r in recommend(gaps, [manual, official])] == ["learn:o", "m"]


def test_recommendation_carries_provenance_for_learn_items():
    gaps = [gap("a", 0, 2, "high")]
    c = Course("learn:o", "Cert", ("a",), 2, None, "https://learn.microsoft.com/o", provider="Microsoft Learn",
               kind="certificação", source="Microsoft Learn Catalog API", verified=True,
               exam_codes=("AI-500",), synced_at="2026-09-30")
    [r] = recommend(gaps, [c])
    assert (r.exam_codes, r.source, r.synced_at, r.match_origin) == (
        ["AI-500"], "Microsoft Learn Catalog API", "2026-09-30", "rule")
    [m] = recommend(gaps, [course("x", ["a"])])
    assert m.exam_codes == [] and m.source is None and m.synced_at is None and m.match_origin == "manual"


def test_uncovered_gaps_lists_skills_no_course_can_teach_by_severity():
    gaps = [gap("low1", 0, 2, "low"), gap("hi", 0, 2, "high"), gap("ok", 0, 2, "medium"),
            gap("tooadv", 2, 3, "high")]
    courses = [course("c", ["ok"]), course("basic", ["tooadv"], level=1)]  # 'basic' não ensina quem já está no nível 2
    assert uncovered_gaps(gaps, courses) == ["hi", "tooadv", "low1"]


def test_uncovered_gaps_ignores_courses_when_none_are_given():
    assert uncovered_gaps([gap("a", 0, 2, "high")], []) == ["a"]
    assert uncovered_gaps([], [course("c", ["a"])]) == []
