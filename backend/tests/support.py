from skillgap.catalog_store import CatalogStore
from skillgap.models import ExtractedProfile, RawSkill
from skillgap.pipeline import Deps
from skillgap.recommender import Course
from skillgap.service import CandidateService
from skillgap.store import Store

COURSES = [
    Course("c1", "Fabric Pipelines Básico", ("fabric.pipelines", "fabric.lakehouse"), 1, 8,
           "https://example.com/c1"),
    Course("c2", "Agentes no Foundry", ("foundry.agents",), 2, 4, "https://example.com/c2"),
]


class FakeExtractor:
    def __init__(self, profile=None):
        self.calls = []
        self.profile = profile or ExtractedProfile(
            candidate="Maria Silva",
            skills=[
                RawSkill(name="OneLake", level=1, evidence="usou OneLake"),
                RawSkill(name="PySpark", level=3, evidence="pipelines em PySpark"),
            ],
        )

    def __call__(self, text, hints):
        self.calls.append((text, hints))
        return self.profile


OPEN_STORES = []  # closed by the autouse fixture in conftest.py


def make_store(path=":memory:"):
    store = Store(path)
    OPEN_STORES.append(store)
    return store


def make_catalog(courses=None):
    catalog = CatalogStore(":memory:")
    catalog.upsert(list(COURSES if courses is None else courses))
    OPEN_STORES.append(catalog)
    return catalog


def make_service(taxonomy, extractor=None):
    extractor = extractor or FakeExtractor()
    catalog = make_catalog()
    service = CandidateService(make_store(), Deps(taxonomy, catalog.all_courses, extractor),
                               catalog=catalog)
    return service, extractor
