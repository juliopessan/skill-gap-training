import pytest
from fastapi.testclient import TestClient

from skillgap.api import create_app
from skillgap.recommender import Course
from support import make_service

COURSES = [
    Course("f1", "Fabric Fundamentals", ("fabric.lakehouse", "fabric.platform"), 1, None, "",
           platform="fabric", focus="OneLake", provider="Microsoft Learn", kind="curso",
           source="S", verified=False),
    Course("f2", "DP-600", ("fabric.warehouse",), 3, 20, "https://x", platform="fabric",
           kind="certificação", verified=True),
    Course("d1", "Spark 100% Real", ("databricks.spark",), 2, None, "", platform="databricks"),
]


@pytest.fixture
def client(small_taxonomy):
    service, _ = make_service(small_taxonomy)
    service.catalog.replace_all(COURSES)
    return TestClient(create_app(service), base_url="http://localhost")


def ids(response):
    return [i["id"] for i in response.json()["items"]]


def test_list_all_with_course_shape(client):
    r = client.get("/catalog")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and ids(r) == ["d1", "f1", "f2"]
    f1 = next(i for i in body["items"] if i["id"] == "f1")
    assert f1 == {"id": "f1", "platform": "fabric", "title": "Fabric Fundamentals",
                  "focus": "OneLake", "level": 1, "provider": "Microsoft Learn", "kind": "curso",
                  "hours": None, "link": "", "source": "S", "verified": False,
                  "skills": ["fabric.lakehouse", "fabric.platform"]}
    f2 = next(i for i in body["items"] if i["id"] == "f2")
    assert f2["hours"] == 20 and f2["verified"] is True


@pytest.mark.parametrize("query, expected", [
    ("platform=fabric", ["f1", "f2"]), ("level=2", ["d1"]), ("kind=certificação", ["f2"]),
    ("skill=fabric.warehouse", ["f2"]), ("q=100%25", ["d1"]), ("q=onelake", ["f1"]),
    ("platform=fabric&level=3", ["f2"]), ("platform=nada", []),
])
def test_filters(client, query, expected):
    r = client.get(f"/catalog?{query}")
    assert r.status_code == 200 and ids(r) == expected and r.json()["total"] == len(expected)


def test_total_counts_before_limit(client):
    r = client.get("/catalog?limit=2")
    assert len(r.json()["items"]) == 2 and r.json()["total"] == 3


@pytest.mark.parametrize("query", ["level=9", "level=0", "level=abc", "limit=0", "limit=201", "limit=x"])
def test_invalid_params_are_422_in_portuguese(client, query):
    r = client.get(f"/catalog?{query}")
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and "inválid" in r.json()["detail"].lower()


def test_limit_200_is_accepted(client):
    assert client.get("/catalog?limit=200").status_code == 200


def test_stats_route_is_not_shadowed_by_id_route(client):
    r = client.get("/catalog/stats")
    assert r.status_code == 200
    assert r.json() == {"total": 3, "by_platform": {"databricks": 1, "fabric": 2},
                        "by_level": {"1": 1, "2": 1, "3": 1}, "by_kind": {"certificação": 1, "curso": 2},
                        "verified": 1, "unverified": 2, "hours_unknown": 2}


def test_get_one_and_404(client):
    assert client.get("/catalog/f2").json()["title"] == "DP-600"
    r = client.get("/catalog/nao-existe")
    assert r.status_code == 404 and r.json() == {"detail": "Curso não encontrado"}


def test_injection_in_query_is_inert(client):
    r = client.get("/catalog", params={"q": "'; DROP TABLE courses;--"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/catalog").json()["total"] == 3


@pytest.mark.parametrize("path", ["/catalog", "/catalog/stats", "/catalog/f1"])
def test_bad_host_is_403(client, path):
    r = client.get(path, headers={"Host": "evil.com"})
    assert r.status_code == 403


def test_app_works_without_a_catalog_attribute(small_taxonomy):
    service, _ = make_service(small_taxonomy)
    service.catalog = None
    client = TestClient(create_app(service), base_url="http://localhost")
    assert client.get("/taxonomy").status_code == 200
    assert client.get("/catalog").status_code == 404


