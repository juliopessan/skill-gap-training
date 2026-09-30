from skillgap.catalog_store import CatalogStore
from skillgap.config import Settings
from skillgap.keystore import KeyStore
from skillgap.pipeline import Deps
from skillgap.service import CandidateService
from skillgap.skill_extractor import extract_profile
from skillgap.store import Store
from skillgap.taxonomy import load_taxonomy


def build_service(settings: Settings, extract=None,
                  keystore: KeyStore | None = None) -> CandidateService:
    taxonomy = load_taxonomy(settings.taxonomy_path)
    catalog = CatalogStore(settings.db_path)
    try:
        # Só importa o CSV quando a tabela está vazia; nunca sobrescreve edições.
        # CSV inválido derruba a inicialização com mensagem clara.
        catalog.seed_from_csv_if_empty(settings.catalog_path, taxonomy)
    except Exception:
        catalog.close()
        raise
    keystore = keystore if keystore is not None else KeyStore()
    if extract is None:
        def extract(text, hints):
            # Lê a chave a cada chamada: alterações em runtime valem na hora.
            return extract_profile(text, hints, model=settings.model, api_key=keystore.get())
    # courses é lido do SQLite a cada CV processado (sem reiniciar o servidor).
    return CandidateService(Store(settings.db_path), Deps(taxonomy, catalog.all_courses, extract),
                            keystore, catalog=catalog)
