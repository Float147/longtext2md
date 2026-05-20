import asyncio, os, threading
from datetime import datetime
from src.task.task_store import create_task, get_task, update_task, list_tasks, delete_task
from src.task.concurrency_limiter import task_slot_limiter

async def run_task(task_id: str, progress_callback=None):
    task = get_task(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
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
        from src.pipeline.stage0_preprocess import clean_noise_stage
        text = orch.run_stage("0.0", clean_noise_stage, text)
        from src.pipeline.stage0_preprocess import correct_errors_stage_sync
        text = orch.run_stage("0.2", correct_errors_stage_sync, text)
        from src.pipeline.stage0_preprocess import generate_summary_sync
        summary = orch.run_stage("0.3", generate_summary_sync, text)
        from src.chunking.boundary_detector import detect_boundaries
        chunks = orch.run_stage("0.4", detect_boundaries, text)
        from src.pipeline.stage1_polish import polish_chunks
        polished = orch.run_stage("1", lambda: asyncio.run(polish_chunks(chunks, summary)))
        from src.pipeline.stage2_structure import structure_and_inject
        code_files = _load_code_files(task["inputs"])
        structured = orch.run_stage("2", structure_and_inject, polished, code_files)
        from src.utils.toc_generator import insert_toc
        final = insert_toc(structured)
        if task.get("mindmap_enabled", True):
            from src.utils.mindmap import generate_mindmap
            mm = generate_mindmap(final, summary.get("course_title", "Course Notes"))
            if mm:
                final = final + "\n\n" + mm
        orch._save("07_final.md", final)
        update_task(task_id, {"status": "completed", "completed_at": datetime.now().isoformat()})
    except Exception as e:
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
