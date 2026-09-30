import pytest

from skillgap.cli import main
from skillgap.config import Settings, load_settings
from skillgap.catalog_store import CatalogStore
from learn_fixtures import catalog_payload
from support import OPEN_STORES

def open_store(path):
    store = CatalogStore(path)
    OPEN_STORES.append(store)
    return store


TAXONOMY = "config/taxonomy_fy27.yaml"
SHIPPED = "config/catalog_fy27.csv"


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "s.db"), taxonomy_path=TAXONOMY, catalog_path=SHIPPED,
                    learn_mapping_path="config/learn_mapping.yaml")


def payload_for_real_taxonomy():
    p = catalog_payload()
    p["learningPaths"][0]["products"] = ["fabric"]  # já é fabric: casa fabric.lakehouse
    return p


def run(settings, payload, *extra):
    return main(["catalog", "sync-learn", *extra], settings=settings, learn_fetch=lambda locale: payload)


def test_sync_seeds_manual_catalog_first_then_adds_learn_items(settings, capsys):
    assert run(settings, payload_for_real_taxonomy()) == 0
    out = capsys.readouterr().out
    assert "Sincronização concluída" in out and "inserido(s)" in out
    store = open_store(settings.db_path)
    ids = {c.id for c in store.list_courses()}
    assert "foundry-rag" in ids  # os 26 manuais continuam
    assert any(i.startswith("learn:") for i in ids)
    assert store.learn_status()["last_sync"]


def test_second_sync_is_idempotent_and_retires_what_left(settings, capsys):
    p = payload_for_real_taxonomy()
    assert run(settings, p) == 0
    capsys.readouterr()
    p["learningPaths"].pop(0)
    assert run(settings, p) == 0
    assert "1 aposentado(s)" in capsys.readouterr().out
    store = open_store(settings.db_path)
    assert "learn:learn.fabric.lakehouse" not in {c.id for c in store.list_courses()}
    assert store.get("learn:learn.fabric.lakehouse").retired is True


def test_empty_result_does_not_retire_the_existing_learn_catalog(settings, capsys):
    assert run(settings, payload_for_real_taxonomy()) == 0
    before = open_store(settings.db_path).learn_status()["items"]
    capsys.readouterr()
    assert run(settings, {}) == 1
    assert "nada foi alterado" in capsys.readouterr().out
    assert open_store(settings.db_path).learn_status()["items"] == before


def test_fetch_failure_exits_1_and_changes_nothing(settings, capsys):
    def boom(locale):
        raise ValueError("Não foi possível baixar o catálogo da Microsoft Learn: sem rede")

    assert main(["catalog", "sync-learn"], settings=settings, learn_fetch=boom) == 1
    assert "ERRO" in capsys.readouterr().out
    assert open_store(settings.db_path).learn_status()["items"] == 0


def test_report_goes_to_a_file_when_requested(settings, tmp_path, capsys):
    report = tmp_path / "r.md"
    assert run(settings, payload_for_real_taxonomy(), "--report", str(report)) == 0
    text = report.read_text(encoding="utf-8")
    assert "Skills sem nenhum item" in text
    assert "Skills sem nenhum item" not in capsys.readouterr().out


def test_locale_flag_is_passed_to_the_fetcher(settings):
    seen = []
    main(["catalog", "sync-learn", "--locale", "pt-br"], settings=settings,
         learn_fetch=lambda locale: seen.append(locale) or payload_for_real_taxonomy())
    assert seen == ["pt-br"]


def test_settings_from_env(monkeypatch):
    monkeypatch.delenv("SKILLGAP_LEARN_MCP", raising=False)
    assert load_settings().learn_mcp is True and Settings().learn_mcp is False
    monkeypatch.setenv("SKILLGAP_LEARN_MCP", "0")
    assert load_settings().learn_mcp is False
    monkeypatch.setenv("SKILLGAP_LEARN_LOCALE", "pt-br")
    monkeypatch.setenv("SKILLGAP_LEARN_MAPPING", "x.yaml")
    s = load_settings()
    assert (s.learn_locale, s.learn_mapping_path) == ("pt-br", "x.yaml")


def test_partial_payload_does_not_retire_the_kinds_it_omits(settings):
    full = payload_for_real_taxonomy()
    assert run(settings, full) == 0
    store = open_store(settings.db_path)
    assert store.get("learn:course.dp-600t00").retired is False
    assert run(settings, {"learningPaths": full["learningPaths"]}) == 0  # sem courses/certifications
    assert store.get("learn:course.dp-600t00").retired is False
    assert store.get("learn:certification.fabric-data-engineer-associate").retired is False
    assert run(settings, {"learningPaths": [], "courses": full["courses"],
                          "certifications": full["certifications"]}) == 0  # lista vazia = ausente
    assert store.get("learn:learn.fabric.lakehouse").retired is False
