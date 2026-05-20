from src.utils.mindmap import generate_mindmap

def test_generate_mindmap():
    md = "# Course\n## Ch1\n### Topic A\n## Ch2"
    mm = generate_mindmap(md, "Test Course")
    assert "mindmap" in mm
    assert "Ch1" in mm
    assert "Ch2" in mm
