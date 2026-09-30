import pytest
from fastapi.testclient import TestClient

from pdfs import make_text_pdf
from skillgap import api
from skillgap.api import create_app
from support import make_service

CV = make_text_pdf(["Maria Silva", "Experience with Microsoft Fabric OneLake and PySpark pipelines."])


@pytest.fixture
def setup(small_taxonomy):
    service, extractor = make_service(small_taxonomy)
    return TestClient(create_app(service), base_url="http://localhost"), extractor


def upload(client, *files):
    return client.post("/candidates", files=[("files", (n, d, "application/pdf")) for n, d in files])


def test_upload_runs_the_whole_pipeline_and_card_is_ready(setup):
    client, _ = setup
    response = upload(client, ("maria.pdf", CV))
    assert response.status_code == 202
    [item] = response.json()

    card = client.get(f"/candidates/{item['id']}").json()
    assert card["status"] == "done" and card["candidate"] == "Maria Silva"
    assert {s["id"] for s in card["skills"]} == {"fabric.lakehouse", "databricks.spark"}
    assert [g["skill"] for g in card["gaps"]] == ["fabric.pipelines", "fabric.lakehouse"]
    assert card["no_data_tracks"] == ["foundry"]
    assert card["recommendations"][0]["course_id"] == "c1"
    assert card["skills"][0]["evidence"]


def test_same_pdf_uploaded_twice_is_one_candidate_and_one_api_call(setup):
    client, extractor = setup
    first = upload(client, ("a.pdf", CV)).json()[0]
    second = upload(client, ("b.pdf", CV)).json()[0]
    assert first["id"] == second["id"]
    assert len(client.get("/candidates").json()) == 1
    assert len(extractor.calls) == 1


def test_batch_with_a_non_pdf_still_processes_the_others(setup):
    client, _ = setup
    items = upload(client, ("ruim.docx", b"PK\x03\x04 nao e pdf"), ("maria.pdf", CV)).json()
    # as chaves são o nome do arquivo (candidate provisório devolvido pelo POST)
    by_name = {i["candidate"]: client.get(f"/candidates/{i['id']}").json() for i in items}
    assert by_name["ruim"]["status"] == "error"
    assert by_name["ruim"]["error"] == "INVALID_PDF"
    assert "PDF" in by_name["ruim"]["error_message"]
    assert by_name["maria"]["status"] == "done"
    assert by_name["maria"]["candidate"] == "Maria Silva"


def test_empty_file_becomes_an_invalid_pdf_error(setup):
    client, _ = setup
    [item] = upload(client, ("vazio.pdf", b"")).json()
    assert client.get(f"/candidates/{item['id']}").json()["error"] == "INVALID_PDF"


def test_request_without_files_is_rejected(setup):
    client, _ = setup
    assert client.post("/candidates").status_code in (400, 422)


def test_oversized_file_is_rejected_with_413(setup, monkeypatch):
    client, _ = setup
    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 10)
    assert upload(client, ("grande.pdf", CV)).status_code == 413


def test_unknown_candidate_is_404(setup):
    client, _ = setup
    assert client.get("/candidates/nao-existe").status_code == 404
    assert client.get("/candidates/nao-existe/export").status_code == 404


def test_export_csv_and_xlsx(setup):
    client, _ = setup
    [item] = upload(client, ("maria.pdf", CV)).json()
    csv_response = client.get(f"/candidates/{item['id']}/export?format=csv")
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "treinamento" in csv_response.text
    xlsx_response = client.get(f"/candidates/{item['id']}/export?format=xlsx")
    assert xlsx_response.status_code == 200
    assert xlsx_response.content[:2] == b"PK"


def test_export_of_unfinished_candidate_is_409(setup, small_taxonomy):
    client, _ = setup
    service, _ = make_service(small_taxonomy)
    pending, _ = service.submit(CV)
    other = TestClient(create_app(service), base_url="http://localhost")
    assert other.get(f"/candidates/{pending.id}/export").status_code == 409


def test_export_rejects_unknown_format(setup):
    client, _ = setup
    [item] = upload(client, ("maria.pdf", CV)).json()
    assert client.get(f"/candidates/{item['id']}/export?format=pdf").status_code == 422


def test_taxonomy_lists_tracks(setup):
    client, _ = setup
    assert client.get("/taxonomy").json()["tracks"][0] == {"id": "fabric", "name": "Microsoft Fabric"}


def test_cors_allows_the_frontend_origin(setup):
    client, _ = setup
    response = client.get("/candidates", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def _limit_between(monkeypatch, small, big):
    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", (len(small) + len(big)) // 2)


BIG = b"%PDF-" + b"x" * (len(CV) * 3)


def test_oversized_last_file_persists_nothing_and_valid_cv_still_works(setup, monkeypatch):
    client, _ = setup
    _limit_between(monkeypatch, CV, BIG)
    response = upload(client, ("maria.pdf", CV), ("grande.pdf", BIG))
    assert response.status_code == 413
    assert "grande.pdf" in response.json()["detail"]
    assert client.get("/candidates").json() == []
    [item] = upload(client, ("maria.pdf", CV)).json()
    assert client.get(f"/candidates/{item['id']}").json()["status"] == "done"


def test_oversized_first_file_persists_nothing(setup, monkeypatch):
    client, _ = setup
    _limit_between(monkeypatch, CV, BIG)
    assert upload(client, ("grande.pdf", BIG), ("maria.pdf", CV)).status_code == 413
    assert client.get("/candidates").json() == []
    [item] = upload(client, ("maria.pdf", CV)).json()
    assert client.get(f"/candidates/{item['id']}").json()["status"] == "done"


def test_too_many_files_is_400_and_persists_nothing(setup, monkeypatch):
    client, _ = setup
    monkeypatch.setattr(api, "MAX_FILES_PER_REQUEST", 2)
    response = upload(client, ("a.pdf", CV), ("b.pdf", CV + b" "), ("c.pdf", CV + b"  "))
    assert response.status_code == 400
    assert client.get("/candidates").json() == []


def test_same_pdf_twice_in_one_request_is_one_candidate(setup):
    client, extractor = setup
    items = upload(client, ("a.pdf", CV), ("b.pdf", CV)).json()
    assert len(items) == 2 and items[0]["id"] == items[1]["id"]
    assert len(client.get("/candidates").json()) == 1
    assert len(extractor.calls) == 1


def test_candidate_json_exposes_evidence_verified_on_skills(setup):
    client, _ = setup
    [item] = upload(client, ("maria.pdf", CV)).json()
    card = client.get(f"/candidates/{item['id']}").json()
    assert card["skills"]
    assert all("evidence_verified" in s and isinstance(s["evidence_verified"], bool) for s in card["skills"])


def test_candidate_json_exposes_rating_and_recommendation_level_platform(setup):
    client, _ = setup
    [item] = upload(client, ("maria.pdf", CV)).json()
    card = client.get(f"/candidates/{item['id']}").json()
    assert isinstance(card["rating"], dict)
    assert {t["track"] for t in card["rating"]["tracks"]} == {"fabric", "databricks"}
    assert card["rating"]["adherence"] == 57.1
    rec = card["recommendations"][0]
    assert rec["level"] == 1 and rec["platform"] is None
