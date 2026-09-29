from skillgap.models import CandidateResult
from support import make_store


def test_save_and_get_roundtrip():
    store = make_store()
    result = CandidateResult(id="a", candidate="Maria")
    store.save(result, "hash-1")
    assert store.get("a") == result
    assert store.get("missing") is None


def test_update_keeps_hash_and_changes_payload():
    store = make_store()
    store.save(CandidateResult(id="a"), "hash-1")
    store.save(CandidateResult(id="a", status="done", stage="done"))
    assert store.find_reusable_by_hash("hash-1").status == "done"


def test_list_returns_newest_first():
    store = make_store()
    for i in ("a", "b", "c"):
        store.save(CandidateResult(id=i), f"h-{i}")
    assert [r.id for r in store.list()] == ["c", "b", "a"]


def test_error_results_are_not_reusable():
    store = make_store()
    store.save(CandidateResult(id="a", status="error", stage="error", error="NO_TEXT"), "h")
    assert store.find_reusable_by_hash("h") is None


def test_processing_and_done_results_are_reusable():
    store = make_store()
    store.save(CandidateResult(id="p"), "hp")
    store.save(CandidateResult(id="d", status="done", stage="done"), "hd")
    assert store.find_reusable_by_hash("hp").id == "p"
    assert store.find_reusable_by_hash("hd").id == "d"


def test_fail_stale_processing_flips_only_processing_rows():
    store = make_store()
    store.save(CandidateResult(id="p"), "hp")
    store.save(CandidateResult(id="d", status="done", stage="done"), "hd")
    assert store.fail_stale_processing("reiniciado") == 1
    p = store.get("p")
    assert (p.status, p.stage, p.error, p.error_message) == ("error", "error", "INTERNAL", "reiniciado")
    assert store.get("d").status == "done"
    assert store.find_reusable_by_hash("hp") is None
    assert store.find_reusable_by_hash("hd").id == "d"
    assert store.fail_stale_processing("reiniciado") == 0
