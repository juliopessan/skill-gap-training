from pdfs import make_text_pdf
from skillgap.models import ExtractedProfile, RawSkill
from support import FakeExtractor, make_service

CV = make_text_pdf([
    "Maria Silva maria@empresa.com",
    "Experience with Microsoft Fabric OneLake and PySpark pipelines.",
])


def profile(*evidences):
    names = ["OneLake", "PySpark", "Power BI"]
    return ExtractedProfile(candidate="Maria Silva", skills=[
        RawSkill(name=n, level=2, evidence=e) for n, e in zip(names, evidences)])


def test_real_quote_is_verified_and_invented_quote_is_not(small_taxonomy):
    extractor = FakeExtractor(profile("Experience with Microsoft Fabric OneLake", "wrote Rust compilers"))
    service, _ = make_service(small_taxonomy, extractor)
    result, _ = service.submit(CV)
    service.run(result.id, CV)
    done = service.get(result.id)
    by_name = {s.name: s.evidence_verified for s in done.skills}
    assert list(by_name.values()).count(True) == 1 and list(by_name.values()).count(False) == 1
    assert next(s for s in done.skills if s.evidence.startswith("Experience")).evidence_verified is True
    assert next(s for s in done.skills if s.evidence.startswith("wrote")).evidence_verified is False


def test_other_skills_are_checked_too(small_taxonomy):
    extractor = FakeExtractor(profile("OneLake and PySpark pipelines", "Experience with Microsoft Fabric"))
    extractor.profile.skills.append(
        RawSkill(name="Zzz Unknown Tool", level=1, evidence="Fabric OneLake and PySpark"))
    extractor.profile.skills.append(
        RawSkill(name="Yyy Other Tool", level=1, evidence="never written anywhere"))
    service, _ = make_service(small_taxonomy, extractor)
    result, _ = service.submit(CV)
    service.run(result.id, CV)
    done = service.get(result.id)
    assert {o.name: o.evidence_verified for o in done.other_skills} == {
        "Zzz Unknown Tool": True, "Yyy Other Tool": False}


def test_check_runs_against_the_scrubbed_text_sent_to_the_extractor(small_taxonomy):
    extractor = FakeExtractor(profile("Maria Silva maria@empresa.com", "Microsoft Fabric OneLake and PySpark"))
    service, _ = make_service(small_taxonomy, extractor)
    result, _ = service.submit(CV)
    service.run(result.id, CV)
    sent, _ = extractor.calls[0]
    assert "maria@empresa.com" not in sent
    done = service.get(result.id)
    flags = {s.evidence: s.evidence_verified for s in done.skills}
    assert flags["Maria Silva maria@empresa.com"] is False
    assert flags["Microsoft Fabric OneLake and PySpark"] is True


def test_rating_is_stored_and_supported_reflects_evidence(small_taxonomy):
    service, _ = make_service(small_taxonomy)  # FakeExtractor: quotes are not in the CV
    result, _ = service.submit(CV)
    service.run(result.id, CV)
    r = service.get(result.id).rating
    # lakehouse level 1 (exp 2), pipelines 0 (exp 2), spark 3 (exp 3): covered 4 / expected 7
    assert (r.covered, r.expected, r.adherence) == (4, 7, 57.1)
    assert r.adherence_supported == 0.0  # neither quote appears in the CV
    assert [t.track for t in r.tracks] == ["fabric", "databricks"]
    assert r.mean_level == 2.0 and r.level_label == "Intermediário"


def test_real_quote_raises_supported_but_invented_does_not(small_taxonomy):
    extractor = FakeExtractor(ExtractedProfile(candidate="Maria", skills=[
        RawSkill(name="OneLake", level=2, evidence="Experience with Microsoft Fabric OneLake"),
        RawSkill(name="PySpark", level=3, evidence="wrote Rust compilers")]))
    service, _ = make_service(small_taxonomy, extractor)
    result, _ = service.submit(CV)
    service.run(result.id, CV)
    r = service.get(result.id).rating
    # adherence (2+0+3)/7 = 71.4 ; supported only lakehouse: 2/7 = 28.6
    assert (r.adherence, r.adherence_supported) == (71.4, 28.6)


def test_old_record_without_rating_loads_and_result_round_trips(small_taxonomy):
    from skillgap.models import CandidateResult
    old = CandidateResult.model_validate_json('{"id": "x", "recommendations": '
                                              '[{"course_id": "c", "title": "t", "covers": []}]}')
    assert old.rating is None
    assert old.recommendations[0].level is None and old.recommendations[0].platform is None
    service, _ = make_service(small_taxonomy)
    result, _ = service.submit(CV)
    service.run(result.id, CV)
    done = service.get(result.id)
    assert CandidateResult.model_validate_json(done.model_dump_json()) == done
    assert done.rating is not None
