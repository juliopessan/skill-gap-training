import json
import shutil

import pytest

from skillgap.catalog_store import CatalogStore
from skillgap.cli import main
from skillgap.config import Settings, load_settings
from skillgap.recommender import load_catalog

TAXONOMY = "config/taxonomy_fy27.yaml"
SHIPPED = "config/catalog_fy27.csv"
HEADER = "id,plataforma,titulo,foco,nivel,provedor,tipo,skills_cobertas,carga_horaria,link,fonte,verificado\n"


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "s.db"), taxonomy_path=TAXONOMY, catalog_path=SHIPPED)


def cli(settings, *argv):
    return main(["catalog", *argv], settings=settings)


def test_stats_seeds_empty_db_and_prints_totals(settings, capsys):
    assert cli(settings, "stats") == 0
    out = capsys.readouterr().out
    assert "26" in out and "fabric" in out and "databricks" in out and "foundry" in out
    assert "horas desconhecidas" in out.lower() or "hours_unknown" in out


def test_list_table_and_filters(settings, capsys):
    assert cli(settings, "list", "--platform", "fabric", "--level", "2") == 0
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    assert "fabric-lakehouse" in out and "fabric-warehouse" in out and "fabric-data-engineering" in out
    assert "dp-600" not in out and "foundry-rag" not in out
    assert "—" in out and "não" in out
    assert lines[0].split()[0] == "id"


def test_list_q_kind_skill_and_limit(settings, capsys):
    assert cli(settings, "list", "--q", "rag") == 0
    out = capsys.readouterr().out
    assert "foundry-rag" in out and "dbx-genai-engineering" in out and "fabric-lakehouse" not in out
    assert cli(settings, "list", "--kind", "certificação", "--limit", "2") == 0
    rows = capsys.readouterr().out.strip().splitlines()[1:]
    assert len(rows) == 2
    assert cli(settings, "list", "--skill", "fabric.realtime") == 0
    assert "fabric-realtime" in capsys.readouterr().out


def test_list_json(settings, capsys):
    assert cli(settings, "list", "--platform", "foundry", "--json") == 0
    items = json.loads(capsys.readouterr().out)
    assert len(items) == 8 and {i["platform"] for i in items} == {"foundry"}
    assert items[0]["hours"] is None and items[0]["verified"] is False
    assert isinstance(items[0]["skills"], list)


def test_list_with_no_match_is_ok(settings, capsys):
    assert cli(settings, "list", "--q", "zzzzzz") == 0
    assert "Nenhum" in capsys.readouterr().out


def test_import_upsert_counts_and_replace(settings, tmp_path, capsys):
    src = tmp_path / "novo.csv"
    src.write_text(HEADER + "novo-1,fabric,Novo,,2,P,curso,fabric.ai,,,S,0\n"
                            "fabric-lakehouse,fabric,Lakehouse Editado,,2,P,curso,fabric.lakehouse,,,S,0\n",
                   encoding="utf-8")
    assert cli(settings, "stats") == 0
    capsys.readouterr()
    assert cli(settings, "import", str(src)) == 0
    out = capsys.readouterr().out
    assert "1 inserido" in out and "1 atualizado" in out
    store = CatalogStore(settings.db_path)
    assert store.count() == 27 and store.get("fabric-lakehouse").title == "Lakehouse Editado"
    store.close()
    assert cli(settings, "import", str(src), "--replace") == 0
    store = CatalogStore(settings.db_path)
    assert [c.id for c in store.all_courses()] == ["fabric-lakehouse", "novo-1"]
    store.close()


def test_import_validation_error_exits_1_with_message_and_changes_nothing(settings, tmp_path, capsys):
    bad = tmp_path / "ruim.csv"
    bad.write_text(HEADER + "x,fabric,X,,1,P,curso,fabric.nao_existe,,,S,0\n"
                            "y,nada,Y,,1,P,curso,fabric.ai,,,S,0\n", encoding="utf-8")
    assert cli(settings, "import", str(bad)) == 1
    out = capsys.readouterr().out
    assert "fabric.nao_existe" in out and "x" in out and "nada" in out
    store = CatalogStore(settings.db_path)
    assert store.count() == 0
    store.close()


def test_import_bad_row_and_missing_file_exit_1(settings, tmp_path, capsys):
    bad = tmp_path / "ruim.csv"
    bad.write_text("id,titulo,skills_cobertas,nivel\nc,C,fabric.ai,7\n", encoding="utf-8")
    assert cli(settings, "import", str(bad)) == 1
    assert "linha 2" in capsys.readouterr().out
    assert cli(settings, "import", str(tmp_path / "nao-existe.csv")) == 1
    assert "não encontrado" in capsys.readouterr().out


def test_export_roundtrips_into_load_catalog(settings, tmp_path):
    out = tmp_path / "export.csv"
    assert cli(settings, "export", str(out)) == 0
    # o SQLite guarda as skills ordenadas; fora isso o conteúdo é idêntico ao CSV de origem
    from dataclasses import replace
    original = [replace(c, skills=tuple(sorted(c.skills))) for c in load_catalog(SHIPPED)]
    assert sorted(load_catalog(out), key=lambda c: c.id) == sorted(original, key=lambda c: c.id)


def test_seed_with_invalid_shipped_csv_exits_1(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    shutil.copy(SHIPPED, bad)
    bad.write_text(bad.read_text(encoding="utf-8").replace("foundry.rag", "foundry.zzz"), encoding="utf-8")
    s = Settings(db_path=str(tmp_path / "s.db"), taxonomy_path=TAXONOMY, catalog_path=str(bad))
    assert cli(s, "stats") == 1
    assert "foundry.zzz" in capsys.readouterr().out


def test_uses_env_settings_and_needs_no_api_key(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SKILLGAP_DB", str(tmp_path / "env.db"))
    monkeypatch.setenv("SKILLGAP_CATALOG", SHIPPED)
    monkeypatch.setenv("SKILLGAP_TAXONOMY", TAXONOMY)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["catalog", "stats"]) == 0
    assert (tmp_path / "env.db").exists()
    assert load_settings().db_path == str(tmp_path / "env.db")
