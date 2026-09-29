from dataclasses import dataclass
from typing import Callable

from skillgap.classifier import build_profile
from skillgap.gap_analyzer import analyze_gaps
from skillgap.models import ExtractedProfile
from skillgap.pdf_reader import extract_text
from skillgap.privacy import scrub
from skillgap.recommender import Course, recommend
from skillgap.taxonomy import Taxonomy


@dataclass
class Deps:
    taxonomy: Taxonomy
    courses: list[Course]
    extract: Callable[[str, list[str]], ExtractedProfile]


def run_pipeline(data: bytes, deps: Deps, on_stage: Callable[[str], None] = lambda s: None) -> dict:
    on_stage("reading")
    text = extract_text(data)

    on_stage("extracting")
    extracted = deps.extract(scrub(text), deps.taxonomy.hint_names())

    on_stage("analyzing")
    skills, other_skills = build_profile(extracted, deps.taxonomy)
    gaps, no_data_tracks = analyze_gaps(skills, deps.taxonomy)

    on_stage("recommending")
    recommendations = recommend(gaps, deps.courses)

    return {
        "candidate": extracted.candidate,
        "skills": skills,
        "other_skills": other_skills,
        "gaps": gaps,
        "recommendations": recommendations,
        "no_data_tracks": no_data_tracks,
    }
