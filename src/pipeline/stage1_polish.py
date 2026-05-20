"""
阶段 1：全并行上下文润色。

每块 LLM 拿到四层上下文（全局摘要 + 位置标签 + 前文结尾 + 后文开头），
所有块通过 asyncio.gather 并行调用，总耗时 = 最慢那块的时间。
提示词从 prompts/polish_chunk_*.md 加载。
"""
import asyncio
from pathlib import Path
from src.llm.client import chat
from src.utils.config import config

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    """从 prompts/ 目录加载提示词文件。"""
    with open(_PROMPT_DIR / filename, "r", encoding="utf-8") as f:
        return f.read()


async def polish_chunks(
    chunks: list[str],
    summary: dict,
    rag_fingerprints_map: dict[int, str] | None = None,
    max_concurrency: int = 30,
) -> list[str]:
    """
    全并行润色。

    参数：
        chunks: 话题块列表
        summary: 全局摘要 dict
        rag_fingerprints_map: 块索引 -> RAG 代码指纹的映射
        max_concurrency: 最大并发数
    """
    system_prompt = _load_prompt("polish_chunk_system.md")
    user_template = _load_prompt("polish_chunk_user.md")
    total = len(chunks)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def polish_one(idx: int, chunk: str) -> str:
        prev_end = chunks[idx - 1][-80:] if idx > 0 else "（这是第一块）"
        next_start = chunks[idx + 1][:60] if idx < total - 1 else "（这是最后一块）"
        rags = rag_fingerprints_map.get(idx, "") if rag_fingerprints_map else ""
        user_msg = user_template.format(
            course_overview=summary.get("overview", summary.get("course_title", "")),
            chunk_index=idx + 1, total_chunks=total,
            prev_chunk_last_80=prev_end, next_chunk_first_60=next_start,
            rag_fingerprints=rags, current_chunk=chunk,
        )
        async with semaphore:
            return await chat(profile=config.economy, system_prompt=system_prompt, user_message=user_msg)

    tasks = [polish_one(i, c) for i, c in enumerate(chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # 失败时回退到原始文本
    return [chunks[i] if isinstance(r, Exception) else r for i, r in enumerate(results)]