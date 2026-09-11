"""HTML and PDF text extraction."""

from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def html_title(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else None


def extract_links(html: str, base_url: str) -> list[str]:
    from urllib.parse import urljoin, urlparse

    soup = BeautifulSoup(html, "lxml")
    base_host = urlparse(base_url).netloc
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc != base_host:
            continue
        links.append(href.split("#")[0])
    return sorted(set(links))


def extract_pdf_text(path_or_bytes) -> str:
    text = ""
    try:
        import pdfplumber

        if isinstance(path_or_bytes, (bytes, bytearray)):
            import io

            with pdfplumber.open(io.BytesIO(path_or_bytes)) as pdf:
                parts = [page.extract_text() or "" for page in pdf.pages]
                text = "\n".join(parts)
        else:
            with pdfplumber.open(path_or_bytes) as pdf:
                parts = [page.extract_text() or "" for page in pdf.pages]
                text = "\n".join(parts)
    except Exception:
        text = ""

    if text and len(text.strip()) > 40:
        return text

    # OCR fallback for scanned PDFs
    try:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image
        import io

        if isinstance(path_or_bytes, (bytes, bytearray)):
            doc = fitz.open(stream=path_or_bytes, filetype="pdf")
        else:
            doc = fitz.open(path_or_bytes)
        ocr_parts = []
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_parts.append(pytesseract.image_to_string(img, lang="eng+hin"))
        return "\n".join(ocr_parts)
    except Exception:
        return text
