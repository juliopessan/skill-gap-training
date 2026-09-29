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
