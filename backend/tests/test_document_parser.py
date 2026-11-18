import fitz

from backend.app.services.document_parser import extract_document_text


def test_extract_pdf_text_from_text_based_pdf():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Question: What is photosynthesis?")
    content = document.tobytes()
    document.close()

    text, extraction_method = extract_document_text(content, "assessment.pdf")

    assert "What is photosynthesis?" in text
    assert extraction_method == "pdf_text"
