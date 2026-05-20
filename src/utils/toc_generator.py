import re

def generate_toc(markdown: str) -> str:
    lines = []
    for match in re.finditer(r"^(#{2,4})\s+(.+)$", markdown, re.MULTILINE):
        level = len(match.group(1)) - 2
        title = match.group(2).strip()
        anchor = re.sub(r"[^a-z0-9\u4e00-\u9fff-]", "", title.lower().replace(" ", "-"))
        lines.append(f"{'  ' * level}- [{title}](#{anchor})")
    return "\n".join(lines)

def insert_toc(markdown: str) -> str:
    toc = generate_toc(markdown)
    if not toc:
        return markdown
    toc_block = f"## Table of Contents\n\n{toc}\n\n---\n\n"
    first_heading = re.search(r"^#\s+.+$", markdown, re.MULTILINE)
    if first_heading:
        pos = first_heading.end()
        return markdown[:pos] + "\n\n" + toc_block + markdown[pos:].lstrip("\n")
    return toc_block + markdown
