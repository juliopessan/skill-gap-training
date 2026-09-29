from skillgap.config import load_settings


def test_defaults(monkeypatch):
    for name in ("SKILLGAP_DB", "SKILLGAP_TAXONOMY", "SKILLGAP_CATALOG", "SKILLGAP_MODEL"):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert settings.db_path == "data/skillgap.db"
    assert settings.taxonomy_path == "config/taxonomy_fy27.yaml"
    assert settings.catalog_path == "config/catalog.csv"
    assert settings.model == "claude-sonnet-5-5"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("SKILLGAP_DB", "/tmp/x.db")
    monkeypatch.setenv("SKILLGAP_MODEL", "outro-modelo")
    settings = load_settings()
    assert settings.db_path == "/tmp/x.db"
    assert settings.model == "outro-modelo"
