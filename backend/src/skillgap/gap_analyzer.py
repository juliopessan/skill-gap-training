from skillgap.models import Gap, Severity, Skill
from skillgap.taxonomy import Taxonomy

_RANK = {"high": 0, "medium": 1, "low": 2}


def severity(current: int, expected: int) -> Severity:
    if (current == 0 and expected >= 2) or expected - current >= 2:
        return "high"
    if current == 0:
        return "medium"
    return "low"


def analyze_gaps(skills: list[Skill], taxonomy: Taxonomy) -> tuple[list[Gap], list[str]]:
    levels = {s.id: s.level for s in skills}
    tracks_with_data = {s.track for s in skills}
    no_data = [t for t in taxonomy.tracks if t not in tracks_with_data]
    gaps: list[Gap] = []
    for track_id in taxonomy.tracks:
        if track_id not in tracks_with_data:
            continue
        for tax_skill in taxonomy.skills_in_track(track_id):
            current = levels.get(tax_skill.id, 0)
            if tax_skill.expected_level > current:
                gaps.append(Gap(
                    skill=tax_skill.id, name=tax_skill.name, track=track_id,
                    expected=tax_skill.expected_level, current=current,
                    severity=severity(current, tax_skill.expected_level)))
    gaps.sort(key=lambda g: _RANK[g.severity])
    return gaps, no_data
