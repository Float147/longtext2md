"""
任务管理器 —— 流水线的完整执行入口。

负责：加载逐字稿 -> 构建术语词典 -> 构建 RAG 索引 ->
按阶段顺序执行流水线 -> 后处理（TOC + 思维导图）-> 落盘。
"""
import asyncio, os
from datetime import datetime
from src.task.task_store import get_task, update_task
from src.task.concurrency_limiter import task_slot_limiter
from src.utils.logger import get_task_logger

_log = get_task_logger()


async def run_task(task_id: str, progress_callback=None):
    """执行一个完整任务的全部阶段。"""
    task = get_task(task_id)
    if not task:
        raise ValueError(f"任务 {task_id} 不存在")
    _log.info("任务 %s 开始: %s", task_id, task.get("name", ""))
    update_task(task_id, {"status": "running"})
    await task_slot_limiter.acquire()
    try:
        from src.pipeline.orchestrator import Orchestrator, PipelineState
        state = PipelineState(task_id=task_id, output_dir=task["output_dir"])
        orch = Orchestrator(state, progress_callback)

        # 加载逐字稿
        text = task["inputs"].get("transcript_text", "")
        if not text and task["inputs"].get("transcript_file"):
            with open(task["inputs"]["transcript_file"], "r", encoding="utf-8") as f:
                text = f.read()
        _log.info("任务 %s: 逐字稿已加载，%d 字", task_id, len(text))

        # 0.1 构建术语词典
        glossary = _build_glossary(task["inputs"])
        if glossary:
            _log.info("任务 %s: 术语词典已构建，%d 词", task_id, len(glossary))

        # 0.5 构建 RAG 索引
        rag_collection = _build_rag_index(task["inputs"], task["output_dir"])
        code_files = _load_code_files(task["inputs"])
        if rag_collection:
            _log.info("任务 %s: RAG 索引就绪", task_id)
        if code_files:
            _log.info("任务 %s: %d 个代码文件已加载，供阶段 2 使用", task_id, len(code_files))

        # 0.0 噪音清洗
        from src.pipeline.stage0_preprocess import clean_noise_stage
        text = await orch.run_stage("0.0", clean_noise_stage, text)

        # 0.2 错别字纠正（含术语词典）
        from src.pipeline.stage0_preprocess import correct_errors_stage
        text = await orch.run_stage("0.2", correct_errors_stage, text, glossary)

        # 0.3 全局摘要
        from src.pipeline.stage0_preprocess import generate_summary
        summary = await orch.run_stage("0.3", generate_summary, text)

        # 0.4 边界检测
        from src.chunking.boundary_detector import detect_boundaries
        chunks = await orch.run_stage("0.4", detect_boundaries, text)
        _log.info("任务 %s: %d 个话题块", task_id, len(chunks))

        # 阶段 1：全并行润色（含 RAG 指纹）
        from src.pipeline.stage1_polish import polish_chunks
        rag_fingerprints_map = _build_rag_fingerprints_map(
            rag_collection, chunks
        ) if rag_collection else None
        polished = await orch.run_stage(
            "1", polish_chunks, chunks, summary, rag_fingerprints_map
        )

        # 阶段 2：结构化 + 代码注入
        from src.pipeline.stage2_structure import structure_and_inject
        structured = await orch.run_stage(
            "2", structure_and_inject, polished, code_files
        )

        # 后处理
        from src.utils.toc_generator import insert_toc
        final = insert_toc(structured)
        mindmap_enabled = task.get("inputs", {}).get("mindmap_enabled", True)
        if mindmap_enabled:
            from src.utils.mindmap import generate_mindmap
            mm = generate_mindmap(final, summary.get("course_title", "课程笔记"))
            if mm:
                final = final + "\n\n" + mm

        orch._save("07_final.md", final)
        update_task(task_id, {"status": "completed", "completed_at": datetime.now().isoformat()})
        _log.info("任务 %s 完成", task_id)
    except Exception as e:
        _log.error("任务 %s 失败: %s", task_id, str(e))
        update_task(task_id, {"status": "failed", "error": str(e)})
        raise
    finally:
        task_slot_limiter.release()


# ---- 辅助函数 ----

_CODE_EXTS = {
    ".py", ".java", ".js", ".ts", ".go", ".rs", ".kt", ".swift",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".xml", ".yaml",
    ".yml", ".properties", ".json", ".sql", ".gradle",
}


def _build_glossary(inputs: dict) -> list[str] | None:
    """从代码 / 课件目录构建术语词典。"""
    code_dir = inputs.get("code_dir")
    courseware_dir = inputs.get("courseware_dir")
    if not code_dir and not courseware_dir:
        return None
    from src.rag.glossary import build_glossary
    glossary = build_glossary(code_dir, courseware_dir)
    return glossary if glossary else None


def _build_rag_index(inputs: dict, output_dir: str) -> object | None:
    """从代码 + 课件文件构建 ChromaDB RAG 索引。"""
    code_dir = inputs.get("code_dir")
    courseware_dir = inputs.get("courseware_dir")
    if not code_dir and not courseware_dir:
        return None

    slices = []
    # 解析代码文件
    if code_dir and os.path.isdir(code_dir):
        from src.rag.parsers.code_parser import parse_code_file
        for root, _, fns in os.walk(code_dir):
            for fn in fns:
                ext = os.path.splitext(fn)[1].lower()
                if ext in _CODE_EXTS:
                    try:
                        slices.extend(parse_code_file(os.path.join(root, fn)))
                    except Exception:
                        pass

    # 解析课件文件
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
                except Exception:
                    pass

    if not slices:
        return None

    from src.rag.indexer import build_index
    persist_dir = os.path.join(output_dir, "chromadb")
    return build_index(slices, "course_rag", persist_dir)


def _build_rag_fingerprints_map(
    rag_collection, chunks: list[str]
) -> dict[int, str] | None:
    """为每个话题块检索相关代码指纹。"""
    if rag_collection is None:
        return None
    from src.rag.retriever import retrieve_relevant
    result = {}
    for i, chunk in enumerate(chunks):
        # 用块尾作为查询（讲师通常在这个位置讨论代码）
        query = chunk[-300:] if len(chunk) > 300 else chunk
        fps = retrieve_relevant(rag_collection, query, k=2)
        if fps:
            result[i] = fps
    return result if result else None


def _load_code_files(inputs: dict) -> dict[str, str] | None:
    """加载完整代码文件，供阶段 2 代码注入使用。"""
    code_dir = inputs.get("code_dir")
    if not code_dir or not os.path.isdir(code_dir):
        return None
    files = {}
    for root, _, fns in os.walk(code_dir):
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in _CODE_EXTS:
                try:
                    with open(os.path.join(root, fn), "r", encoding="utf-8", errors="ignore") as f:
                        files[fn] = f.read()
                except Exception:
                    pass
    return files if files else None