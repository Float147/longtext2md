"""
Token 计数器 —— tiktoken 封装。
"""
import tiktoken

_enc = None

def _get_encoder():
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc

def count_tokens(text: str) -> int:
    """计算文本的 token 数量。"""
    if not text:
        return 0
    return len(_get_encoder().encode(text))
