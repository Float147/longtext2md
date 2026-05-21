"""
阶段 0：预处理 —— 噪音清洗 + LLM 全文纠错 + 全局摘要。

所有提示词从 prompts/ 目录加载，所有模型参数从 config 读取。
"""
import asyncio
import json
from pathlib import Path
from src.llm.client import chat
from src.utils.config import config
from src.utils.text_utils import clean_noise
from src.utils.prompt_loader import load_prompt
from src.utils.suspicious_scanner import scan_suspicious_terms, format_suspicious_hints

# 纠错分块大小（字符数，含相邻块 200 字重叠）
_ERROR_CHUNK_SIZE = 8000
_ERROR_OVERLAP = 200


def clean_noise_stage(text: str) -> str:
    """0.0 噪音清洗阶段。纯正则，零 LLM 成本。"""
    return clean_noise(text)


def _build_reference_info(glossary: list[str] | None, text: str) -> str:
    """构造纠错 LLM 的参考信息：术语词典优先，无词典时用可疑词扫描兜底。"""
    if glossary:
        return "已从代码/课件中提取的正确术语（供参考，判断哪些是错误音译）：" + ", ".join(glossary)
    suspicious = scan_suspicious_terms(text)
    if suspicious:
        return format_suspicious_hints(suspicious)
    return "（无参考术语，请依据编程上下文自行判断哪些是语音识别错误的技术术语）"


def _split_for_correction(text: str) -> list[str]:
    """将文本按 ~8000 字切块，相邻块重叠 200 字防止边界漏词。"""
    if len(text) <= _ERROR_CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + _ERROR_CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        start = end - _ERROR_OVERLAP if end < len(text) else end
    return chunks


async def _correct_chunk(
    chunk: str, reference_info: str, system_prompt: str
) -> str:
    """对单个文本块执行 LLM 纠错。"""
    user_msg = f"## 参考信息\n{reference_info}\n\n## 需要纠错的文本\n{chunk}"
    result = await chat(profile=config.economy, system_prompt=system_prompt, user_message=user_msg)
    return result.strip()


def _merge_corrected(original: str, corrected_chunks: list[str]) -> str:
    """合并纠错后的文本块。利用 original 的重叠区域去重衔接。"""
    if len(corrected_chunks) == 1:
        return corrected_chunks[0]

    result = corrected_chunks[0]
    for i in range(1, len(corrected_chunks)):
        # 找到重叠部分在前后块中的位置，做去重拼接
        # 简单策略：取前一块末尾 _ERROR_OVERLAP 字与后一块开头匹配
        prev_tail = corrected_chunks[i - 1][-_ERROR_OVERLAP:] if len(corrected_chunks[i - 1]) >= _ERROR_OVERLAP else corrected_chunks[i - 1]
        curr_head = corrected_chunks[i][:_ERROR_OVERLAP] if len(corrected_chunks[i]) >= _ERROR_OVERLAP else corrected_chunks[i]
        # 找最长公共子串来做去重
        overlap_len = 0
        for j in range(min(len(prev_tail), len(curr_head)), 0, -1):
            if prev_tail[-j:] == curr_head[:j]:
                overlap_len = j
                break
        result += corrected_chunks[i][overlap_len:]
    return result


async def correct_errors_stage(text: str, glossary: list[str] | None = None) -> str:
    """
    0.2 全文错别字纠正 —— LLM 方案。

    使用经济档模型（DeepSeek-V4-Flash）按 ~8000 字分块纠错。
    每块输入含术语词典或可疑词扫描结果作为参考。
    提示词通过反例严格约束：只替换技术术语，不改结构、不去口语。
    相邻块重叠 200 字防止边界漏词。
    """
    system_prompt = load_prompt("correct_errors_system.md")
    reference_info = _build_reference_info(glossary, text)
    chunks = _split_for_correction(text)

    # 串行执行：纠错任务不需要并行（块数少，且 Flash 响应快）
    corrected = []
    for i, chunk in enumerate(chunks):
        result = await _correct_chunk(chunk, reference_info, system_prompt)
        corrected.append(result)

    return _merge_corrected(text, corrected)


def correct_errors_stage_sync(text: str, glossary: list[str] | None = None) -> str:
    """同步版纠错。"""
    return asyncio.run(correct_errors_stage(text, glossary))


async def generate_summary(text: str) -> dict:
    """
    0.3 课程全局摘要阶段。
    通过均匀采样（头尾各 3000 + 每 10000 采 500）生成课程概要。
    """
    system_prompt = load_prompt("global_summary_system.md")

    if not text or not text.strip():
        return {
            "course_title": "未知",
            "overview": "未提供课程逐字稿文本，无法生成摘要。",
            "tech_stack": [],
            "chapters_summary": [],
        }

    if len(text) <= 8000:
        sample = text
    else:
        sample = text[:3000]
        for i in range(10000, len(text) - 3000, 10000):
            sample += "\n...\n" + text[i:i + 500]
        sample += "\n...\n" + text[-3000:]

    result = await chat(profile=config.economy, system_prompt=system_prompt, user_message=sample)
    result = result.strip()
    if result.startswith("```"):
        lines = result.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        result = "\n".join(lines)
    return json.loads(result)


def generate_summary_sync(text: str) -> dict:
    """同步版摘要生成。"""
    return asyncio.run(generate_summary(text))