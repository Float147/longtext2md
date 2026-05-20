"""
SiliconFlow Reranker — 对向量检索结果重排序，提升召回精度。

流程：粗排 (ChromaDB top_k=10) → 精排 (reranker) → 取前 k 条
"""
import httpx
from src.utils.config import config


async def rerank(
    query: str,
    documents: list[str],
    top_k: int = 3,
) -> list[dict]:
    """
    调用 SiliconFlow reranker API 重排序。

    参数:
        query: 查询文本
        documents: 候选文档列表
        top_k: 返回前 k 条

    返回:
        [{"index": int, "text": str, "score": float}, ...]
    """
    if not documents or not config.siliconflow_api_key:
        return [{"index": i, "text": doc, "score": 1.0} for i, doc in enumerate(documents[:top_k])]

    url = f"{config.siliconflow_base_url}/rerank"
    headers = {
        "Authorization": f"Bearer {config.siliconflow_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.reranker_model,
        "query": query,
        "documents": documents,
        "top_n": min(top_k, len(documents)),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("results", []):
        idx = item["index"]
        if idx < len(documents):
            results.append({
                "index": idx,
                "text": documents[idx],
                "score": item.get("relevance_score", 0.0),
            })
    return results


def rerank_sync(
    query: str,
    documents: list[str],
    top_k: int = 3,
) -> list[dict]:
    """同步版 rerank，内部用 asyncio.run 包装。"""
    import asyncio
    return asyncio.run(rerank(query, documents, top_k))
