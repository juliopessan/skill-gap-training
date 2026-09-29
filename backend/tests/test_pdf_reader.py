import shutil

import pytest
from pytesseract import TesseractNotFoundError

from pdfs import make_scanned_pdf, make_text_pdf, make_two_page_pdf
from skillgap import pdf_reader
from skillgap.errors import PipelineError
from skillgap.pdf_reader import extract_text

TEXT_LINES = ["Maria Silva", "Experience with Microsoft Fabric and Azure AI Foundry in projects."]


def test_native_text_pdf_is_read_without_ocr(monkeypatch):
    monkeypatch.setattr(pdf_reader, "_ocr_page", lambda *a: pytest.fail("OCR não deveria rodar"))
    text = extract_text(make_text_pdf(TEXT_LINES))
    assert "Microsoft Fabric" in text and "Maria Silva" in text


def test_scanned_page_falls_back_to_ocr(monkeypatch):
    monkeypatch.setattr(pdf_reader, "_ocr_page", lambda data, index: "Texto lido pelo OCR: Databricks e Spark")
    text = extract_text(make_scanned_pdf(TEXT_LINES))
    assert "Databricks" in text


def test_ocr_that_reads_nothing_raises_no_text(monkeypatch):
    monkeypatch.setattr(pdf_reader, "_ocr_page", lambda data, index: "   ")
    with pytest.raises(PipelineError) as error:
        extract_text(make_scanned_pdf(TEXT_LINES))
    assert error.value.code == "NO_TEXT"


def test_missing_tesseract_raises_ocr_unavailable(monkeypatch):
    def boom(*args, **kwargs):
        raise TesseractNotFoundError()
    monkeypatch.setattr(pdf_reader.pytesseract, "image_to_string", boom)
    with pytest.raises(PipelineError) as error:
        extract_text(make_scanned_pdf(TEXT_LINES))
    assert error.value.code == "OCR_UNAVAILABLE"


def test_native_pdf_with_nearly_empty_page_survives_missing_tesseract(monkeypatch):
    def boom(*args, **kwargs):
        raise TesseractNotFoundError()
    monkeypatch.setattr(pdf_reader.pytesseract, "image_to_string", boom)
    text = extract_text(make_two_page_pdf(TEXT_LINES, ["p. 2"]))
    assert "Microsoft Fabric" in text


def test_only_short_native_fragments_with_missing_tesseract_raises_ocr_unavailable(monkeypatch):
    def boom(*args, **kwargs):
        raise TesseractNotFoundError()
    monkeypatch.setattr(pdf_reader.pytesseract, "image_to_string", boom)
    with pytest.raises(PipelineError) as error:
        extract_text(make_two_page_pdf(["1"], ["2"]))
    assert error.value.code == "OCR_UNAVAILABLE"


@pytest.mark.parametrize("data", [b"", b"isto nao e um pdf", b"PK\x03\x04 docx renomeado"])
def test_non_pdf_bytes_raise_invalid_pdf(data):
    with pytest.raises(PipelineError) as error:
        extract_text(data)
    assert error.value.code == "INVALID_PDF"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract não instalado")
def test_real_tesseract_reads_a_scanned_pdf():
    text = extract_text(make_scanned_pdf(["Microsoft Fabric Lakehouse", "Azure AI Foundry Agents"]))
    assert "fabric" in text.lower()
