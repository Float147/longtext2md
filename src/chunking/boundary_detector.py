import re

SECTION_MARKERS = [r"next we talk about", r"let's look at", r"the last part", r"we continue", r"chapter \d+", r"to summarize", r"let's review"]
CODE_SWITCH = [r"let's write", r"look at the code", r"let's run", r"create a new", r"create a class"]
ENUMERATION = [r"first.*second.*finally", r"step 1.*step 2", r"first.*then.*finally"]

def detect_boundaries(text: str, max_chars: int = 2000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = text.split("\n")
    scores = []
    for i, para in enumerate(paragraphs):
        score = 0
        ctx = "\n".join(paragraphs[max(0,i-1):min(len(paragraphs),i+2)])
        for m in SECTION_MARKERS:
            if re.search(m, ctx, re.IGNORECASE):
                score += 5
        for m in CODE_SWITCH:
            if re.search(m, ctx, re.IGNORECASE):
                score += 3
        for m in ENUMERATION:
            if re.search(m, ctx, re.IGNORECASE):
                score += 2
        if para.strip() == "":
            score += 1
        scores.append(score)
    return _split(paragraphs, scores, max_chars)

def _split(paragraphs, scores, max_chars, depth=0):
    text = "\n".join(paragraphs)
    if len(text) <= max_chars or depth > 20:
        return [text] if text.strip() else []
    if len(paragraphs) <= 1:
        # Force character-level split
        return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
    n = len(paragraphs)
    lo, hi = max(1, int(n * 0.2)), min(n - 1, int(n * 0.8))
    if lo >= hi:
        lo = hi = n // 2
    best_idx = lo
    best_score = -1
    for i in range(lo, hi + 1):
        if scores[i] > best_score:
            best_score = scores[i]
            best_idx = i
    if best_score <= 1:
        # Force split at midpoint
        best_idx = n // 2
    if best_idx <= 0:
        best_idx = 1
    if best_idx >= n:
        best_idx = n - 1
    return _split(paragraphs[:best_idx], scores[:best_idx], max_chars, depth+1) + \
           _split(paragraphs[best_idx:], scores[best_idx:], max_chars, depth+1)
