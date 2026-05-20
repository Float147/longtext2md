"""
?????? ?? ??????????????
"""
import asyncio
import json, os, time
from src.utils.logger import get_pipeline_logger
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable

# ??? -> ????? ??
_STAGE_OUTPUT_FILES = {
    "0.0": "00_cleaned.txt",
    "0.2": "02_corrected.txt",
    "0.3": "03_summary.json",
    "0.4": "04_chunks.json",
    "1": "05_polished.txt",
    "2": "06_structured.md",
}

# ???????????
_SUMMARY_STAGES = {"0.3"}
_CHUNKS_STAGES = {"0.4"}
_JOIN_STAGES = {"1"}


@dataclass
class StageResult:
    """??????????"""
    stage_name: str
    status: str = "pending"
    output_file: str = ""
    error: str | None = None
    duration_s: float = 0.0


@dataclass
class PipelineState:
    """????????"""
    task_id: str
    output_dir: str
    stages: dict[str, StageResult] = field(default_factory=dict)
    current_stage: str = "0.0"
    summary: dict | None = None
    chunks: list[str] | None = None


class Orchestrator:
    """????????????????????????"""
    _logger = get_pipeline_logger()

    def __init__(self, state: PipelineState, progress_callback: Callable | None = None):
        self.state = state
        self.progress_callback = progress_callback
        Path(state.output_dir).mkdir(parents=True, exist_ok=True)

    def _save(self, filename: str, content):
        """??????? output ???"""
        filepath = os.path.join(self.state.output_dir, filename)
        if isinstance(content, str):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        elif isinstance(content, (dict, list)):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        else:
            raise TypeError(
                f"_save ??????: {type(content).__name__}???? str / dict / list"
            )

    async def run_stage(self, stage_name: str, fn: Callable, *args, **kwargs):
        """?????????????????"""
        self.state.current_stage = stage_name
        self.state.stages[stage_name] = StageResult(stage_name=stage_name, status="running")
        if self.progress_callback:
            self.progress_callback(self.state)
        try:
            self._logger.info("?? %s ??", stage_name)
            t0 = time.time()
            result = fn(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            dt = time.time() - t0

            # ???????
            out_file = _STAGE_OUTPUT_FILES.get(
                stage_name, f"{stage_name.replace(".", "_")}_output"
            )

            # ????????
            if stage_name in _SUMMARY_STAGES:
                self.state.summary = result if isinstance(result, dict) else None
            elif stage_name in _CHUNKS_STAGES:
                self.state.chunks = result
            elif stage_name in _JOIN_STAGES:
                result = "\n\n".join(result) if isinstance(result, list) else result

            self._save(out_file, result)
            self.state.stages[stage_name] = StageResult(
                stage_name=stage_name, status="completed",
                output_file=out_file, duration_s=dt,
            )
            self._logger.info("?? %s ????? %.1fs -> %s", stage_name, dt, out_file)
            return result
        except Exception as e:
            self._logger.error("?? %s ??: %s", stage_name, str(e))
            self.state.stages[stage_name] = StageResult(
                stage_name=stage_name, status="failed", error=str(e),
            )
            raise
        finally:
            if self.progress_callback:
                self.progress_callback(self.state)
