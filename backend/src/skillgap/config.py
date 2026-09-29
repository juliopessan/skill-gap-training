import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/skillgap.db"
    taxonomy_path: str = "config/taxonomy_fy27.yaml"
    catalog_path: str = "config/catalog.csv"
    model: str = "claude-sonnet-5-5"


def load_settings() -> Settings:
    defaults = Settings()
    return Settings(
        db_path=os.environ.get("SKILLGAP_DB", defaults.db_path),
        taxonomy_path=os.environ.get("SKILLGAP_TAXONOMY", defaults.taxonomy_path),
        catalog_path=os.environ.get("SKILLGAP_CATALOG", defaults.catalog_path),
        model=os.environ.get("SKILLGAP_MODEL", defaults.model),
    )
