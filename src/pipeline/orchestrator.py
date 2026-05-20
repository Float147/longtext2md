import json, os, time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class StageResult:
    stage_name: str
    status: str = "pending"
    output_file: str = ""
    error: str | None = None
    duration_s: float = 0.0

@dataclass
class PipelineState:
    task_id: str
    output_dir: str
    stages: dict[str, StageResult] = field(default_factory=dict)
    current_stage: str = "0.0"
    summary: dict | None = None
    chunks: list[str] | None = None

class Orchestrator:
    def __init__(self, state: PipelineState, progress_callback: Callable | None = None):
        self.state = state
        self.progress_callback = progress_callback
        Path(state.output_dir).mkdir(parents=True, exist_ok=True)

    def _save(self, filename: str, content):
        filepath = os.path.join(self.state.output_dir, filename)
        if isinstance(content, (dict, list)):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

    def run_stage(self, stage_name: str, fn: Callable, *args, **kwargs):
        self.state.current_stage = stage_name
        self.state.stages[stage_name] = StageResult(stage_name=stage_name, status="running")
        if self.progress_callback:
            self.progress_callback(self.state)
        try:
            t0 = time.time()
            result = fn(*args, **kwargs)
            dt = time.time() - t0
            out_file = f"{stage_name.replace('.','_')}_output"
            if stage_name == "0.0":
                out_file = "00_cleaned.txt"
            elif stage_name == "0.2":
                out_file = "02_corrected.txt"
            elif stage_name == "0.3":
                out_file = "03_summary.json"
                self.state.summary = result if isinstance(result, dict) else None
            elif stage_name == "0.4":
                out_file = "04_chunks.json"
                self.state.chunks = result
            elif stage_name == "1":
                out_file = "05_polished.txt"
                result = "\n\n".join(result) if isinstance(result, list) else result
            elif stage_name == "2":
                out_file = "06_structured.md"
            self._save(out_file, result)
            self.state.stages[stage_name] = StageResult(
                stage_name=stage_name, status="completed",
                output_file=out_file, duration_s=dt,
            )
            return result
        except Exception as e:
            self.state.stages[stage_name] = StageResult(
                stage_name=stage_name, status="failed", error=str(e),
            )
            raise
        finally:
            if self.progress_callback:
                self.progress_callback(self.state)
