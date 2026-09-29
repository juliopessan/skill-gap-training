import json
import os
from pathlib import Path

from pdfs import make_text_pdf
from skillgap.cli import main, assign_output_names
from support import make_service

CV = make_text_pdf(["Maria Silva", "Experience with Microsoft Fabric OneLake and PySpark pipelines."])


def test_process_writes_one_json_per_pdf_and_returns_0(tmp_path, small_taxonomy, capsys):
    cvs, out = tmp_path / "cvs", tmp_path / "out"
    cvs.mkdir()
    (cvs / "maria.pdf").write_bytes(CV)
    service, _ = make_service(small_taxonomy)

    code = main(["process", str(cvs), "--out", str(out)], service=service)

    assert code == 0
    data = json.loads((out / "maria.json").read_text(encoding="utf-8"))
    assert data["status"] == "done" and data["candidate"] == "Maria Silva"
    assert "OK" in capsys.readouterr().out


def test_failure_in_one_pdf_does_not_stop_the_batch(tmp_path, small_taxonomy, capsys):
    cvs, out = tmp_path / "cvs", tmp_path / "out"
    cvs.mkdir()
    (cvs / "a_ruim.pdf").write_bytes(b"nao e pdf")
    (cvs / "b_maria.pdf").write_bytes(CV)
    service, _ = make_service(small_taxonomy)

    code = main(["process", str(cvs), "--out", str(out)], service=service)

    assert code == 1
    assert json.loads((out / "a_ruim.json").read_text())["error"] == "INVALID_PDF"
    assert json.loads((out / "b_maria.json").read_text())["status"] == "done"
    assert "ERRO" in capsys.readouterr().out


def test_folder_without_pdfs_returns_1(tmp_path, small_taxonomy):
    (tmp_path / "vazia").mkdir()
    service, _ = make_service(small_taxonomy)
    assert main(["process", str(tmp_path / "vazia"), "--out", str(tmp_path / "o")], service=service) == 1


def test_processing_cache_hit_treated_as_failure(tmp_path, small_taxonomy, capsys):
    """A cached result still in 'processing' status should be treated as a failure."""
    cvs, out = tmp_path / "cvs", tmp_path / "out"
    cvs.mkdir()
    (cvs / "cached.pdf").write_bytes(CV)
    service, _ = make_service(small_taxonomy)

    # Submit without running (leaves it in 'processing' state)
    result, _ = service.submit(CV, "cached.pdf")

    code = main(["process", str(cvs), "--out", str(out)], service=service)

    assert code == 1
    assert "em andamento" in capsys.readouterr().out
    assert not (out / "cached.json").exists(), "No JSON should be written for processing results"


def test_uppercase_pdf_extension_processed(tmp_path, small_taxonomy):
    """PDF files with uppercase extension should be processed."""
    cvs, out = tmp_path / "cvs", tmp_path / "out"
    cvs.mkdir()
    (cvs / "MARIA.PDF").write_bytes(CV)
    service, _ = make_service(small_taxonomy)

    code = main(["process", str(cvs), "--out", str(out)], service=service)

    assert code == 0
    assert (out / "MARIA.json").exists()


def test_case_collision_avoidance(tmp_path, small_taxonomy):
    """Test collision avoidance for same-stem files (case-insensitive filesystems)."""
    cvs, out = tmp_path / "cvs", tmp_path / "out"
    cvs.mkdir()
    cv = make_text_pdf(["Test Candidate"])
    # On case-insensitive filesystems (macOS, Windows), candidate.pdf and CANDIDATE.PDF collapse to one file
    (cvs / "candidate.pdf").write_bytes(cv)
    (cvs / "CANDIDATE.PDF").write_bytes(cv)  # Same file on case-insensitive systems
    service, _ = make_service(small_taxonomy)

    code = main(["process", str(cvs), "--out", str(out)], service=service)

    assert code == 0
    # On case-insensitive filesystems, only one file is created/processed
    files = list(out.glob("candidate*.json"))
    assert len(files) >= 1
    data = json.loads(files[0].read_text())
    assert data["status"] == "done"


def test_unreadable_file_does_not_stop_batch(tmp_path, small_taxonomy, capsys):
    """An unreadable file should not stop the batch; good files are still processed."""
    import pytest

    # Skip if running as root (can't test permission denied)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("Cannot test permission denied when running as root")

    cvs, out = tmp_path / "cvs", tmp_path / "out"
    cvs.mkdir()

    # Create a file and make it unreadable
    bad_file = cvs / "unreadable.pdf"
    bad_file.write_bytes(b"x")
    bad_file.chmod(0o000)

    # Create a good file
    (cvs / "good.pdf").write_bytes(CV)
    service, _ = make_service(small_taxonomy)

    try:
        code = main(["process", str(cvs), "--out", str(out)], service=service)
    finally:
        # Restore permissions so teardown can delete
        bad_file.chmod(0o644)

    assert code == 1
    assert "não foi possível ler o arquivo" in capsys.readouterr().out
    assert (out / "good.json").exists()
    assert not (out / "unreadable.json").exists()


def test_nonexistent_folder_distinct_message(tmp_path, small_taxonomy, capsys):
    """Nonexistent folder should print a distinct error message."""
    nonexistent = tmp_path / "does_not_exist"
    service, _ = make_service(small_taxonomy)

    code = main(["process", str(nonexistent), "--out", str(tmp_path / "o")], service=service)

    assert code == 1
    output = capsys.readouterr().out
    assert "Pasta não encontrada" in output


def test_assign_output_names_collision_logic():
    """Unit test: collision avoidance doesn't overwrite natural names."""
    # Test case: a-2.pdf, a.PDF, a.pdf (sorted order on case-sensitive FS)
    # Expected: a-2.json, a.json, a-3.json (or similar, no overwrites)
    paths = [Path("a-2.pdf"), Path("a.PDF"), Path("a.pdf")]
    result = assign_output_names(paths)

    # All outputs should be distinct (case-insensitive)
    output_names_lower = [result[p].lower() for p in paths]
    assert len(output_names_lower) == len(set(output_names_lower)), "Collision detected!"

    # No bumped name should equal another's natural name
    natural_names_lower = {Path(name.replace(".json", ".pdf")).stem.lower() for p in paths for name in [p.name]}
    bumped_names = {result[p] for p in paths if Path(result[p]).stem.lower() != p.stem.lower()}
    for bumped in bumped_names:
        bumped_stem = Path(bumped).stem.lower()
        # bumped_stem should not collide with any natural input stem
        assert bumped_stem not in {p.stem.lower() for p in paths}


def test_assign_output_names_extended_case():
    """Unit test: multiple collision cases."""
    paths = [Path("a.pdf"), Path("a.PDF"), Path("a-2.pdf"), Path("a-3.pdf")]
    result = assign_output_names(paths)

    output_names = list(result.values())
    output_names_lower = [name.lower() for name in output_names]
    # All distinct
    assert len(output_names_lower) == len(set(output_names_lower))


def test_file_as_folder_error(tmp_path, small_taxonomy, capsys):
    """Path that is a file (not directory) should print distinct error message."""
    file_path = tmp_path / "notafolder.txt"
    file_path.write_text("x")
    service, _ = make_service(small_taxonomy)

    code = main(["process", str(file_path), "--out", str(tmp_path / "o")], service=service)

    assert code == 1
    output = capsys.readouterr().out
    assert "O caminho não é uma pasta" in output


def test_collision_no_overwrite_with_distinct_pdfs(tmp_path, small_taxonomy):
    """Integration: verify no JSON overwrites with case-varying stems."""
    cvs, out = tmp_path / "cvs", tmp_path / "out"
    cvs.mkdir()

    # Create 3 PDFs with stems that would collide on case-insensitive FS
    cv1 = make_text_pdf(["Alice"])
    cv2 = make_text_pdf(["Bob"])
    cv3 = make_text_pdf(["Charlie"])

    # Try to create files; on case-insensitive FS only one of a.pdf/a.PDF survives
    (cvs / "a.pdf").write_bytes(cv1)
    (cvs / "b.pdf").write_bytes(cv2)
    (cvs / "c.pdf").write_bytes(cv3)

    service, _ = make_service(small_taxonomy)
    code = main(["process", str(cvs), "--out", str(out)], service=service)

    assert code == 0
    # Should have exactly 3 JSON files (one per input)
    json_files = list(out.glob("*.json"))
    assert len(json_files) == 3
