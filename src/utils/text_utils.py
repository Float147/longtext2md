"""
中文逐字稿噪音清洗 —— 纯正则，零 LLM 成本。
保守策略：只去掉确信无疑的噪音，边缘情况留给阶段 1 的 LLM 处理。
按 AGENTS.md 0.0 预估可节省 5%-10% 的 token。
"""
import os
import re

# ---- 项目根路径 ----
_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_filler_words_path = os.path.join(_project_root, "filler_words.txt")


def _load_filler_words(path: str) -> list[str]:
    """从本地文本文件按行加载屏蔽词 / 填充词。"""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip().lstrip("\ufeff") for line in f]
        return [ln for ln in lines if ln and not ln.startswith("#")]


_FILLER_WORDS_CACHE: list[str] | None = None


def _get_filler_words() -> list[str]:
    """惰性加载 + 缓存填充词列表。"""
    global _FILLER_WORDS_CACHE
    if _FILLER_WORDS_CACHE is None:
        _FILLER_WORDS_CACHE = _load_filler_words(_filler_words_path)
    return _FILLER_WORDS_CACHE


# ============================================================
# 独立叹词（行首 / 行尾匹配）
# ============================================================

INTERJECTION_LEADING = [
    r"^(?:啊|哦|呃|嗯|诶|哎|唔|嘻|嘻|嚯|呵|哟|唉|呀)[！!，,\s]*",
]

INTERJECTION_TRAILING = [
    r"[，,\s]*(?:啊|哦|呃|嗯|诶|哎|唔|嘻|嚯|呵|哟|唉|呀)[！!。.]?$",
]


# ---- 公开 API ----

def clean_noise(text: str) -> str:
    """
    保守的正则噪音清洗。
    处理内容：
    1. 去除口语填充词（从 filler_words.txt 加载）
    2. 去除行首行尾独立叹词
    3. 折叠连续重复字符
    4. 标准化多余空行
    5. 去除每行首尾空白
    """
    if not text:
        return ""

    # 1. 直接字符串替换去除填充词
    for filler in _get_filler_words():
        text = text.replace(filler, "")

    # 2. 去除行首独立叹词
    for pattern in INTERJECTION_LEADING:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)

    # 3. 去除行尾独立叹词
    for pattern in INTERJECTION_TRAILING:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)

    # 4. 折叠连续重复字符
    text = re.sub(r"([\u4e00-\u9fff])\1{3,}", r"\1", text)
    text = re.sub(r"([\u4e00-\u9fff]{2})\1{2,}", r"\1", text)

    # 5. 标准化多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 6. 去除每行首尾空白，保留段落结构
    lines = text.split("\n")
    lines = [l.strip() for l in lines]
    text = "\n".join(lines)

    return text.strip()