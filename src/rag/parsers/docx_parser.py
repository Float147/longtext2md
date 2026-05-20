"""
Word 文档解析器 —— 将 .docx 课件解析为 RAG 切片。
"""
from docx import Document

def parse_docx_file(filepath: str) -> list[dict]:
    """解析 Word 文档，按段落切分，每段为一个切片。"""
    doc = Document(filepath)
    return [{
        "file": filepath,
        "type": "courseware",
        "content": p.text.strip(),
        "metadata": {"title": p.text.strip()[:50]},
    } for p in doc.paragraphs if p.text.strip()]