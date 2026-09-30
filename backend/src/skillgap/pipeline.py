from dataclasses import dataclass
from typing import Callable

from skillgap.classifier import build_profile
from skillgap.evidence import verify_evidence
from skillgap.gap_analyzer import analyze_gaps
from skillgap.models import ExtractedProfile, Supplementary
from skillgap.rating import compute_rating
from skillgap.pdf_reader import extract_text
from skillgap.privacy import scrub
from skillgap.recommender import Course, recommend, uncovered_gaps
from skillgap.taxonomy import Taxonomy


@dataclass
class Deps:
    taxonomy: Taxonomy
    # Lista fixa ou callable resolvido a cada execução (edições no banco valem no próximo CV).
    courses: list[Course] | Callable[[], list[Course]]
    extract: Callable[[str, list[str]], ExtractedProfile]
    supplement: Callable[[list[str]], tuple[list[Supplementary], str]] | None = None


def run_pipeline(data: bytes, deps: Deps, on_stage: Callable[[str], None] = lambda s: None) -> dict:
    on_stage("reading")
    text = extract_text(data)

    on_stage("extracting")
    sent = scrub(text)
    extracted = deps.extract(sent, deps.taxonomy.hint_names())

    on_stage("analyzing")
    skills, other_skills = build_profile(extracted, deps.taxonomy)
    skills = [s.model_copy(update={"evidence_verified": verify_evidence(s.evidence, sent)}) for s in skills]
    other_skills = [o.model_copy(update={"evidence_verified": verify_evidence(o.evidence, sent)})
                    for o in other_skills]
    gaps, no_data_tracks = analyze_gaps(skills, deps.taxonomy)
    rating = compute_rating(skills, deps.taxonomy)

    on_stage("recommending")
    courses = deps.courses() if callable(deps.courses) else deps.courses
    recommendations = recommend(gaps, courses)
    supplementary: list[Supplementary] | None = None
    learn_status: str | None = None
    if deps.supplement is not None:
        # Só nomes de skills da taxonomia saem daqui; nunca texto do CV.
        try:
            supplementary, learn_status = deps.supplement(uncovered_gaps(gaps, courses))
        except Exception:
            supplementary, learn_status = [], "unavailable"

    return {
        "candidate": extracted.candidate,
        "skills": skills,
        "other_skills": other_skills,
        "gaps": gaps,
        "recommendations": recommendations,
        "no_data_tracks": no_data_tracks,
        "rating": rating,
        "supplementary": supplementary,
        "learn_status": learn_status,
    }
