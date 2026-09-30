"""Busca complementar via MCP da Microsoft Learn (documentação, sem nível).

Só o nome de skills da taxonomia sai daqui; nunca texto do CV. Qualquer falha vira status
``unavailable``, nunca erro para o usuário.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from skillgap.models import Supplementary
from skillgap.taxonomy import Taxonomy

MCP_URL = "https://learn.microsoft.com/api/mcp"
PROTOCOL = "2025-03-26"
ALLOWED_HOST = "learn.microsoft.com"
MAX_BYTES = 2 * 1024 * 1024
MAX_SKILLS = 4
HITS_PER_SKILL = 3
CACHE_TTL = 7 * 24 * 3600
TOTAL_BUDGET = 20.0  # segundos de busca complementar por CV

Transport = Callable[[dict, "str | None"], "tuple[dict | None, str | None]"]


class McpError(Exception):
    pass


@dataclass(frozen=True)
class DocHit:
    title: str
    url: str


def learn_url(url: object) -> str:
    """https em learn.microsoft.com; mantém a query (``?view=``), remove o fragmento."""
    if not isinstance(url, str):
        return ""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return ""
    if (parts.scheme != "https" or parts.hostname != ALLOWED_HOST
            or parts.username or parts.password or port not in (None, 443)):
        return ""
    return urlunsplit(("https", ALLOWED_HOST, parts.path, parts.query, ""))


def _parse(raw: str) -> dict | None:
    if not raw.strip():
        return None
    match = re.search(r"^data: (.*)$", raw, re.M)
    try:
        value = json.loads(match.group(1) if match else raw)
    except ValueError as exc:
        raise McpError("resposta do MCP não é JSON") from exc
    return value if isinstance(value, dict) else None


def http_transport(body: dict, session_id: str | None, *, url: str = MCP_URL,
                   timeout: float = 8.0, opener=urllib.request.urlopen):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(url, json.dumps(body).encode("utf-8"), headers, method="POST")
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
            new_id = response.headers.get("Mcp-Session-Id") or session_id
    except OSError as exc:
        raise McpError(f"MCP indisponível: {exc}") from exc
    if len(raw) > MAX_BYTES:
        raise McpError("resposta do MCP grande demais")
    return _parse(raw.decode("utf-8", "replace")), new_id


class LearnMcpClient:
    def __init__(self, transport: Transport = http_transport):
        self._transport = transport
        self._session: str | None = None
        self._ready = False
        self._next_id = 0
        self._lock = threading.Lock()  # só protege estado (sessão, contador); nunca envolve I/O de rede
        self._open_lock = threading.Lock()  # serializa apenas o handshake, que acontece uma vez

    def _rpc(self, method: str, params: dict) -> dict:
        with self._lock:
            self._next_id += 1
            request_id, session = self._next_id, self._session
        reply, new_session = self._transport(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, session)
        if new_session:
            with self._lock:
                self._session = new_session
        if not reply or not isinstance(reply.get("result"), dict):
            raise McpError(f"MCP sem resultado para {method}")
        return reply["result"]

    def _open(self) -> None:
        with self._open_lock:
            if self._ready:
                return
            self._rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                     "clientInfo": {"name": "skillgap", "version": "1"}})
            with self._lock:
                session = self._session
            self._transport({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
            self._ready = True

    def _reset(self) -> None:
        with self._lock:
            self._session = None
        self._ready = False  # a sessão pode ter expirado: reabre na próxima

    def search(self, query: str, limit: int = HITS_PER_SKILL) -> list[DocHit]:
        try:
            self._open()
            result = self._rpc("tools/call", {"name": "microsoft_docs_search",
                                              "arguments": {"query": query}})
        except McpError:
            self._reset()
            raise
        text = next((c.get("text") for c in result.get("content") or []
                     if isinstance(c, dict) and c.get("type") == "text"), None)
        if not text:
            return []
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise McpError("resultado do MCP não é JSON") from exc
        rows = payload.get("results") if isinstance(payload, dict) else None
        hits: list[DocHit] = []
        seen: set[str] = set()
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            url = learn_url(row.get("contentUrl"))
            title = " ".join(str(row.get("title") or "").split())
            if not url or not title or url in seen:
                continue
            seen.add(url)
            hits.append(DocHit(title[:200], url))
            if len(hits) >= limit:
                break
        return hits


class McpCache:
    def __init__(self, path: str, ttl: float = CACHE_TTL, clock: Callable[[], float] = time.time):
        self._ttl, self._clock = ttl, clock
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        with self._lock:
            if path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("CREATE TABLE IF NOT EXISTS mcp_cache ("
                             "query TEXT PRIMARY KEY, fetched_at REAL NOT NULL, json TEXT NOT NULL)")
            self._db.commit()

    def get(self, query: str) -> list[DocHit] | None:
        with self._lock:
            row = self._db.execute("SELECT fetched_at, json FROM mcp_cache WHERE query = ?",
                                   (query,)).fetchone()
        if not row or self._clock() - row[0] > self._ttl:
            return None
        try:
            return [DocHit(**h) for h in json.loads(row[1])]
        except (ValueError, TypeError):
            return None

    def put(self, query: str, hits: list[DocHit]) -> None:
        payload = json.dumps([{"title": h.title, "url": h.url} for h in hits])
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO mcp_cache (query, fetched_at, json) VALUES (?, ?, ?)",
                             (query, self._clock(), payload))

    def close(self) -> None:
        with self._lock:
            self._db.close()


class Supplementer:
    def __init__(self, client: LearnMcpClient, cache: McpCache, taxonomy: Taxonomy,
                 enabled: bool = True, budget: float = TOTAL_BUDGET,
                 clock: Callable[[], float] = time.monotonic):
        self._client, self._cache, self._taxonomy, self.enabled = client, cache, taxonomy, enabled
        self._budget, self._clock = budget, clock

    def __call__(self, skill_ids: list[str]) -> tuple[list[Supplementary], str]:
        if not self.enabled:
            return [], "disabled"
        if not skill_ids:
            return [], "none"
        found: list[Supplementary] = []
        failed = False
        started = self._clock()
        for sid in skill_ids[:MAX_SKILLS]:
            if self._clock() - started > self._budget:  # orçamento total por CV: não trava o pipeline
                failed = True
                break
            skill = self._taxonomy.match(sid)
            if skill is None:
                continue
            query = f"{skill.name} {self._taxonomy.tracks[skill.track]} training"
            hits = self._cache.get(query)
            if hits is None:
                try:
                    hits = self._client.search(query)
                except Exception:  # rede/protocolo: não insiste nas demais skills
                    failed = True
                    break
                self._cache.put(query, hits)
            found.extend(Supplementary(skill=sid, title=h.title, url=h.url) for h in hits)
        if found:
            return found, "ok"
        return [], "unavailable" if failed else "none"
