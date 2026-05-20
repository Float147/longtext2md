"""
高频可疑词扫描器。

按 AGENTS.md 0.2 兜底方案：没有课件/代码时，
纯程序化扫描逐字稿中的高频疑似乱码片段（如 "斯普瑞布特" 出现 47 次），
将这些高频疑似词单独列给纠错 LLM 推断正确术语。
"""
import re
from collections import Counter
from typing import List, Tuple

# 判断一个片段是疑似乱码技术术语的规则：
# - 2-12 个连续中文字符，出现 >= 3 次
# - 中文 + 英文字母混合片段

_MIN_FREQ = 3        # 最小出现次数
_MIN_LEN = 2          # 最小片段长度
_MAX_LEN = 12         # 最大片段长度（再长多半是真句子）


def scan_suspicious_terms(text: str, top_k: int = 30) -> List[Tuple[str, int]]:
    """
    扫描逐字稿中的高频率可疑术语片段。

    返回：(词条, 出现次数) 列表，按频率降序排列。
    这些极可能是被语音识别错误转录的技术术语。
    """
    # 提取连续中文 N-gram
    chinese_runs = re.findall(r"[\u4e00-\u9fff]{%d,%d}" % (_MIN_LEN, _MAX_LEN), text)
    counter = Counter(chinese_runs)

    # 过滤常见日常短语
    common_phrases = _get_common_phrases()

    suspicious = []
    for term, count in counter.most_common(top_k * 3):
        if count < _MIN_FREQ:
            break
        if term in common_phrases:
            continue
        if len(term) < 3 and count < 5:
            # 短词需要更高频率才算可疑
            continue
        suspicious.append((term, count))

    # 也扫描中英混合片段
    mixed_patterns = re.findall(
        r"[\u4e00-\u9fff]{2,}[a-zA-Z][\u4e00-\u9fff]{0,4}", text
    ) + re.findall(
        r"[a-zA-Z]{2,}[\u4e00-\u9fff]{2,}", text
    )
    mixed_counter = Counter(mixed_patterns)
    for term, count in mixed_counter.most_common(10):
        if count >= _MIN_FREQ:
            suspicious.append((term, count))

    # 去重并按频率排序
    seen = set()
    result = []
    for term, count in sorted(suspicious, key=lambda x: -x[1]):
        if term not in seen:
            seen.add(term)
            result.append((term, count))

    return result[:top_k]


def format_suspicious_hints(terms: List[Tuple[str, int]]) -> str:
    """
    将可疑词列表格式化为纠错 LLM 的提示信息。
    """
    if not terms:
        return ""

    lines = [
        "以下词汇在文中高频出现，极可能是被语音识别错误转录的技术术语。",
        "请推断每个词对应的正确技术术语：",
        "",
    ]
    for term, count in terms:
        lines.append(f"  - '{term}'（出现 {count} 次）")

    return "\n".join(lines)


def _get_common_phrases() -> set:
    """常见中文短语白名单 —— 这些不是可疑技术术语。"""
    return {
        # 基础虚词
        "我们", "他们", "你们", "自己", "大家",
        "这个", "那个", "哪个", "什么", "怎么",
        "可以", "能够", "应该", "需要", "必须",
        "一个", "一些", "这个", "这样", "那样",
        "因为", "所以", "但是", "虽然", "如果",
        "然后", "接着", "最后", "首先", "其次",
        "现在", "已经", "正在", "将要", "刚才",
        "知道", "觉得", "认为", "看到", "听到",
        "没有", "不是", "不会", "不能", "不要",
        # 常见课堂用语
        "接下来", "看一下", "我们看", "比如说",
        "对不对", "是不是", "有没有", "就是说",
        "实际上", "基本上", "一般来说",
        "代码", "运行", "配置", "方法", "类",
        "文件", "项目", "接口", "数据", "服务",
        # 时间表达
        "今天", "昨天", "明天", "上次", "下次",
        "之前", "之后", "以前", "以后",
    }