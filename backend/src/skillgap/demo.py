"""Sobe a API com um extrator simulado (sem ANTHROPIC_API_KEY) para demonstrar a UI."""
import uvicorn

from skillgap.api import create_app
from skillgap.bootstrap import build_service
from skillgap.config import Settings
from skillgap.evidence import MIN_FRAGMENT
from skillgap.models import ExtractedProfile, RawSkill


def _cut(line: str, limit: int = 60) -> str:
    """Cut at ~limit chars on a word boundary (the verifier rejects mid-word matches)."""
    if len(line) <= limit:
        return line
    return line[:limit].rsplit(" ", 1)[0] if " " in line[:limit] else line


def _real_fragments(text: str, count: int) -> list[str] | None:
    lines = [_cut(line.strip()) for line in text.splitlines() if len(line.strip()) >= MIN_FRAGMENT]
    return lines[:count] if len(lines) >= count else None


def fake_extract(text: str, hints: list[str]) -> ExtractedProfile:
    # The demo mixes real and invented quotes on purpose: the last one must show up as "not found".
    fixed = ["projetos com OneLake (simulado)", "dashboards em Power BI (simulado)", "curso de PySpark (simulado)"]
    evidence = _real_fragments(text, 3) or fixed
    return ExtractedProfile(
        candidate="Candidato de Demonstração",
        skills=[
            RawSkill(name="Lakehouse e OneLake", level=2, evidence=evidence[0]),
            RawSkill(name="Power BI", level=3, evidence=evidence[1]),
            RawSkill(name="PySpark", level=1, evidence=evidence[2]),
            RawSkill(name="Kubernetes", level=2, evidence="operação de clusters (simulado)"),
        ],
    )


if __name__ == "__main__":
    service = build_service(Settings(db_path="data/demo.db"), extract=fake_extract)
    uvicorn.run(create_app(service), host="127.0.0.1", port=8000)
