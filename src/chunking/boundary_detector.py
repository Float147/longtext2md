"""
中文网课逐字稿话题边界检测。

多信号融合 + 递归切割，按 AGENTS.md 0.4 设计：
1. 按段落分割，对每个边界进行多信号加权打分
2. 在得分最高的语义边界处递归切割
3. 无信号时回退到段落中点强切
4. 单段落时在句子边界（。！？；，）附近智能切分
"""
import re
from typing import List

# ============================================================
# 信号模式（按权重降序排列）
# ============================================================

# 最高权重：章节标记词
SECTION_MARKERS = [
    r"(?:接下来|下面|现在|然后)(?:我们|来|我)(?:讲|看|说|介绍|聊|进入|开始)",
    r"(?:最后一个|下一个|这个)(?:部分|环节|模块|章节|知识点)",
    r"第[一二两三四五六七八九十\d]+(?:章|节|部分|课|讲|步)",
    r"(?:总结|回顾|复习|小结)(?:一下|来看|一下刚才)",
    r"(?:我们|先)(?:继续|回到|返回)",
    r"(?:以上|前面|刚才)(?:就是|我们讲了)",
    r"(?:那|那么)(?:我们|咱们)(?:接着|继续|再)",
    r"(?:好|好了|OK)[，,]\s*(?:那|那么)(?:我们|咱们)",
    r"(?:今天|这节课)(?:我们|来|主要)(?:讲|学习|看)",
]

# 高权重：讲解到代码的切换
CODE_SWITCH = [
    r"(?:我们|咱们|来|我)(?:写|创建|新建|建|定义)(?:一下|一个|个)",
    r"(?:来看|看|打开|运行)(?:一下|看|下)(?:代码|这个|这段)",
    r"(?:运行|执行|启动|测试)(?:一下|看|一次|结果)",
    r"(?:创建|新建)(?:一个|个)(?:类|接口|枚举|文件|项目|配置)",
    r"(?:添加|加上|配置|修改|实现)(?:一下|一个|个)",
    r"(?:写|敲)(?:完|好)(?:了|之后)",
    r"(?:代码|演示)(?:如下|在这里|长这样)",
    r"(?:把|把这段)(?:代码|注释)(?:加上|去掉)",
]

# 中权重：列举结构
ENUMERATION = [
    r"首先.*?(?:其次|然后|接着).*?(?:最后|第三)",
    r"第[一二三123]步.*?第[二三123]步",
    r"第[一二三123][，,].*?第[二三123][，,]",
    r"一是.*?二是.*?(?:三是)?",
    r"(?:先|首先)[，,].*?(?:然后|再)[，,].*?(?:最后|接着)",
    r"(?:有|分成?|分为)(?:以下|这样)?(?:几个|三个|两种|几种|三点)",
    r"(?:主要|核心|关键)(?:有|包括|是)(?:以下|这么)?(?:几个|几点|几方面)",
]

# ---- 单段文本智能切分的边界字符 ----
_SENTENCE_BOUNDARY = "。！？"
_CLAUSE_BOUNDARY = "；，"


# ---- 公开 API ----

def detect_boundaries(text: str, max_chars: int = 2000) -> List[str]:
    """
    递归多层级话题边界检测。

    策略：
    1. 按段落分割文本，对每个边界进行多信号融合打分
    2. 在得分最高的语义边界处递归切割
    3. 无有效信号时回退到段落中点强切
    4. 单个超大段落无换行时，在句子边界附近智能切分
    """
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    paragraphs = text.split("\n")
    scores = _score_boundaries(paragraphs)
    return _recursive_split(paragraphs, scores, max_chars)


def _score_boundaries(paragraphs: List[str]) -> List[int]:
    """对每个段落边界进行多信号加权打分。"""
    scores = [0] * len(paragraphs)

    for i in range(1, len(paragraphs)):
        prev_tail = paragraphs[i - 1][-120:] if i > 0 else ""
        curr_head = paragraphs[i][:120]
        ctx = prev_tail + "\n" + curr_head
        score = 0

        for pattern in SECTION_MARKERS:
            if re.search(pattern, ctx):
                score += 5
                break

        for pattern in CODE_SWITCH:
            if re.search(pattern, ctx):
                score += 3
                break

        for pattern in ENUMERATION:
            if re.search(pattern, ctx):
                score += 2
                break

        if paragraphs[i].strip() == "" and i > 0 and paragraphs[i - 1].strip() != "":
            score += 1

        scores[i] = score

    return scores


def _split_single_paragraph(text: str, max_chars: int) -> List[str]:
    """对无段落结构的单段文本，在句子/分句边界处智能切分。
    
    优先在 。！？ 处切，其次在 ；， 处切。
    在切割点前后各 max_chars//4 范围内搜索最近边界。
    若整个范围无任何边界，认栽在 max_chars 字节处硬切。
    """
    chunks = []
    pos = 0
    n = len(text)
    while pos < n:
        if n - pos <= max_chars:
            chunks.append(text[pos:])
            break

        target = pos + max_chars
        lookback = max_chars // 4
        best = target

        # 向后搜索最近边界
        for j in range(target, max(target - lookback, pos), -1):
            ch = text[j - 1] if j > 0 else ""
            if ch in _SENTENCE_BOUNDARY:
                best = j
                break
            if ch in _CLAUSE_BOUNDARY and best == target:
                best = j

        # 回退没找到，向前搜索
        if best == target:
            for j in range(target, min(target + lookback, n)):
                ch = text[j - 1] if j > 0 else ""
                if ch in _SENTENCE_BOUNDARY:
                    best = j
                    break
                if ch in _CLAUSE_BOUNDARY and best == target:
                    best = j

        chunks.append(text[pos:best])
        pos = best

    return chunks


def _recursive_split(
    paragraphs: List[str],
    scores: List[int],
    max_chars: int,
    depth: int = 0,
) -> List[str]:
    """在得分最高的边界处递归切割。"""
    text = "\n".join(paragraphs)

    if len(text) <= max_chars or depth > 20:
        return [text] if text.strip() else []

    if len(paragraphs) <= 1:
        return _split_single_paragraph(text, max_chars)

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
        best_idx = n // 2

    best_idx = max(1, min(n - 1, best_idx))

    return _recursive_split(
        paragraphs[:best_idx], scores[:best_idx], max_chars, depth + 1
    ) + _recursive_split(
        paragraphs[best_idx:], scores[best_idx:], max_chars, depth + 1
    )
