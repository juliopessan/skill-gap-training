import json

import pytest

from skillgap.learn_catalog import clean_url, fetch_catalog, normalize_catalog
from learn_fixtures import catalog_payload


def by_uid(items):
    return {i.uid: i for i in items}


def test_normalize_levels_hours_urls_and_kinds():
    items, dropped = normalize_catalog(catalog_payload())
    m = by_uid(items)
    lake = m["learn.fabric.lakehouse"]
    assert (lake.kind, lake.level, lake.hours) == ("trilha", 2, 8)  # 421 min -> 8 h (teto)
    assert lake.url == "https://learn.microsoft.com/en-us/training/paths/implement-lakehouse/"
    assert "<" not in lake.summary and "lakehouse" in lake.summary
    agents = m["learn.foundry.agents"]
    assert agents.level == 2 and agents.levels == ("intermediate", "advanced")  # vale o menor
    assert m["learn.dbx.spark"].level == 1 and m["learn.dbx.spark"].hours is None  # 0 min = desconhecido
    assert m["course.dp-600t00"].kind == "curso"
    # duration_in_hours dos cursos vale dias x 24 (24/48/96...), não horas de estudo: fica desconhecida
    assert m["course.dp-600t00"].hours is None
    assert m["exam.ai-500"].kind == "exame" and m["exam.ai-500"].level == 3


def test_certification_keeps_exam_codes_only_when_the_catalog_gives_them():
    m = by_uid(normalize_catalog(catalog_payload())[0])
    assert m["certification.fabric-data-engineer-associate"].exam_codes == ()
    assert m["certification.multi-agent-ai-solutions-expert"].exam_codes == ("AI-500",)
    assert m["certification.multi-agent-ai-solutions-expert"].kind == "certificação"


def test_exam_entries_may_be_dicts():
    payload = {"certifications": [{"uid": "c", "title": "C", "levels": ["beginner"],
                                   "exams": [{"uid": "exam.az-900"}], "url": "https://learn.microsoft.com/c"}]}
    [item], _ = normalize_catalog(payload)
    assert item.exam_codes == ("AZ-900",)


def test_incomplete_items_are_dropped_with_a_reason_and_never_crash():
    items, dropped = normalize_catalog(catalog_payload())
    reasons = {uid: why for uid, _, why in dropped}
    assert "learn.nolevel" not in by_uid(items) and "nível" in reasons["learn.nolevel"]
    assert "learn.nourl" not in by_uid(items) and "link" in reasons["learn.nourl"]
    assert "learn.nulls" not in by_uid(items) and "learn.nulls" in reasons


def test_payload_with_missing_lists_or_garbage_is_tolerated():
    assert normalize_catalog({}) == ([], [])
    assert normalize_catalog({"courses": "x", "exams": [None, 3, {}]})[0] == []


@pytest.mark.parametrize("raw,expected", [
    ("https://learn.microsoft.com/en-us/x/?WT.mc_id=api#frag", "https://learn.microsoft.com/en-us/x/"),
    ("http://learn.microsoft.com/x", ""),
    ("https://evil.example.com/x", ""),
    ("https://learn.microsoft.com.evil.com/x", ""),
    ("https://user:pw@learn.microsoft.com/x", ""),
    ("javascript:alert(1)", ""),
    ("", ""),
    (None, ""),
])
def test_clean_url(raw, expected):
    assert clean_url(raw) == expected


class FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_builds_the_url_and_parses_json():
    seen = {}

    def opener(url, timeout):
        seen["url"] = url
        return FakeResponse(json.dumps({"courses": []}).encode())

    assert fetch_catalog("pt-br", opener=opener) == {"courses": []}
    assert "locale=pt-br" in seen["url"] and "type=courses,learningPaths,certifications,exams" in seen["url"]


def test_fetch_rejects_a_malformed_locale_before_any_request():
    def opener(url, timeout):
        raise AssertionError("não deveria chamar a rede")

    with pytest.raises(ValueError, match="locale"):
        fetch_catalog("../../etc", opener=opener)


def test_fetch_turns_network_and_json_failures_into_value_error():
    def down(url, timeout):
        raise OSError("sem rede")

    with pytest.raises(ValueError, match="Microsoft Learn"):
        fetch_catalog(opener=down)
    with pytest.raises(ValueError, match="inválida"):
        fetch_catalog(opener=lambda u, timeout: FakeResponse(b"<html>"))
    with pytest.raises(ValueError, match="inválida"):
        fetch_catalog(opener=lambda u, timeout: FakeResponse(b"[1, 2]"))


def test_malformed_field_types_are_dropped_or_ignored_never_crash():
    payload = {
        "learningPaths": [
            {"uid": "a", "title": "A", "levels": 5, "url": "https://learn.microsoft.com/a"},
            {"uid": "b", "title": "B", "levels": [["beginner"]], "url": "https://learn.microsoft.com/b"},
            {"uid": "c", "title": "C", "levels": ["beginner"], "products": "fabric",
             "url": "https://learn.microsoft.com/c"}],
        "certifications": [
            {"uid": "d", "title": "D", "levels": ["beginner"], "exams": 7,
             "url": "https://learn.microsoft.com/d"}],
    }
    items, dropped = normalize_catalog(payload)
    by = {i.uid: i for i in items}
    assert set(by) == {"c", "d"}
    assert by["c"].products == () and by["d"].exam_codes == ()
    assert {uid for uid, _, _ in dropped} == {"a", "b"}
