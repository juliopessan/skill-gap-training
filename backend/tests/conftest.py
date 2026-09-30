import pytest

from skillgap.taxonomy import load_taxonomy

SMALL_YAML = """
tracks:
  - id: fabric
    name: Microsoft Fabric
    skills:
      - id: fabric.lakehouse
        name: Lakehouse
        synonyms: [OneLake, Delta Lake]
        expected_level: 2
      - id: fabric.pipelines
        name: Data Pipelines
        synonyms: [Data Factory]
        expected_level: 2
  - id: foundry
    name: Azure AI Foundry
    skills:
      - id: foundry.agents
        name: AI Agents
        synonyms: [Agent Service]
        expected_level: 2
      - id: foundry.models
        name: Model Deployment
        expected_level: 1
  - id: databricks
    name: Databricks
    skills:
      - id: databricks.spark
        name: Apache Spark
        synonyms: [PySpark, Spark]
        expected_level: 3
"""


@pytest.fixture
def small_taxonomy(tmp_path):
    path = tmp_path / "taxonomy.yaml"
    path.write_text(SMALL_YAML, encoding="utf-8")
    return load_taxonomy(path)


@pytest.fixture(autouse=True)
def _close_stores():
    from support import OPEN_STORES
    yield
    while OPEN_STORES:
        OPEN_STORES.pop().close()


@pytest.fixture(autouse=True)
def _no_learn_mcp(monkeypatch):
    """Nenhum teste toca a rede: o MCP da Learn fica desligado."""
    monkeypatch.setenv("SKILLGAP_LEARN_MCP", "0")
