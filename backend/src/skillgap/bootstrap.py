from skillgap.config import Settings
from skillgap.pipeline import Deps
from skillgap.recommender import load_catalog
from skillgap.service import CandidateService
from skillgap.skill_extractor import extract_profile
from skillgap.store import Store
from skillgap.taxonomy import load_taxonomy


def build_service(settings: Settings, extract=None) -> CandidateService:
    taxonomy = load_taxonomy(settings.taxonomy_path)
    courses = load_catalog(settings.catalog_path)
    if extract is None:
        def extract(text, hints):
            return extract_profile(text, hints, model=settings.model)
    return CandidateService(Store(settings.db_path), Deps(taxonomy, courses, extract))
