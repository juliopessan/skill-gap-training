"""Candidate rating: adherence to the expected levels plus an overall level label.

The arithmetic is deterministic and rule-based (no LLM), but it is computed FROM
LEVELS INFERRED BY THE MODEL from the CV text. It is therefore an estimate built
on inferred data, not a measurement of the candidate's real skill.

Only tracks WITH DATA count (same rule as ``analyze_gaps``: at least one mapped
skill of the candidate belongs to the track). For each taxonomy skill of such a
track, ``covered += min(level, expected_level)`` (level 0 when absent) and
``expected += expected_level``; adherence is ``100 * covered / expected``.

``adherence_supported`` repeats the computation counting a skill only when its
``evidence_verified`` is True (quote found in the CV). It is a lower bound: how
much of the adherence is backed by a citation actually found in the text.
"""
from skillgap.models import Rating, Skill, TrackRating
from skillgap.taxonomy import Taxonomy


def level_label(mean: float | None) -> str | None:
    if mean is None:
        return None
    if mean < 1.5:
        return "Básico"
    if mean < 2.5:
        return "Intermediário"
    return "Avançado"


def _mean(levels: list[int]) -> float | None:
    return round(sum(levels) / len(levels), 2) if levels else None


def _pct(covered: int, expected: int) -> float:
    return round(100 * covered / expected, 1) if expected else 0.0


def compute_rating(skills: list[Skill], taxonomy: Taxonomy) -> Rating | None:
    levels = {s.id: s.level for s in skills}
    supported = {s.id: s.level for s in skills if s.evidence_verified is True}
    tracks_with_data = {s.track for s in skills}
    rows: list[TrackRating] = []
    tot_cov = tot_sup = tot_exp = 0
    for track_id, name in taxonomy.tracks.items():
        if track_id not in tracks_with_data:
            continue
        cov = sup = exp = 0
        mapped: list[int] = []
        for ts in taxonomy.skills_in_track(track_id):
            exp += ts.expected_level
            cov += min(levels.get(ts.id, 0), ts.expected_level)
            sup += min(supported.get(ts.id, 0), ts.expected_level)
            if levels.get(ts.id, 0) >= 1:
                mapped.append(levels[ts.id])
        mean = _mean(mapped)
        rows.append(TrackRating(
            track=track_id, name=name, adherence=_pct(cov, exp),
            adherence_supported=_pct(sup, exp), covered=cov, expected=exp,
            skills_rated=len(mapped), mean_level=mean, level_label=level_label(mean)))
        tot_cov += cov
        tot_sup += sup
        tot_exp += exp
    if not rows:
        return None
    overall = _mean([s.level for s in skills if s.level >= 1])
    return Rating(
        adherence=_pct(tot_cov, tot_exp), adherence_supported=_pct(tot_sup, tot_exp),
        covered=tot_cov, expected=tot_exp, mean_level=overall,
        level_label=level_label(overall), tracks=rows)
