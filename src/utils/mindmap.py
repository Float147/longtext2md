"""
思维导图生成器 —— 解析 Markdown 标题树，生成 Mermaid mindmap。
"""
import re

def generate_mindmap(md_text: str, title: str = "Course Notes") -> str:
    """从 Markdown 标题生成 Mermaid mindmap 格式的思维导图。"""
    lines = md_text.split("\n")
    headers = []
    for line in lines:
        m = re.match(r"^(#{1,4})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            htext = m.group(2).strip()
            headers.append((level, htext))
    if not headers:
        return ""
    result = ["```mermaid", "mindmap", f"  root(({title}))"]
    for level, htext in headers:
        indent = "    " * level
        result.append(f"{indent}{htext}")
    result.append("```")
    return "\n".join(result)
