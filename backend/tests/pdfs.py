import io

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas


def make_text_pdf(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()
    return buffer.getvalue()


def make_scanned_pdf(lines: list[str]) -> bytes:
    """PDF só com imagem (sem camada de texto), como um scan."""
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    y = 100
    for line in lines:
        draw.text((100, y), line, fill="black", font=font)
        y += 70
    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()


def make_two_page_pdf(page1: list[str], page2: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for lines in (page1, page2):
        y = 800
        for line in lines:
            pdf.drawString(72, y, line)
            y -= 20
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()
