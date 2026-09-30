"""Regras item → skill da taxonomia para itens da Microsoft Learn (código, sem modelo).

Uma skill casa com um item quando (produto da trilha E palavra-chave em título/resumo) OU
(frase forte no título, sem exigir produto — o caso das certificações, que não têm produto).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from skillgap.learn_catalog import SOURCE, LearnItem
from skillgap.recommender import Course
from skillgap.taxonomy import Taxonomy, normalize


@dataclass(frozen=True)
class SkillRule:
    skill: str
    track: str
    keywords: tuple[str, ...]
    strong: tuple[str, ...]


@dataclass(frozen=True)
class Mapping:
    track_products: dict[str, frozenset[str]]
    rules: tuple[SkillRule, ...]


@dataclass
class MappingReport:
    total: int = 0
    matched: dict[str, list[str]] = field(default_factory=dict)
    dropped: list[tuple[str, str, str]] = field(default_factory=list)
    uncovered: list[str] = field(default_factory=list)


def load_mapping(path: str | Path, taxonomy: Taxonomy) -> Mapping:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: YAML inválido: {exc}") from exc
    valid = {s.id: s.track for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)}
    problems: list[str] = []
    track_products: dict[str, frozenset[str]] = {}
    for tid, cfg in (data.get("tracks") or {}).items():
        if tid not in taxonomy.tracks:
            problems.append(f"trilha '{tid}' não existe na taxonomia")
        track_products[tid] = frozenset((cfg or {}).get("products") or [])
    rules: list[SkillRule] = []
    for sid, cfg in (data.get("skills") or {}).items():
        cfg = cfg or {}
        if sid not in valid:
            problems.append(f"skill '{sid}' não existe na taxonomia")
            continue
        track = valid[sid]
        if track not in track_products:
            problems.append(f"skill '{sid}': a trilha '{track}' não está em 'tracks'")
        keywords = tuple(cfg.get("keywords") or [])
        strong = tuple(cfg.get("strong") or [])
        if not keywords and not strong:
            problems.append(f"skill '{sid}': defina 'keywords' ou 'strong'")
        rules.append(SkillRule(sid, track, keywords, strong))
    if problems:
        raise ValueError(f"{path}: mapeamento inválido:\n  " + "\n  ".join(problems))
    return Mapping(track_products, tuple(rules))


def _contains(haystack: str, phrase: str) -> bool:
    return bool(phrase) and f" {phrase} " in f" {haystack} "


def match_item(item: LearnItem, mapping: Mapping) -> tuple[str, tuple[str, ...]] | None:
    title = normalize(item.title)
    body = normalize(f"{item.title} {item.summary}")
    products = set(item.products)
    hits: dict[str, list[str]] = {}
    for rule in mapping.rules:
        in_track = bool(mapping.track_products.get(rule.track, frozenset()) & products)
        by_keyword = in_track and any(_contains(body, normalize(k)) for k in rule.keywords)
        by_strong = any(_contains(title, normalize(k)) for k in rule.strong)
        if by_keyword or by_strong:
            hits.setdefault(rule.track, []).append(rule.skill)
    if not hits:
        return None
    order = list(mapping.track_products)
    track = max(hits, key=lambda t: (len(hits[t]), -order.index(t) if t in order else 0))
    return track, tuple(hits[track])


def to_courses(items: list[LearnItem], mapping: Mapping, taxonomy: Taxonomy,
               dropped_before=()) -> tuple[list[Course], MappingReport]:
    report = MappingReport(total=len(items) + len(dropped_before), dropped=list(dropped_before))
    courses: list[Course] = []
    for item in items:
        hit = match_item(item, mapping)
        if hit is None:
            report.dropped.append((item.uid, item.title, "sem skill casada"))
            continue
        track, skills = hit
        for skill in skills:
            report.matched.setdefault(skill, []).append(item.title)
        courses.append(Course(
            id=f"learn:{item.uid}", title=item.title, skills=skills, level=item.level,
            hours=item.hours, link=item.url, platform=track, focus=item.summary[:200],
            provider="Microsoft Learn", kind=item.kind, source=SOURCE, verified=True,
            exam_codes=item.exam_codes))
    every = [s.id for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)]
    report.uncovered = [sid for sid in every if sid not in report.matched]
    return courses, report


def render_report(report: MappingReport, taxonomy: Taxonomy) -> str:
    names = {s.id: s.name for t in taxonomy.tracks for s in taxonomy.skills_in_track(t)}
    kept = sum(len(v) for v in report.matched.values())
    lines = [
        "# Relatório de mapeamento Microsoft Learn",
        "",
        f"Itens lidos: {report.total} · vínculos item→skill: {kept} · descartados: {len(report.dropped)}",
        "",
        "## Itens por skill",
    ]
    for skill, titles in sorted(report.matched.items()):
        lines.append(f"- {skill} ({names.get(skill, skill)}): {len(titles)}")
    lines += ["", "## Skills sem nenhum item"]
    lines += [f"- {s} ({names.get(s, s)})" for s in report.uncovered] or ["- nenhuma"]
    lines += ["", "## Descartados"]
    by_reason: dict[str, int] = {}
    for _, _, why in report.dropped:
        by_reason[why] = by_reason.get(why, 0) + 1
    lines += [f"- {why}: {n}" for why, n in sorted(by_reason.items())] or ["- nenhum"]
    return "\n".join(lines) + "\n"
