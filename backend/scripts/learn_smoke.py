"""Teste ao vivo: sincroniza o catálogo real num banco temporário e faz uma busca no MCP.

Uso (a partir de backend/):  .venv/bin/python scripts/learn_smoke.py
Não grava nada no banco do app.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillgap.catalog_store import CatalogStore, validate_courses  # noqa: E402
from skillgap.learn_catalog import fetch_catalog, normalize_catalog  # noqa: E402
from skillgap.learn_mapping import load_mapping, render_report, to_courses  # noqa: E402
from skillgap.learn_mcp import LearnMcpClient  # noqa: E402
from skillgap.taxonomy import load_taxonomy  # noqa: E402


def main() -> int:
    taxonomy = load_taxonomy("config/taxonomy_fy27.yaml")
    items, dropped = normalize_catalog(fetch_catalog("en-us"))
    courses, report = to_courses(items, load_mapping("config/learn_mapping.yaml", taxonomy), taxonomy, dropped)
    validate_courses(courses, taxonomy)
    with tempfile.TemporaryDirectory() as tmp:
        store = CatalogStore(f"{tmp}/smoke.db")
        print(store.sync_learn(courses, "smoke"))
        print(store.learn_status())
        store.close()
    print(render_report(report, taxonomy))
    hits = LearnMcpClient().search("Microsoft Fabric lakehouse training")
    print("MCP:", [(h.title, h.url) for h in hits])
    return 0 if courses and hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
