from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()


@dataclass(frozen=True)
class TaxSkill:
    id: str
    name: str
    track: str
    expected_level: int


class Taxonomy:
    def __init__(self, tracks: dict[str, str], skills: list[TaxSkill],
                 synonyms: dict[str, list[str]]):
        self.tracks = tracks
        self._skills = skills
        self._index: dict[str, TaxSkill] = {}
        for skill in skills:
            for label in [skill.name, skill.id, *synonyms.get(skill.id, [])]:
                owner = self._index.setdefault(normalize(label), skill)
                if owner is not skill:
                    raise ValueError(
                        f"Rótulo ambíguo '{label}': {owner.id} e {skill.id}")

    def match(self, name: str) -> TaxSkill | None:
        return self._index.get(normalize(name))

    def skills_in_track(self, track_id: str) -> list[TaxSkill]:
        return [s for s in self._skills if s.track == track_id]

    def hint_names(self) -> list[str]:
        return [s.name for s in self._skills]


def load_taxonomy(path: str | Path) -> Taxonomy:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    tracks: dict[str, str] = {}
    skills: list[TaxSkill] = []
    synonyms: dict[str, list[str]] = {}
    for track in data["tracks"]:
        tracks[track["id"]] = track["name"]
        for item in track["skills"]:
            level = item["expected_level"]
            if level not in (1, 2, 3):
                raise ValueError(
                    f"expected_level inválido em {item['id']}: {level}")
            skills.append(TaxSkill(item["id"], item["name"], track["id"], level))
            synonyms[item["id"]] = item.get("synonyms") or []
    return Taxonomy(tracks, skills, synonyms)
