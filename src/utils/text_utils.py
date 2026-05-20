import re

FILLER_PATTERNS = [
    (re.compile(r'\b(那个|就是说|然后呢|对吧|是不是|这个嘛)\b'), ''),
    (re.compile(r'(嗯|啊|哦|呃){3,}'), ''),
]

def clean_noise(text: str) -> str:
    for pattern, replacement in FILLER_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
