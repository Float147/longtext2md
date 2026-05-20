"""
向量索引构建 —— ChromaDB 封装。

嵌入模型和 API key 从 config 读取，无硬编码。
"""
import chromadb
from chromadb.utils import embedding_functions
from src.utils.config import config


def build_index(slices: list[dict], collection_name: str, persist_dir: str = "./chromadb"):
    """
    从切片列表构建 ChromaDB 向量索引。

    参数：
        slices: 切片列表，每项含 content 和 metadata
        collection_name: 集合名称
        persist_dir: 持久化目录
    """
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=config.siliconflow_api_key,
        api_base=config.siliconflow_base_url,
        model_name=config.embedding_model,
    )
    client = chromadb.PersistentClient(path=persist_dir)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(name=collection_name, embedding_function=ef)
    if not slices:
        return collection
    collection.add(
        ids=[f"s_{i}" for i in range(len(slices))],
        documents=[s["content"] for s in slices],
        metadatas=[s["metadata"] for s in slices],
    )
    return collection
