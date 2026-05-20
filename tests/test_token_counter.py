from src.utils.token_counter import count_tokens

def test_count_tokens_english():
    assert 0 < count_tokens('Hello, world!') < 10

def test_count_tokens_chinese():
    assert count_tokens('hello world') > 0

def test_count_tokens_empty():
    assert count_tokens('') == 0
