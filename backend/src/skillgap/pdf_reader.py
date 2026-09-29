import io

import pdfplumber
import pypdfium2 as pdfium
import pytesseract
from pytesseract import TesseractError, TesseractNotFoundError

from skillgap.errors import PipelineError

MIN_CHARS = 30
OCR_DPI = 300


def _ocr_page(data: bytes, index: int) -> str:
    pdf = pdfium.PdfDocument(data)
    try:
        image = pdf[index].render(scale=OCR_DPI / 72).to_pil()
        return pytesseract.image_to_string(image, lang="por+eng")
    except (TesseractNotFoundError, TesseractError) as exc:
        raise PipelineError("OCR_UNAVAILABLE") from exc
    finally:
        pdf.close()


def extract_text(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            native = [(page.extract_text() or "").strip() for page in pdf.pages]
    except Exception as exc:  # pdfminer levanta vários tipos para arquivos inválidos
        raise PipelineError("INVALID_PDF") from exc

    pages: list[str] = []
    ocr_unavailable = False
    for index, text in enumerate(native):
        if len(text) >= MIN_CHARS:
            pages.append(text)
            continue
        try:
            ocr_text = _ocr_page(data, index).strip()
        except PipelineError as exc:
            if exc.code != "OCR_UNAVAILABLE":
                raise
            ocr_unavailable = True
            pages.append(text)
            continue
        pages.append(ocr_text if len(ocr_text) > len(text) else text)

    full_text = "\n\n".join(page for page in pages if page)
    if ocr_unavailable and not any(len(t) >= MIN_CHARS for t in native):
        raise PipelineError("OCR_UNAVAILABLE")
    if not full_text:
        raise PipelineError("NO_TEXT")
    return full_text
