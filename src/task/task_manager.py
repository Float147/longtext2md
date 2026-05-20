import asyncio, os, threading
from datetime import datetime
from src.task.task_store import create_task, get_task, update_task, list_tasks, delete_task
from src.task.concurrency_limiter import task_slot_limiter
from src.utils.logger import get_task_logger

_log = get_task_logger()

async def run_task(task_id: str, progress_callback=None):
    task = get_task(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    _log.info("Task %s started: %s", task_id, task.get("name", ""))
    update_task(task_id, {"status": "running"})
    await task_slot_limiter.acquire()
    try:
        from src.pipeline.orchestrator import Orchestrator, PipelineState
        state = PipelineState(task_id=task_id, output_dir=task["output_dir"])
        orch = Orchestrator(state, progress_callback)
        text = task["inputs"].get("transcript_text", "")
        if not text and task["inputs"].get("transcript_file"):
            with open(task["inputs"]["transcript_file"], "r", encoding="utf-8") as f:
                text = f.read()
        _log.info("Task %s: transcript loaded, %d chars", task_id, len(text))
        from src.pipeline.stage0_preprocess import clean_noise_stage
        text = await orch.run_stage("0.0", clean_noise_stage, text)
        from src.pipeline.stage0_preprocess import correct_errors_stage
        text = await orch.run_stage("0.2", correct_errors_stage, text)
        from src.pipeline.stage0_preprocess import generate_summary
        summary = await orch.run_stage("0.3", generate_summary, text)
        from src.chunking.boundary_detector import detect_boundaries
        chunks = await orch.run_stage("0.4", detect_boundaries, text)
        _log.info("Task %s: %d chunks created", task_id, len(chunks))
        from src.pipeline.stage1_polish import polish_chunks
        polished = await orch.run_stage("1", polish_chunks, chunks, summary)
        from src.pipeline.stage2_structure import structure_and_inject
        code_files = _load_code_files(task["inputs"])
        if code_files:
            _log.info("Task %s: %d code files loaded", task_id, len(code_files))
        structured = await orch.run_stage("2", structure_and_inject, polished, code_files)
        from src.utils.toc_generator import insert_toc
        final = insert_toc(structured)
        if task.get("mindmap_enabled", True):
            from src.utils.mindmap import generate_mindmap
            mm = generate_mindmap(final, summary.get("course_title", "Course Notes"))
            if mm:
                final = final + "\n\n" + mm
        orch._save("07_final.md", final)
        update_task(task_id, {"status": "completed", "completed_at": datetime.now().isoformat()})
        _log.info("Task %s completed", task_id)
    except Exception as e:
        _log.error("Task %s failed: %s", task_id, str(e))
        update_task(task_id, {"status": "failed", "error": str(e)})
        raise
    finally:
        task_slot_limiter.release()

def _load_code_files(inputs: dict) -> dict[str, str] | None:
    code_dir = inputs.get("code_dir")
    if not code_dir or not os.path.isdir(code_dir):
        return None
    files = {}
    for root, _, fns in os.walk(code_dir):
        for fn in fns:
            if fn.endswith((".py",".java",".js",".ts",".go",".rs",".kt",".swift",".xml",".yaml",".yml",".properties")):
                try:
                    with open(os.path.join(root, fn), "r", encoding="utf-8", errors="ignore") as f:
                        files[fn] = f.read()
                except:
                    pass
    return files if files else None