from src.chunking.boundary_detector import detect_boundaries

def test_detect_section_markers():
    text = "first chapter content. let's look at the next topic. more details here."
    chunks = detect_boundaries(text, max_chars=2000)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert len(chunk) <= 2000

def test_respects_max_chars():
    text = "A" * 5000
    chunks = detect_boundaries(text, max_chars=1000)
    for chunk in chunks:
        assert len(chunk) <= 1000
    assert len(chunks) >= 5
