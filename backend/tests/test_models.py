import pytest
from pydantic import ValidationError

from skillgap.errors import MESSAGES, PipelineError
from skillgap.models import CandidateResult, RawSkill


@pytest.mark.parametrize("level", [0, 4, -1])
def test_raw_skill_rejects_level_out_of_range(level):
    with pytest.raises(ValidationError):
        RawSkill(name="x", level=level, evidence="e")


def test_raw_skill_accepts_levels_1_to_3():
    for level in (1, 2, 3):
        assert RawSkill(name="x", level=level, evidence="e").level == level


def test_candidate_result_defaults():
    result = CandidateResult(id="1")
    assert result.status == "processing"
    assert result.stage == "queued"
    assert result.skills == [] and result.gaps == [] and result.recommendations == []
    assert result.no_data_tracks == []
    assert result.error is None


def test_pipeline_error_carries_code_and_message():
    error = PipelineError("NO_TEXT")
    assert error.code == "NO_TEXT"
    assert error.message == MESSAGES["NO_TEXT"]


def test_every_documented_error_code_has_a_message():
    for code in ("INVALID_PDF", "NO_TEXT", "OCR_UNAVAILABLE",
                 "LLM_INVALID_OUTPUT", "LLM_UNAVAILABLE", "INTERNAL"):
        assert MESSAGES[code]


def test_skill_and_other_skill_evidence_verified_defaults_to_none():
    from skillgap.models import OtherSkill, Skill
    assert Skill(id="a", name="A", track="t", level=1, evidence="e").evidence_verified is None
    assert OtherSkill(name="A", level=1, evidence="e").evidence_verified is None


def test_old_record_without_evidence_verified_still_loads():
    old = ('{"id":"1","skills":[{"id":"a","name":"A","track":"t","level":1,"evidence":"e"}],'
           '"other_skills":[{"name":"B","level":2,"evidence":"e"}]}')
    result = CandidateResult.model_validate_json(old)
    assert result.skills[0].evidence_verified is None
    assert result.other_skills[0].evidence_verified is None


def test_evidence_verified_round_trips_through_json():
    from skillgap.models import OtherSkill, Skill
    for flag in (True, False):
        result = CandidateResult(
            id="1",
            skills=[Skill(id="a", name="A", track="t", level=1, evidence="e", evidence_verified=flag)],
            other_skills=[OtherSkill(name="B", level=1, evidence="e", evidence_verified=flag)])
        loaded = CandidateResult.model_validate_json(result.model_dump_json())
        assert loaded.skills[0].evidence_verified is flag
        assert loaded.other_skills[0].evidence_verified is flag
