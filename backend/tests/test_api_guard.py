import anthropic
import pytest
from fastapi.testclient import TestClient

from pdfs import make_text_pdf
from skillgap.api import create_app
from skillgap.settings_api import is_allowed_host
from support import make_service

FAKE = "sk-ant-test-0000000000000000"
ORIGIN = {"Origin": "http://localhost:3000"}
EVIL = {"Origin": "https://evil.example"}
CV = make_text_pdf(["Maria Silva", "Experience with Microsoft Fabric."])
ROUTES = [("GET", "/settings/api-key"), ("PUT", "/settings/api-key"),
          ("DELETE", "/settings/api-key"), ("POST", "/settings/api-key/test")]
BAD_HOSTS = ["evil.com", "localhost.evil.com", "127.0.0.1.nip.io", "evil.com:8000"]


@pytest.fixture
def client(small_taxonomy, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    service, _ = make_service(small_taxonomy)
    return TestClient(create_app(service), base_url="http://localhost")


def body_variants():
    return [
        {"content": b"{not json " + FAKE.encode(), "headers": {"Content-Type": "application/json"}},
        {"content": b"x" * (2 * 1024 * 1024), "headers": {"Content-Type": "application/json"}},
        {"content": b"plain", "headers": {"Content-Type": "text/plain"}},
        {},
    ]


@pytest.mark.parametrize("method,path", ROUTES)
def test_evil_or_missing_origin_is_403_before_any_body_parsing(client, method, path):
    for variant in body_variants():
        extra = dict(variant)
        headers = {**EVIL, **extra.pop("headers", {})}
        r = client.request(method, path, headers=headers, **extra)
        assert r.status_code == 403
        assert r.json() == {"detail": "Origem não permitida."}
        assert FAKE not in r.text
        headers = extra_headers = dict(variant.get("headers", {}))
        r = client.request(method, path, headers=extra_headers,
                           **{k: v for k, v in variant.items() if k != "headers"})
        assert r.status_code == 403


@pytest.mark.parametrize("method,path", ROUTES)
def test_bad_host_is_403_before_any_body_parsing(client, method, path):
    for variant in body_variants():
        extra = dict(variant)
        headers = {**ORIGIN, "Host": "evil.com", **extra.pop("headers", {})}
        r = client.request(method, path, headers=headers, **extra)
        assert r.status_code == 403
        assert r.json() == {"detail": "Host não permitido."}


def test_good_origin_with_invalid_json_is_422_without_echo(client):
    r = client.put("/settings/api-key", content=b"{nope " + FAKE.encode(),
                   headers={**ORIGIN, "Content-Type": "application/json"})
    assert r.status_code == 422 and FAKE not in r.text


def test_validation_error_never_echoes_client_key_names(client):
    r = client.put("/settings/api-key", json={FAKE: "x", "api_key": "y" * 30}, headers=ORIGIN)
    assert r.status_code == 422
    assert FAKE not in r.text
    assert set(r.json()["fields"]) <= {"api_key", "body", "campo desconhecido"}
    assert "campo desconhecido" in r.json()["fields"]


@pytest.mark.parametrize("host", BAD_HOSTS)
def test_rebinding_hosts_are_403_on_every_route(client, host, small_taxonomy):
    h = {"Host": host}
    assert client.get("/candidates", headers=h).status_code == 403
    assert client.get("/candidates/abc", headers=h).status_code == 403
    assert client.get("/candidates/abc/export", headers=h).status_code == 403
    assert client.get("/taxonomy", headers=h).status_code == 403
    r = client.post("/candidates", files=[("files", ("a.pdf", CV, "application/pdf"))], headers=h)
    assert r.status_code == 403
    assert client.get("/candidates").json() == []  # nothing persisted
    for method, path in ROUTES:
        r = client.request(method, path, headers={**ORIGIN, **h})
        assert r.status_code == 403 and r.json() == {"detail": "Host não permitido."}


@pytest.mark.parametrize("host", ["localhost", "LOCALHOST:8000", "127.0.0.1:8000", "[::1]:8000"])
def test_legitimate_hosts_work(client, host):
    assert client.get("/taxonomy", headers={"Host": host}).status_code == 200
    assert client.get("/candidates", headers={"Host": host}).status_code == 200


def test_preflight_from_allowed_origin_still_works(client):
    r = client.options("/settings/api-key", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "PUT"})
    assert r.status_code == 200
    r = client.options("/candidates", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200


def test_allowed_hosts_is_configurable(small_taxonomy):
    service, _ = make_service(small_taxonomy)
    c = TestClient(create_app(service, allowed_hosts=["testserver"]))
    assert c.get("/taxonomy").status_code == 200
    assert c.get("/taxonomy", headers={"Host": "localhost"}).status_code == 403


@pytest.mark.parametrize("value,ok", [
    ("localhost", True), ("localhost:8000", True), ("LocalHost:1", True),
    ("127.0.0.1", True), ("[::1]:8000", True),
    ("localhost\n", False), ("localhost\nevil", False), (" localhost", False),
    ("localhost:", False), ("localhost:8000\n", False), ("", False), ("evil.com", False),
])
def test_host_regex_is_a_fullmatch(value, ok):
    assert is_allowed_host(value) is ok


def test_settings_slash_variant_does_not_redirect(client):
    r = client.get("/settings/api-key/", headers=ORIGIN, follow_redirects=False)
    assert r.status_code == 404


@pytest.mark.parametrize("method,path", ROUTES)
def test_settings_responses_are_no_store(client, method, path):
    r = client.request(method, path, headers=ORIGIN)
    assert r.headers["cache-control"] == "no-store"
    r = client.request(method, path, headers=EVIL)  # errors too
    assert r.headers["cache-control"] == "no-store"
    r = client.put("/settings/api-key", json={"api_key": "x"}, headers=ORIGIN)
    assert r.headers["cache-control"] == "no-store"


def test_non_settings_responses_are_not_forced_no_store(client):
    assert "no-store" not in client.get("/taxonomy").headers.get("cache-control", "")
