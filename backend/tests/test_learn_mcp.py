import itertools
import json

import pytest

from support import OPEN_STORES
from skillgap.learn_mcp import (DocHit, LearnMcpClient, McpCache, McpError, Supplementer,
                                http_transport, learn_url)


def sse(obj):
    return "event: message\ndata: " + json.dumps(obj) + "\n\n"


def search_result(rows):
    return {"jsonrpc": "2.0", "id": 2, "result": {"content": [
        {"type": "text", "text": json.dumps({"results": rows})}]}}


class FakeTransport:
    """Simula o servidor: initialize devolve sessão; tools/call devolve ``rows``."""

    def __init__(self, rows=None, fail=False):
        self.rows, self.fail, self.calls = rows or [], fail, []

    def __call__(self, body, session_id):
        self.calls.append((body, session_id))
        if self.fail:
            raise McpError("MCP indisponível: timeout")
        method = body.get("method")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": body["id"], "result": {"serverInfo": {"name": "x"}}}, "sess-1"
        if method == "notifications/initialized":
            return None, session_id
        return search_result(self.rows), session_id


ROWS = [
    {"title": "Implement a Lakehouse", "content": "# md", "contentUrl": "https://learn.microsoft.com/en-us/training/paths/a/"},
    {"title": "Dup", "content": "", "contentUrl": "https://learn.microsoft.com/en-us/training/paths/a/"},
    {"title": "Evil", "content": "", "contentUrl": "https://evil.example.com/x"},
    {"title": "", "content": "", "contentUrl": "https://learn.microsoft.com/no-title"},
    {"title": "Second", "content": "", "contentUrl": "https://learn.microsoft.com/en-us/training/paths/b/?x=1#f"},
    "garbage",
]


def test_handshake_then_search_filters_domain_dupes_and_limits():
    t = FakeTransport(ROWS)
    hits = LearnMcpClient(t).search("fabric lakehouse", limit=5)
    assert hits == [DocHit("Implement a Lakehouse", "https://learn.microsoft.com/en-us/training/paths/a/"),
                    DocHit("Second", "https://learn.microsoft.com/en-us/training/paths/b/?x=1")]
    methods = [c[0].get("method") for c in t.calls]
    assert methods == ["initialize", "notifications/initialized", "tools/call"]
    assert t.calls[2][1] == "sess-1"  # o id de sessão volta nas chamadas seguintes
    assert t.calls[2][0]["params"] == {"name": "microsoft_docs_search", "arguments": {"query": "fabric lakehouse"}}


def test_session_is_opened_once_and_limit_applies():
    t = FakeTransport(ROWS)
    c = LearnMcpClient(t)
    assert len(c.search("a", limit=1)) == 1
    c.search("b")
    assert [x[0].get("method") for x in t.calls].count("initialize") == 1


def test_transport_failure_raises_and_next_search_reopens_the_session():
    t = FakeTransport(ROWS)
    c = LearnMcpClient(t)
    c.search("a")
    t.fail = True
    with pytest.raises(McpError):
        c.search("b")
    t.fail = False
    c.search("c")
    assert [x[0].get("method") for x in t.calls].count("initialize") == 2


@pytest.mark.parametrize("bad", [{"jsonrpc": "2.0", "id": 2, "result": {"content": []}},
                                 {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "not json"}]}}])
def test_malformed_results(bad):
    class T(FakeTransport):
        def __call__(self, body, sid):
            if body.get("method") == "tools/call":
                return bad, sid
            return super().__call__(body, sid)

    c = LearnMcpClient(T())
    try:
        assert c.search("x") == []
    except McpError:
        pass  # texto que não é JSON deve virar McpError, nunca outra exceção


def test_learn_url():
    assert learn_url("https://learn.microsoft.com/a/b?view=x#frag") == "https://learn.microsoft.com/a/b?view=x"
    for bad in ("http://learn.microsoft.com/a", "https://learn.microsoft.com.evil.com/a", "ftp://x", None, 5, ""):
        assert learn_url(bad) == ""


class FakeResp:
    def __init__(self, body, sid=None):
        self._b, self.headers = body, ({"Mcp-Session-Id": sid} if sid else {})

    def read(self, n=-1):
        return self._b if n < 0 else self._b[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_transport_parses_sse_and_plain_json_and_session_header():
    body, sid = http_transport({"a": 1}, None, opener=lambda r, timeout: FakeResp(sse({"result": {}}).encode(), "s9"))
    assert body == {"result": {}} and sid == "s9"
    body, sid = http_transport({"a": 1}, "keep", opener=lambda r, timeout: FakeResp(b'{"result": {"x": 1}}'))
    assert body == {"result": {"x": 1}} and sid == "keep"
    assert http_transport({"a": 1}, None, opener=lambda r, timeout: FakeResp(b""))[0] is None


def test_http_transport_errors_become_mcp_error():
    def down(r, timeout):
        raise OSError("boom")

    with pytest.raises(McpError):
        http_transport({}, None, opener=down)
    with pytest.raises(McpError):
        http_transport({}, None, opener=lambda r, timeout: FakeResp(b"<html>"))
    with pytest.raises(McpError, match="grande demais"):
        http_transport({}, None, opener=lambda r, timeout: FakeResp(b"x" * (2 * 1024 * 1024 + 5)))


def test_cache_hit_expiry_and_corrupt_row(tmp_path):
    now = [1000.0]
    cache = McpCache(str(tmp_path / "c.db"), ttl=10, clock=lambda: now[0])
    OPEN_STORES.append(cache)
    assert cache.get("q") is None
    cache.put("q", [DocHit("T", "https://learn.microsoft.com/t")])
    assert cache.get("q") == [DocHit("T", "https://learn.microsoft.com/t")]
    now[0] = 1011.0
    assert cache.get("q") is None
    cache._db.execute("INSERT OR REPLACE INTO mcp_cache VALUES ('bad', ?, 'not json')", (now[0],))
    assert cache.get("bad") is None


_caches = itertools.count()


def make(tmp_path, taxonomy, transport, enabled=True):
    # um cache por chamada: respostas gravadas por uma não podem esconder a falha de outra
    cache = McpCache(str(tmp_path / f"c{next(_caches)}.db"))
    OPEN_STORES.append(cache)
    return Supplementer(LearnMcpClient(transport), cache, taxonomy, enabled)


def test_supplementer_queries_only_taxonomy_names_and_caches(tmp_path, small_taxonomy):
    t = FakeTransport(ROWS)
    sup = make(tmp_path, small_taxonomy, t)
    found, status = sup(["fabric.lakehouse"])
    assert status == "ok" and [s.skill for s in found] == ["fabric.lakehouse"] * 2
    assert found[0].url.startswith("https://learn.microsoft.com/")
    query = [c[0] for c in t.calls if c[0].get("method") == "tools/call"][0]["params"]["arguments"]["query"]
    assert query == "Lakehouse Microsoft Fabric training"  # nome da skill + nome da trilha, nada mais
    n = len(t.calls)
    sup(["fabric.lakehouse"])
    assert len(t.calls) == n  # segunda vez vem do cache


def test_supplementer_statuses(tmp_path, small_taxonomy):
    assert make(tmp_path, small_taxonomy, FakeTransport(ROWS), enabled=False)(["fabric.lakehouse"]) == ([], "disabled")
    assert make(tmp_path, small_taxonomy, FakeTransport(ROWS))([]) == ([], "none")
    assert make(tmp_path, small_taxonomy, FakeTransport([]))(["fabric.lakehouse"]) == ([], "none")
    assert make(tmp_path, small_taxonomy, FakeTransport(ROWS, fail=True))(["fabric.lakehouse"]) == ([], "unavailable")
    assert make(tmp_path, small_taxonomy, FakeTransport(ROWS))(["not.a.skill"]) == ([], "none")


def test_supplementer_stops_after_the_first_network_failure_and_caps_skills(tmp_path, small_taxonomy):
    t = FakeTransport(ROWS, fail=True)
    make(tmp_path, small_taxonomy, t)(["fabric.lakehouse", "fabric.pipelines", "foundry.agents"])
    assert len(t.calls) == 1  # não insiste em cada skill quando a rede caiu
    t2 = FakeTransport(ROWS)
    skills = ["fabric.lakehouse", "fabric.pipelines", "foundry.agents", "foundry.models", "databricks.spark"]
    make(tmp_path, small_taxonomy, t2)(skills)
    assert sum(1 for c in t2.calls if c[0].get("method") == "tools/call") <= 4


def test_supplementer_respects_a_total_time_budget(tmp_path, small_taxonomy):
    now = [0.0]

    class Slow(FakeTransport):
        def __call__(self, body, sid):
            now[0] += 10
            return super().__call__(body, sid)

    t = Slow(ROWS)
    cache = McpCache(str(tmp_path / "budget.db"))
    OPEN_STORES.append(cache)
    sup = Supplementer(LearnMcpClient(t), cache, small_taxonomy, budget=25, clock=lambda: now[0])
    sup(["fabric.lakehouse", "fabric.pipelines", "foundry.agents", "foundry.models"])
    assert sum(1 for c in t.calls if c[0].get("method") == "tools/call") == 1  # estourou o orçamento: para


def test_concurrent_searches_do_not_serialize_on_a_client_lock():
    import threading
    barrier = threading.Barrier(2, timeout=3)

    class Rendezvous(FakeTransport):
        def __call__(self, body, sid):
            if body.get("method") == "tools/call":
                barrier.wait()  # só passa se as duas buscas estiverem em voo ao mesmo tempo
            return super().__call__(body, sid)

    client = LearnMcpClient(Rendezvous(ROWS))
    client._open()
    errors = []

    def go(q):
        try:
            client.search(q)
        except Exception as exc:  # BrokenBarrierError se ficou serializado
            errors.append(exc)

    threads = [threading.Thread(target=go, args=(q,)) for q in ("a", "b")]
    [t.start() for t in threads]
    [t.join(10) for t in threads]
    assert errors == []
