import chromadb, os
from chromadb.utils import embedding_functions

_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    model_name="text-embedding-3-small",
)

def build_index(slices: list[dict], collection_name: str, persist_dir: str = "./chromadb"):
    client = chromadb.PersistentClient(path=persist_dir)
    try:
        client.delete_collection(collection_name)
    except:
        pass
    collection = client.create_collection(name=collection_name, embedding_function=_ef)
    if not slices:
        return collection
    collection.add(
        ids=[f"s_{i}" for i in range(len(slices))],
        documents=[s["content"] for s in slices],
        metadatas=[s["metadata"] for s in slices],
    )
    return collection
