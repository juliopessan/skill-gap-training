"""Sobe a API com um extrator simulado (sem ANTHROPIC_API_KEY) para demonstrar a UI."""
import uvicorn

from skillgap.api import create_app
from skillgap.bootstrap import build_service
from skillgap.config import Settings
from skillgap.models import ExtractedProfile, RawSkill


def fake_extract(text: str, hints: list[str]) -> ExtractedProfile:
    return ExtractedProfile(
        candidate="Candidato de Demonstração",
        skills=[
            RawSkill(name="Lakehouse e OneLake", level=2, evidence="projetos com OneLake (simulado)"),
            RawSkill(name="Power BI", level=3, evidence="dashboards em Power BI (simulado)"),
            RawSkill(name="PySpark", level=1, evidence="curso de PySpark (simulado)"),
            RawSkill(name="Kubernetes", level=2, evidence="operação de clusters (simulado)"),
        ],
    )


if __name__ == "__main__":
    service = build_service(Settings(db_path="data/demo.db"), extract=fake_extract)
    uvicorn.run(create_app(service), host="127.0.0.1", port=8000)
