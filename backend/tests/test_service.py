import threading

from pdfs import make_text_pdf
from skillgap.bootstrap import build_service
from skillgap.config import Settings
from skillgap.errors import PipelineError
from skillgap.models import ExtractedProfile
from skillgap.pipeline import Deps
from skillgap.service import CandidateService
from support import COURSES, OPEN_STORES, FakeExtractor, make_service, make_store

CV = make_text_pdf(["Maria Silva", "Experience with Microsoft Fabric OneLake and PySpark pipelines."])


def test_full_pipeline_produces_skills_gaps_and_recommendations(small_taxonomy):
    service, extractor = make_service(small_taxonomy)
    result, is_new = service.submit(CV, "maria.pdf")
    assert is_new and result.status == "processing" and result.candidate == "maria"

    service.run(result.id, CV)
    done = service.get(result.id)

    assert done.status == "done" and done.stage == "done"
    assert done.candidate == "Maria Silva"
    assert {s.id: s.level for s in done.skills} == {"fabric.lakehouse": 1, "databricks.spark": 3}
    assert {g.skill: g.severity for g in done.gaps} == {
        "fabric.pipelines": "high", "fabric.lakehouse": "low"}
    assert done.no_data_tracks == ["foundry"]
    assert [r.course_id for r in done.recommendations] == ["c1"]
    assert done.recommendations[0].covers == ["fabric.pipelines", "fabric.lakehouse"]


def test_extractor_receives_scrubbed_text_and_taxonomy_hints(small_taxonomy):
    service, extractor = make_service(small_taxonomy)
    cv = make_text_pdf(["Maria Silva maria@empresa.com", "Experience with Microsoft Fabric and PySpark daily."])
    result, _ = service.submit(cv)
    service.run(result.id, cv)
    text, hints = extractor.calls[0]
    assert "maria@empresa.com" not in text and "Microsoft Fabric" in text
    assert "Lakehouse" in hints


def test_same_pdf_twice_returns_same_candidate_and_calls_api_once(small_taxonomy):
    service, extractor = make_service(small_taxonomy)
    first, first_new = service.submit(CV, "a.pdf")
    service.run(first.id, CV)
    second, second_new = service.submit(CV, "b.pdf")
    assert first_new and not second_new
    assert second.id == first.id
    assert len(extractor.calls) == 1


def test_invalid_pdf_is_stored_as_error_with_message(small_taxonomy):
    service, _ = make_service(small_taxonomy)
    result, _ = service.submit(b"isto nao e pdf", "falso.pdf")
    service.run(result.id, b"isto nao e pdf")
    failed = service.get(result.id)
    assert failed.status == "error" and failed.stage == "error"
    assert failed.error == "INVALID_PDF" and "PDF" in failed.error_message


def test_failed_upload_can_be_retried_and_calls_api(small_taxonomy):
    def flaky(text, hints):
        raise PipelineError("LLM_UNAVAILABLE")
    service, _ = make_service(small_taxonomy, extractor=flaky)
    first, _ = service.submit(CV)
    service.run(first.id, CV)
    assert service.get(first.id).error == "LLM_UNAVAILABLE"
    retry, is_new = service.submit(CV)
    assert is_new and retry.id != first.id


def test_unexpected_exception_becomes_internal_error(small_taxonomy):
    def broken(text, hints):
        raise RuntimeError("boom")
    service, _ = make_service(small_taxonomy, extractor=broken)
    result, _ = service.submit(CV)
    service.run(result.id, CV)
    assert service.get(result.id).error == "INTERNAL"


def test_tracks_lists_id_and_name(small_taxonomy):
    service, _ = make_service(small_taxonomy)
    assert service.tracks()[0] == {"id": "fabric", "name": "Microsoft Fabric"}


def test_build_service_loads_shipped_config(tmp_path):
    settings = Settings(db_path=str(tmp_path / "x.db"))
    service = build_service(settings, extract=FakeExtractor())
    OPEN_STORES.append(service.store)
    assert [t["id"] for t in service.tracks()] == ["foundry", "fabric", "databricks"]
    assert len(service.deps.courses) >= 10


def test_restart_fails_stuck_processing_upload_so_resubmit_is_new(small_taxonomy):
    store = make_store()
    deps = Deps(small_taxonomy, COURSES, FakeExtractor())
    first, first_new = CandidateService(store, deps).submit(CV)
    assert first_new and first.status == "processing"
    restarted = CandidateService(store, deps)
    stuck = restarted.get(first.id)
    assert stuck.status == "error" and stuck.error == "INTERNAL"
    again, again_new = restarted.submit(CV)
    assert again_new and again.id != first.id


def test_concurrent_submits_of_same_bytes_create_one_candidate(small_taxonomy):
    service, _ = make_service(small_taxonomy)
    n = 8
    barrier = threading.Barrier(n)
    out = []

    def worker():
        barrier.wait()
        out.append(service.submit(CV))

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(out) == n
    assert len({r.id for r, _ in out}) == 1
    assert sum(1 for _, new in out if new) == 1
    assert len(service.store.list()) == 1


def test_run_with_unknown_id_is_a_noop(small_taxonomy):
    service, extractor = make_service(small_taxonomy)
    service.run("missing", CV)
    assert extractor.calls == []


def test_blank_candidate_name_falls_back_to_filename_stem(small_taxonomy):
    extractor = FakeExtractor(ExtractedProfile(candidate="  ", skills=[]))
    service, _ = make_service(small_taxonomy, extractor=extractor)
    result, _ = service.submit(CV, "joao.pdf")
    service.run(result.id, CV)
    assert service.get(result.id).candidate == "joao"
