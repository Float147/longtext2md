"""
阶段 0：预处理 —— 噪音清洗 + 全文纠错 + 全局摘要。

所有提示词从 prompts/ 目录加载，所有模型参数从 config 读取。
"""
import asyncio
import json
from pathlib import Path
from src.llm.client import chat
from src.utils.config import config
from src.utils.text_utils import clean_noise
from src.utils.suspicious_scanner import scan_suspicious_terms, format_suspicious_hints

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    """从 prompts/ 目录加载提示词文件。"""
    with open(_PROMPT_DIR / filename, "r", encoding="utf-8") as f:
        return f.read()


def clean_noise_stage(text: str) -> str:
    """0.0 噪音清洗阶段。纯正则，零 LLM 成本。"""
    return clean_noise(text)


def _build_correction_hints(text: str, glossary: list[str] | None) -> str:
    """构造纠错提示信息：有术语词典用术语词典，没有则用可疑词扫描兜底。"""
    parts = []
    if glossary:
        parts.append("术语词典（已知正确术语）: " + ", ".join(glossary))
    else:
        suspicious = scan_suspicious_terms(text)
        if suspicious:
            parts.append(format_suspicious_hints(suspicious))
    return "\n\n".join(parts) if parts else ""


async def correct_errors_stage(text: str, glossary: list[str] | None = None) -> str:
    """
    0.2 全文错别字纠正阶段。
    将文本切为 ~10000 字的大块，用 asyncio.gather 并行纠正。
    """
    system_prompt = _load_prompt("correct_errors_system.md")
    chunk_size = config.max_chunk_chars * 5
    hints = _build_correction_hints(text, glossary)

    if len(text) <= chunk_size:
        user_msg = hints + "\n\n" + text if hints else text
        return await chat(profile=config.economy, system_prompt=system_prompt, user_message=user_msg)

    # 按段落边界切分，保证上下文完整
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current)
            current = para
        else:
            current = current + "\n\n" + para if current else para
    if current:
        chunks.append(current)

    # 全并行纠正
    async def correct_one(chunk: str) -> str:
        user_msg = hints + "\n\n" + chunk if hints else chunk
        return await chat(profile=config.economy, system_prompt=system_prompt, user_message=user_msg)

    results = await asyncio.gather(*[correct_one(c) for c in chunks], return_exceptions=True)
    # 失败时回退到原始文本
    return "\n".join([chunks[i] if isinstance(r, Exception) else r for i, r in enumerate(results)])


def correct_errors_stage_sync(text: str, glossary: list[str] | None = None) -> str:
    """同步版纠错。"""
    return asyncio.run(correct_errors_stage(text, glossary))


async def generate_summary(text: str) -> dict:
    """
    0.3 课程全局摘要阶段。
    通过均匀采样（头尾各 3000 + 每 10000 采 500）生成课程概要。
    """
    system_prompt = _load_prompt("global_summary_system.md")

    if len(text) <= 8000:
        sample = text
    else:
        sample = text[:3000]
        for i in range(10000, len(text) - 3000, 10000):
            sample += "\n...\n" + text[i:i + 500]
        sample += "\n...\n" + text[-3000:]

    result = await chat(profile=config.economy, system_prompt=system_prompt, user_message=sample)
    result = result.strip()
    # 去掉可能的 markdown 代码围栏
    if result.startswith("```"):
        lines = result.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        result = "\n".join(lines)
    return json.loads(result)


def generate_summary_sync(text: str) -> dict:
    """同步版摘要生成。"""
    return asyncio.run(generate_summary(text))