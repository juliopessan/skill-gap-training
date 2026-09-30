import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/skillgap.db"
    taxonomy_path: str = "config/taxonomy_fy27.yaml"
    catalog_path: str = "config/catalog_fy27.csv"
    model: str = "claude-sonnet-5-5"
    learn_mapping_path: str = "config/learn_mapping.yaml"
    learn_locale: str = "en-us"
    learn_mcp: bool = False  # a dataclass não liga a rede sozinha; load_settings() liga


def load_settings() -> Settings:
    defaults = Settings()
    return Settings(
        db_path=os.environ.get("SKILLGAP_DB", defaults.db_path),
        taxonomy_path=os.environ.get("SKILLGAP_TAXONOMY", defaults.taxonomy_path),
        catalog_path=os.environ.get("SKILLGAP_CATALOG", defaults.catalog_path),
        model=os.environ.get("SKILLGAP_MODEL", defaults.model),
        learn_mapping_path=os.environ.get("SKILLGAP_LEARN_MAPPING", defaults.learn_mapping_path),
        learn_locale=os.environ.get("SKILLGAP_LEARN_LOCALE", defaults.learn_locale),
        learn_mcp=os.environ.get("SKILLGAP_LEARN_MCP", "1").strip() != "0",
    )
