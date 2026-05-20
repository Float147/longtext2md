
"""
知识库管理器 —— 命名知识库的创建、复用、删除、清理。

每个知识库是一个 ChromaDB 持久化索引，存储在 kb/{name}/ 目录下。
退出应用时自动清理所有知识库。
"""
import os, shutil, json, atexit
from datetime import datetime
from pathlib import Path
from src.utils.logger import get_pipeline_logger

_log = get_pipeline_logger()
KB_ROOT = "kb"
_CLEANUP_REGISTERED = False

# ---- 代码/课件扩展名 ----
_CODE_EXTS = {
    ".py", ".java", ".js", ".ts", ".go", ".rs", ".kt", ".swift",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".xml", ".yaml",
    ".yml", ".properties", ".json", ".sql", ".gradle",
}


def _ensure_cleanup():
    """注册退出清理（仅一次）。"""
    global _CLEANUP_REGISTERED
    if not _CLEANUP_REGISTERED:
        atexit.register(cleanup_all)
        _CLEANUP_REGISTERED = True


def create_kb(name: str, code_dir: str | None = None, courseware_dir: str | None = None) -> dict:
    """
    创建命名知识库。
    从代码/课件目录解析文件，构建 ChromaDB 向量索引。
    返回知识库元数据。
    """
    _ensure_cleanup()
    kb_dir = os.path.join(KB_ROOT, name)
    if os.path.exists(kb_dir):
        raise ValueError(f"知识库 [{name}] 已存在，请先删除或使用其他名称")

    os.makedirs(kb_dir, exist_ok=True)

    # 解析代码和课件为切片
    slices = []
    if code_dir and os.path.isdir(code_dir):
        from src.rag.parsers.code_parser import parse_code_file
        for root, _, fns in os.walk(code_dir):
            for fn in fns:
                ext = os.path.splitext(fn)[1].lower()
                if ext in _CODE_EXTS:
                    try:
                        slices.extend(parse_code_file(os.path.join(root, fn)))
                    except Exception as e:
                        _log.warning("解析代码文件失败: %s (%s)", fn, str(e))

    if courseware_dir and os.path.isdir(courseware_dir):
        from src.rag.parsers.markdown_parser import parse_markdown_file
        from src.rag.parsers.docx_parser import parse_docx_file
        for root, _, fns in os.walk(courseware_dir):
            for fn in fns:
                filepath = os.path.join(root, fn)
                ext = os.path.splitext(fn)[1].lower()
                try:
                    if ext in (".md", ".txt"):
                        slices.extend(parse_markdown_file(filepath))
                    elif ext == ".docx":
                        slices.extend(parse_docx_file(filepath))
                except Exception as e:
                    _log.warning("解析课件文件失败: %s (%s)", fn, str(e))

    if not slices:
        shutil.rmtree(kb_dir)
        raise ValueError(f"知识库 [{name}] 没有解析到任何有效文件")

    # 构建 ChromaDB 索引
    from src.rag.indexer import build_index
    persist_dir = os.path.join(kb_dir, "chromadb")
    try:
        collection = build_index(slices, name, persist_dir)
    except ValueError as e:
        raise ValueError(f"Knowledge base [{name}] build failed: {e}. Check OPENAI_API_KEY.") from e

    meta = {
        "name": name,
        "code_dir": code_dir,
        "courseware_dir": courseware_dir,
        "slice_count": len(slices),
        "created_at": datetime.now().isoformat(),
    }
    with open(os.path.join(kb_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    _log.info("知识库 [%s] 创建完成，%d 个切片", name, len(slices))
    return meta


def list_kbs() -> list[dict]:
    """列出所有知识库。"""
    Path(KB_ROOT).mkdir(exist_ok=True)
    kbs = []
    for name in os.listdir(KB_ROOT):
        meta_path = os.path.join(KB_ROOT, name, "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            # Check if ChromaDB collection exists
            chroma_dir = os.path.join(KB_ROOT, name, "chromadb")
            meta["valid"] = os.path.isdir(chroma_dir)
            kbs.append(meta)
    return sorted(kbs, key=lambda k: k.get("created_at", ""), reverse=True)


def get_kb_collection(name: str):
    """获取知识库的 ChromaDB collection（用于 RAG 检索）。"""
    import chromadb
    persist_dir = os.path.join(KB_ROOT, name, "chromadb")
    if not os.path.isdir(persist_dir):
        return None
    client = chromadb.PersistentClient(path=persist_dir)
    try:
        return client.get_collection(name)
    except Exception:
        return None


def delete_kb(name: str):
    """删除指定知识库。"""
    kb_dir = os.path.join(KB_ROOT, name)
    if os.path.isdir(kb_dir):
        shutil.rmtree(kb_dir)
        _log.info("知识库 [%s] 已删除", name)


def cleanup_all():
    """删除所有知识库（退出时自动调用）。"""
    if os.path.isdir(KB_ROOT):
        shutil.rmtree(KB_ROOT)
        _log.info("所有知识库已清理")
