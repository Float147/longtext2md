import asyncio
from pathlib import Path
from src.llm.client import chat
from src.utils.config import config

POLISH_SYSTEM = "You are a Chinese course note polisher. Remove filler words, organize into clear paragraphs. No headings, no code blocks. Do not omit any knowledge. Output polished text directly."

def _load_template() -> str:
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "polish_chunk.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

async def polish_chunks(chunks: list[str], summary: dict, rag_fingerprints_map: dict[int, str] | None = None, max_concurrency: int = 30) -> list[str]:
    template = _load_template()
    total = len(chunks)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def polish_one(idx: int, chunk: str) -> str:
        prev_end = chunks[idx - 1][-80:] if idx > 0 else "(This is the first chunk)"
        next_start = chunks[idx + 1][:60] if idx < total - 1 else "(This is the last chunk)"
        rags = rag_fingerprints_map.get(idx, "") if rag_fingerprints_map else ""
        user_msg = template.format(
            course_overview=summary.get("overview", summary.get("course_title", "")),
            chunk_index=idx + 1, total_chunks=total,
            prev_chunk_last_80=prev_end, next_chunk_first_60=next_start,
            rag_fingerprints=rags, current_chunk=chunk,
        )
        async with semaphore:
            return await chat(model=config.polish_model, system_prompt=POLISH_SYSTEM, user_message=user_msg, temperature=0.3)

    tasks = [polish_one(i, c) for i, c in enumerate(chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [chunks[i] if isinstance(r, Exception) else r for i, r in enumerate(results)]
