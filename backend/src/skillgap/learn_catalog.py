"""Download e normalização do Learn Catalog API (fonte oficial de nível, duração e link).

Só código: nenhuma chamada de modelo. O vínculo item → skill vem de ``learn_mapping``.
"""
from __future__ import annotations

import json
import math
import re
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

CATALOG_URL = "https://learn.microsoft.com/api/catalog/"
TYPES = "courses,learningPaths,certifications,exams"
SOURCE = "Microsoft Learn Catalog API"
MAX_BYTES = 64 * 1024 * 1024
ALLOWED_HOST = "learn.microsoft.com"

_LEVEL = {"beginner": 1, "intermediate": 2, "advanced": 3}
_KINDS = {"learningPaths": "trilha", "courses": "curso",
          "certifications": "certificação", "exams": "exame"}


@dataclass(frozen=True)
class LearnItem:
    uid: str
    kind: str
    title: str
    summary: str
    level: int
    levels: tuple[str, ...]
    hours: int | None
    url: str
    products: tuple[str, ...]
    exam_codes: tuple[str, ...]


def clean_url(url: object) -> str:
    """Só https em learn.microsoft.com; remove query (rastreio ``WT.mc_id``) e fragmento."""
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
    return urlunsplit(("https", ALLOWED_HOST, parts.path, "", ""))


def _text(value: object) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value).split()) if isinstance(value, str) else ""


def _hours(raw: dict) -> int | None:
    """Só ``duration_in_minutes`` (trilhas). ``duration_in_hours`` dos cursos vale dias x 24
    (24/48/96/120), não horas de estudo, e nunca é estimada: fica desconhecida."""
    value = raw.get("duration_in_minutes")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return math.ceil(value / 60)
    return None


def _exam_codes(raw: dict) -> tuple[str, ...]:
    codes: list[str] = []
    exams = raw.get("exams")
    for entry in exams if isinstance(exams, list) else []:
        uid = entry.get("uid") if isinstance(entry, dict) else entry
        if isinstance(uid, str) and "." in uid:
            codes.append(uid.split(".", 1)[1].upper())
    return tuple(codes)


def normalize_catalog(payload: dict) -> tuple[list[LearnItem], list[tuple[str, str, str]]]:
    items: list[LearnItem] = []
    dropped: list[tuple[str, str, str]] = []
    for key, kind in _KINDS.items():
        rows = payload.get(key) if isinstance(payload, dict) else None
        for raw in rows if isinstance(rows, list) else []:
            if not isinstance(raw, dict):
                continue
            uid = raw.get("uid")
            title = _text(raw.get("title"))
            if not isinstance(uid, str) or not uid or not title:
                if isinstance(uid, str) and uid:
                    dropped.append((uid, title, "sem título"))
                continue
            raw_levels = raw.get("levels")
            levels = tuple(v for v in (raw_levels if isinstance(raw_levels, list) else [])
                           if isinstance(v, str) and v in _LEVEL)
            if not levels:
                dropped.append((uid, title, "sem nível informado pela Microsoft"))
                continue
            url = clean_url(raw.get("url"))
            if not url:
                dropped.append((uid, title, "sem link válido em learn.microsoft.com"))
                continue
            raw_products = raw.get("products")
            products = tuple(p for p in (raw_products if isinstance(raw_products, list) else [])
                             if isinstance(p, str))
            items.append(LearnItem(
                uid=uid, kind=kind, title=title,
                summary=_text(raw.get("summary") or raw.get("subtitle")),
                level=min(_LEVEL[v] for v in levels), levels=levels, hours=_hours(raw),
                url=url, products=products, exam_codes=_exam_codes(raw)))
    return items, dropped


def present_kinds(payload: dict) -> set[str]:
    """Tipos (``kind``) cuja lista veio não vazia: só esses podem aposentar itens na sincronização."""
    if not isinstance(payload, dict):
        return set()
    return {kind for key, kind in _KINDS.items()
            if isinstance(payload.get(key), list) and payload[key]}


def fetch_catalog(locale: str = "en-us", opener=urllib.request.urlopen,
                  timeout: float = 90) -> dict:
    if not re.fullmatch(r"[a-z]{2}-[a-z]{2}", locale or ""):
        raise ValueError(f"locale inválido: '{locale}' (use algo como en-us ou pt-br)")
    url = f"{CATALOG_URL}?type={TYPES}&locale={locale}"
    try:
        with opener(url, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"Não foi possível baixar o catálogo da Microsoft Learn: {exc}") from exc
    if len(raw) > MAX_BYTES:
        raise ValueError("Resposta do catálogo da Microsoft Learn grande demais")
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError("Resposta inválida do catálogo da Microsoft Learn (não é JSON)") from exc
    if not isinstance(data, dict):
        raise ValueError("Resposta inválida do catálogo da Microsoft Learn (formato inesperado)")
    return data
