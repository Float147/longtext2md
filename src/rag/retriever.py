from src.rag.parsers.code_parser import create_code_fingerprint

def retrieve_relevant(collection, query: str, k: int = 3) -> str:
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
            fps.append(f"Courseware: {meta.get('title', '')}
{doc[:100]}")
    return "
---
".join(fps)
