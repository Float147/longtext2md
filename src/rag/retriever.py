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


def retrieve_code_slices(
    collection,
    query: str,
    top_k: int = 15,
    use_reranker: bool = True,
) -> list[tuple[dict, str]]:
    """
    检索全量代码切片（不压缩），供阶段 2b 代码注入使用。

    返回：[(metadata, 完整代码文本), ...]
    与 retrieve_relevant 的区别：
    - 不做指纹压缩
    - 返回完整代码内容而非摘要
    - 只返回 code 类型切片（过滤课件）
    """
    if collection is None or collection.count() == 0:
        return []

    fetch_k = min(top_k * 3, collection.count())
    results = collection.query(query_texts=[query], n_results=fetch_k)

    docs = results["documents"][0]
    metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)

    # 过滤：只保留 code 类型
    code_pairs = []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        if meta.get("type") == "code":
            code_pairs.append((meta, doc))

    if not code_pairs:
        return []

    # 精排
    if use_reranker and len(code_pairs) > top_k:
        try:
            from src.rag.reranker import rerank_sync
            code_docs = [doc for _, doc in code_pairs]
            reranked = rerank_sync(query, code_docs, top_k=top_k)
            result = []
            for r in reranked:
                idx = r["index"]
                if idx < len(code_pairs):
                    result.append(code_pairs[idx])
            return result
        except Exception:
            pass

    return code_pairs[:top_k]