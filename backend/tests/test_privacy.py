import pytest
from skillgap.privacy import scrub


# Original simple tests (kept for compatibility)
def test_removes_email():
    assert "maria@empresa.com.br" not in scrub("Contato: maria@empresa.com.br hoje")


def test_removes_cep():
    assert "01234-567" not in scrub("CEP 01234-567")


def test_keeps_name_year_ranges_and_skills():
    text = "Maria Silva\n2019-2021 Engenheira, PySpark e Microsoft Fabric (2022 - 2024)"
    assert scrub(text) == text


def test_keeps_tech_words_that_look_like_links():
    text = "Python, SQL, GitHub, CI/CD, REST APIs, Jan 2011 – Jan 2021"
    assert scrub(text) == text


# ROUND 2: Exact-equality phone removal tests (must-remove list with 18 phones)
@pytest.mark.parametrize("phone", [
    "07700 900123",           # UK without +44
    "020 7946 0958",          # UK area code
    "555-123-4567",           # US
    "(555) 123-4567",         # US
    "555.123.4567",           # US
    "+1 (555) 123-4567",      # US with country code
    "1-555-123-4567",         # US with country code
    "0044 7700 900123",       # UK with 00 prefix
    "(011) 91234-5678",       # Brazilian with leading 0
    "11 9 1234 5678",         # Brazilian with spaces
    "(11) 9 1234 5678",       # Brazilian with spaces
    "+44 (0)20 7946 0958",    # UK with (0) notation
    "+44 7700 900123",        # UK international
    "+55 11 91234 5678",      # BR international
    "(11) 91234-5678",        # BR standard
    "11 91234-5678",          # BR without parens
    "(11) 3456-7890",         # BR landline
])
def test_removes_phone_exact(phone):
    """Exact-output assertion: phone must be completely removed."""
    assert scrub(f"Tel: {phone}. Next") == "Tel: . Next"


# False-positive guards (must stay unchanged)
@pytest.mark.parametrize("text", [
    "150M+ OCR reads/month",
    "53x ROI",
    "£260K+",
    "99.9% uptime",
    "1,200,000 records",
    "2019-2021",
    "2019 - 2021",
    "(2022 - 2024)",
    "Apr 2026 – Present",
    "Jan 2011 – Jan 2021",
])
def test_keeps_false_positive_exact(text):
    """Exact-output assertion: false positives must be unchanged."""
    assert scrub(text) == text


# Address masking tests: exact output assertions
def test_masks_portuguese_address_simple():
    """Rua das Flores, 123 must be masked."""
    input_text = "Maria Silva\nRua das Flores, 123 - Centro\nEngenheira de dados"
    output = scrub(input_text)
    # The address span "Rua das Flores, 123" should be removed
    assert "Flores" not in output
    assert "Maria Silva" in output
    assert "Engenheira de dados" in output
    assert "- Centro" in output  # This part should remain


def test_masks_portuguese_multiword_addresses():
    """Multi-word Portuguese addresses must be masked."""
    # Avenida Brigadeiro Faria Lima, 3477
    text1 = "Worked at Avenida Brigadeiro Faria Lima, 3477 in São Paulo"
    result1 = scrub(text1)
    assert "Avenida Brigadeiro Faria Lima, 3477" not in result1
    assert "Worked at" in result1
    assert "in São Paulo" in result1

    # Rua Visconde de Piraja 550
    text2 = "Office: Rua Visconde de Piraja 550 near beach"
    result2 = scrub(text2)
    assert "Rua Visconde de Piraja 550" not in result2
    assert "Office:" in result2
    assert "near beach" in result2

    # Rua das Flores Bonitas, 123
    text3 = "Rua das Flores Bonitas, 123 - Apt 5"
    result3 = scrub(text3)
    assert "Rua das Flores Bonitas, 123" not in result3
    assert "- Apt 5" in result3


def test_masks_english_addresses_case_sensitive():
    """English addresses must use case-sensitive matching."""
    # "12 Baker Street" must be masked
    text1 = "Located at 12 Baker Street, London"
    result1 = scrub(text1)
    assert "12 Baker Street" not in result1
    assert "Located at" in result1
    assert ", London" in result1

    # "42 Wallaby Way" must be masked
    text2 = "Headquarters: 42 Wallaby Way Sydney"
    result2 = scrub(text2)
    assert "42 Wallaby Way" not in result2
    assert "Headquarters:" in result2
    assert "Sydney" in result2


def test_keeps_english_false_positives_case_sensitive():
    """English text with lowercase street words must be preserved."""
    # "Improved 3 Street View services" - "street" is lowercase, should be kept
    text1 = "Improved 3 Street View services"
    assert scrub(text1) == text1

    # "Moved 40 Road projects"
    text2 = "Moved 40 Road projects"
    assert scrub(text2) == text2

    # "Trained 5 Road Warrior models"
    text3 = "Trained 5 Road Warrior models"
    assert scrub(text3) == text3

    # "Increased 30 Way Points"
    text4 = "Increased 30 Way Points"
    assert scrub(text4) == text4

    # "Reached 20 St Louis clients"
    text5 = "Reached 20 St Louis clients"
    assert scrub(text5) == text5

    # "Used 2 Dr Watson tools"
    text6 = "Used 2 Dr Watson tools"
    assert scrub(text6) == text6


def test_keeps_portuguese_false_positives():
    """Portuguese text with lowercase street words must be preserved."""
    # "Led Estrada project migration, 3 teams"
    text1 = "Led Estrada project migration, 3 teams"
    assert scrub(text1) == text1

    # "Reduced av processing time to 2 days"
    text2 = "Reduced av processing time to 2 days"
    assert scrub(text2) == text2

    # "Built REST road-mapping system; improved Street View pipeline latency by 40%"
    text3 = "Built REST road-mapping system; improved Street View pipeline latency by 40%"
    assert scrub(text3) == text3

    # "Reduced av processing time to 2 days; Avenida Paulista 1000"
    text4 = "Reduced av processing time to 2 days; Avenida Paulista 1000"
    expected4 = "Reduced av processing time to 2 days; "
    assert scrub(text4) == expected4


def test_masks_uk_postcodes():
    """UK postcodes must be masked."""
    text1 = "London NW1 6XE and Manchester SW1A 1AA are locations"
    result1 = scrub(text1)
    assert "NW1 6XE" not in result1
    assert "SW1A 1AA" not in result1
    assert "London" in result1
    assert "Manchester" in result1

    # Full address with postcode
    text2 = "221B Baker Street, London NW1 6XE"
    result2 = scrub(text2)
    assert "Baker Street" not in result2
    assert "NW1 6XE" not in result2


def test_masks_avaliable_portuguese_address_formats():
    """Test various Portuguese address formats."""
    # Av. Paulista 1000
    text1 = "Located at Av. Paulista 1000"
    result1 = scrub(text1)
    assert "Av. Paulista 1000" not in result1
    assert "Located at" in result1

    # Avenida Paulista 1000
    text2 = "Headquarters: Avenida Paulista 1000"
    result2 = scrub(text2)
    assert "Avenida Paulista 1000" not in result2
    assert "Headquarters:" in result2

    # Rua XV de Novembro, 200
    text3 = "Rua XV de Novembro, 200 - Centro"
    result3 = scrub(text3)
    assert "Rua XV de Novembro, 200" not in result3
    assert "- Centro" in result3


# ROUND 3: Brazilian forms found in the final review
@pytest.mark.parametrize("text,expected", [
    ("Zap: wa.me/5511912345678 fim", "Zap:  fim"),
    ("Zap: https://wa.me/5511912345678 fim", "Zap:  fim"),
    ("Tel 5511912345678 fim", "Tel  fim"),
    ("Tel 551133334444 fim", "Tel  fim"),
    ("Cel: 91234-5678", "Cel: "),
    ("Celular 91234-5678 fim", "Celular  fim"),
    ("Fone: 3456-7890", "Fone: "),
    ("WhatsApp - 91234-5678", "WhatsApp - "),
    ("Contato: 91234-5678", "Contato: "),
    ("CEP: 01234567 fim", "CEP:  fim"),
    ("CEP 01234567", "CEP "),
])
def test_removes_brazilian_forms_exact(text, expected):
    assert scrub(text) == expected


@pytest.mark.parametrize("text", [
    "2019-2021",
    "2019 - 2021",
    "(2022 - 2024)",
    "Apr 2026 – Present",
    "150M+ OCR reads/month",
    "53x ROI",
    "99.9% uptime",
    "1,200,000 records",
    "Python 3.11.4",
    "Q3 2025",
    "2025-01-15",
    "Contato 2019-2021 Engenheira",
])
def test_keeps_more_false_positives_exact(text):
    assert scrub(text) == text
