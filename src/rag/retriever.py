"""
RAG 检索器 — 两阶段检索：粗排(ChromaDB) → 精排(SiliconFlow reranker)
检索结果自动经 code_parser.create_code_fingerprint 压缩为指纹，
控制在 80-150 tokens，供阶段 1 润色上下文使用。
"""
from src.rag.parsers.code_parser import create_code_fingerprint


def retrieve_relevant(
    collection,
    query: str,
    k: int = 3,
    use_reranker: bool = True,
) -> str:
    """
    两阶段检索：
    1. ChromaDB 粗排取 k*3 条
    2. (可选) SiliconFlow reranker 精排取 top_k
    代码自动压缩为指纹，课件截取前 100 字。

    返回：压缩后的指纹文本（供阶段 1 润色上下文使用）。
    """
    if collection is None or collection.count() == 0:
        return ""

    # 阶段1: 粗排 — 多取一些候选
    fetch_k = min(k * 3, collection.count())
    results = collection.query(query_texts=[query], n_results=fetch_k)

    docs = results["documents"][0]
    metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)

    # 阶段2: 精排 — reranker
    if use_reranker and len(docs) > k:
        try:
            from src.rag.reranker import rerank_sync
            reranked = rerank_sync(query, docs, top_k=k)
            docs = [r["text"] for r in reranked]
            reranked_metas = []
            for r in reranked:
                idx = r["index"]
                if idx < len(metas):
                    reranked_metas.append(metas[idx])
            metas = reranked_metas
        except Exception:
            pass

    # 阶段3: 压缩为指纹
    fps = []
    for i, doc in enumerate(docs[:k]):
        meta = metas[i] if i < len(metas) else {}
        fn = meta.get("file", "unknown")
        if meta.get("type") == "code":
            fps.append(create_code_fingerprint(doc, fn))
        else:
            fps.append(f"课件: {meta.get('title', '')}\n{doc[:100]}")
    return "\n---\n".join(fps)


def retrieve_slices_for_injection(
    collection,
    query: str,
    top_k: int = 10,
    use_reranker: bool = True,
) -> list[tuple[dict, str]]:
    """
    检索全量切片（不压缩、不过滤类型），供阶段 2b 注入使用。

    返回：[(metadata, 完整文本), ...]
    LLM 根据 metadata.type 决定插入方式：
    - type=="code"       → 插入为代码块 (```java ... ```)
    - type=="courseware" → 插入为引用块 (> ...) 或补充说明
    """
    if collection is None or collection.count() == 0:
        return []

    fetch_k = min(top_k * 3, collection.count())
    results = collection.query(query_texts=[query], n_results=fetch_k)

    docs = results["documents"][0]
    metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)

    # 不过滤类型 —— 代码 + 课件全部返回
    all_pairs = []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        all_pairs.append((meta, doc))

    if not all_pairs:
        return []

    # 精排
    if use_reranker and len(all_pairs) > top_k:
        try:
            from src.rag.reranker import rerank_sync
            all_docs = [doc for _, doc in all_pairs]
            reranked = rerank_sync(query, all_docs, top_k=top_k)
            result = []
            for r in reranked:
                idx = r["index"]
                if idx < len(all_pairs):
                    result.append(all_pairs[idx])
            return result
        except Exception:
            pass

    return all_pairs[:top_k]


def retrieve_code_slices(collection, query, top_k=15, use_reranker=True):
    """[兼容旧接口] 仅返回 code 类型切片。"""
    all_slices = retrieve_slices_for_injection(collection, query, top_k, use_reranker)
    return [(m, c) for m, c in all_slices if m.get("type") == "code"]