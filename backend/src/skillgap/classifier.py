from skillgap.models import ExtractedProfile, OtherSkill, Skill
from skillgap.taxonomy import Taxonomy, normalize


def build_profile(
    extracted: ExtractedProfile, taxonomy: Taxonomy
) -> tuple[list[Skill], list[OtherSkill]]:
    known: dict[str, Skill] = {}
    others: dict[str, OtherSkill] = {}
    for raw in extracted.skills:
        tax_skill = taxonomy.match(raw.name)
        if tax_skill:
            current = known.get(tax_skill.id)
            if current is None or raw.level > current.level:
                known[tax_skill.id] = Skill(
                    id=tax_skill.id, name=tax_skill.name, track=tax_skill.track,
                    level=raw.level, evidence=raw.evidence)
        else:
            key = normalize(raw.name)
            current = others.get(key)
            if current is None or raw.level > current.level:
                others[key] = OtherSkill(
                    name=raw.name, level=raw.level, evidence=raw.evidence)
    return list(known.values()), list(others.values())
