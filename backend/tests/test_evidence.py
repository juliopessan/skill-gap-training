import time

from skillgap.evidence import verify_evidence

TEXT = "Liderei projetos com OneLake e criei dashboards em Power BI para a diretoria."


def test_exact_substring_is_verified():
    assert verify_evidence("projetos com OneLake", TEXT)


def test_case_differences_are_ignored():
    assert verify_evidence("PROJETOS COM ONELAKE", TEXT)


def test_whitespace_newline_and_nbsp_differences_are_ignored():
    text = "Liderei  projetos\ncom OneLake\t e criei dashboards"
    assert verify_evidence("projetos com OneLake e criei", text)


def test_soft_hyphen_and_zero_width_chars_are_ignored():
    text = "dashboards em Po­wer​ BI para a diretoria"
    assert verify_evidence("dashboards em Power BI", text)
    assert verify_evidence("dashboards em Po­wer BI", "dashboards em Power BI")


def test_curly_quotes_and_dashes_are_normalised():
    text = 'Usei "Delta Lake" - camada prata e o l’ arquivo'
    assert verify_evidence("Usei “Delta Lake” – camada prata", text)


def test_ellipsis_fragments_found_in_order():
    assert verify_evidence("projetos com OneLake … dashboards em Power BI", TEXT)
    assert verify_evidence("projetos com OneLake ... dashboards em Power BI", TEXT)


def test_ellipsis_fragments_in_reverse_order_are_not_verified():
    assert not verify_evidence("dashboards em Power BI … projetos com OneLake", TEXT)


def test_one_missing_fragment_is_not_verified():
    assert not verify_evidence("projetos com OneLake … pipelines em Kubernetes", TEXT)


def test_paraphrase_is_not_verified():
    assert not verify_evidence("trabalhou com lakehouse e relatórios", TEXT)


def test_invented_quote_is_not_verified():
    assert not verify_evidence("operação de clusters Kubernetes em produção", TEXT)


def test_evidence_shorter_than_8_chars_proves_nothing():
    assert not verify_evidence("Spark", "Trabalho com Spark todo dia")


def test_short_fragments_are_ignored_but_long_one_must_match():
    assert verify_evidence("xx … projetos com OneLake", TEXT)
    assert not verify_evidence("xx … projetos com Kubernetes", TEXT)


def test_empty_evidence_or_text_is_not_verified():
    assert not verify_evidence("", TEXT)
    assert not verify_evidence("   \n ", TEXT)
    assert not verify_evidence("projetos com OneLake", "")


def test_accents_matter_but_case_does_not_gestao_vs_gestao_without_accent():
    text = "Experiência em Gestão de projetos"
    assert verify_evidence("GESTÃO de projetos", text)
    assert not verify_evidence("gestao de projetos", text)


def test_very_long_text_with_evidence_at_the_end_is_fast():
    text = ("linha de curriculo sem relevancia\n" * 6000) + "ultimo bullet: projetos com OneLake"
    assert len(text) > 200_000
    start = time.perf_counter()
    assert verify_evidence("projetos com OneLake", text)
    assert time.perf_counter() - start < 1


import pytest  # noqa: E402


@pytest.mark.parametrize("evidence,text", [
    ("Led a team of 5", "Led a team of 50 engineers"),
    ("5 years of Java experience", "15 years of Java experience"),
    ("Python and SQL for data", "Cpython and SQL for data"),
    ("engineering lead", "reengineering leadership"),
])
def test_match_inside_a_longer_word_or_number_is_not_verified(evidence, text):
    assert not verify_evidence(evidence, text)


@pytest.mark.parametrize("evidence,text", [
    ("Led a team of 5", "Led a team of 5 engineers."),
    ("... team of 5, then", "Led a team of 5, then left"),
    ("Led a team of 5", "Led a team of 5"),
    ("5 years of Java experience", "5 years of Java experience at ACME"),
    ("projetos com OneLake.", "Fiz projetos com OneLake. Depois outros"),
    ("5 years of Java experience", "15 years of Java experience ... 5 years of Java experience"),
    ("front−end dev work", "front-end dev work"),
    ("front‐end dev‑work", "front-end dev-work"),
    ("dev⁠ops platform", "devops platform"),
])
def test_boundary_positive_controls(evidence, text):
    assert verify_evidence(evidence, text)


def test_ordering_across_fragments_is_still_enforced_with_boundaries():
    text = "alpha beta gamma ... delta epsilon zeta"
    assert verify_evidence("alpha beta gamma ... delta epsilon", text)
    assert not verify_evidence("delta epsilon ... alpha beta gamma", text)
