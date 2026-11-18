from __future__ import annotations

from io import BytesIO
from typing import Tuple


class DocumentParserError(RuntimeError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


MAX_DOCUMENT_PAGES = 80


def extract_document_text(content: bytes, filename: str, ocr_language: str = "eng") -> Tuple[str, str]:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension == "pdf":
        return _extract_pdf_text(content, ocr_language)
    if extension in {"jpg", "jpeg"}:
        return _extract_image_text(content, ocr_language), "ocr"
    raise DocumentParserError("Only PDF, JPG, and JPEG assessment documents are supported.")


def _extract_pdf_text(content: bytes, ocr_language: str) -> Tuple[str, str]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ModuleNotFoundError as error:
        raise DocumentParserError("PDF support is unavailable. Install the backend requirements.", 503) from error

    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if len(reader.pages) > MAX_DOCUMENT_PAGES:
            raise DocumentParserError(f"PDFs may contain at most {MAX_DOCUMENT_PAGES} pages.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except DocumentParserError:
        raise
    except (PdfReadError, ValueError, OSError) as error:
        raise DocumentParserError("The PDF could not be read. Verify that it is a valid, unencrypted PDF.") from error

    text = "\n\n".join(page.strip() for page in pages if page.strip()).strip()
    if text:
        return text, "pdf_text"
    return _ocr_pdf(content, ocr_language), "ocr"


def _ocr_pdf(content: bytes, ocr_language: str) -> str:
    try:
        import fitz
        from PIL import Image
        import pytesseract
    except ModuleNotFoundError as error:
        raise DocumentParserError(
            "Scanned PDF OCR dependencies are unavailable. Install the backend requirements and Tesseract.",
            503,
        ) from error

    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            if len(document) > MAX_DOCUMENT_PAGES:
                raise DocumentParserError(f"PDFs may contain at most {MAX_DOCUMENT_PAGES} pages.")
            page_text = []
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.open(BytesIO(pixmap.tobytes("png")))
                page_text.append(pytesseract.image_to_string(image, lang=ocr_language))
    except DocumentParserError:
        raise
    except pytesseract.pytesseract.TesseractNotFoundError as error:
        raise DocumentParserError(
            "Tesseract OCR was not found. Install Tesseract on Windows and add its executable to PATH.",
            503,
        ) from error
    except pytesseract.pytesseract.TesseractError as error:
        raise DocumentParserError(
            f"Tesseract could not OCR this PDF using language data '{ocr_language}'."
        ) from error
    except (fitz.FileDataError, OSError, RuntimeError, ValueError) as error:
        raise DocumentParserError("The scanned PDF could not be rendered for OCR.") from error

    text = "\n\n".join(part.strip() for part in page_text if part.strip()).strip()
    if not text:
        raise DocumentParserError("No readable text was found in the scanned PDF.")
    return text


def _extract_image_text(content: bytes, ocr_language: str) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ModuleNotFoundError as error:
        raise DocumentParserError(
            "Image OCR dependencies are unavailable. Install the backend requirements and Tesseract."
        ) from error

    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != "JPEG":
                raise DocumentParserError("The image must be a valid JPEG file.")
            image.verify()
        with Image.open(BytesIO(content)) as image:
            text = pytesseract.image_to_string(image, lang=ocr_language).strip()
    except DocumentParserError:
        raise
    except pytesseract.pytesseract.TesseractNotFoundError as error:
        raise DocumentParserError(
            "Tesseract OCR was not found. Install Tesseract on Windows and add its executable to PATH.",
            503,
        ) from error
    except pytesseract.pytesseract.TesseractError as error:
        raise DocumentParserError(
            f"Tesseract could not OCR this image using language data '{ocr_language}'."
        ) from error
    except (OSError, ValueError) as error:
        raise DocumentParserError("The JPG/JPEG file is invalid or could not be read.") from error

    if not text:
        raise DocumentParserError("No readable text was found in the image.")
    return text
