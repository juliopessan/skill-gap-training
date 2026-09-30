import pytest

from pdfs import make_text_pdf
from skillgap import bootstrap
from skillgap.config import Settings
from skillgap.keystore import KeyStore
from skillgap.models import ExtractedProfile
from support import OPEN_STORES, make_service

CV = make_text_pdf(["Maria Silva", "Experience with Microsoft Fabric."])
KEY_A = "sk-ant-test-aaaaaaaaaaaaaaaa"
KEY_B = "sk-ant-test-bbbbbbbbbbbbbbbb"


@pytest.fixture
def built(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    service = bootstrap.build_service(Settings(db_path=str(tmp_path / "x.db")))
    OPEN_STORES.extend([service.store, service.catalog])
    return service


def run_upload(service, data=CV):
    result, _ = service.submit(data)
    service.run(result.id, data)
    return service.get(result.id)


def test_build_service_exposes_a_keystore(built):
    assert isinstance(built.keystore, KeyStore)
    assert built.keystore.get() is None


def test_default_extractor_reads_the_key_on_every_call(built, monkeypatch):
    seen = []

    def spy(text, hints, model=None, api_key=None, **kw):
        seen.append(api_key)
        return ExtractedProfile(candidate="Maria Silva", skills=[])

    monkeypatch.setattr(bootstrap, "extract_profile", spy)

    built.keystore.set(KEY_A)
    run_upload(built, make_text_pdf(["Maria Silva", "um " * 30]))
    built.keystore.set(KEY_B)
    run_upload(built, make_text_pdf(["Maria Silva", "dois " * 30]))
    assert seen == [KEY_A, KEY_B]


def test_clearing_the_key_makes_the_next_run_llm_unavailable(built):
    built.keystore.clear()
    result = run_upload(built)
    assert result.status == "error" and result.error == "LLM_UNAVAILABLE"


def test_explicit_keystore_is_used(tmp_path):
    ks = KeyStore()
    service = bootstrap.build_service(Settings(db_path=str(tmp_path / "y.db")), keystore=ks)
    OPEN_STORES.extend([service.store, service.catalog])
    assert service.keystore is ks


def test_make_service_has_an_empty_keystore(small_taxonomy):
    service, _ = make_service(small_taxonomy)
    assert isinstance(service.keystore, KeyStore)
