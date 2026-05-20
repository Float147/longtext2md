import os, re

def parse_code_file(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    ext = os.path.splitext(filepath)[1]
    return [{"file": filepath, "type": "code", "content": content, "metadata": {"language": ext.lstrip(".")}}]

def create_code_fingerprint(slice_content: str, filename: str, annotations: str = "") -> str:
    lines = slice_content.split("
")
    keywords = ["class ", "def ", "function ", "public ", "@", "import ", "from ", "const ", "interface "]
    key_lines = [l.strip() for l in lines if any(kw in l.strip() for kw in keywords)]
    fp = f"Code: {filename}
" + "
".join(key_lines[:5])
    if annotations:
        fp += f"
// {annotations}"
    return fp
