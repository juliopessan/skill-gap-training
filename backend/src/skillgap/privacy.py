import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# Enhanced phone regex: handles international (+), 00 prefix, 0X format, US/NANP, and Brazilian variants
_PHONE = re.compile(
    r"(?<!\d)(?:"
    r"\+\d{1,3}[\s.-]?\(?0?\)?[\s.-]?\d(?:[\s.-]?\d){7,10}"  # +44 (0)20 7946 0958, +55 11 91234 5678, +1 (555) 123-4567
    r"|00\d{1,3}[\s.-]?\d(?:[\s.-]?\d){7,10}"  # 0044 7700 900123
    r"|0\d[\s.-]?\d(?:[\s.-]?\d){6,9}"  # 07700 900123, 020 7946 0958
    r"|(?:\+?1[\s.-])?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]\d{4}"  # US/NANP: 555-123-4567, (555) 123-4567, +1 (555) 123-4567
    r"|\(0\d{2}\)[\s.-]?9?\d{4}[\s.-]?\d{4}"  # BR with leading 0: (011) 91234-5678
    r"|(?:\(\d{2}\)|\d{2})[\s.-]?9?[\s.-]?\d{4}[\s.-]?\d{4}"  # (11) 91234-5678, 11 9 1234 5678
    r")(?!\d)"
)

_PROFILE_URL = re.compile(
    r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/[\w./-]+", re.IGNORECASE)

_CEP = re.compile(r"\b\d{5}-\d{3}\b")

_WA_LINK = re.compile(r"(?:https?://)?wa\.me/\d+", re.IGNORECASE)

# 55 + DDD + number written without "+", e.g. 5511912345678
_BR_BARE_INTL = re.compile(r"(?<!\d)55\d{10,11}(?!\d)")

# Local numbers only when preceded by a label (an unlabelled 9?\d{4}-\d{4} would eat year ranges)
_LABELLED_LOCAL_PHONE = re.compile(
    r"(?i)(\b(?:cel(?:ular)?|tel(?:efone)?|fone|whats(?:app)?|contato)\b\s*[:.\-]?\s*)(?!(?:19|20)\d{2}-(?:19|20)\d{2}\b)9?\d{4}-\d{4}(?!\d)"
)

# 8-digit CEP without hyphen only after the label CEP (keeps the label)
_LABELLED_CEP = re.compile(r"(?i)(\bCEP:?\s*)\d{8}\b")

# Portuguese address pattern: street word (case-insensitive) + up to 5 name tokens + optional comma + number
# Tokens can be capitalized words or lowercase connectors (da, das, de, do, dos, e)
_PT_ADDRESS_SPAN = re.compile(
    r"\b(?i:rua|av\.?|avenida|alameda|travessa|rodovia|estrada)"
    r"(?:\s+(?:[A-ZÀ-Ú][\w'.-]*|d[aeo]s?|e))+?"  # 1-5 tokens (capitalized or lowercase connectors)
    r"(?:\s*,)?"
    r"\s+\d{1,5}",
)

# English address pattern: CASE-SENSITIVE, number (with optional letter) + required capitalized name words + street type
_EN_ADDRESS_SPAN = re.compile(
    r"\b\d+[A-Z]?\s+(?:[A-Z][a-z]*\s+)+(?:Street|St|Road|Rd|Lane|Ln|Drive|Dr|Avenue|Ave|Close|Way)\b"
)

# UK postcode pattern: NW1 6XE, SW1A 1AA format
_UK_POSTCODE_SPAN = re.compile(
    r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b"
)


def scrub(text: str) -> str:
    # Remove emails, profile URLs, phones, CEPs
    cleaned = text
    for pattern in (_EMAIL, _PROFILE_URL, _WA_LINK, _BR_BARE_INTL):
        cleaned = pattern.sub("", cleaned)
    cleaned = _LABELLED_LOCAL_PHONE.sub(r"\1", cleaned)
    cleaned = _LABELLED_CEP.sub(r"\1", cleaned)
    for pattern in (_PHONE, _CEP):
        cleaned = pattern.sub("", cleaned)

    # Mask address spans (Portuguese, English, UK postcodes)
    cleaned = _PT_ADDRESS_SPAN.sub("", cleaned)
    cleaned = _EN_ADDRESS_SPAN.sub("", cleaned)
    cleaned = _UK_POSTCODE_SPAN.sub("", cleaned)

    return cleaned
