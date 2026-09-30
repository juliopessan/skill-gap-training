import logging

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from pdfs import make_text_pdf
from skillgap.api import create_app
from support import make_service

FAKE = "sk-ant-test-0000000000000000"
ORIGIN = {"Origin": "http://localhost:3000"}
HOST = {"Host": "localhost:8000"}
GOOD = {**ORIGIN, **HOST}
ROUTES = [("GET", "/settings/api-key"), ("PUT", "/settings/api-key"),
          ("DELETE", "/settings/api-key"), ("POST", "/settings/api-key/test")]

_REQ = httpx.Request("POST", "http://x")


def _resp(status):
    return httpx.Response(status, request=_REQ)


class FakeClient:
    def __init__(self, key, error=None, factory=None):
        self.key, self.error = key, error
        self.models = self

    def list(self, limit=1):
        if self.error:
            raise self.error
        return []


class Factory:
    def __init__(self, error=None):
        self.error, self.keys = error, []

    def __call__(self, key):
        self.keys.append(key)
        return FakeClient(key, self.error)


@pytest.fixture
def env(small_taxonomy, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    service, extractor = make_service(small_taxonomy)
    factory = Factory()
    client = TestClient(create_app(service, client_factory=factory), base_url="http://localhost")
    return client, service, factory


def put(client, key=FAKE, headers=GOOD):
    return client.put("/settings/api-key", json={"api_key": key}, headers=headers)


def headers_text(response):
    return " ".join(f"{k}: {v}" for k, v in response.headers.items())


def test_status_when_nothing_is_set(env):
    client, _, _ = env
    response = client.get("/settings/api-key", headers=GOOD)
    assert response.status_code == 200
    assert response.json() == {"configured": False, "source": None}


def test_put_get_delete_cycle_never_exposes_the_key(env):
    client, service, _ = env
    r = put(client)
    assert r.status_code == 200
    assert r.json() == {"configured": True, "source": "session"}
    assert service.keystore.get() == FAKE
    g = client.get("/settings/api-key", headers=GOOD)
    assert g.json() == {"configured": True, "source": "session"}
    for response in (r, g):
        assert FAKE not in response.text and FAKE not in headers_text(response)
    d = client.delete("/settings/api-key", headers=GOOD)
    assert d.status_code == 200
    assert d.json() == {"configured": False, "source": None}
    assert service.keystore.get() is None


def test_delete_falls_back_to_environment(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-envenvenvenvenvenv")
    put(client)
    d = client.delete("/settings/api-key", headers=GOOD)
    assert d.json() == {"configured": True, "source": "environment"}
    assert "envenv" not in d.text


@pytest.mark.parametrize("bad", ["xyz123", "     ", "sk-ant-test-0000 0000000000"])
def test_invalid_key_is_422_in_portuguese_without_echo(env, bad):
    client, service, _ = env
    r = put(client, bad)
    assert r.status_code == 422
    assert bad.strip() == "" or bad not in r.text
    assert isinstance(r.json()["detail"], str) and "chave" in r.json()["detail"].lower()
    assert service.keystore.get() is None


def test_extra_fields_are_422_without_echo(env):
    client, _, _ = env
    r = client.put("/settings/api-key",
                   json={"api_key": FAKE, "extra": "SEGREDO-EXTRA"}, headers=GOOD)
    assert r.status_code == 422
    assert FAKE not in r.text and "SEGREDO-EXTRA" not in r.text


def test_wrong_type_and_missing_field_do_not_echo(env):
    client, _, _ = env
    r = client.put("/settings/api-key", json={"api_key": {"k": FAKE}}, headers=GOOD)
    assert r.status_code == 422 and FAKE not in r.text
    r = client.put("/settings/api-key", content=b"nao-json " + FAKE.encode(),
                   headers={**GOOD, "Content-Type": "application/json"})
    assert r.status_code == 422 and FAKE not in r.text


@pytest.mark.parametrize("method,path", ROUTES)
def test_guard_requires_an_allowed_origin(env, method, path):
    client, _, _ = env
    kwargs = {"json": {"api_key": FAKE}} if method == "PUT" else {}
    assert client.request(method, path, headers=HOST, **kwargs).status_code == 403
    r = client.request(method, path, headers={**HOST, "Origin": "https://evil.example"}, **kwargs)
    assert r.status_code == 403
    assert r.json() == {"detail": "Origem não permitida."}
    ok = client.request(method, path, headers={**HOST, "Origin": "http://127.0.0.1:3000"}, **kwargs)
    assert ok.status_code != 403


@pytest.mark.parametrize("method,path", ROUTES)
def test_guard_blocks_rebinding_hosts(env, method, path):
    client, _, _ = env
    kwargs = {"json": {"api_key": FAKE}} if method == "PUT" else {}
    for host in ("evil.example", "evil.example:8000", "localhost.evil.example"):
        r = client.request(method, path, headers={**ORIGIN, "Host": host}, **kwargs)
        assert r.status_code == 403, host
    for host in ("localhost", "localhost:8000", "127.0.0.1:8000", "[::1]:8000"):
        r = client.request(method, path, headers={**ORIGIN, "Host": host}, **kwargs)
        assert r.status_code != 403, host


def test_guard_failure_does_not_set_the_key(env):
    client, service, _ = env
    put(client, headers={**HOST, "Origin": "https://evil.example"})
    assert service.keystore.get() is None


def test_test_endpoint_without_key_is_409(env):
    client, _, factory = env
    r = client.post("/settings/api-key/test", headers=GOOD)
    assert r.status_code == 409
    assert r.json() == {"detail": "Nenhuma chave configurada."}
    assert factory.keys == []


def test_test_endpoint_valid_uses_session_key(env):
    client, _, factory = env
    put(client)
    r = client.post("/settings/api-key/test", headers=GOOD)
    assert r.status_code == 200 and r.json() == {"status": "valid"}
    assert factory.keys == [FAKE]


@pytest.mark.parametrize("error,expected", [
    (anthropic.AuthenticationError("SDK-SECRET-MSG", response=_resp(401), body=None), "invalid"),
    (anthropic.PermissionDeniedError("SDK-SECRET-MSG", response=_resp(403), body=None), "invalid"),
    (anthropic.APIConnectionError(message="SDK-SECRET-MSG", request=_REQ), "unreachable"),
    (anthropic.APITimeoutError(request=_REQ), "unreachable"),
    (anthropic.InternalServerError("SDK-SECRET-MSG", response=_resp(500), body=None), "error"),
    (anthropic.RateLimitError("SDK-SECRET-MSG", response=_resp(429), body=None), "error"),
])
def test_test_endpoint_maps_sdk_errors(small_taxonomy, monkeypatch, error, expected):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    service, _ = make_service(small_taxonomy)
    client = TestClient(create_app(service, client_factory=Factory(error)), base_url="http://localhost")
    put(client)
    r = client.post("/settings/api-key/test", headers=GOOD)
    assert r.status_code == 200 and r.json() == {"status": expected}
    assert FAKE not in r.text and "SDK-SECRET-MSG" not in r.text
    assert FAKE not in headers_text(r)


def test_default_factory_builds_a_real_client_without_network(small_taxonomy, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seen = {}

    class Spy:
        def __init__(self, **kwargs):
            seen.update(kwargs)
            self.models = self

        def list(self, limit=1):
            return []

    monkeypatch.setattr("skillgap.settings_api.anthropic.Anthropic", Spy)
    service, _ = make_service(small_taxonomy)
    client = TestClient(create_app(service), base_url="http://localhost")
    put(client)
    assert client.post("/settings/api-key/test", headers=GOOD).json() == {"status": "valid"}
    assert seen["api_key"] == FAKE


def test_no_log_record_contains_the_key(env, caplog):
    client, _, _ = env
    caplog.set_level(logging.DEBUG)
    put(client)
    put(client, "xyz123")
    client.post("/settings/api-key/test", headers=GOOD)
    client.delete("/settings/api-key", headers=GOOD)
    err = anthropic.AuthenticationError("x", response=_resp(401), body=None)
    c2 = TestClient(create_app(env[1], client_factory=Factory(err)), base_url="http://localhost")
    put(c2)
    c2.post("/settings/api-key/test", headers=GOOD)
    assert FAKE not in caplog.text
    assert all(FAKE not in r.getMessage() for r in caplog.records)
    assert "AuthenticationError" in caplog.text


def test_cors_still_allows_frontend_and_preflight_for_put(env):
    client, _, _ = env
    r = client.options("/settings/api-key", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "PUT"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "PUT" in r.headers["access-control-allow-methods"]


def test_upload_still_works_without_any_key(env):
    client, service, _ = env
    cv = make_text_pdf(["Maria Silva", "Experience with Microsoft Fabric OneLake and PySpark."])
    r = client.post("/candidates", files=[("files", ("m.pdf", cv, "application/pdf"))])
    assert r.status_code == 202
    assert client.get(f"/candidates/{r.json()[0]['id']}").json()["status"] == "done"
    assert service.keystore.get() is None
