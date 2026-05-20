import json, os
from pathlib import Path
from datetime import datetime

STORE_DIR = "tasks"

def _path(task_id: str) -> str:
    Path(STORE_DIR).mkdir(exist_ok=True)
    return os.path.join(STORE_DIR, f"{task_id}.json")

def create_task(task_id: str, name: str, inputs: dict) -> dict:
    task = {
        "id": task_id, "name": name, "status": "pending",
        "inputs": inputs, "output_dir": f"output/{task_id}",
        "created_at": datetime.now().isoformat(),
        "mindmap_enabled": inputs.get("mindmap_enabled", True),
    }
    _save(task)
    return task

def get_task(task_id: str) -> dict | None:
    p = _path(task_id)
    return json.load(open(p, "r", encoding="utf-8")) if os.path.exists(p) else None

def update_task(task_id: str, updates: dict):
    t = get_task(task_id)
    if t:
        t.update(updates)
        _save(t)

def list_tasks(status: str | None = None) -> list[dict]:
    Path(STORE_DIR).mkdir(exist_ok=True)
    tasks = []
    for fn in os.listdir(STORE_DIR):
        if fn.endswith(".json"):
            t = json.load(open(os.path.join(STORE_DIR, fn), "r", encoding="utf-8"))
            if status is None or t.get("status") == status:
                tasks.append(t)
    return sorted(tasks, key=lambda t: t.get("created_at", ""))

def delete_task(task_id: str):
    p = _path(task_id)
    if os.path.exists(p):
        os.remove(p)

def _save(task: dict):
    json.dump(task, open(_path(task["id"]), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
