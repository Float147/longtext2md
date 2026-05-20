from src.utils.toc_generator import generate_toc, insert_toc

def test_generate_toc():
    md = "# Title\n## Section 1\n### Sub 1.1\n## Section 2"
    toc = generate_toc(md)
    assert "Section 1" in toc
    assert "Sub 1.1" in toc

def test_insert_toc():
    md = "# Course\n## Chapter 1"
    result = insert_toc(md)
    assert "Table of Contents" in result
