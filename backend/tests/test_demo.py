from skillgap.demo import fake_extract
from skillgap.evidence import verify_evidence

LONG = "\n".join(
    f"Linha {i} do curriculo com experiencia em projetos de dados numero {i} na empresa exemplo" for i in range(10))


def test_first_skills_take_real_fragments_and_last_is_invented():
    skills = fake_extract(LONG, []).skills
    assert len(skills) == 4
    for skill in skills[:3]:
        assert skill.evidence in LONG and verify_evidence(skill.evidence, LONG)
    assert not verify_evidence(skills[-1].evidence, LONG)


def test_short_text_falls_back_to_fixed_strings():
    skills = fake_extract("curto", []).skills
    assert len(skills) == 4
    assert not verify_evidence(skills[-1].evidence, "curto")
