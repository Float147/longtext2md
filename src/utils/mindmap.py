import re

def generate_mindmap(markdown: str, root_title: str = "Course Notes") -> str:
    headings = []
    for match in re.finditer(r"^(#{2,4})\s+(.+)$", markdown, re.MULTILINE):
        level = len(match.group(1)) - 1
        headings.append((level, match.group(2).strip()))
    if not headings:
        return ""
    lines = ["```mermaid", "mindmap", f"  root(({root_title}))"]
    for level, title in headings:
        lines.append(f"{'    ' + '  ' * (level - 1)}{title}")
    lines.append("```")
    return "\n".join(lines) + "\n"
