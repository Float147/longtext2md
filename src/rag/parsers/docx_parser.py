from docx import Document

def parse_docx_file(filepath: str) -> list[dict]:
    doc = Document(filepath)
    return [{"file": filepath, "type": "courseware", "content": p.text.strip(), "metadata": {"title": p.text.strip()[:50]}} for p in doc.paragraphs if p.text.strip()]
