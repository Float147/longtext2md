from src.utils.text_utils import clean_noise

def test_clean_collapses_blank_lines():
    result = clean_noise('line1\n\n\n\nline2')
    assert result.count('\n\n') == 1

def test_clean_preserves_english():
    result = clean_noise('We will learn about Spring Boot autoconfiguration')
    assert 'Spring Boot' in result

def test_clean_handles_empty():
    assert clean_noise('') == ''
