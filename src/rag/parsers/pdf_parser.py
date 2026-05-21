"""
PDF 课件解析器 — 按页提取文本，切片为 RAG 切片。
"""
import os
from PyPDF2 import PdfReader

MAX_CHARS_PER_SLICE = 2000


def parse_pdf_file(filepath: str) -> list[dict]:
    """解析 PDF 文件，按页提取文本，超长页自动切分。"""
    fn = os.path.basename(filepath)
    try:
        reader = PdfReader(filepath)
    except Exception:
        return []

    slices = []
    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if not text or not text.strip():
            continue
        text = text.strip()

        # 超长页按字符数切分
        if len(text) <= MAX_CHARS_PER_SLICE:
            slices.append({
                "file": fn,
                "type": "courseware",
                "content": text,
                "metadata": {
                    "title": f"{fn} p.{page_idx + 1}",
                    "page": page_idx + 1,
                    "filepath": filepath,
                },
            })
        else:
            for chunk_idx in range(0, len(text), MAX_CHARS_PER_SLICE):
                chunk = text[chunk_idx:chunk_idx + MAX_CHARS_PER_SLICE]
                if chunk.strip():
                    slices.append({
                        "file": fn,
                        "type": "courseware",
                        "content": chunk,
                        "metadata": {
                            "title": f"{fn} p.{page_idx + 1}/{chunk_idx // MAX_CHARS_PER_SLICE + 1}",
                            "page": page_idx + 1,
                            "filepath": filepath,
                        },
                    })

    return slices