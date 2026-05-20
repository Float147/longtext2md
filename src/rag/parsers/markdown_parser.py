import re

def parse_markdown_file(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    slices = []
    for section in re.split(r"
(?=#{1,4}\s)", content):
        section = section.strip()
        if not section:
            continue
        title_match = re.match(r"#{1,4}\s+(.+)", section)
        slices.append({"file": filepath, "type": "courseware", "content": section, "metadata": {"title": title_match.group(1) if title_match else filepath}})
    return slices
