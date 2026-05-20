import re

def extract_terms_from_code(code: str, file_ext: str = "") -> list[str]:
    terms = set()
    terms.update(re.findall(r"(?:class|interface|enum)\s+(\w+)", code))
    terms.update(re.findall(r"(?:public|private|protected)\s+\w+\s+(\w+)\s*\(", code))
    terms.update(re.findall(r"@(\w+)", code))
    terms.update(re.findall(r"class\s+(\w+)", code))
    terms.update(re.findall(r"def\s+(\w+)", code))
    return sorted(terms)

def extract_terms_from_markdown(md: str) -> list[str]:
    terms = set()
    for match in re.finditer(r"```\w*
(.*?)```", md, re.DOTALL):
        terms.update(extract_terms_from_code(match.group(1)))
    terms.update(re.findall(r"`([A-Z]\w+(?:\.\w+)*)`", md))
    return sorted(terms)
