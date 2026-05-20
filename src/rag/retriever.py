"""
RAG 检索器 —— 从 ChromaDB 索引中检索相关内容。

检索结果自动经 code_parser.create_code_fingerprint 压缩为指纹，
控制在 80-150 tokens，供阶段 1 润色上下文使用。
"""
from src.rag.parsers.code_parser import create_code_fingerprint


def retrieve_relevant(collection, query: str, k: int = 3) -> str:
    """
    从向量索引中检索与查询最相关的 k 条记录。
    代码自动压缩为指纹，课件截取前 100 字。
    """
    if collection is None or collection.count() == 0:
        return ""
    results = collection.query(query_texts=[query], n_results=k)
    fps = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i] if results.get("metadatas") else {}
        fn = meta.get("file", "unknown")
        if meta.get("type") == "code":
            fps.append(create_code_fingerprint(doc, fn))
        else:
            fps.append(f"课件: {meta.get('title', '')}\n{doc[:100]}")
    return "\n---\n".join(fps)