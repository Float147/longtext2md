"""
目录生成器 —— 程序化解析 Markdown 标题生成可跳转 TOC。

纯程序实现，零 LLM 成本，零错误率。
"""
import re

def generate_toc(md_text: str) -> str:
    """从 Markdown 标题生成层级目录。"""
    lines = md_text.split("\n")
    toc = ["## 目录\n"]
    for line in lines:
        m = re.match(r"^(#{2,4})\s+(.+)", line)
        if m:
            level = len(m.group(1)) - 2
            htext = m.group(2).strip()
            anchor = re.sub(r"[^\w\u4e00-\u9fff-]", "", htext.lower().replace(" ", "-"))
            indent = "  " * level
            toc.append(f"{indent}- [{htext}](#{anchor})")
    return "\n".join(toc) if len(toc) > 1 else ""

def insert_toc(md_text: str) -> str:
    """在 Markdown 开头插入目录。"""
    toc = generate_toc(md_text)
    if not toc:
        return md_text
    # 在第一个 ## 标题前插入
    first_h2 = re.search(r"\n##\s", md_text)
    if first_h2:
        return md_text[:first_h2.start()] + "\n" + toc + "\n" + md_text[first_h2.start():]
    return toc + "\n\n" + md_text
