"""
中文逐字稿噪音清洗 —— 纯正则，零 LLM 成本。

保守策略：只去掉确信无疑的噪音，边缘情况留给阶段 1 的 LLM 处理。
按 AGENTS.md 0.0 估算可节省 5%-10% 的 token。
"""
import re

# ============================================================
# 填充词列表（直接字符串替换，中文不需要 \b）
# ============================================================

FILLER_WORDS = [
    "就是说", "就是说呢", "然后呢", "对吧", "是不是",
    "那个", "这个嘛", "怎么说呢", "怎么说",
    "就是说呀", "对吧对吧", "的话呢", "那啥",
    "讲白了", "说白了", "说白了就是", "基本上的话",
]

# 独立叹词（行首 / 行尾匹配）
INTERJECTION_LEADING = [
    r"^(?:啊|哦|呃|嗯|诶|咦|嗨|喂|噢|哎|呀|哇|哼|哈)[，,！\s]*",
]

INTERJECTION_TRAILING = [
    r"[，,，\s]*(?:啊|哦|呃|嗯|诶|咦|嗨|噢|哎|呀|哇|哼|哈)[！!。.]?$",
]


# ---- 公开 API ----

def clean_noise(text: str) -> str:
    """
    保守的正则噪音清洗。

    处理内容：
    1. 去除口语填充词
    2. 去除行首行尾独立叹词
    3. 折叠连续重复字符
    4. 标准化多余空行
    5. 去除每行首尾空白
    """
    if not text:
        return ""

    # 1. 直接字符串替换去除填充词（中文无 word boundary，不用 \b）
    for filler in FILLER_WORDS:
        text = text.replace(filler, "")

    # 2. 去除行首独立叹词
    for pattern in INTERJECTION_LEADING:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)

    # 3. 去除行尾独立叹词
    for pattern in INTERJECTION_TRAILING:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)

    # 4. 折叠连续重复字符
    #    单个汉字重复 4 次以上 -> 保留 1 个
    text = re.sub(r"([\u4e00-\u9fff])\1{3,}", r"\1", text)
    #    双字模式重复 3 次以上 -> 保留 1 组
    text = re.sub(r"([\u4e00-\u9fff]{2})\1{2,}", r"\1", text)

    # 5. 标准化多余空行：3 个以上换行 -> 2 个
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 6. 去除每行首尾空白，保留段落结构
    lines = text.split("\n")
    lines = [l.strip() for l in lines]
    text = "\n".join(lines)

    return text.strip()